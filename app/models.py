"""The three domain tables used by the local PoC."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    users: Mapped[list["User"]] = relationship(back_populates="company")
    devices: Mapped[list["Device"]] = relationship(back_populates="company")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    business_role: Mapped[str] = mapped_column(String(20))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    company: Mapped[Company] = relationship(back_populates="users")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    company: Mapped[Company] = relationship(back_populates="devices")
