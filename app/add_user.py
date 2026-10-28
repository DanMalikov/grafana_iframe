"""Add a portal user to an existing demo company."""

from argparse import ArgumentParser
from getpass import getpass
from uuid import NAMESPACE_URL, uuid5

from pwdlib import PasswordHash
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Company, User


def main() -> None:
    parser = ArgumentParser(description="Add a portal user")
    parser.add_argument("username")
    parser.add_argument("--company-id", choices=("1", "2"), required=True)
    parser.add_argument("--role", choices=("analyst", "director"), required=True)
    parser.add_argument("--email")
    args = parser.parse_args()

    username = args.username.strip()
    if not username:
        parser.error("username cannot be empty")
    email = args.email or f"{username}@poc.local"

    with SessionLocal() as session:
        if session.get(Company, args.company_id) is None:
            parser.error(f"company {args.company_id} does not exist")
        if session.scalar(select(User).where(User.username == username)):
            parser.error(f"user {username} already exists")
        if session.scalar(select(User).where(User.email == email)):
            parser.error(f"email {email} already exists")

    password = getpass("Password: ")
    if not password:
        parser.error("password cannot be empty")
    if password != getpass("Repeat password: "):
        parser.error("passwords do not match")

    user = User(
        id=str(uuid5(NAMESPACE_URL, f"grafana-iframe-poc:{username}")),
        username=username,
        email=email,
        password_hash=PasswordHash.recommended().hash(password),
        business_role=args.role,
        company_id=args.company_id,
    )
    with SessionLocal.begin() as session:
        session.add(user)
    print(f"Created {username} for Company {args.company_id}")


if __name__ == "__main__":
    main()
