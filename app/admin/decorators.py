from functools import wraps
from typing import Callable

from flask import abort
from flask_login import current_user


def admin_required(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin:
            abort(403)
        return func(*args, **kwargs)

    return wrapper
