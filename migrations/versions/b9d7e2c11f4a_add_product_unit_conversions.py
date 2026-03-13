"""add product unit conversions

Revision ID: b9d7e2c11f4a
Revises: a67b13c4f29e
Create Date: 2026-03-13 14:38:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b9d7e2c11f4a"
down_revision = "a67b13c4f29e"
branch_labels = None
depends_on = None


PRODUCTS_TABLE = "billaware_products"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def upgrade():
    if not _has_table(PRODUCTS_TABLE):
        return
    if not _has_column(PRODUCTS_TABLE, "unit_conversions"):
        op.add_column(PRODUCTS_TABLE, sa.Column("unit_conversions", sa.JSON(), nullable=True))
        op.get_bind().execute(
            sa.text(
                """
                UPDATE billaware_products
                SET unit_conversions = JSON_ARRAY()
                WHERE unit_conversions IS NULL
                """
            )
        )


def downgrade():
    if _has_table(PRODUCTS_TABLE) and _has_column(PRODUCTS_TABLE, "unit_conversions"):
        op.drop_column(PRODUCTS_TABLE, "unit_conversions")
