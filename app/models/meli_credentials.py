from datetime import datetime, timezone

from app.factory import db


class MeliCredentials(db.Model):
    """OAuth tokens for a single Mercado Libre site (MLU or MLA)."""

    __tablename__ = "meli_credentials"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.String(10), unique=True, nullable=False, index=True)

    meli_user_id = db.Column(db.String(50), nullable=True)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return now >= expires_at

    def __repr__(self) -> str:
        return f"<MeliCredentials site={self.site_id} user={self.meli_user_id}>"
