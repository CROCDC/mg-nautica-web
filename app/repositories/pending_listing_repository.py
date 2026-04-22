import os
import uuid
from datetime import datetime
from typing import Optional

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.factory import db
from app.models import ModerationStatus, PendingListing, ProductCondition

ALLOWED_EXTENSIONS: set[str] = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "heic",
    "pdf",
}


class PendingListingRepository:
    @staticmethod
    def _is_allowed(filename: str) -> bool:
        if "." not in filename:
            return False
        ext = filename.rsplit(".", 1)[1].lower()
        return ext in ALLOWED_EXTENSIONS

    @staticmethod
    def _save_files(files: list[FileStorage]) -> list[str]:
        upload_folder: str = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_folder, exist_ok=True)
        saved_urls: list[str] = []
        for file in files:
            if not file or not file.filename:
                continue
            if not PendingListingRepository._is_allowed(file.filename):
                continue
            base = secure_filename(file.filename)
            unique = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}_{base}"
            path = os.path.join(upload_folder, unique)
            file.save(path)
            saved_urls.append(f"/uploads/{unique}")
        return saved_urls

    @staticmethod
    def create(
        first_name: str,
        last_name: str,
        email: str,
        phone: Optional[str],
        condition: ProductCondition,
        description: str,
        asked_price_usd: Optional[int],
        files: Optional[list[FileStorage]] = None,
    ) -> PendingListing:
        file_urls: list[str] = (
            PendingListingRepository._save_files(files) if files else []
        )

        listing = PendingListing(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email.strip().lower(),
            phone=phone.strip() if phone else None,
            condition=condition,
            description=description.strip(),
            asked_price_usd=asked_price_usd,
            file_urls=file_urls,
            moderation_status=ModerationStatus.PENDING,
        )
        try:
            db.session.add(listing)
            db.session.commit()
            return listing
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def list_pending() -> list[PendingListing]:
        return (
            db.session.query(PendingListing)
            .filter(PendingListing.moderation_status == ModerationStatus.PENDING)
            .order_by(PendingListing.created_at.desc())
            .all()
        )
