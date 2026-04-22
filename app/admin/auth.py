from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app.admin import admin_bp
from app.factory import db
from app.models import User


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = db.session.query(User).filter_by(email=email).one_or_none()
        if user is None or not user.check_password(password) or not user.active:
            flash("Credenciales inválidas.", "error")
            return render_template("admin/login.html"), 401
        login_user(user)
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        next_url = request.args.get("next") or url_for("admin.dashboard")
        return redirect(next_url)
    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("admin.login"))
