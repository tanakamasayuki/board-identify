"""Normalisation of the parts that make up a board identifier."""

import re
import unicodedata

MIN_UNIQUE_ID_LENGTH = 6


def normalize_component(value: str) -> str:
    """Fold a name such as ``ESP32-S3`` into a lowercase ASCII component.

    Accents are dropped rather than treated as punctuation, so a board named
    ``Arduino Yún`` folds to ``arduino-yun`` and not to ``arduino-y-n``.

    Raises ValueError when nothing usable remains.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    unaccented = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalized = unaccented.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    if not normalized:
        raise ValueError(f"identifier component is empty: {value!r}")
    return normalized


def normalize_unique_id(value: str) -> str:
    """Strip punctuation from a unique ID such as a MAC address.

    Raises ValueError when too few characters remain to be plausibly unique.
    """
    normalized = re.sub(r"[^a-zA-Z0-9]", "", value).lower()
    if len(normalized) < MIN_UNIQUE_ID_LENGTH:
        raise ValueError(f"unique ID is too short: {value!r}")
    return normalized
