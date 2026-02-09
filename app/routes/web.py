from flask import Blueprint

bp = Blueprint("web", __name__)

@bp.get("/")
def home():
    return """
    <h1>BillAware</h1>
    <p>Status: online</p>
    <p>Try <code>/health</code> and <code>/api/me</code> (requires JWT).</p>
    """
