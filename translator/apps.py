"""Django app configuration for the translator UI."""
from __future__ import annotations

from django.apps import AppConfig


class TranslatorConfig(AppConfig):
    """Registers the translator app with Django."""

    name = "translator"
    default_auto_field = "django.db.models.BigAutoField"
