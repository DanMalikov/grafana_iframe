"""Create companies, users and devices.

Revision ID: 0001_initial
Revises:
"""

import sqlalchemy as sa
from alembic import op


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("business_role", sa.String(20), nullable=False),
        sa.Column(
            "company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False
        ),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("devices")
    op.drop_table("users")
    op.drop_table("companies")
