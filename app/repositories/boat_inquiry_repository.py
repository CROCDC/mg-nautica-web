from typing import Optional

from app.factory import db
from app.models import BoatInquiry, InquiryChannel


class BoatInquiryRepository:
    @staticmethod
    def create(
        boat_id: int,
        name: str,
        email: str,
        phone: Optional[str],
        message: Optional[str],
        channel: InquiryChannel = InquiryChannel.FORM,
    ) -> BoatInquiry:
        inquiry = BoatInquiry(
            boat_id=boat_id,
            name=name.strip(),
            email=email.strip().lower(),
            phone=phone.strip() if phone else None,
            message=message.strip() if message else None,
            channel=channel,
        )
        try:
            db.session.add(inquiry)
            db.session.commit()
            return inquiry
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def list_for_boat(boat_id: int) -> list[BoatInquiry]:
        return (
            db.session.query(BoatInquiry)
            .filter(BoatInquiry.boat_id == boat_id)
            .order_by(BoatInquiry.created_at.desc())
            .all()
        )
