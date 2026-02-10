from flask import Blueprint, render_template

bp = Blueprint("web", __name__)

@bp.get("/")
def dashboard():
    return render_template("dashboard/index.html")
