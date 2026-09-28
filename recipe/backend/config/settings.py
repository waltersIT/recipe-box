"""
Django settings for the Recipe Box backend.

Everything that differs between machines is read from environment variables
(optionally via a `.env` file next to manage.py — see `.env.example`).
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-dev-only-change-me-before-hosting-anywhere",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
if not DEBUG and SECRET_KEY.startswith("django-insecure"):
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in backend/.env before running with DEBUG off.")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Scheme-qualified origins allowed to POST here, e.g. https://recipes.example.com.
# In production the React build is served from this same origin, so nothing is
# needed; in development the Vite dev server proxies /api from another port, so
# signing in and saving arrive with its origin.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") or (
    ["http://localhost:5173", "http://127.0.0.1:5173"] if DEBUG else []
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "recipes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Local development uses SQLite, a file next to manage.py. Setting DB_HOST
# switches to PostgreSQL, e.g. Amazon RDS. As in Filler-Local, RDS IAM auth is
# the default: no stored password, just a short-lived token signed per
# connection from the instance role. Set DB_IAM_AUTH=False to use DB_PASSWORD.
DB_HOST = os.environ.get("DB_HOST", "").strip()
if DB_HOST:
    DB_IAM_AUTH = env_bool("DB_IAM_AUTH", True)
    DATABASES = {
        "default": {
            "ENGINE": "config.db.postgresql_iam" if DB_IAM_AUTH else "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "recipebox"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": DB_HOST,
            "PORT": os.environ.get("DB_PORT", "5432"),
            # Region the IAM token is signed for; read from the RDS hostname when blank.
            "AWS_REGION": os.environ.get("AWS_REGION") or None,
            # RDS is a network hop away, so keep connections open between requests.
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "600")),
            "CONN_HEALTH_CHECKS": env_bool("DB_CONN_HEALTH_CHECKS", True),
            "OPTIONS": {
                # IAM auth is refused over plaintext.
                "sslmode": os.environ.get("DB_SSLMODE", "require"),
                # Fail fast (rather than hang) when a security group blocks the port.
                "connect_timeout": int(os.environ.get("DB_CONNECT_TIMEOUT", "10")),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(os.environ.get("DJANGO_SQLITE_PATH") or BASE_DIR / "db.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Admin/DRF assets. The React app is a separate Vite build that nginx serves.
STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT") or BASE_DIR / "staticfiles")
# Recipe photos and imported PDFs/screenshots. On a server this lives outside
# the code directory so redeploys never touch it.
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT") or BASE_DIR / "media")
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }

# --- Behind nginx ------------------------------------------------------------

# nginx sets X-Forwarded-Proto; this makes request.is_secure() true behind it.
if env_bool("USE_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Turn on once HTTPS works (deploy.sh does this after getting a certificate).
if env_bool("DJANGO_SECURE_SSL", False):
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    # The deploy health check calls this over plain HTTP from the instance itself.
    SECURE_REDIRECT_EXEMPT = [r"^healthz$"]

# Everything goes to stdout/stderr, which systemd sends to the journal.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The bookmarklet posts a whole page of HTML, and PDFs/screenshots can be large.
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024

REST_FRAMEWORK = {
    # The browser signs in with a Django session cookie, so unsafe requests
    # need the CSRF token (the frontend reads it from the csrftoken cookie).
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    # Reading recipes needs no account; each view says what writing needs.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

# Signing in is a session cookie; it doesn't need to travel to other sites.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
LOGIN_URL = "/login"

# --- Recipe import -----------------------------------------------------------

# "auto" uses Claude for PDFs, screenshots and pages without recipe markup when
# an Anthropic credential is configured; "on" forces it; "off" never uses it.
RECIPE_LLM = os.environ.get("RECIPE_LLM", "auto").strip().lower()
RECIPE_LLM_MODEL = os.environ.get("RECIPE_LLM_MODEL", "claude-opus-5")
RECIPE_LLM_EFFORT = os.environ.get("RECIPE_LLM_EFFORT", "low")

# Recipe links are fetched once, when you ask for them, like opening the page
# in a browser. Many recipe sites refuse requests that don't look like a
# browser, so we send a regular browser User-Agent by default.
RECIPE_FETCH_USER_AGENT = os.environ.get(
    "RECIPE_FETCH_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
)
RECIPE_FETCH_TIMEOUT = float(os.environ.get("RECIPE_FETCH_TIMEOUT", "20"))
# Links that resolve to private/loopback addresses are refused so the importer
# can't be pointed at things on your own network. Tests flip this on.
RECIPE_ALLOW_PRIVATE_URLS = env_bool("RECIPE_ALLOW_PRIVATE_URLS", False)

RECIPE_MAX_UPLOAD_FILES = 10
RECIPE_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
