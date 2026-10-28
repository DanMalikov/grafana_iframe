"""Initialize local credentials and preserve an existing Grafana RSA pair."""

import os
from pathlib import Path
from secrets import token_urlsafe

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


ROOT = Path("/state")
LEGACY = Path("/legacy")
PRIVATE = ROOT / "jwt-private" / "jwt-private.pem"
PUBLIC = ROOT / "jwt-public" / "jwt-public.pem"
MYSQL_ROOT = ROOT / "mysql-root" / "password"
MYSQL_APP = ROOT / "mysql-app" / "password"
API_SECRET = ROOT / "api-secrets" / "jwt-secret"
DEMO_PASSWORD = ROOT / "api-secrets" / "demo-password"
GRAFANA_ADMIN = ROOT / "grafana-admin" / "password"
CLICKHOUSE_ADMIN = ROOT / "clickhouse-admin" / "password"
CLICKHOUSE_READER = ROOT / "clickhouse-reader" / "password"


def write_once(path: Path, data: bytes, mode: int = 0o600) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    temporary.chmod(mode)
    temporary.replace(path)


def public_bytes(private_key: rsa.RSAPrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def load_private(path: Path) -> rsa.RSAPrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError(f"Expected RSA private key: {path}")
    return key


def check_legacy_pair() -> rsa.RSAPrivateKey | None:
    old_private = LEGACY / "jwt-private.pem"
    old_public = LEGACY / "jwt-public.pem"
    if old_private.exists() != old_public.exists():
        raise RuntimeError("Incomplete legacy RSA pair in secrets/; restore both files")
    if not old_private.exists():
        return None
    key = load_private(old_private)
    old_public_key = serialization.load_pem_public_key(old_public.read_bytes())
    if old_public_key.public_numbers() != key.public_key().public_numbers():
        raise RuntimeError("Legacy RSA private/public keys do not match")
    return key


def init_keys(existing_database: bool) -> None:
    legacy = check_legacy_pair()
    if PRIVATE.exists():
        key = load_private(PRIVATE)
        if (
            legacy
            and key.public_key().public_numbers()
            != legacy.public_key().public_numbers()
        ):
            raise RuntimeError("RSA volume and secrets/ contain different key pairs")
    else:
        if PUBLIC.exists():
            raise RuntimeError(
                "RSA public key exists without private key; restore the pair"
            )
        if legacy:
            write_once(PRIVATE, (LEGACY / "jwt-private.pem").read_bytes())
            key = legacy
        elif existing_database:
            raise RuntimeError(
                "RSA key missing while database exists; restore original key"
            )
        else:
            key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
            write_once(
                PRIVATE,
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
            )

    expected = public_bytes(key)
    if PUBLIC.exists():
        actual = serialization.load_pem_public_key(PUBLIC.read_bytes())
        if actual.public_numbers() != key.public_key().public_numbers():
            raise RuntimeError("RSA volume keys do not match; restore original pair")
    else:
        write_once(PUBLIC, expected, 0o644)


def init_secret(
    path: Path,
    database_exists: bool,
    legacy_value: str = "",
    mode: int = 0o600,
) -> None:
    if path.exists():
        if not path.read_bytes().strip():
            raise RuntimeError(f"Empty secret: {path}")
        path.chmod(mode)
        return
    if legacy_value:
        value = legacy_value
    elif database_exists:
        raise RuntimeError(f"Missing secret for existing database: {path}")
    else:
        value = token_urlsafe(32)
    write_once(path, value.encode("utf-8"), mode)


def main() -> None:
    mysql_exists = any(Path("/mysql-data").iterdir())
    grafana_exists = (Path("/grafana-data") / "grafana.db").exists()
    clickhouse_exists = any(Path("/clickhouse-data").iterdir())
    init_keys(grafana_exists)
    init_secret(MYSQL_ROOT, mysql_exists)
    init_secret(MYSQL_APP, mysql_exists)
    init_secret(API_SECRET, mysql_exists)
    init_secret(DEMO_PASSWORD, mysql_exists)
    init_secret(
        GRAFANA_ADMIN,
        grafana_exists,
        os.environ.get("GRAFANA_ADMIN_PASSWORD", ""),
        mode=0o640,
    )
    init_secret(CLICKHOUSE_ADMIN, clickhouse_exists)
    init_secret(CLICKHOUSE_READER, clickhouse_exists)
    print("Local secrets validated")


if __name__ == "__main__":
    main()
