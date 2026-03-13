"""add encoded total amount to bills

Revision ID: d92a4f1b7c3e
Revises: c3f18d9b6e2a
Create Date: 2026-03-13 17:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d92a4f1b7c3e"
down_revision = "c3f18d9b6e2a"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade():
    if not _has_column("billaware_bills", "encoded_total_amount"):
        op.add_column("billaware_bills", sa.Column("encoded_total_amount", sa.Numeric(12, 2), nullable=True))


def downgrade():
    if _has_column("billaware_bills", "encoded_total_amount"):
        op.drop_column("billaware_bills", "encoded_total_amount")
