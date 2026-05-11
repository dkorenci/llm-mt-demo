"""ASGI entrypoint for the LLM MT demo (reserved for future async use)."""
from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mtdemo.settings")
application = get_asgi_application()
