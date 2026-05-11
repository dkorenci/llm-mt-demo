"""URL routing for the translator app."""
from __future__ import annotations

from django.urls import path

from . import views

app_name = "translator"

urlpatterns = [
    path("", views.index, name="index"),
]
