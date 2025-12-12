"""Settings API endpoints."""

from flask import Blueprint, request, jsonify

from database.repositories.settings_repository import SettingsRepository

settings_bp = Blueprint("settings", __name__)
settings_repo = SettingsRepository()


@settings_bp.route("", methods=["GET"])
def get_all_settings():
    """Get all application settings."""
    settings = settings_repo.get_all()
    return jsonify({"settings": settings})


@settings_bp.route("", methods=["PUT"])
def update_settings():
    """Update multiple settings at once."""
    data = request.get_json()

    for key, value in data.items():
        settings_repo.set(key, value)

    return jsonify({"settings": settings_repo.get_all()})


@settings_bp.route("/<key>", methods=["GET"])
def get_setting(key: str):
    """Get a specific setting."""
    value = settings_repo.get(key)
    if value is None:
        return jsonify({"error": "Setting not found"}), 404
    return jsonify({"key": key, "value": value})


@settings_bp.route("/<key>", methods=["PUT"])
def update_setting(key: str):
    """Update a specific setting."""
    data = request.get_json()
    value = data.get("value")
    settings_repo.set(key, value)
    return jsonify({"key": key, "value": value})


@settings_bp.route("/defaults", methods=["POST"])
def reset_to_defaults():
    """Reset all settings to defaults."""
    settings_repo.reset_defaults()
    return jsonify({"settings": settings_repo.get_all()})
