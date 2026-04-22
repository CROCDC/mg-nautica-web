from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.admin.decorators import admin_required
from app.factory import db
from app.models import User, UserRole


@admin_bp.route("/users")
@login_required
@admin_required
def users_list() -> str:
    users = db.session.query(User).order_by(User.created_at.asc()).all()
    return render_template("admin/users_list.html", users=users, roles=list(UserRole))


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def users_new() -> Any:
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        name = request.form.get("name") or None
        role_raw = request.form.get("role")
        try:
            role = UserRole(role_raw) if role_raw else UserRole.EDITOR
        except ValueError:
            role = UserRole.EDITOR
        if not email or len(password) < 8:
            flash("Email y contraseña (mínimo 8 caracteres) son obligatorios.", "error")
            return render_template(
                "admin/users_form.html", user=None, form=request.form, roles=list(UserRole)
            ), 400
        if db.session.query(User).filter_by(email=email).first():
            flash("Ya existe un usuario con ese email.", "error")
            return render_template(
                "admin/users_form.html", user=None, form=request.form, roles=list(UserRole)
            ), 400
        user = User(email=email, name=name, role=role, active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Usuario creado.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template(
        "admin/users_form.html", user=None, form={}, roles=list(UserRole)
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def users_edit(user_id: int) -> Any:
    user = db.session.get(User, user_id)
    if user is None:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("admin.users_list"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        name = request.form.get("name") or None
        role_raw = request.form.get("role")
        try:
            role = UserRole(role_raw) if role_raw else user.role
        except ValueError:
            role = user.role
        active = request.form.get("active") == "on"
        new_password = request.form.get("password") or ""
        if not email:
            flash("Email es obligatorio.", "error")
            return render_template(
                "admin/users_form.html", user=user, form=request.form, roles=list(UserRole)
            ), 400
        dup = db.session.query(User).filter(User.email == email, User.id != user.id).first()
        if dup:
            flash("Otro usuario ya usa ese email.", "error")
            return render_template(
                "admin/users_form.html", user=user, form=request.form, roles=list(UserRole)
            ), 400
        user.email = email
        user.name = name
        user.role = role
        # Prevent self-demote or self-deactivate of the last admin.
        if user.id == current_user.id and (not active or role != UserRole.ADMIN):
            admins_left = (
                db.session.query(User)
                .filter(User.role == UserRole.ADMIN, User.active.is_(True), User.id != user.id)
                .count()
            )
            if admins_left == 0:
                flash("No podés quitarte el rol o desactivarte siendo el único admin activo.", "error")
                return render_template(
                    "admin/users_form.html", user=user, form=request.form, roles=list(UserRole)
                ), 400
        user.active = active
        if new_password:
            if len(new_password) < 8:
                flash("La nueva contraseña debe tener al menos 8 caracteres.", "error")
                return render_template(
                    "admin/users_form.html", user=user, form=request.form, roles=list(UserRole)
                ), 400
            user.set_password(new_password)
        db.session.commit()
        flash("Usuario actualizado.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template(
        "admin/users_form.html", user=user, form={}, roles=list(UserRole)
    )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def users_delete(user_id: int) -> Any:
    user = db.session.get(User, user_id)
    if user is None:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("admin.users_list"))
    if user.id == current_user.id:
        flash("No podés borrar tu propio usuario.", "error")
        return redirect(url_for("admin.users_list"))
    if user.role == UserRole.ADMIN:
        admins_left = (
            db.session.query(User)
            .filter(User.role == UserRole.ADMIN, User.active.is_(True), User.id != user.id)
            .count()
        )
        if admins_left == 0:
            flash("No podés borrar al único admin activo.", "error")
            return redirect(url_for("admin.users_list"))
    db.session.delete(user)
    db.session.commit()
    flash("Usuario eliminado.", "success")
    return redirect(url_for("admin.users_list"))
