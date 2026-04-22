import uuid
from typing import Optional

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from app.models import (
    AccessoryCategory,
    BoatType,
    Flag,
    InquiryChannel,
    ProductCondition,
)
from app.repositories.accessory_repository import AccessoryRepository
from app.repositories.boat_inquiry_repository import BoatInquiryRepository
from app.repositories.boat_repository import BoatRepository
from app.repositories.favorite_repository import FavoriteRepository
from app.repositories.pending_listing_repository import PendingListingRepository
from app.repositories.sale_inquiry_repository import SaleInquiryRepository


def _get_session_id() -> str:
    sid: Optional[str] = session.get("sid")
    if not sid:
        sid = uuid.uuid4().hex
        session["sid"] = sid
    return sid


def _parse_enum(enum_cls: type, value: Optional[str]):
    if not value:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def register_routes(app: Flask) -> None:
    # ---------------------------------------------------------------- Home
    @app.route("/")
    def home() -> str:
        recent = BoatRepository.list_available(limit=6, sort="recent")
        total_available = BoatRepository.count_available()
        return render_template(
            "home.html",
            featured_boats=recent,
            total_available=total_available,
        )

    # ---------------------------------------------------------------- Boats
    @app.route("/boats")
    def boats_list() -> str:
        boat_type = _parse_enum(BoatType, request.args.get("type"))
        flag = _parse_enum(Flag, request.args.get("flag"))
        min_price = _parse_int(request.args.get("min_price"))
        max_price = _parse_int(request.args.get("max_price"))
        min_length = _parse_float(request.args.get("min_length"))
        max_length = _parse_float(request.args.get("max_length"))
        min_year = _parse_int(request.args.get("min_year"))
        max_year = _parse_int(request.args.get("max_year"))
        search = request.args.get("q") or None
        sort = request.args.get("sort", "recent")

        boats = BoatRepository.list_available(
            boat_type=boat_type,
            flag=flag,
            min_price_usd=min_price,
            max_price_usd=max_price,
            min_length_m=min_length,
            max_length_m=max_length,
            min_year=min_year,
            max_year=max_year,
            search=search,
            sort=sort,
        )
        return render_template(
            "boats/list.html",
            boats=boats,
            boat_types=list(BoatType),
            flags=list(Flag),
            selected_type=boat_type,
            selected_flag=flag,
            search=search,
            sort=sort,
        )

    @app.route("/boats/<slug>")
    def boat_detail(slug: str) -> tuple[str, int] | str:
        boat = BoatRepository.get_by_slug(slug)
        if boat is None:
            return render_template("404.html"), 404
        is_favorite = (
            FavoriteRepository.get(boat.id, _get_session_id()) is not None
        )
        return render_template(
            "boats/detail.html",
            boat=boat,
            is_favorite=is_favorite,
        )

    @app.route("/boats/<slug>/inquire", methods=["POST"])
    def boat_inquire(slug: str) -> Response | tuple[Response, int]:
        boat = BoatRepository.get_by_slug(slug)
        if boat is None:
            return jsonify({"error": "Boat not found"}), 404

        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = request.form.get("phone")
        message = request.form.get("message")

        if not name or not email:
            return jsonify({"error": "Name and email are required"}), 400

        BoatInquiryRepository.create(
            boat_id=boat.id,
            name=name,
            email=email,
            phone=phone,
            message=message,
            channel=InquiryChannel.FORM,
        )
        return redirect(url_for("boat_detail", slug=slug) + "?inquiry=ok")

    # ---------------------------------------------------------------- Favorites
    @app.route("/favorites")
    def favorites_list() -> str:
        sid = _get_session_id()
        favorites = FavoriteRepository.list_for_session(sid)
        return render_template("favorites.html", favorites=favorites)

    @app.route("/favorites/<slug>/toggle", methods=["POST"])
    def favorite_toggle(slug: str) -> Response | tuple[Response, int]:
        boat = BoatRepository.get_by_slug(slug)
        if boat is None:
            return jsonify({"error": "Boat not found"}), 404
        sid = _get_session_id()
        # boat.id == listed_object.id (joined table inheritance shares the PK)
        existing = FavoriteRepository.get(boat.id, sid)
        if existing:
            FavoriteRepository.remove(boat.id, sid)
            return jsonify({"favorite": False})
        FavoriteRepository.add(boat.id, sid)
        return jsonify({"favorite": True})

    # ---------------------------------------------------------------- Accessories
    @app.route("/accessories")
    def accessories_list() -> str:
        category = _parse_enum(AccessoryCategory, request.args.get("category"))
        accessories = AccessoryRepository.list_active(category=category)
        return render_template(
            "accessories/list.html",
            accessories=accessories,
            categories=list(AccessoryCategory),
            selected_category=category,
        )

    @app.route("/accessories/<slug>")
    def accessory_detail(slug: str) -> tuple[str, int] | str:
        accessory = AccessoryRepository.get_by_slug(slug)
        if accessory is None:
            return render_template("404.html"), 404
        return render_template("accessories/detail.html", accessory=accessory)

    # ---------------------------------------------------------------- Static pages
    @app.route("/about")
    def about() -> str:
        return render_template("about.html")

    @app.route("/services")
    def services() -> str:
        return render_template("services.html")

    @app.route("/contact")
    def contact() -> str:
        return render_template("contact.html")

    # ---------------------------------------------------------------- Sell your boat
    @app.route("/sell-your-boat", methods=["GET", "POST"])
    def sell_your_boat() -> str | Response:
        if request.method == "POST":
            first_name = (request.form.get("first_name") or "").strip()
            last_name = (request.form.get("last_name") or "").strip()
            email = (request.form.get("email") or "").strip()
            phone = request.form.get("phone")
            boat_type = _parse_enum(BoatType, request.form.get("boat_type"))
            message = request.form.get("message")

            if not first_name or not last_name or not email or boat_type is None:
                return render_template(
                    "sell_your_boat.html",
                    boat_types=list(BoatType),
                    error="Please fill in all required fields.",
                ), 400

            SaleInquiryRepository.create(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                boat_type=boat_type,
                message=message,
            )
            return redirect(url_for("sell_your_boat") + "?submitted=1")

        return render_template(
            "sell_your_boat.html",
            boat_types=list(BoatType),
            error=None,
        )

    # ---------------------------------------------------------------- Publish free
    @app.route("/publish", methods=["GET", "POST"])
    def publish() -> str | Response:
        if request.method == "POST":
            first_name = (request.form.get("first_name") or "").strip()
            last_name = (request.form.get("last_name") or "").strip()
            email = (request.form.get("email") or "").strip()
            phone = request.form.get("phone")
            condition = _parse_enum(
                ProductCondition, request.form.get("condition")
            )
            description = (request.form.get("description") or "").strip()
            asked_price = _parse_int(request.form.get("asked_price_usd"))
            files = request.files.getlist("files")

            if (
                not first_name
                or not last_name
                or not email
                or condition is None
                or not description
            ):
                return render_template(
                    "publish.html",
                    conditions=list(ProductCondition),
                    error="Please fill in all required fields.",
                ), 400

            PendingListingRepository.create(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                condition=condition,
                description=description,
                asked_price_usd=asked_price,
                files=files,
            )
            return redirect(url_for("publish") + "?submitted=1")

        return render_template(
            "publish.html",
            conditions=list(ProductCondition),
            error=None,
        )

    # ---------------------------------------------------------------- System
    @app.route("/health")
    def health() -> tuple[Response, int]:
        return jsonify({"status": "ok"}), 200

    @app.route("/robots.txt")
    def robots() -> Response:
        return send_from_directory(app.static_folder, "robots.txt")

    @app.route("/uploads/<path:filename>")
    def uploads(filename: str) -> Response:
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.errorhandler(404)
    def not_found(error) -> tuple[str, int]:  # noqa: ANN001
        return render_template("404.html"), 404
