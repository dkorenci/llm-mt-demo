"""WSGI entrypoint for the LLM MT demo (used by production-style servers)."""
from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mtdemo.settings")
application = get_wsgi_application()
