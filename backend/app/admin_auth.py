"""Session-based administrator authentication and authorization."""

from functools import wraps

from flask import jsonify, session


def admin_required(view):
    """Require an authenticated administrator for an API endpoint."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"status": "error", "message": "Authentication required."}), 401
        if session.get("role") != "ADMIN":
            return jsonify({"status": "error", "message": "Administrator access required."}), 403
        return view(*args, **kwargs)

    return wrapped
