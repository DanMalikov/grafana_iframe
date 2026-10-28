"""Database connection and session lifecycle."""

import os
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


password = Path("/run/mysql-app/password").read_text(encoding="utf-8").strip()
host = os.environ.get("MYSQL_HOST", "mysql")
name = os.environ.get("MYSQL_DATABASE", "grafana_iframe")
user = os.environ.get("MYSQL_USER", "app")
engine = create_engine(
    f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@{host}/{name}",
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine)
