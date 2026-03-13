"""baseline_and_document_types

Revision ID: 0bee568e4c6b
Revises: 
Create Date: 2026-03-13 13:01:14.159795

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0bee568e4c6b'
down_revision = 'c144e9ccf6a5'
branch_labels = None
depends_on = None


DOCUMENT_TYPES_TABLE = "billaware_document_types"
BILLS_TABLE = "billaware_bills"
DOCUMENT_TYPE_FK = "fk_billaware_bills_document_type"
DOCUMENT_TYPE_INDEX = "ix_billaware_bills_document_type_id"
DOCUMENT_TYPE_CODE_INDEX = "ix_billaware_document_types_code"
DOCUMENT_TYPE_NAME_UQ = "uq_billaware_document_types_name"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in _inspector().get_indexes(table_name)}


def _has_foreign_key(table_name: str, fk_name: str) -> bool:
    return fk_name in {fk["name"] for fk in _inspector().get_foreign_keys(table_name)}


def upgrade():
    if not _has_table(DOCUMENT_TYPES_TABLE):
        op.create_table(
            DOCUMENT_TYPES_TABLE,
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("code", sa.String(length=30), nullable=False),
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name=DOCUMENT_TYPE_NAME_UQ),
        )

    if _has_table(DOCUMENT_TYPES_TABLE) and not _has_index(DOCUMENT_TYPES_TABLE, DOCUMENT_TYPE_CODE_INDEX):
        op.create_index(DOCUMENT_TYPE_CODE_INDEX, DOCUMENT_TYPES_TABLE, ["code"], unique=True)

    if _has_table(BILLS_TABLE) and not _has_column(BILLS_TABLE, "document_type_id"):
        op.add_column(BILLS_TABLE, sa.Column("document_type_id", sa.BigInteger(), nullable=True))

    if _has_table(BILLS_TABLE) and _has_column(BILLS_TABLE, "document_type_id") and not _has_index(BILLS_TABLE, DOCUMENT_TYPE_INDEX):
        op.create_index(DOCUMENT_TYPE_INDEX, BILLS_TABLE, ["document_type_id"], unique=False)

    if (
        _has_table(BILLS_TABLE)
        and _has_table(DOCUMENT_TYPES_TABLE)
        and _has_column(BILLS_TABLE, "document_type_id")
        and not _has_foreign_key(BILLS_TABLE, DOCUMENT_TYPE_FK)
    ):
        op.create_foreign_key(
            DOCUMENT_TYPE_FK,
            BILLS_TABLE,
            DOCUMENT_TYPES_TABLE,
            ["document_type_id"],
            ["id"],
        )


def downgrade():
    if _has_table(BILLS_TABLE) and _has_foreign_key(BILLS_TABLE, DOCUMENT_TYPE_FK):
        op.drop_constraint(DOCUMENT_TYPE_FK, BILLS_TABLE, type_="foreignkey")

    if _has_table(BILLS_TABLE) and _has_index(BILLS_TABLE, DOCUMENT_TYPE_INDEX):
        op.drop_index(DOCUMENT_TYPE_INDEX, table_name=BILLS_TABLE)

    if _has_table(BILLS_TABLE) and _has_column(BILLS_TABLE, "document_type_id"):
        op.drop_column(BILLS_TABLE, "document_type_id")

    if _has_table(DOCUMENT_TYPES_TABLE) and _has_index(DOCUMENT_TYPES_TABLE, DOCUMENT_TYPE_CODE_INDEX):
        op.drop_index(DOCUMENT_TYPE_CODE_INDEX, table_name=DOCUMENT_TYPES_TABLE)

    if _has_table(DOCUMENT_TYPES_TABLE):
        op.drop_table(DOCUMENT_TYPES_TABLE)
