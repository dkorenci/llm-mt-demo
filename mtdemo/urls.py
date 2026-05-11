"""Project-level URL configuration.

All application routes are delegated to the ``translator`` app, which owns
the single page that makes up the demo.
"""
from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("", include("translator.urls")),
]
