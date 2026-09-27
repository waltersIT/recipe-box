"""PostgreSQL, authenticated to Amazon RDS with a rotating IAM auth token.

(Shared with Filler-Local's filler/db/postgresql_iam, so both apps connect to
RDS the same way.)

RDS IAM auth replaces the database password with a token that AWS signs from
the caller's credentials and that stops working fifteen minutes later. That
expiry is the whole reason this module exists: `settings.DATABASES["PASSWORD"]`
is read once at import time, which is fine for a value that never changes and
useless for one that goes stale over lunch. The token has to be minted at
connect time instead, which is exactly what `get_connection_params()` is for.

Nothing else about the backend changes — it is the stock PostgreSQL one with
the password filled in late. Set `DB_IAM_AUTH=False` and supply a real
`DB_PASSWORD` to fall back to ordinary password auth without touching code.

The database user has to be granted the IAM role on the server side, once:

    GRANT rds_iam TO <db user>;
"""

import re
import threading
import time

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.postgresql import base

# AWS mints tokens with a fifteen-minute life. Reusing one for only ten leaves
# a five-minute margin, so a connection opened on the last cache hit before
# expiry still presents a token with time left on it.
#
# That margin is not the only thing that can kill a token early, though. A
# token is a SigV4-signed request, so it is only good while the credentials
# that signed it are: with temporary credentials (SSO, `aws login`, an assumed
# role, an instance role) the effective life is whichever runs out first, and
# the fifteen minutes stamped on the token counts for nothing once the session
# behind it rotates. Hence the fingerprint below.
TOKEN_REUSE_SECONDS = 10 * 60

# database-1.cluster-abc123.us-east-1.rds.amazonaws.com -> us-east-1
_REGION_IN_HOSTNAME = re.compile(
    r"\.([a-z]{2}(?:-gov|-iso[a-z]?)?-[a-z]+-\d+)\.rds\.amazonaws\.com\.?$",
    re.IGNORECASE,
)


def region_from_host(host):
    """Pull the region out of an RDS endpoint, or return None if it isn't one."""
    match = _REGION_IN_HOSTNAME.search(host or "")
    return match.group(1).lower() if match else None


class _TokenMinter:
    """Mints auth tokens, and holds on to them for a while.

    Signing a token is local work, but resolving the credentials to sign it
    with is not always: an SSO or assume-role profile refreshes over the
    network. Caching one token per endpoint keeps that off the request path,
    and caching the boto3 client keeps its (slow) construction off it too.

    The cache is thrown away whenever the credentials underneath it change.
    Without that, a rotation part-way through the reuse window leaves every
    connection presenting a token signed by a session that no longer exists,
    and RDS rejects those as `PAM authentication failed` — an authentication
    error with nothing wrong with the configuration, which then clears up by
    itself once the cache ages out. Cheaper to notice the rotation.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._session = None
        self._client = None
        self._client_region = None
        self._fingerprint = None
        self._tokens = {}

    def token_for(self, host, port, user, region):
        key = (host, int(port), user, region)
        now = time.monotonic()
        with self._lock:
            fingerprint = self._credentials_fingerprint()
            if fingerprint != self._fingerprint:
                self._tokens.clear()
                self._fingerprint = fingerprint

            cached = self._tokens.get(key)
            if cached is not None and now - cached[1] < TOKEN_REUSE_SECONDS:
                return cached[0]
            token = self._mint(host, port, user, region)
            self._tokens[key] = (token, now)
            return token

    def _boto3(self):
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - install-time problem
            raise ImproperlyConfigured(
                "RDS IAM authentication needs boto3. Install it with "
                "`pip install -r backend/requirements.txt`, or set "
                "DB_IAM_AUTH=False and use a password instead."
            ) from exc

        if self._session is None:
            self._session = boto3.Session()
        return self._session

    def _credentials_fingerprint(self):
        """Identify the credentials in force, refreshing them if they are due.

        Resolving is what triggers botocore's refresh, so this doubles as the
        thing that keeps them current. The access key is the part of a rotation
        that always changes, and it is already carried in plain sight inside
        every token this signs — nothing secret is being held here.
        """
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            credentials = self._boto3().get_credentials()
            # A rotation happens here, inside `get_frozen_credentials`, when
            # the current set is close enough to expiry.
            frozen = credentials and credentials.get_frozen_credentials()
        except (BotoCoreError, ClientError) as exc:
            # The usual one: a login/SSO session that has run out and cannot be
            # renewed without the human. Worth saying plainly, because from
            # Postgres it arrives as a bare authentication failure.
            raise ImproperlyConfigured(
                f"Could not refresh the AWS credentials for RDS IAM auth: {exc}. "
                "If this is an SSO or `aws login` session, sign in again."
            ) from exc

        if frozen is None:
            raise ImproperlyConfigured(
                "RDS IAM authentication needs AWS credentials and none could be "
                "found. Set AWS_PROFILE, or AWS_ACCESS_KEY_ID and "
                "AWS_SECRET_ACCESS_KEY, or run on an instance/task role."
            )
        return frozen.access_key

    def _mint(self, host, port, user, region):
        try:
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError as exc:  # pragma: no cover - install-time problem
            raise ImproperlyConfigured(
                "RDS IAM authentication needs boto3. Install it with "
                "`pip install -r backend/requirements.txt`, or set "
                "DB_IAM_AUTH=False and use a password instead."
            ) from exc

        if self._client is None or self._client_region != region:
            self._client = self._boto3().client("rds", region_name=region)
            self._client_region = region

        try:
            return self._client.generate_db_auth_token(
                DBHostname=host, Port=int(port), DBUsername=user, Region=region
            )
        except (BotoCoreError, ClientError) as exc:
            # Almost always "no credentials". Say so here rather than letting
            # it surface as an opaque authentication failure from Postgres.
            raise ImproperlyConfigured(
                f"Could not mint an RDS IAM auth token for {user}@{host}: {exc}. "
                "Check that AWS credentials are available (AWS_PROFILE, "
                "environment variables, or an instance role) and that they are "
                "allowed rds-db:connect on this cluster."
            ) from exc


_minter = _TokenMinter()


class DatabaseWrapper(base.DatabaseWrapper):
    def get_connection_params(self):
        params = super().get_connection_params()
        settings_dict = self.settings_dict

        host = settings_dict.get("HOST")
        user = settings_dict.get("USER")
        port = settings_dict.get("PORT") or 5432
        if not host or not user:
            raise ImproperlyConfigured(
                "RDS IAM authentication needs both HOST and USER in "
                "settings.DATABASES['default'] — there is nothing to sign a "
                "token for otherwise."
            )

        region = settings_dict.get("AWS_REGION") or region_from_host(host)
        if not region:
            raise ImproperlyConfigured(
                f"Cannot work out an AWS region for '{host}'. Set AWS_REGION in "
                "backend/.env when the endpoint is not a standard "
                "*.<region>.rds.amazonaws.com name."
            )

        # The server refuses an IAM token over an unencrypted connection, so a
        # missing sslmode would fail late and confusingly. Fail here instead.
        if params.get("sslmode") in (None, "disable", "allow", "prefer"):
            raise ImproperlyConfigured(
                "RDS IAM authentication requires TLS. Set DB_SSLMODE to "
                "'require' (or stricter) — 'disable', 'allow' and 'prefer' "
                "all let the connection fall back to plaintext."
            )

        params["password"] = _minter.token_for(host, port, user, region)
        return params
