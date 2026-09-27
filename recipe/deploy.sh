#!/usr/bin/env bash
#
# Deploy Recipe Box to an EC2 instance.
#
# Same layout as Filler-Local's deploy/: nginx serves the React build and
# proxies /api to gunicorn (run by systemd), and Django talks to PostgreSQL on
# Amazon RDS with IAM auth. Everything is in this one file.
#
#          :80/:443
#   nginx ──────────── /          → frontend/dist
#     │  (password)    /media/    → /var/lib/recipe-box/media (photos, imports)
#     │                /static/   → backend/staticfiles (Django admin)
#     └─ /api/ /admin/ → gunicorn  (unix:/run/recipe-box/gunicorn.sock)
#                          └──────→ PostgreSQL on RDS
#
# DEPLOY - from your Mac, copy this folder to the instance and run it there:
#
#   rsync -az --delete --exclude .venv --exclude node_modules --exclude dist \
#     --exclude db.sqlite3 --exclude media --exclude .env \
#     ~/Desktop/recipe-box/recipe/ ec2-user@<instance>:recipe/
#   ssh -t ec2-user@<instance> 'sudo ~/recipe/deploy.sh'
#
# To test the database connection first (IAM role, security groups, rds_iam),
# run check-db.sh on the instance: sudo ~/recipe/check-db.sh <rds-endpoint>
#
# (Ubuntu AMIs log in as `ubuntu` instead of `ec2-user`. Keep the -t: the first
# run asks a few questions.)
#
# The first run asks for your settings (domain, RDS endpoint, site password,
# optional Anthropic key), installs packages, then builds, migrates and starts
# everything. To redeploy, run the same two commands again: the code is
# re-synced and rebuilt, and your settings, database and uploads are kept.
#
# Options:
#   --reconfigure   ask for the settings again (keeps the secret key)
#   --https         get a Let's Encrypt certificate for your domain now
#   --no-migrate    skip database migrations
#   -h, --help      show this help
#
# Code can come from git instead of rsync:
#   sudo APP_REPO=https://github.com/you/recipe.git ./deploy.sh
#
# Settings can be passed as environment variables instead of answered
# (DOMAIN, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_IAM_AUTH, DB_PASSWORD,
# SITE_USER, SITE_PASSWORD, ANTHROPIC_API_KEY) for unattended runs.
#
# Before the first deploy, in AWS:
#   * Instance security group: inbound 80 and 443 from anywhere, 22 from you.
#   * RDS security group: inbound 5432 from the instance's security group.
#   * IAM auth (the default, as in Filler): attach an instance role allowing
#     rds-db:connect on arn:aws:rds-db:<region>:<account>:dbuser:<cluster-resource-id>/<db user>,
#     and run `GRANT rds_iam TO <db user>;` once in the database.

set -euo pipefail

APP_NAME=recipe-box
APP_USER="${APP_USER:-recipebox}"
APP_ROOT="${APP_ROOT:-/srv/$APP_NAME}"
DATA_DIR="/var/lib/$APP_NAME"
SERVICE="$APP_NAME"
SOCKET="/run/$APP_NAME/gunicorn.sock"
ENV_FILE="$APP_ROOT/backend/.env"
HTPASSWD="/etc/nginx/$APP_NAME.htpasswd"
PROXY_PARAMS="/etc/nginx/$APP_NAME-proxy.conf"
APP_REPO="${APP_REPO:-}"
APP_BRANCH="${APP_BRANCH:-main}"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

RECONFIGURE=0
WANT_HTTPS=0
MIGRATE=1
while [[ $# -gt 0 ]]; do
    case $1 in
        --reconfigure) RECONFIGURE=1 ;;
        --https) WANT_HTTPS=1 ;;
        --no-migrate) MIGRATE=0 ;;
        -h | --help)
            sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown option: $1 (try --help)" >&2; exit 1 ;;
    esac
    shift
done

bold=$'\033[1m'; green=$'\033[32m'; yellow=$'\033[33m'; dim=$'\033[2m'; reset=$'\033[0m'
step() { printf '\n%s==>%s %s\n' "$bold" "$reset" "$*"; }
note() { printf '    %s%s%s\n' "$dim" "$*" "$reset"; }
warn() { printf '    %sWarning:%s %s\n' "$yellow" "$reset" "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run this with sudo: sudo $0"
INTERACTIVE=0
[[ -t 0 ]] && INTERACTIVE=1

if command -v dnf >/dev/null 2>&1; then
    PKG=dnf; WEB_USER=nginx; NGINX_SITE="/etc/nginx/conf.d/$APP_NAME.conf"
elif command -v apt-get >/dev/null 2>&1; then
    PKG=apt; WEB_USER=www-data; NGINX_SITE="/etc/nginx/sites-available/$APP_NAME"
else
    die "this script supports Amazon Linux 2023 and Ubuntu (dnf or apt-get)."
fi

# Run a command as the service account, so nothing in the checkout ends up root-owned.
as_app() { sudo -u "$APP_USER" env HOME="/home/$APP_USER" PATH="/usr/local/bin:/usr/bin:/bin" "$@"; }

# Instance metadata (IMDSv2). One token for the whole run; off EC2 it's empty
# and every lookup just prints nothing.
imds_token="$(curl -fsS -m 2 -X PUT http://169.254.169.254/latest/api/token \
    -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600' 2>/dev/null || true)"
imds() {
    [[ -n $imds_token ]] || return 0
    curl -fsS -m 2 -H "X-aws-ec2-metadata-token: $imds_token" \
        "http://169.254.169.254/latest/meta-data/$1" 2>/dev/null || true
}

# --- settings ----------------------------------------------------------------------
# Asked first, so the slow part afterwards can run unattended.

env_get() { # read a value back out of the existing .env
    [[ -f $ENV_FILE ]] || return 0
    local line quote="'"
    line="$(grep -E "^$1=" "$ENV_FILE" | tail -1 || true)"
    line="${line#*=}"
    line="${line#"$quote"}"
    line="${line%"$quote"}"
    printf '%s' "$line"
}
env_or() { local value; value="$(env_get "$1")"; printf '%s' "${value:-$2}"; }
dotenv_quote() { # single quotes, which python-dotenv reads literally
    if [[ $1 == *"'"* ]]; then
        local escaped="${1//\\/\\\\}"
        printf '"%s"' "${escaped//\"/\\\"}"
    else
        printf "'%s'" "$1"
    fi
}
ask() { # ask VAR "question" "default" [secret]
    local var=$1 question=$2 default=$3 secret=${4:-} answer
    [[ -n ${!var:-} ]] && return 0 # already given as an environment variable
    if [[ $INTERACTIVE -eq 0 ]]; then printf -v "$var" '%s' "$default"; return 0; fi
    if [[ -n $secret ]]; then
        read -r -s -p "  $question${default:+ [keep current]}: " answer
        echo
    else
        read -r -p "  $question${default:+ [$default]}: " answer
    fi
    printf -v "$var" '%s' "${answer:-$default}"
}
yes_no() { # yes_no "question" y|n
    local answer
    [[ $INTERACTIVE -eq 1 ]] || { [[ $2 == y ]]; return; }
    read -r -p "  $1 [$([[ $2 == y ]] && echo Y/n || echo y/N)]: " answer
    [[ ${answer:-$2} =~ ^[Yy] ]]
}

NEED_SETTINGS=0
[[ ! -f $ENV_FILE || $RECONFIGURE -eq 1 ]] && NEED_SETTINGS=1
GENERATED_PASSWORD=""
if [[ $NEED_SETTINGS -eq 1 ]]; then
    step "Settings"
    if [[ $INTERACTIVE -eq 1 ]]; then
        echo "  Press Enter to accept the value in brackets."
    elif [[ -z ${DB_HOST:-} ]]; then
        warn "no terminal and no DB_HOST given, so the database will be SQLite on this instance. Run with ssh -t to answer the questions."
    fi

    ask DOMAIN "Domain for the site, e.g. recipes.example.com (blank: use this instance's public address)" "$(env_get SITE_DOMAIN)"
    ask DB_HOST "RDS endpoint, e.g. database-1.cluster-xxxx.us-east-1.rds.amazonaws.com (blank: SQLite on this instance)" "$(env_get DB_HOST)"
    if [[ -n $DB_HOST ]]; then
        ask DB_PORT "Database port" "$(env_or DB_PORT 5432)"
        ask DB_NAME "Database name (created if it doesn't exist)" "$(env_or DB_NAME recipebox)"
        ask DB_USER "Database user" "$(env_or DB_USER postgres)"
        if [[ -z ${DB_IAM_AUTH:-} ]]; then
            if yes_no "Connect with IAM auth like Filler (no password; uses the instance role)?" \
                "$([[ $(env_or DB_IAM_AUTH True) == True ]] && echo y || echo n)"; then
                DB_IAM_AUTH=True
            else
                DB_IAM_AUTH=False
            fi
        fi
        if [[ $DB_IAM_AUTH == False ]]; then
            ask DB_PASSWORD "Database password" "$(env_get DB_PASSWORD)" secret
            [[ -n $DB_PASSWORD ]] || die "a database password is needed when IAM auth is off."
        fi
    fi

    [[ $INTERACTIVE -eq 1 ]] && printf '\n  %s\n' "The site is protected by a username and password (the app has no accounts yet)."
    current_user="$(awk -F: 'NR==1 {print $1}' "$HTPASSWD" 2>/dev/null || true)"
    ask SITE_USER "Site username" "${current_user:-recipes}"
    if [[ -s $HTPASSWD && $SITE_USER == "$current_user" ]]; then
        ask SITE_PASSWORD "Site password (blank: keep the current one)" "" secret
    else
        ask SITE_PASSWORD "Site password (blank: generate one)" "" secret
        if [[ -z $SITE_PASSWORD ]]; then
            SITE_PASSWORD="$(head -c 64 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | cut -c1-16)"
            GENERATED_PASSWORD="$SITE_PASSWORD"
        fi
    fi

    [[ $INTERACTIVE -eq 1 ]] && echo
    ask ANTHROPIC_API_KEY "Anthropic API key, to read PDFs/screenshots with Claude (optional)" "$(env_get ANTHROPIC_API_KEY)" secret
    [[ $INTERACTIVE -eq 1 ]] && echo && echo "  Thanks. The rest runs on its own (a few minutes the first time)."
fi

# --- packages --------------------------------------------------------------------

python_ok() { "$1" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; }
find_python() {
    local candidate
    for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && python_ok "$candidate"; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}
node_ok() { # Vite 8 needs Node 20.19+ or 22.12+
    command -v node >/dev/null 2>&1 && node -e '
        const [a, b] = process.versions.node.split(".").map(Number);
        process.exit(a > 22 || (a === 22 && b >= 12) || (a === 20 && b >= 19) ? 0 : 1)' 2>/dev/null
}

step "Installing system packages ($PKG)"
if [[ $PKG == dnf ]]; then
    dnf install -y -q nginx git rsync tar openssl >/dev/null
    # Amazon Linux's default python3 is 3.9; the app needs 3.10+.
    if ! find_python >/dev/null; then
        dnf install -y -q python3.12 python3.12-pip >/dev/null 2>&1 \
            || dnf install -y -q python3.11 python3.11-pip >/dev/null
    fi
    if ! node_ok; then
        curl -fsSL https://rpm.nodesource.com/setup_22.x | bash - >/dev/null 2>&1
        dnf install -y -q nodejs >/dev/null
    fi
    # For screenshot OCR without Claude. Not packaged in every Amazon Linux release.
    command -v tesseract >/dev/null 2>&1 \
        || dnf install -y -q tesseract tesseract-langpack-eng >/dev/null 2>&1 || true
else
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq nginx git rsync curl openssl python3 python3-venv python3-pip tesseract-ocr >/dev/null
    if ! node_ok; then
        curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null 2>&1
        apt-get install -y -qq nodejs >/dev/null
    fi
fi
PYTHON="$(find_python)" || die "couldn't install Python 3.10 or newer."
node_ok || die "couldn't install Node.js 20.19+ (needed to build the frontend)."
note "$("$PYTHON" --version), node $(node --version), $(nginx -v 2>&1 | sed 's/.*: //')"
if command -v tesseract >/dev/null 2>&1; then
    note "tesseract $(tesseract --version 2>&1 | head -1 | awk '{print $2}') for screenshot OCR"
else
    warn "Tesseract isn't available here, so screenshots and scanned PDFs need Claude (an Anthropic API key). Links and text PDFs work either way."
fi

# The frontend build doesn't fit comfortably in 1 GB of memory.
mem_mb=$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo)
if [[ $mem_mb -lt 1800 ]] && ! swapon --show | grep -q .; then
    step "Adding 2 GB of swap (this instance has ${mem_mb} MB of memory)"
    if [[ ! -f /swapfile ]]; then
        fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
        chmod 600 /swapfile
        mkswap /swapfile >/dev/null
    fi
    swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

# --- service account & code ------------------------------------------------------

step "Setting up the $APP_USER service account"
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    useradd --system --create-home --home-dir "/home/$APP_USER" --shell /usr/sbin/nologin "$APP_USER" 2>/dev/null \
        || useradd --system --create-home --home-dir "/home/$APP_USER" --shell /sbin/nologin "$APP_USER"
fi
# Lets nginx open the gunicorn socket and read uploaded photos.
usermod -aG "$APP_USER" "$WEB_USER"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$DATA_DIR" "$DATA_DIR/media"

step "Updating the code in $APP_ROOT"
mkdir -p "$APP_ROOT"
if [[ -n $APP_REPO ]]; then
    if [[ -d $APP_ROOT/.git ]]; then
        chown -R "$APP_USER:$APP_USER" "$APP_ROOT"
        as_app git -C "$APP_ROOT" fetch --quiet origin "$APP_BRANCH"
        as_app git -C "$APP_ROOT" reset --quiet --hard "origin/$APP_BRANCH"
    else
        [[ -z $(ls -A "$APP_ROOT") ]] || die "$APP_ROOT isn't empty and isn't a git checkout."
        git clone --quiet --branch "$APP_BRANCH" "$APP_REPO" "$APP_ROOT"
    fi
    note "$(git -C "$APP_ROOT" log -1 --format='%h %s')"
elif [[ $SOURCE_DIR != "$APP_ROOT" ]]; then
    [[ -d $SOURCE_DIR/backend && -d $SOURCE_DIR/frontend ]] || die "run this from inside the recipe folder."
    # --delete drops files removed locally; excluded paths (the server's
    # virtualenv, node_modules, .env and uploads) are left alone. macOS
    # metadata files (._*) are hidden but not protected, so stray ones go too.
    rsync -a --delete --filter 'H ._*' --filter 'H .DS_Store' \
        --exclude '.git/' --exclude '.claude/' --exclude '__pycache__/' \
        --exclude 'backend/.venv/' --exclude 'backend/.env' --exclude 'backend/db.sqlite3' \
        --exclude 'backend/media/' --exclude 'backend/staticfiles/' \
        --exclude 'frontend/node_modules/' --exclude 'frontend/dist/' \
        "$SOURCE_DIR/" "$APP_ROOT/"
    note "copied from $SOURCE_DIR"
fi
chown -R "$APP_USER:$APP_USER" "$APP_ROOT"
chmod 750 "$APP_ROOT"

# --- write settings --------------------------------------------------------------

# Hostnames the browser may use: the domain plus this instance's current
# addresses. Refreshed on every deploy, since a stopped-and-started instance
# gets a new public address unless it has an Elastic IP.
allowed_hosts() {
    local hosts="localhost,127.0.0.1" value
    for value in "$1" "$(imds public-hostname)" "$(imds public-ipv4)" "$(imds local-ipv4)"; do
        [[ -n $value ]] && hosts="$hosts,$value"
    done
    printf '%s' "$hosts"
}

if [[ $NEED_SETTINGS -eq 1 ]]; then
    secret_key="$(env_get DJANGO_SECRET_KEY)"
    [[ -n $secret_key ]] || secret_key="$(openssl rand -hex 32)"
    https_on=False
    [[ -n $DOMAIN && -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]] && https_on=True
    (
        umask 077
        {
            echo "# Written by deploy.sh. Change with: sudo $APP_ROOT/deploy.sh --reconfigure"
            echo "# (or edit, then: sudo systemctl restart $SERVICE)"
            echo "DJANGO_SECRET_KEY=$secret_key"
            echo "DJANGO_DEBUG=False"
            echo "DJANGO_ALLOWED_HOSTS=$(allowed_hosts "$DOMAIN")"
            echo "SITE_DOMAIN=$DOMAIN"
            echo "CSRF_TRUSTED_ORIGINS=${DOMAIN:+https://$DOMAIN,http://$DOMAIN}"
            echo "DJANGO_MEDIA_ROOT=$DATA_DIR/media"
            echo "USE_X_FORWARDED_PROTO=True"
            echo "DJANGO_SECURE_SSL=$https_on"
            echo
            if [[ -n $DB_HOST ]]; then
                echo "DB_HOST=$DB_HOST"
                echo "DB_PORT=$DB_PORT"
                echo "DB_NAME=$DB_NAME"
                echo "DB_USER=$DB_USER"
                echo "DB_IAM_AUTH=$DB_IAM_AUTH"
                [[ $DB_IAM_AUTH == False ]] && echo "DB_PASSWORD=$(dotenv_quote "$DB_PASSWORD")"
                echo "DB_SSLMODE=require"
            else
                echo "# No DB_HOST, so the database is SQLite on this instance."
                echo "DJANGO_SQLITE_PATH=$DATA_DIR/db.sqlite3"
            fi
            echo
            [[ -n $ANTHROPIC_API_KEY ]] && echo "ANTHROPIC_API_KEY=$(dotenv_quote "$ANTHROPIC_API_KEY")"
            echo "RECIPE_LLM=auto"
        } >"$ENV_FILE"
    )
    if [[ -n $SITE_PASSWORD ]]; then
        printf '%s:%s\n' "$SITE_USER" "$(printf '%s' "$SITE_PASSWORD" | openssl passwd -apr1 -stdin)" >"$HTPASSWD"
    fi
    note "saved to $ENV_FILE"
else
    sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$(allowed_hosts "$(env_get SITE_DOMAIN)")|" "$ENV_FILE"
fi
chown "$APP_USER:$APP_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"
[[ -s $HTPASSWD ]] || die "$HTPASSWD is missing. Run with --reconfigure to set a site password."
chown "root:$WEB_USER" "$HTPASSWD"
chmod 640 "$HTPASSWD"

DOMAIN="$(env_get SITE_DOMAIN)"
DB_HOST="$(env_get DB_HOST)"
if [[ -n $DB_HOST && $(env_get DB_IAM_AUTH) != False ]]; then
    role="$(imds iam/security-credentials/)"
    if [[ -n $role ]]; then
        note "instance role $role (it needs rds-db:connect for $(env_get DB_USER))"
    elif [[ -n $imds_token ]]; then
        warn "no IAM role is attached to this instance, so IAM database auth will fail. Attach one: EC2 console > Actions > Security > Modify IAM role."
    fi
fi

# --- build -----------------------------------------------------------------------

VENV="$APP_ROOT/backend/.venv"
PY="$VENV/bin/python"
manage() { as_app "$PY" "$APP_ROOT/backend/manage.py" "$@"; }

step "Installing Python dependencies"
if [[ -x $PY ]] && ! python_ok "$PY"; then rm -rf "$VENV"; fi
[[ -d $VENV ]] || as_app "$PYTHON" -m venv "$VENV"
as_app "$VENV/bin/pip" install --quiet --upgrade pip
as_app "$VENV/bin/pip" install --quiet -r "$APP_ROOT/backend/requirements.txt"

step "Building the frontend"
as_app npm --prefix "$APP_ROOT/frontend" ci --no-fund --no-audit --no-update-notifier --loglevel=error >/dev/null
as_app npm --prefix "$APP_ROOT/frontend" run lint --silent >/dev/null \
    || die "frontend lint failed and nothing was changed. See: npm --prefix $APP_ROOT/frontend run lint"
as_app npm --prefix "$APP_ROOT/frontend" run build --silent >/dev/null \
    || die "frontend build failed and nothing was changed. See: npm --prefix $APP_ROOT/frontend run build"
note "$APP_ROOT/frontend/dist"

step "Collecting Django static files"
manage collectstatic --noinput --clear >/dev/null

step "Running Django's deployment checks"
if ! manage check --deploy --fail-level ERROR >/dev/null 2>&1; then
    manage check --deploy --fail-level ERROR || true
    die "Django's deployment checks failed (above)."
fi

step "Checking the database connection"
if ! manage ensure_database; then
    if [[ -n $DB_HOST ]]; then
        cat >&2 <<EOF

    Can't reach the database. The usual causes:
      * A timeout: the RDS security group doesn't allow 5432 from this instance's security group.
      * "PAM authentication failed": no instance role, the role lacks rds-db:connect on this user,
        or the user needs \`GRANT rds_iam TO <user>;\`.
      * A typo in the endpoint or user. Fix with: sudo $APP_ROOT/deploy.sh --reconfigure
EOF
    fi
    die "database check failed. The running site (if any) wasn't changed."
fi

if [[ $MIGRATE -eq 1 ]]; then
    step "Applying migrations"
    manage migrate --noinput | sed 's/^/    /'
fi

# --- systemd ---------------------------------------------------------------------

step "Installing the $SERVICE service"
cat >"/etc/systemd/system/$SERVICE.service" <<EOF
# Written by $APP_ROOT/deploy.sh; edits are overwritten on the next deploy.
[Unit]
Description=Recipe Box (gunicorn)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=notify
NotifyAccess=main
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_ROOT/backend
# /run/$APP_NAME holds the socket and /var/lib/$APP_NAME the uploads. Group access
# is what lets nginx (in the $APP_USER group) reach both.
RuntimeDirectory=$APP_NAME
RuntimeDirectoryMode=0750
StateDirectory=$APP_NAME
StateDirectoryMode=0750
UMask=0027
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
# Imports can take a while (OCR, or Claude reading a PDF), hence the long timeout.
ExecStart=$VENV/bin/gunicorn config.wsgi:application \\
    --bind unix:$SOCKET --umask 007 \\
    --workers 2 --worker-class gthread --threads 4 \\
    --timeout 300 --graceful-timeout 30 --keep-alive 5 \\
    --max-requests 500 --max-requests-jitter 50 \\
    --forwarded-allow-ips '*' --access-logfile - --error-logfile -
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=35
Restart=always
RestartSec=3

NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
# tmpfs rather than yes: libpq probes ~/.postgresql and must see "missing", not "denied".
ProtectHome=tmpfs
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictNamespaces=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --quiet "$SERVICE"

# --- nginx -----------------------------------------------------------------------

cat >"$PROXY_PARAMS" <<'EOF'
# Written by deploy.sh.
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
# The site password is nginx's business; don't pass it to the app.
proxy_set_header Authorization "";
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_connect_timeout 5s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
proxy_buffering off;
proxy_redirect off;
EOF

site_body() {
    cat <<EOF
    root $APP_ROOT/frontend/dist;
    index index.html;
    server_tokens off;
    client_max_body_size 120m;
    gzip on;
    gzip_proxied any;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    access_log /var/log/nginx/$APP_NAME.access.log;
    error_log /var/log/nginx/$APP_NAME.error.log;

    auth_basic "Recipe Box";
    auth_basic_user_file $HTPASSWD;

    location = /healthz {
        auth_basic off;
        access_log off;
        include $PROXY_PARAMS;
        proxy_pass http://recipe_box_api;
    }
    location /api/ {
        include $PROXY_PARAMS;
        proxy_pass http://recipe_box_api;
    }
    location /admin/ {
        include $PROXY_PARAMS;
        proxy_pass http://recipe_box_api;
    }
    location /static/ {
        alias $APP_ROOT/backend/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    location /media/ {
        alias $DATA_DIR/media/;
        expires 7d;
        add_header X-Content-Type-Options nosniff;
    }
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files \$uri =404;
    }
    location = /index.html {
        add_header Cache-Control "no-cache";
    }
    # Client-side routes (/recipes/12, /import) all load the app.
    location / {
        try_files \$uri \$uri/ /index.html;
    }
EOF
}

write_nginx_site() {
    local server_name="${DOMAIN:-_}" cert="/etc/letsencrypt/live/$DOMAIN"
    {
        echo "# Written by $APP_ROOT/deploy.sh; edits are overwritten on the next deploy."
        echo "upstream recipe_box_api {"
        echo "    server unix:$SOCKET fail_timeout=0;"
        echo "}"
        echo
        if [[ -n $DOMAIN && -f $cert/fullchain.pem ]]; then
            cat <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $server_name;
    location = /healthz {
        include $PROXY_PARAMS;
        proxy_pass http://recipe_box_api;
    }
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $server_name;
    ssl_certificate $cert/fullchain.pem;
    ssl_certificate_key $cert/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:recipe_box_ssl:10m;

$(site_body)
}
EOF
        else
            echo "server {"
            echo "    listen 80;"
            echo "    listen [::]:80;"
            echo "    server_name $server_name;"
            echo
            site_body
            echo "}"
        fi
    } >"$NGINX_SITE"
    if [[ $PKG == apt ]]; then
        ln -sfn "$NGINX_SITE" "/etc/nginx/sites-enabled/$APP_NAME"
        rm -f /etc/nginx/sites-enabled/default
    fi
}

step "Configuring nginx"
write_nginx_site
nginx -t >/dev/null 2>&1 || { nginx -t || true; die "nginx rejected the configuration (above)."; }
if [[ -z $DOMAIN ]]; then
    # Another site (Filler, say) that also answers every hostname would win or lose at random.
    others="$(grep -ls 'server_name[[:space:]]\+_;' /etc/nginx/conf.d/*.conf /etc/nginx/sites-enabled/* 2>/dev/null \
        | grep -v "$APP_NAME" || true)"
    [[ -z $others ]] || warn "another nginx site also answers every hostname ($others). Give Recipe Box its own domain with --reconfigure."
fi

# --- start -----------------------------------------------------------------------

step "Restarting $SERVICE"
systemctl restart "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE" || die "$SERVICE didn't start. See: journalctl -u $SERVICE -n 50"
systemctl enable --quiet nginx
# nginx only picks up its new group membership (for the socket) when it starts,
# so the first deploy after boot restarts it; later ones just reload.
if systemctl is-active --quiet nginx && [[ -f /run/$APP_NAME.nginx-restarted ]]; then
    systemctl reload nginx
else
    systemctl restart nginx
    touch "/run/$APP_NAME.nginx-restarted"
fi

step "Checking the site"
ok=0
for _ in 1 2 3 4 5; do
    if curl -fsS -m 5 -o /dev/null -H "Host: ${DOMAIN:-localhost}" http://127.0.0.1/healthz; then ok=1; break; fi
    sleep 2
done
[[ $ok -eq 1 ]] || die "gunicorn is running but nginx isn't serving it. See /var/log/nginx/$APP_NAME.error.log and journalctl -u $SERVICE -n 50"
note "ok"

# --- HTTPS -----------------------------------------------------------------------

install_certbot() {
    command -v certbot >/dev/null 2>&1 && return 0
    if [[ $PKG == apt ]]; then
        apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
    elif ! dnf install -y -q certbot python3-certbot-nginx >/dev/null 2>&1; then
        # Amazon Linux: certbot's recommended pip install, renewed by a systemd timer.
        "$PYTHON" -m venv /opt/certbot
        /opt/certbot/bin/pip install --quiet --upgrade pip certbot certbot-nginx
        ln -sf /opt/certbot/bin/certbot /usr/bin/certbot
        cat >/etc/systemd/system/certbot-renew.service <<'EOF'
[Unit]
Description=Renew Let's Encrypt certificates
[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet
EOF
        cat >/etc/systemd/system/certbot-renew.timer <<'EOF'
[Unit]
Description=Renew Let's Encrypt certificates twice a day
[Timer]
OnCalendar=*-*-* 00,12:00:00
RandomizedDelaySec=1h
Persistent=true
[Install]
WantedBy=timers.target
EOF
        systemctl daemon-reload
        systemctl enable --now --quiet certbot-renew.timer
    fi
}

if [[ -n $DOMAIN && ! -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]]; then
    if [[ $WANT_HTTPS -eq 0 && $INTERACTIVE -eq 1 ]]; then
        echo
        echo "  HTTPS needs $DOMAIN's DNS (an A record) pointing at this instance ($(imds public-ipv4))."
        yes_no "Get a free Let's Encrypt certificate for $DOMAIN now?" y && WANT_HTTPS=1
    fi
    if [[ $WANT_HTTPS -eq 1 ]]; then
        step "Getting an HTTPS certificate for $DOMAIN"
        install_certbot
        # certbot asks for your email and for agreement to Let's Encrypt's terms itself.
        if certbot certonly --nginx -d "$DOMAIN" --deploy-hook "systemctl reload nginx"; then
            write_nginx_site
            nginx -t >/dev/null 2>&1 || die "nginx rejected the HTTPS configuration."
            systemctl reload nginx
            sed -i 's/^DJANGO_SECURE_SSL=.*/DJANGO_SECURE_SSL=True/' "$ENV_FILE"
            systemctl restart "$SERVICE"
            note "HTTPS is on"
        else
            warn "couldn't get a certificate. Check that $DOMAIN points at this instance and port 80 is open, then run: sudo $APP_ROOT/deploy.sh --https"
        fi
    fi
fi

# --- done ------------------------------------------------------------------------

if [[ -n $DOMAIN && -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]]; then
    url="https://$DOMAIN"
elif [[ -n $DOMAIN ]]; then
    url="http://$DOMAIN"
else
    address="$(imds public-hostname)"
    [[ -n $address ]] || address="$(imds public-ipv4)"
    [[ -n $address ]] || address="<instance address>"
    url="http://$address"
fi

printf '\n%s%sDeployed.%s  %s\n' "$bold" "$green" "$reset" "$url"
echo "    Sign in as: $(awk -F: 'NR==1 {print $1}' "$HTPASSWD")"
if [[ -n $GENERATED_PASSWORD ]]; then
    printf '    Password:   %s%s%s  (generated; save it now, it is not shown again)\n' "$bold" "$GENERATED_PASSWORD" "$reset"
fi
if [[ $url == http://* ]]; then
    warn "the site is plain HTTP, so the password travels unencrypted. Point a domain at this instance, then run: sudo $APP_ROOT/deploy.sh --reconfigure"
fi
[[ -z $DOMAIN ]] && note "Without a domain, give the instance an Elastic IP so its address survives a stop/start."
cat <<EOF

    Redeploy:   sudo $APP_ROOT/deploy.sh  (git checkout: cd $APP_ROOT && git pull first)
    Logs:       journalctl -u $SERVICE -f
                sudo tail -f /var/log/nginx/$APP_NAME.error.log
    Settings:   sudo $APP_ROOT/deploy.sh --reconfigure
    Data:       $([[ -n $DB_HOST ]] && echo "RDS $DB_HOST" || echo "SQLite $DATA_DIR/db.sqlite3"), uploads in $DATA_DIR/media
EOF
