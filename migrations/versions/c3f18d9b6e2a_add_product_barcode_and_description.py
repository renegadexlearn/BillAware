"""add product barcode and description

Revision ID: c3f18d9b6e2a
Revises: b9d7e2c11f4a
Create Date: 2026-03-13 14:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c3f18d9b6e2a"
down_revision = "b9d7e2c11f4a"
branch_labels = None
depends_on = None


PRODUCTS_TABLE = "billaware_products"
BARCODE_INDEX = "ix_billaware_products_barcode"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in _inspector().get_indexes(table_name)}


def upgrade():
    if not _has_table(PRODUCTS_TABLE):
        return
    if not _has_column(PRODUCTS_TABLE, "barcode"):
        op.add_column(PRODUCTS_TABLE, sa.Column("barcode", sa.String(length=120), nullable=True))
    if not _has_column(PRODUCTS_TABLE, "description"):
        op.add_column(PRODUCTS_TABLE, sa.Column("description", sa.String(length=255), nullable=True))
    if _has_column(PRODUCTS_TABLE, "barcode") and not _has_index(PRODUCTS_TABLE, BARCODE_INDEX):
        op.create_index(BARCODE_INDEX, PRODUCTS_TABLE, ["barcode"], unique=True)


def downgrade():
    if _has_table(PRODUCTS_TABLE) and _has_index(PRODUCTS_TABLE, BARCODE_INDEX):
        op.drop_index(BARCODE_INDEX, table_name=PRODUCTS_TABLE)
    if _has_table(PRODUCTS_TABLE) and _has_column(PRODUCTS_TABLE, "description"):
        op.drop_column(PRODUCTS_TABLE, "description")
    if _has_table(PRODUCTS_TABLE) and _has_column(PRODUCTS_TABLE, "barcode"):
        op.drop_column(PRODUCTS_TABLE, "barcode")
