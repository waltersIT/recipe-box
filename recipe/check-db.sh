#!/usr/bin/env bash
#
# Check that Recipe Box can use its RDS database, before running deploy.sh.
#
# Run it ON THE EC2 INSTANCE: it logs in with the instance's IAM role over the
# instance's network path, exactly as the app will, so if this passes, the
# deploy's database step will too.
#
#   sudo ./check-db.sh <rds-endpoint>
#
# Optional environment: DB_PORT (5432), DB_USER (postgres), DB_NAME (recipebox),
# AWS_REGION (read from the endpoint). sudo is only needed to install the psql
# client or AWS CLI if they're missing. The database isn't changed unless you
# say yes to creating DB_NAME at the end.

set -uo pipefail

DB_HOST="${1:-${DB_HOST:-}}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-recipebox}"
ENV_FILE=/srv/recipe-box/backend/.env

bold=$'\033[1m'; green=$'\033[32m'; red=$'\033[31m'; yellow=$'\033[33m'; dim=$'\033[2m'; reset=$'\033[0m'
failures=0
section() { printf '\n%s%s%s\n' "$bold" "$*" "$reset"; }
pass() { printf '  %sok%s    %s\n' "$green" "$reset" "$*"; }
fail() { printf '  %sFAIL%s  %s\n' "$red" "$reset" "$*"; failures=$((failures + 1)); }
warn() { printf '  %swarn%s  %s\n' "$yellow" "$reset" "$*"; }
hint() { printf '        %s%s%s\n' "$dim" "$*" "$reset"; }

# An already-deployed instance remembers its endpoint.
if [[ -z $DB_HOST && -r $ENV_FILE ]]; then
    DB_HOST="$(sed -nE "s/^DB_HOST=['\"]?([^'\"]*)['\"]?$/\1/p" "$ENV_FILE" | tail -1)"
fi
if [[ -z $DB_HOST && -t 0 ]]; then
    read -r -p "RDS endpoint (e.g. database-1.cluster-xxxx.us-east-1.rds.amazonaws.com): " DB_HOST
fi
[[ -n $DB_HOST ]] || { echo "Usage: sudo $0 <rds-endpoint>" >&2; exit 2; }
REGION="${AWS_REGION:-$(sed -nE 's/.*\.([a-z]{2}(-gov)?-[a-z]+-[0-9]+)\.rds\.amazonaws\.com\.?$/\1/p' <<<"$DB_HOST")}"

printf 'Checking %s%s:%s%s as %s (database %s)\n' "$bold" "$DB_HOST" "$DB_PORT" "$reset" "$DB_USER" "$DB_NAME"

summary() {
    echo
    if [[ $failures -eq 0 ]]; then
        printf '%s%sThe database is ready.%s Deploy with:\n\n' "$bold" "$green" "$reset"
        printf '  sudo DB_HOST=%s DB_PORT=%s DB_NAME=%s DB_USER=%s DB_IAM_AUTH=True ./deploy.sh\n\n' \
            "$DB_HOST" "$DB_PORT" "$DB_NAME" "$DB_USER"
        echo "  (deploy.sh then only asks for the domain, the site password and the optional Anthropic key.)"
        exit 0
    fi
    printf '%s%s%d problem(s) above.%s Fix them and run this again.\n' "$bold" "$red" "$failures" "$reset"
    exit 1
}

# --- the instance ------------------------------------------------------------------

section "Instance"
imds_token="$(curl -fsS -m 2 -X PUT http://169.254.169.254/latest/api/token \
    -H 'X-aws-ec2-metadata-token-ttl-seconds: 300' 2>/dev/null || true)"
imds() { curl -fsS -m 2 -H "X-aws-ec2-metadata-token: $imds_token" "http://169.254.169.254/latest/meta-data/$1" 2>/dev/null; }
if [[ -z $imds_token ]]; then
    warn "not on EC2 (no instance metadata). Run this on the instance to test what the app will see."
else
    pass "instance $(imds instance-id) in $(imds placement/availability-zone)"
    role="$(imds iam/security-credentials/ || true)"
    if [[ -n $role ]]; then
        pass "IAM role attached: $role"
    else
        fail "no IAM role is attached, so IAM database login can't work"
        hint "EC2 console > this instance > Actions > Security > Modify IAM role"
    fi
    hint "security groups: $(imds security-groups | tr '\n' ' ')"
fi

# --- network -----------------------------------------------------------------------

section "Network"
if ! getent hosts "$DB_HOST" >/dev/null 2>&1; then
    fail "$DB_HOST doesn't resolve. Check the endpoint for typos (copy it from the RDS console)."
    summary
fi
pass "$DB_HOST resolves to $(getent hosts "$DB_HOST" | awk '{print $1}' | head -1)"
if timeout 6 bash -c ">/dev/tcp/$DB_HOST/$DB_PORT" 2>/dev/null; then
    pass "port $DB_PORT is reachable"
else
    fail "port $DB_PORT timed out"
    hint "The RDS cluster's security group needs an inbound rule: PostgreSQL (5432) from this"
    hint "instance's security group. Both must also be in the same VPC (or peered)."
    summary
fi

# --- tools -------------------------------------------------------------------------

section "Tools"
if command -v dnf >/dev/null 2>&1; then PKG=dnf; elif command -v apt-get >/dev/null 2>&1; then PKG=apt; else PKG=; fi
install_psql() {
    case $PKG in
        dnf) dnf install -y -q postgresql17 >/dev/null 2>&1 || dnf install -y -q postgresql16 >/dev/null 2>&1 \
                 || dnf install -y -q postgresql15 >/dev/null 2>&1 ;;
        apt) apt-get update -qq >/dev/null && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql-client >/dev/null 2>&1 ;;
        *) return 1 ;;
    esac
}
install_aws() {
    case $PKG in
        dnf) dnf install -y -q awscli-2 >/dev/null 2>&1 ;;
        apt) snap install aws-cli --classic >/dev/null 2>&1 ;;
        *) return 1 ;;
    esac
}
for tool in psql aws; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        if [[ $EUID -ne 0 ]]; then
            fail "$tool isn't installed. Run this with sudo to install it."
            continue
        fi
        echo "  installing $tool..."
        "install_$tool" || true
        hash -r
    fi
    command -v "$tool" >/dev/null 2>&1 || { fail "couldn't install $tool"; continue; }
    pass "$tool: $("$tool" --version 2>&1 | head -1)"
done
[[ $failures -eq 0 ]] || summary

# --- AWS credentials & IAM login -----------------------------------------------------

section "IAM login"
if identity="$(aws sts get-caller-identity --query Arn --output text 2>&1)"; then
    pass "AWS identity: $identity"
    account="$(cut -d: -f5 <<<"$identity")"
else
    fail "no usable AWS credentials: $identity"
    hint "On EC2 these come from the instance's IAM role (see above)."
    summary
fi
[[ -n $REGION ]] || { fail "can't tell the region from the endpoint. Set AWS_REGION=... and re-run."; summary; }

if ! token="$(aws rds generate-db-auth-token --hostname "$DB_HOST" --port "$DB_PORT" \
    --username "$DB_USER" --region "$REGION" 2>&1)"; then
    fail "couldn't generate an auth token: $token"
    summary
fi

sql() { # sql <database> <<<"statement"   (reads SQL from stdin so :'var' interpolation works)
    PGPASSWORD="$token" PGCONNECT_TIMEOUT=10 psql -X -q -t -A -F '|' -v ON_ERROR_STOP=1 \
        -v name="$DB_NAME" -v user="$DB_USER" \
        "host=$DB_HOST port=$DB_PORT dbname=$1 user=$DB_USER sslmode=require"
}

if ! login="$(sql postgres <<<"SELECT current_user, split_part(version(), ' ', 2), inet_server_addr() IS NOT NULL;" 2>&1)"; then
    fail "the database refused the IAM login"
    hint "${login//$'\n'/ }"
    case $login in
        *"PAM authentication failed"*)
            hint "The role's policy must allow rds-db:connect on"
            hint "  arn:aws:rds-db:$REGION:${account:-<account>}:dbuser:<cluster-resource-id>/$DB_USER"
            hint "(<cluster-resource-id> is the cluster-XXXX ID on the cluster's Configuration tab,"
            hint "not the endpoint name.)"
            ;;
        *"password authentication failed"*)
            hint "Either IAM database authentication is off for the cluster (RDS console > Modify >"
            hint "Database authentication > Password and IAM), or the user was never granted it:"
            hint "  GRANT rds_iam TO $DB_USER;   (run once, logged in with the master password)"
            ;;
        *"SSL"* | *"ssl"*)
            hint "The connection needs SSL (sslmode=require), which RDS supports by default."
            ;;
    esac
    summary
fi
IFS='|' read -r who server_version _ <<<"$login"
pass "logged in as $who with an IAM token over SSL (PostgreSQL $server_version)"

# --- privileges & the app's database ---------------------------------------------------

section "Database"
IFS='|' read -r has_rds_iam can_createdb <<<"$(sql postgres <<'SQL'
SELECT
  EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid
          JOIN pg_roles u ON u.oid = m.member WHERE r.rolname = 'rds_iam' AND u.rolname = current_user),
  (SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user);
SQL
)"
[[ $has_rds_iam == t ]] && pass "$DB_USER has the rds_iam role"

exists="$(sql postgres <<<"SELECT 1 FROM pg_database WHERE datname = :'name';")"
if [[ $exists == 1 ]]; then
    if ! contents="$(sql "$DB_NAME" 2>&1 <<'SQL'
SELECT (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'),
       EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'recipes_recipe');
SQL
)"; then
        fail "database $DB_NAME exists but couldn't be read: ${contents//$'\n'/ }"
        summary
    fi
    IFS='|' read -r tables migrated <<<"$contents"
    if [[ $migrated == t ]]; then
        recipes="$(sql "$DB_NAME" <<<"SELECT count(*) FROM recipes_recipe;")"
        pass "database $DB_NAME exists and already holds Recipe Box ($recipes recipe$([[ $recipes == 1 ]] || echo s))"
    elif [[ ${tables:-0} -eq 0 ]]; then
        pass "database $DB_NAME exists and is empty; the deploy will set it up"
    else
        fail "database $DB_NAME already has $tables table(s) from something else (another app?)"
        hint "Recipe Box's tables would be mixed in with them. Use its own database instead:"
        hint "  sudo DB_NAME=recipebox $0 $DB_HOST"
    fi
elif [[ $can_createdb == t ]]; then
    pass "$DB_USER can create databases, so the deploy will create $DB_NAME"
    if [[ -t 0 ]]; then
        read -r -p "        Create $DB_NAME now instead? [y/N]: " answer
        if [[ $answer =~ ^[Yy] ]]; then
            if created="$(sql postgres <<<'CREATE DATABASE :"name";' 2>&1)"; then
                pass "created database $DB_NAME"
            else
                fail "couldn't create $DB_NAME: $created"
            fi
        fi
    fi
else
    fail "database $DB_NAME doesn't exist, and $DB_USER isn't allowed to create it"
    hint "Log in as the master user and run:  CREATE DATABASE $DB_NAME OWNER $DB_USER;"
fi

summary
