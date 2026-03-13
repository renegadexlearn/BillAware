from app.extensions import db


class CommonAuthSyncRun(db.Model):
    __tablename__ = "common_auth_sync_run"

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="running")
    trigger = db.Column(db.String(30), nullable=False, default="manual")
    reason = db.Column(db.String(255), nullable=True)

    requested_by_user_id = db.Column(db.BigInteger, nullable=True, index=True)
    force_full = db.Column(db.Boolean, nullable=False, default=False)

    main_groups_synced = db.Column(db.Integer, nullable=False, default=0)
    companies_synced = db.Column(db.Integer, nullable=False, default=0)
    branches_synced = db.Column(db.Integer, nullable=False, default=0)
    users_synced = db.Column(db.Integer, nullable=False, default=0)
    employees_synced = db.Column(db.Integer, nullable=False, default=0)

    error_code = db.Column(db.String(100), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
