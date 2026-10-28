"""Idempotently insert local demo companies, users and devices."""

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pwdlib import PasswordHash

from app.database import SessionLocal
from app.models import Company, Device, User


def main() -> None:
    password = Path("/run/api-secrets/demo-password").read_text(
        encoding="utf-8"
    ).strip()
    hasher = PasswordHash.recommended()
    devices = {
        "1": ("0030014467", "10"),
        "2": ("1140000464", "1050"),
    }
    with SessionLocal.begin() as session:
        for company_id, device_ids in devices.items():
            if session.get(Company, company_id) is None:
                session.add(Company(id=company_id, name=f"Company {company_id}"))
            for role in ("analyst", "director"):
                username = f"{role}{company_id}"
                user_id = str(uuid5(NAMESPACE_URL, f"grafana-iframe-poc:{username}"))
                if session.get(User, user_id) is None:
                    session.add(
                        User(
                            id=user_id,
                            username=username,
                            email=f"{username}@poc.local",
                            password_hash=hasher.hash(password),
                            business_role=role,
                            company_id=company_id,
                        )
                    )
            for device_id in device_ids:
                if session.get(Device, device_id) is None:
                    session.add(Device(id=device_id, company_id=company_id))


if __name__ == "__main__":
    main()
