#!/usr/bin/env python
"""Django management entrypoint for the LLM MT demo project."""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mtdemo.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Activate the virtualenv and install requirements."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
