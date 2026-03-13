from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models.base import BaseModel


product_tags = db.Table(
    "billaware_product_tags",
    db.Column("product_id", db.BigInteger, db.ForeignKey("billaware_products.id"), primary_key=True),
    db.Column("tag_id", db.BigInteger, db.ForeignKey("billaware_tags.id"), primary_key=True),
)


class Supplier(BaseModel):
    __tablename__ = "billaware_suppliers"

    name = db.Column(db.String(255), nullable=False, unique=True)
    tin = db.Column(db.String(64), nullable=True)
    address = db.Column(db.Text, nullable=True)

    bills = db.relationship("Bill", back_populates="supplier")


class DocumentType(BaseModel):
    __tablename__ = "billaware_document_types"

    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(30), nullable=False, unique=True, index=True)

    bills = db.relationship("Bill", back_populates="document_type")


class Tag(BaseModel):
    __tablename__ = "billaware_tags"

    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)

    products = db.relationship("Product", secondary=product_tags, back_populates="tags")


class Product(BaseModel):
    __tablename__ = "billaware_products"

    name = db.Column(db.String(255), nullable=False, unique=True)
    barcode = db.Column(db.String(120), nullable=True, unique=True, index=True)
    brand = db.Column(db.String(120), nullable=True)
    description = db.Column(db.String(255), nullable=True)
    dimension = db.Column(db.String(120), nullable=True)
    weight = db.Column(db.String(120), nullable=True)
    alias_name = db.Column(db.String(120), nullable=True)
    color = db.Column(db.String(80), nullable=True)
    default_unit = db.Column(db.String(40), nullable=True)
    unit_options = db.Column(db.JSON, nullable=False, default=list)
    unit_conversions = db.Column(db.JSON, nullable=False, default=list)
    notes = db.Column(db.Text, nullable=True)

    tags = db.relationship("Tag", secondary=product_tags, back_populates="products")
    line_items = db.relationship("BillLineItem", back_populates="product")


class Bill(BaseModel):
    __tablename__ = "billaware_bills"

    document_type_id = db.Column(db.BigInteger, db.ForeignKey("billaware_document_types.id"), nullable=True, index=True)
    supplier_id = db.Column(db.BigInteger, db.ForeignKey("billaware_suppliers.id"), nullable=False, index=True)
    encoded_by_user_id = db.Column(db.BigInteger, db.ForeignKey("auth_cache_users.id"), nullable=True, index=True)

    bill_date = db.Column(db.Date, nullable=False, index=True)
    bill_number = db.Column(db.String(120), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="draft", index=True)
    encoded_total_amount = db.Column(db.Numeric(12, 2), nullable=True, default=None)

    subtotal_discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    additional_tax_type = db.Column(db.String(20), nullable=False, default="none")
    additional_tax_value = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    document_type = db.relationship("DocumentType", back_populates="bills")
    supplier = db.relationship("Supplier", back_populates="bills")
    encoded_by = db.relationship("UserCache", foreign_keys=[encoded_by_user_id])
    line_items = db.relationship(
        "BillLineItem",
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillLineItem.sort_order.asc(), BillLineItem.id.asc()",
    )

    @property
    def subtotal(self) -> Decimal:
        return sum((item.line_total for item in self.line_items), Decimal("0.00"))

    @property
    def subtotal_after_discount(self) -> Decimal:
        value = self.subtotal - Decimal(self.subtotal_discount_amount or 0)
        return value if value > 0 else Decimal("0.00")

    @property
    def additional_tax_amount(self) -> Decimal:
        value = Decimal(self.additional_tax_value or 0)
        if self.additional_tax_type == "percent":
            return (self.subtotal_after_discount * value) / Decimal("100")
        if self.additional_tax_type == "amount":
            return value
        return Decimal("0.00")

    @property
    def grand_total(self) -> Decimal:
        return self.subtotal_after_discount + self.additional_tax_amount

    @property
    def display_total_amount(self) -> Decimal:
        if self.encoded_total_amount is not None:
            return Decimal(self.encoded_total_amount or 0)
        return self.grand_total


class BillLineItem(BaseModel):
    __tablename__ = "billaware_bill_line_items"

    bill_id = db.Column(db.BigInteger, db.ForeignKey("billaware_bills.id"), nullable=False, index=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("billaware_products.id"), nullable=True, index=True)

    sort_order = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=1)
    unit = db.Column(db.String(40), nullable=True)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    line_discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    bill = db.relationship("Bill", back_populates="line_items")
    product = db.relationship("Product", back_populates="line_items")
    allocations = db.relationship(
        "BillLineAllocation",
        back_populates="line_item",
        cascade="all, delete-orphan",
        order_by="BillLineAllocation.sort_order.asc(), BillLineAllocation.id.asc()",
    )

    @property
    def line_subtotal(self) -> Decimal:
        return Decimal(self.quantity or 0) * Decimal(self.unit_price or 0)

    @property
    def line_total(self) -> Decimal:
        value = self.line_subtotal - Decimal(self.line_discount_amount or 0)
        return value if value > 0 else Decimal("0.00")

    @property
    def allocated_quantity(self) -> Decimal:
        return sum((Decimal(item.quantity or 0) for item in self.allocations), Decimal("0.00"))

    @property
    def unallocated_quantity(self) -> Decimal:
        value = Decimal(self.quantity or 0) - self.allocated_quantity
        return value if value > 0 else Decimal("0.00")


class BillLineAllocation(BaseModel):
    __tablename__ = "billaware_bill_line_allocations"

    line_item_id = db.Column(db.BigInteger, db.ForeignKey("billaware_bill_line_items.id"), nullable=False, index=True)

    sort_order = db.Column(db.Integer, nullable=False, default=0)
    target_type = db.Column(db.String(20), nullable=False)  # company | branch
    target_id = db.Column(db.BigInteger, nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    notes = db.Column(db.String(255), nullable=True)

    line_item = db.relationship("BillLineItem", back_populates="allocations")
