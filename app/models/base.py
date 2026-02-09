# app/models/base.py

from datetime import datetime
from ..extensions import db

class BaseModel(db.Model):
    __abstract__ = True  # SQLAlchemy will NOT create a table for this class

    id = db.Column(db.BigInteger, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # ----------------------------
    # Soft delete helpers
    # ----------------------------
    def soft_delete(self, commit=True):
        """Soft delete the record."""
        self.deleted_at = datetime.utcnow()
        if commit:
            db.session.commit()

    def restore(self, commit=True):
        """Undo soft delete."""
        self.deleted_at = None
        if commit:
            db.session.commit()

    def really_delete(self, commit=True):
        """Permanently delete from database."""
        db.session.delete(self)
        if commit:
            db.session.commit()

    @property
    def is_deleted(self):
        return self.deleted_at is not None
