import re
import unicodedata


def normalize_component(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("identifier component is empty")
    return normalized


def normalize_unique_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]", "", value).lower()
    if len(normalized) < 6:
        raise ValueError("unique ID is too short")
    return normalized
