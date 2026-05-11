"""Django settings for the LLM MT demo project.

Secrets (such as the Hugging Face inference endpoint token) live in the
repository-root ``settings.py`` file. That file is gitignored; a
``settings-template.py`` is committed alongside it as a starting point.
This module imports those values explicitly via :func:`_load_secrets` so
that the Django-side configuration stays readable and the secret module
name does not clash with anything in this package.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Secret loading
# ---------------------------------------------------------------------------

def _load_secrets() -> ModuleType:
    """Load the repo-root ``settings.py`` as an ad-hoc module.

    Doing this by file path avoids any ambiguity with Python's regular
    ``import settings`` (which could resolve to the wrong module depending
    on ``sys.path`` ordering).
    """
    secrets_path = BASE_DIR / "settings.py"
    if not secrets_path.exists():  # graceful first-run fallback
        template = BASE_DIR / "settings-template.py"
        if template.exists():
            secrets_path = template
        else:
            raise FileNotFoundError(
                f"Neither settings.py nor settings-template.py found in {BASE_DIR}"
            )
    spec = importlib.util.spec_from_file_location("mt_secrets", secrets_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_secrets = _load_secrets()

# Hugging Face inference endpoint token (used in Phase 2).
HF_INFERENCE_ENDPOINT_TOKEN: str = getattr(_secrets, "HF_INFERENCE_ENDPOINT_TOKEN", "")


# ---------------------------------------------------------------------------
# Core Django settings
# ---------------------------------------------------------------------------

# Demo-only key; replace with an environment-managed secret for any real deploy.
SECRET_KEY: str = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-insecure-demo-key-do-not-use-in-production",
)

DEBUG: bool = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS: list[str] = ["*"]  # demo only


INSTALLED_APPS: list[str] = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "translator.apps.TranslatorConfig",
]

# Sessions deliberately omitted: per-tab state lives in the form (the DOM),
# not in a session cookie, so that "Clone to Tab" yields truly independent
# tabs.  We also drop CSRF middleware because there are no authenticated
# user sessions; the form-driven flow is the entire app and is safe by
# construction (no cross-origin state-changing requests carry credentials).
MIDDLEWARE: list[str] = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF: str = "mtdemo.urls"

TEMPLATES: list[dict[str, Any]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION: str = "mtdemo.wsgi.application"
ASGI_APPLICATION: str = "mtdemo.asgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# A SQLite database is provisioned for completeness (Django requires one for
# ``migrate`` to succeed against contenttypes/auth), but Phase 1 does not
# define any models of its own.
DATABASES: dict[str, dict[str, Any]] = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE: str = "en-us"
TIME_ZONE: str = "UTC"
USE_I18N: bool = True
USE_TZ: bool = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL: str = "static/"

DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
#
# Off by default.  ``run.sh`` exports ``MT_LOG_FILE`` when invoked with
# ``LOG=1``, pointing at a fresh timestamped file next to the script.
# When present, every Python error logged via ``logging`` (including
# request-handler tracebacks) goes to that file at DEBUG/INFO level; the
# console is left untouched so the dev-server output stays readable.

_LOG_FILE: str = os.environ.get("MT_LOG_FILE", "")

if _LOG_FILE:
    LOGGING: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": (
                    "%(asctime)s %(levelname)-7s %(name)s "
                    "[%(process)d:%(thread)d] %(message)s"
                ),
            },
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "filename": _LOG_FILE,
                "formatter": "verbose",
                "level": "DEBUG",
            },
        },
        "root": {
            "handlers": ["file"],
            "level": "INFO",
        },
        "loggers": {
            # Our own modules: keep DEBUG so logger.exception() shows the
            # full traceback.
            "translator": {"level": "DEBUG", "propagate": True},
            # Django's request handler logs unhandled view exceptions
            # here at ERROR; keep it loud.
            "django.request": {"level": "ERROR", "propagate": True},
        },
    }
