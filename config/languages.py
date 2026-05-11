"""Language catalogue for the source/target selectors.

Curated list of roughly fifty languages covering the European Union plus
the major world languages.  English and Croatian are pinned at the top
because they are the most common source/target pair in this demo's
intended use.

Add or remove entries here to change what appears in the UI selectors;
no other code needs to be touched.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    """A single selectable language.

    Attributes:
        code: ISO 639-1 two-letter code (lower-case) used as the
            programmatic identifier and persisted in form submissions.
        name: Human-readable English display name.
    """

    code: str
    name: str

    @property
    def label(self) -> str:
        """Display label of the form ``"Name (CODE)"`` (CODE upper-cased)."""
        return f"{self.name} ({self.code.upper()})"


# Languages that should always appear at the top of the dropdowns.
PINNED: list[Language] = [
    Language("en", "English"),
    Language("hr", "Croatian"),
]

# Remaining languages, kept alphabetical by ISO code for stable ordering.
OTHERS: list[Language] = [
    Language("ar", "Arabic"),
    Language("bg", "Bulgarian"),
    Language("bn", "Bengali"),
    Language("bs", "Bosnian"),
    Language("ca", "Catalan"),
    Language("cs", "Czech"),
    Language("da", "Danish"),
    Language("de", "German"),
    Language("el", "Greek"),
    Language("es", "Spanish"),
    Language("et", "Estonian"),
    Language("fa", "Persian"),
    Language("fi", "Finnish"),
    Language("fr", "French"),
    Language("ga", "Irish"),
    Language("he", "Hebrew"),
    Language("hi", "Hindi"),
    Language("hu", "Hungarian"),
    Language("hy", "Armenian"),
    Language("id", "Indonesian"),
    Language("is", "Icelandic"),
    Language("it", "Italian"),
    Language("ja", "Japanese"),
    Language("ko", "Korean"),
    Language("lt", "Lithuanian"),
    Language("lv", "Latvian"),
    Language("mk", "Macedonian"),
    Language("ms", "Malay"),
    Language("mt", "Maltese"),
    Language("nl", "Dutch"),
    Language("no", "Norwegian"),
    Language("pa", "Punjabi"),
    Language("pl", "Polish"),
    Language("pt", "Portuguese"),
    Language("ro", "Romanian"),
    Language("ru", "Russian"),
    Language("sk", "Slovak"),
    Language("sl", "Slovenian"),
    Language("sq", "Albanian"),
    Language("sr", "Serbian"),
    Language("sv", "Swedish"),
    Language("sw", "Swahili"),
    Language("ta", "Tamil"),
    Language("th", "Thai"),
    Language("tr", "Turkish"),
    Language("uk", "Ukrainian"),
    Language("ur", "Urdu"),
    Language("vi", "Vietnamese"),
    Language("zh", "Chinese"),
]

# Single ordered catalogue consumed by the rest of the app.
ALL: list[Language] = PINNED + OTHERS

# Quick membership / lookup helpers --------------------------------------------------

_BY_CODE: dict[str, Language] = {lang.code: lang for lang in ALL}


def choices() -> list[tuple[str, str]]:
    """Return Django-style ``[(value, label), ...]`` choices for the selectors."""
    return [(lang.code, lang.label) for lang in ALL]


def is_valid(code: str) -> bool:
    """Return ``True`` if ``code`` denotes one of the configured languages."""
    return code in _BY_CODE


def by_code(code: str) -> Language:
    """Look up a :class:`Language` by its ISO code (raises ``KeyError`` if absent)."""
    return _BY_CODE[code]


# Defaults exposed for the form/view layer.
DEFAULT_SOURCE: str = "en"
DEFAULT_TARGET: str = "hr"
