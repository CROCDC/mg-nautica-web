from flask import Blueprint, redirect, url_for

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


@admin_bp.errorhandler(403)
def _forbidden(error):  # noqa: ANN001
    from flask import render_template

    return render_template("admin/403.html"), 403


@admin_bp.errorhandler(401)
def _unauthorized(error):  # noqa: ANN001
    return redirect(url_for("admin.login"))


from app.admin import accessories, auth, boats, dashboard, inquiries, listings, users  # noqa: E402,F401
