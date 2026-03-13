from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Bill, BillLineAllocation, BillLineItem, BranchCache, CompanyCache, DocumentType, Product, Supplier, Tag
from app.utils.permissions import permission_required


bp = Blueprint("billing", __name__, url_prefix="/billing")


def _is_system_admin() -> bool:
    return current_user.has_role("system_admin")


def _can_edit_bill(bill: Bill) -> bool:
    if _is_system_admin():
        return True
    if (bill.status or "").strip().lower() == "draft":
        try:
            current_user_id = int(current_user.id)
        except (TypeError, ValueError):
            return False
        return int(bill.encoded_by_user_id or 0) == current_user_id
    return current_user.has_permission("encode_view")


def _to_decimal(value, *, default: str = "0.00") -> Decimal:
    try:
        return Decimal(str(value).strip() or default)
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def _parse_bill_date(value: str | None) -> date:
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def _parse_unit_options(raw_value: str | None) -> list[str]:
    items: list[str] = []
    for item in (raw_value or "").split(","):
        cleaned = item.strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return items


def _format_unit_conversions(conversions: list[dict] | None) -> str:
    lines: list[str] = []
    for item in conversions or []:
        from_unit = (item.get("from_unit") or "").strip()
        to_unit = (item.get("to_unit") or "").strip()
        from_qty = item.get("from_qty")
        to_qty = item.get("to_qty")
        if not from_unit or not to_unit:
            continue
        try:
            from_qty_text = f"{Decimal(str(from_qty))}".rstrip("0").rstrip(".")
            to_qty_text = f"{Decimal(str(to_qty))}".rstrip("0").rstrip(".")
        except (InvalidOperation, TypeError, ValueError):
            continue
        lines.append(f"{from_qty_text} {from_unit} = {to_qty_text} {to_unit}")
    return "\n".join(lines)


def _parse_unit_conversions(raw_value: str | None, unit_options: list[str]) -> list[dict]:
    conversions: list[dict] = []
    allowed_units = {item.casefold(): item for item in unit_options}
    pattern = re.compile(
        r"^\s*(?P<from_qty>\d+(?:\.\d+)?)\s+(?P<from_unit>.+?)\s*=\s*(?P<to_qty>\d+(?:\.\d+)?)\s+(?P<to_unit>.+?)\s*$"
    )
    for raw_line in (raw_value or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if not match:
            raise ValueError(f"Invalid unit conversion format: {line}")
        from_unit_raw = match.group("from_unit").strip()
        to_unit_raw = match.group("to_unit").strip()
        from_unit = allowed_units.get(from_unit_raw.casefold())
        to_unit = allowed_units.get(to_unit_raw.casefold())
        if not from_unit or not to_unit:
            raise ValueError(f"Conversion units must already exist in the product units: {line}")
        conversions.append(
            {
                "from_qty": str(Decimal(match.group("from_qty"))),
                "from_unit": from_unit,
                "to_qty": str(Decimal(match.group("to_qty"))),
                "to_unit": to_unit,
            }
        )
    return conversions


def _build_product_name(*, brand: str | None, description: str | None, dimension: str | None, weight: str | None, color: str | None) -> str:
    primary_parts = [
        (brand or "").strip(),
        (description or "").strip(),
        (dimension or "").strip(),
    ]
    base_name = " ".join(part for part in primary_parts if part)
    suffix_parts = [
        (weight or "").strip(),
        (color or "").strip(),
    ]
    suffix = ", ".join(part for part in suffix_parts if part)
    final_name = base_name.strip()
    if suffix:
        final_name = f"{final_name}, {suffix}" if final_name else suffix
    return final_name


def _scope_options() -> tuple[list[CompanyCache], list[BranchCache]]:
    company_ids = current_user.effective_company_ids()
    branch_ids = current_user.effective_branch_ids()

    companies = []
    branches = []
    if company_ids:
        companies = CompanyCache.query.filter(CompanyCache.id.in_(company_ids)).order_by(CompanyCache.name.asc()).all()
    if branch_ids:
        branches = BranchCache.query.filter(BranchCache.id.in_(branch_ids)).order_by(BranchCache.name.asc()).all()
    return companies, branches


def _line_payload_from_bill(item: BillLineItem) -> dict:
    return {
        "product_id": item.product_id,
        "description": item.description,
        "quantity": f"{Decimal(item.quantity or 0):.2f}",
        "unit": item.unit or "",
        "unit_price": f"{Decimal(item.unit_price or 0):.2f}",
        "line_discount_amount": f"{Decimal(item.line_discount_amount or 0):.2f}",
        "allocations": [
            {
                "target_type": allocation.target_type,
                "target_id": allocation.target_id,
                "quantity": f"{Decimal(allocation.quantity or 0):.2f}",
                "notes": allocation.notes or "",
            }
            for allocation in item.allocations
        ],
    }


def _bill_form_context(*, bill: Bill | None = None) -> dict:
    companies, branches = _scope_options()
    products = Product.query.filter(Product.deleted_at.is_(None)).order_by(Product.name.asc()).all()
    lines = [_line_payload_from_bill(item) for item in bill.line_items] if bill else []
    context = {
        "companies": companies,
        "branches": branches,
        "lines_seed_json": json.dumps(lines),
        "products_json": json.dumps(
            [
                {
                    "id": product.id,
                    "name": product.name,
                    "barcode": product.barcode or "",
                    "brand": product.brand or "",
                    "description": product.description or "",
                    "dimension": product.dimension or "",
                    "weight": product.weight or "",
                    "alias_name": product.alias_name or "",
                    "color": product.color or "",
                    "default_unit": product.default_unit or "",
                    "unit_options": product.unit_options or ([] if not product.default_unit else [product.default_unit]),
                    "unit_conversions": product.unit_conversions or [],
                    "tags": [tag.name for tag in product.tags],
                }
                for product in products
            ]
        ),
        "companies_json": json.dumps([{"id": company.id, "name": company.name} for company in companies]),
        "branches_json": json.dumps([{"id": branch.id, "name": branch.name} for branch in branches]),
    }
    context.update(_bill_master_context(bill=bill))
    return context


def _bill_master_context(*, bill: Bill | None = None, supplier_name: str | None = None) -> dict:
    document_types = DocumentType.query.filter(DocumentType.deleted_at.is_(None)).order_by(DocumentType.name.asc()).all()
    suppliers = Supplier.query.filter(Supplier.deleted_at.is_(None)).order_by(Supplier.name.asc()).all()
    resolved_supplier_name = (supplier_name or "").strip()
    if not resolved_supplier_name and bill and bill.supplier:
        resolved_supplier_name = bill.supplier.name
    return {
        "document_types": document_types,
        "suppliers": suppliers,
        "supplier_name": resolved_supplier_name,
        "suppliers_json": json.dumps(
            [{"id": supplier.id, "name": supplier.name} for supplier in suppliers]
        ),
    }


def _product_form_context(*, product: Product | None = None, form_data: dict | None = None) -> dict:
    source = form_data or {}
    product = product or Product()
    unit_options = source.get("unit_options")
    if unit_options is None:
        unit_options = ", ".join(product.unit_options or [])
    conversions = source.get("unit_conversions")
    if conversions is None:
        conversions = _format_unit_conversions(product.unit_conversions or [])
    return {
        "product_form": {
            "name": source.get("name", product.name or ""),
            "barcode": source.get("barcode", product.barcode or ""),
            "brand": source.get("brand", product.brand or ""),
            "description": source.get("description", product.description or ""),
            "dimension": source.get("dimension", product.dimension or ""),
            "weight": source.get("weight", product.weight or ""),
            "alias_name": source.get("alias_name", product.alias_name or ""),
            "color": source.get("color", product.color or ""),
            "default_unit": source.get("default_unit", product.default_unit or ""),
            "unit_options": unit_options,
            "unit_conversions": conversions,
            "notes": source.get("notes", product.notes or ""),
            "derived_name": source.get(
                "derived_name",
                _build_product_name(
                    brand=source.get("brand", product.brand or ""),
                    description=source.get("description", product.description or ""),
                    dimension=source.get("dimension", product.dimension or ""),
                    weight=source.get("weight", product.weight or ""),
                    color=source.get("color", product.color or ""),
                ),
            ),
        }
    }


def _apply_product_form(product: Product, *, allow_unit_changes: bool) -> None:
    barcode = (request.form.get("barcode") or "").strip() or None
    brand = (request.form.get("brand") or "").strip() or None
    description = (request.form.get("description") or "").strip() or None
    dimension = (request.form.get("dimension") or "").strip() or None
    weight = (request.form.get("weight") or "").strip() or None
    color = (request.form.get("color") or "").strip() or None
    derived_name = _build_product_name(
        brand=brand,
        description=description,
        dimension=dimension,
        weight=weight,
        color=color,
    )
    if not derived_name:
        raise ValueError("Brand, description, dimension, weight, or color is required to build the product name.")

    existing_named = Product.query.filter(Product.name == derived_name, Product.deleted_at.is_(None))
    if getattr(product, "id", None):
        existing_named = existing_named.filter(Product.id != product.id)
    duplicate_named = existing_named.first()
    if duplicate_named:
        if barcode:
            derived_name = f"{derived_name} [{barcode}]"
        else:
            raise ValueError("A product with the same derived name already exists. Add more identifying details or a barcode.")

    if barcode:
        existing_barcode = Product.query.filter(Product.barcode == barcode, Product.deleted_at.is_(None))
        if getattr(product, "id", None):
            existing_barcode = existing_barcode.filter(Product.id != product.id)
        if existing_barcode.first():
            raise ValueError("Barcode already exists on another product.")

    product.name = derived_name
    product.barcode = barcode
    product.brand = brand
    product.description = description
    product.dimension = (request.form.get("dimension") or "").strip() or None
    product.weight = (request.form.get("weight") or "").strip() or None
    product.alias_name = (request.form.get("alias_name") or "").strip() or None
    product.color = color
    product.notes = (request.form.get("notes") or "").strip() or None

    if allow_unit_changes:
        unit_options = _parse_unit_options(request.form.get("unit_options"))
        default_unit = (request.form.get("default_unit") or "").strip() or None
        if not default_unit and unit_options:
            default_unit = unit_options[0]
        elif default_unit and default_unit not in unit_options:
            unit_options = [default_unit, *unit_options]
        product.default_unit = default_unit
        product.unit_options = unit_options
    else:
        unit_options = product.unit_options or ([] if not product.default_unit else [product.default_unit])

    product.unit_conversions = _parse_unit_conversions(request.form.get("unit_conversions"), unit_options)

    tags = Tag.query.filter(Tag.deleted_at.is_(None)).order_by(Tag.name.asc()).all()
    selected_tag_ids = {int(value) for value in request.form.getlist("tag_ids") if value.isdigit()}
    product.tags = [tag for tag in tags if tag.id in selected_tag_ids]


def _apply_bill_master_form(bill: Bill) -> None:
    document_type_id_raw = (request.form.get("document_type_id") or "").strip()
    if not document_type_id_raw.isdigit():
        raise ValueError("Document type is required.")

    document_type = db.session.get(DocumentType, int(document_type_id_raw))
    if not document_type or document_type.deleted_at is not None:
        raise ValueError("Document type was not found.")

    supplier_name = (request.form.get("supplier_name") or "").strip()
    if not supplier_name:
        raise ValueError("Supplier is required.")

    supplier_id_raw = (request.form.get("supplier_id") or "").strip()
    supplier = None
    if supplier_id_raw.isdigit():
        supplier = db.session.get(Supplier, int(supplier_id_raw))
        if supplier and supplier.deleted_at is not None:
            supplier = None
        if supplier and supplier.name.strip().casefold() != supplier_name.casefold():
            supplier = None
    if supplier is None:
        supplier = (
            Supplier.query.filter(
                Supplier.deleted_at.is_(None),
                func.lower(Supplier.name) == supplier_name.casefold(),
            )
            .order_by(Supplier.id.asc())
            .first()
        )
    if supplier is None:
        supplier = Supplier(name=supplier_name)
        db.session.add(supplier)
        db.session.flush()

    bill.document_type = document_type
    bill.supplier = supplier
    bill.bill_date = _parse_bill_date(request.form.get("bill_date"))
    bill.bill_number = (request.form.get("bill_number") or "").strip() or None
    bill.notes = (request.form.get("notes") or "").strip() or None
    bill.status = "draft"
    bill.encoded_total_amount = _to_decimal(request.form.get("encoded_total_amount")) if (request.form.get("encoded_total_amount") or "").strip() else None
    if bill.encoded_total_amount is None or bill.encoded_total_amount <= 0:
        raise ValueError("Total amount must be greater than zero.")
    bill.subtotal_discount_amount = _to_decimal(request.form.get("subtotal_discount_amount"))
    bill.additional_tax_type = (request.form.get("additional_tax_type") or "none").strip()
    if bill.additional_tax_type not in {"none", "percent", "amount"}:
        bill.additional_tax_type = "none"
    bill.additional_tax_value = _to_decimal(request.form.get("additional_tax_value"))
    bill.encoded_by_user_id = int(current_user.id) if getattr(current_user, "id", None) is not None else None


def _apply_bill_details_form(bill: Bill) -> None:
    lines_raw = request.form.get("lines_json") or "[]"
    try:
        line_payloads = json.loads(lines_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Line items could not be parsed.") from exc

    if not isinstance(line_payloads, list) or not line_payloads:
        raise ValueError("At least one bill line is required.")

    bill.line_items.clear()
    allowed_company_ids = {company.id for company in CompanyCache.query.filter(CompanyCache.id.in_(current_user.effective_company_ids())).all()}
    allowed_branch_ids = {branch.id for branch in BranchCache.query.filter(BranchCache.id.in_(current_user.effective_branch_ids())).all()}

    for index, payload in enumerate(line_payloads):
        quantity = _to_decimal(payload.get("quantity"), default="0")
        unit_price = _to_decimal(payload.get("unit_price"))
        line_discount_amount = _to_decimal(payload.get("line_discount_amount"))
        description = (payload.get("description") or "").strip()
        product_id = payload.get("product_id")

        if quantity <= 0:
            raise ValueError(f"Line {index + 1}: quantity must be greater than zero.")
        if not description:
            raise ValueError(f"Line {index + 1}: description is required.")

        line = BillLineItem(
            sort_order=index,
            description=description,
            quantity=quantity,
            unit=(payload.get("unit") or "").strip() or None,
            unit_price=unit_price,
            line_discount_amount=line_discount_amount,
        )
        if product_id not in (None, "", "null"):
            try:
                parsed_product_id = int(product_id)
            except (TypeError, ValueError):
                parsed_product_id = None
            if parsed_product_id:
                line.product_id = parsed_product_id
        bill.line_items.append(line)

        allocated_qty = Decimal("0")
        for allocation_index, allocation_payload in enumerate(payload.get("allocations") or []):
            target_type = (allocation_payload.get("target_type") or "").strip()
            target_id_raw = allocation_payload.get("target_id")
            allocation_qty = _to_decimal(allocation_payload.get("quantity"), default="0")
            notes = (allocation_payload.get("notes") or "").strip() or None

            if target_type not in {"company", "branch"}:
                raise ValueError(f"Line {index + 1}: allocation {allocation_index + 1} target type is invalid.")
            try:
                target_id = int(target_id_raw)
            except (TypeError, ValueError):
                raise ValueError(f"Line {index + 1}: allocation {allocation_index + 1} target is required.")

            if allocation_qty <= 0:
                raise ValueError(f"Line {index + 1}: allocation {allocation_index + 1} quantity must be greater than zero.")

            if target_type == "company" and target_id not in allowed_company_ids:
                raise ValueError(f"Line {index + 1}: company allocation is out of scope.")
            if target_type == "branch" and target_id not in allowed_branch_ids:
                raise ValueError(f"Line {index + 1}: branch allocation is out of scope.")

            allocated_qty += allocation_qty
            if allocated_qty > quantity:
                raise ValueError(f"Line {index + 1}: allocated quantity exceeds encoded quantity.")

            line.allocations.append(
                BillLineAllocation(
                    sort_order=allocation_index,
                    target_type=target_type,
                    target_id=target_id,
                    quantity=allocation_qty,
                    notes=notes,
                )
            )


@bp.get("/bills")
@login_required
def bill_list():
    bills = (
        Bill.query.filter(Bill.deleted_at.is_(None))
        .order_by(Bill.bill_date.desc(), Bill.id.desc())
        .all()
    )
    return render_template("billing/bill_list.html", bills=bills)


@bp.route("/bills/new", methods=["GET", "POST"])
@login_required
@permission_required("encode_view")
def bill_create():
    bill = Bill(bill_date=date.today(), additional_tax_type="none", status="draft")
    supplier_name = (request.form.get("supplier_name") or "").strip()
    if request.method == "POST":
        try:
            _apply_bill_master_form(bill)
            db.session.add(bill)
            db.session.commit()
            flash("Bill master created. Add the line details next.", "success")
            return redirect(url_for("billing.bill_edit", bill_id=bill.id))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "billing/bill_master_form.html",
        bill=bill,
        is_create=True,
        **_bill_master_context(bill=bill, supplier_name=supplier_name),
    )


@bp.route("/bills/<int:bill_id>/edit", methods=["GET", "POST"])
@login_required
def bill_edit(bill_id: int):
    bill = Bill.query.filter(Bill.id == bill_id, Bill.deleted_at.is_(None)).first_or_404()
    if not _can_edit_bill(bill):
        abort(403)
    if request.method == "POST":
        try:
            if (bill.status or "").strip().lower() == "draft":
                _apply_bill_master_form(bill)
            _apply_bill_details_form(bill)
            db.session.commit()
            flash("Bill details updated.", "success")
            return redirect(url_for("billing.bill_view", bill_id=bill.id))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("billing/bill_form.html", bill=bill, is_create=False, **_bill_form_context(bill=bill))


@bp.get("/bills/<int:bill_id>")
@login_required
def bill_view(bill_id: int):
    bill = Bill.query.filter(Bill.id == bill_id, Bill.deleted_at.is_(None)).first_or_404()
    companies, branches = _scope_options()
    company_map = {item.id: item for item in companies}
    branch_map = {item.id: item for item in branches}
    return render_template("billing/bill_view.html", bill=bill, company_map=company_map, branch_map=branch_map)


@bp.route("/suppliers", methods=["GET", "POST"])
@login_required
def supplier_list():
    if request.method == "POST":
        try:
            name = (request.form.get("name") or "").strip()
            if not name:
                raise ValueError("Supplier name is required.")
            supplier = Supplier(
                name=name,
                tin=(request.form.get("tin") or "").strip() or None,
                address=(request.form.get("address") or "").strip() or None,
            )
            db.session.add(supplier)
            db.session.commit()
            flash("Supplier saved.", "success")
            return redirect(url_for("billing.supplier_list"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    suppliers = Supplier.query.filter(Supplier.deleted_at.is_(None)).order_by(Supplier.name.asc()).all()
    return render_template("billing/suppliers.html", suppliers=suppliers)


@bp.post("/suppliers/<int:supplier_id>/edit")
@login_required
def supplier_edit(supplier_id: int):
    supplier = Supplier.query.filter(Supplier.id == supplier_id, Supplier.deleted_at.is_(None)).first_or_404()
    try:
        name = (request.form.get("name") or "").strip()
        if not name:
            raise ValueError("Supplier name is required.")
        supplier.name = name
        supplier.tin = (request.form.get("tin") or "").strip() or None
        supplier.address = (request.form.get("address") or "").strip() or None
        db.session.commit()
        flash("Supplier updated.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("billing.supplier_list"))


@bp.route("/document-types", methods=["GET", "POST"])
@login_required
def document_type_list():
    if request.method == "POST":
        try:
            name = (request.form.get("name") or "").strip()
            code = (request.form.get("code") or "").strip().upper()
            if not name:
                raise ValueError("Document type name is required.")
            if not code:
                raise ValueError("Document type code is required.")
            item = DocumentType(name=name, code=code)
            db.session.add(item)
            db.session.commit()
            flash("Document type saved.", "success")
            return redirect(url_for("billing.document_type_list"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    document_types = DocumentType.query.filter(DocumentType.deleted_at.is_(None)).order_by(DocumentType.name.asc()).all()
    return render_template("billing/document_types.html", document_types=document_types)


@bp.post("/document-types/<int:document_type_id>/edit")
@login_required
def document_type_edit(document_type_id: int):
    item = DocumentType.query.filter(DocumentType.id == document_type_id, DocumentType.deleted_at.is_(None)).first_or_404()
    try:
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip().upper()
        if not name:
            raise ValueError("Document type name is required.")
        if not code:
            raise ValueError("Document type code is required.")
        item.name = name
        item.code = code
        db.session.commit()
        flash("Document type updated.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("billing.document_type_list"))


@bp.route("/tags", methods=["GET", "POST"])
@login_required
def tag_list():
    if request.method == "POST":
        try:
            name = (request.form.get("name") or "").strip()
            if not name:
                raise ValueError("Tag name is required.")
            tag = Tag(
                name=name,
                description=(request.form.get("description") or "").strip() or None,
            )
            db.session.add(tag)
            db.session.commit()
            flash("Tag saved.", "success")
            return redirect(url_for("billing.tag_list"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    tags = Tag.query.filter(Tag.deleted_at.is_(None)).order_by(Tag.name.asc()).all()
    return render_template("billing/tags.html", tags=tags)


@bp.post("/tags/<int:tag_id>/edit")
@login_required
def tag_edit(tag_id: int):
    tag = Tag.query.filter(Tag.id == tag_id, Tag.deleted_at.is_(None)).first_or_404()
    try:
        name = (request.form.get("name") or "").strip()
        if not name:
            raise ValueError("Tag name is required.")
        tag.name = name
        tag.description = (request.form.get("description") or "").strip() or None
        db.session.commit()
        flash("Tag updated.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("billing.tag_list"))


@bp.route("/products", methods=["GET", "POST"])
@login_required
def product_list():
    tags = Tag.query.filter(Tag.deleted_at.is_(None)).order_by(Tag.name.asc()).all()
    if request.method == "POST":
        try:
            product = Product()
            _apply_product_form(product, allow_unit_changes=True)
            db.session.add(product)
            db.session.commit()
            flash("Product saved.", "success")
            return redirect(url_for("billing.product_list"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    products = Product.query.filter(Product.deleted_at.is_(None)).order_by(Product.name.asc()).all()
    return render_template("billing/products.html", products=products, tags=tags, **_product_form_context())


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def product_edit(product_id: int):
    product = Product.query.filter(Product.id == product_id, Product.deleted_at.is_(None)).first_or_404()
    tags = Tag.query.filter(Tag.deleted_at.is_(None)).order_by(Tag.name.asc()).all()
    if request.method == "POST":
        try:
            _apply_product_form(product, allow_unit_changes=False)
            db.session.commit()
            flash("Product updated. Units remain locked; only details and conversions were changed.", "success")
            return redirect(url_for("billing.product_list"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template(
                "billing/product_edit.html",
                product=product,
                tags=tags,
                selected_tag_ids={tag.id for tag in product.tags},
                **_product_form_context(product=product, form_data=request.form),
            )
    return render_template(
        "billing/product_edit.html",
        product=product,
        tags=tags,
        selected_tag_ids={tag.id for tag in product.tags},
        **_product_form_context(product=product),
    )
