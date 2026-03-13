"""expand product details and units

Revision ID: a67b13c4f29e
Revises: 0bee568e4c6b
Create Date: 2026-03-13 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a67b13c4f29e"
down_revision = "0bee568e4c6b"
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

    if not _has_column(PRODUCTS_TABLE, "brand"):
        op.add_column(PRODUCTS_TABLE, sa.Column("brand", sa.String(length=120), nullable=True))
    if not _has_column(PRODUCTS_TABLE, "dimension"):
        op.add_column(PRODUCTS_TABLE, sa.Column("dimension", sa.String(length=120), nullable=True))
    if not _has_column(PRODUCTS_TABLE, "weight"):
        op.add_column(PRODUCTS_TABLE, sa.Column("weight", sa.String(length=120), nullable=True))
    if not _has_column(PRODUCTS_TABLE, "alias_name"):
        op.add_column(PRODUCTS_TABLE, sa.Column("alias_name", sa.String(length=120), nullable=True))
    if not _has_column(PRODUCTS_TABLE, "color"):
        op.add_column(PRODUCTS_TABLE, sa.Column("color", sa.String(length=80), nullable=True))
    if not _has_column(PRODUCTS_TABLE, "unit_options"):
        op.add_column(PRODUCTS_TABLE, sa.Column("unit_options", sa.JSON(), nullable=True))

    bind = op.get_bind()
    if _has_column(PRODUCTS_TABLE, "unit_options"):
        bind.execute(
            sa.text(
                """
                UPDATE billaware_products
                SET unit_options = JSON_ARRAY(default_unit)
                WHERE unit_options IS NULL AND default_unit IS NOT NULL AND TRIM(default_unit) <> ''
                """
            )
        )
        bind.execute(
            sa.text(
                """
                UPDATE billaware_products
                SET unit_options = JSON_ARRAY()
                WHERE unit_options IS NULL
                """
            )
        )


def downgrade():
    if not _has_table(PRODUCTS_TABLE):
        return

    if _has_column(PRODUCTS_TABLE, "unit_options"):
        op.drop_column(PRODUCTS_TABLE, "unit_options")
    if _has_column(PRODUCTS_TABLE, "color"):
        op.drop_column(PRODUCTS_TABLE, "color")
    if _has_column(PRODUCTS_TABLE, "alias_name"):
        op.drop_column(PRODUCTS_TABLE, "alias_name")
    if _has_column(PRODUCTS_TABLE, "weight"):
        op.drop_column(PRODUCTS_TABLE, "weight")
    if _has_column(PRODUCTS_TABLE, "dimension"):
        op.drop_column(PRODUCTS_TABLE, "dimension")
    if _has_column(PRODUCTS_TABLE, "brand"):
        op.drop_column(PRODUCTS_TABLE, "brand")
