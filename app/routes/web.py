from flask import Blueprint, render_template

bp = Blueprint("web", __name__)

@bp.get("/")
def dashboard():
    return render_template("dashboard/index.html")


@bp.get("/auth/callback")
def auth_callback():
    return render_template("auth/callback.html")


@bp.get("/bills/encode")
def encode_bills():
    return render_template(
        "workspace/placeholder.html",
        page_title="Encode Bills",
        eyebrow="Capture workflow",
        description=(
            "Receive receipts and bills, encode line items, and prepare each purchase "
            "for allocation across one or more owner companies."
        ),
    )


@bp.get("/companies")
def companies():
    return render_template(
        "workspace/placeholder.html",
        page_title="Companies",
        eyebrow="Ownership registry",
        description=(
            "Register the businesses under an owner profile, maintain company details, "
            "and prepare them for downstream allocation and reporting."
        ),
    )


@bp.get("/suppliers")
def suppliers():
    return render_template(
        "workspace/placeholder.html",
        page_title="Suppliers",
        eyebrow="Vendor registry",
        description=(
            "Maintain supplier records for recurring merchants, billers, and vendors "
            "so encoded purchases can be classified consistently."
        ),
    )


@bp.get("/settings")
def settings():
    return render_template(
        "workspace/placeholder.html",
        page_title="Settings & Configuration",
        eyebrow="Workspace setup",
        description=(
            "Manage the shared master data behind BillAware, including companies, "
            "suppliers, and the item masterlist used during encoding and allocation."
        ),
    )


@bp.get("/tags")
def tags():
    return render_template(
        "workspace/placeholder.html",
        page_title="Tag Management",
        eyebrow="Classification system",
        description=(
            "Create reusable tags that can be attached to many different items so "
            "purchases can be grouped, filtered, and reported across suppliers and companies."
        ),
    )
