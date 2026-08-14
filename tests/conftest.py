from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def esptool_output() -> Callable[[str], str]:
    """Load a recorded esptool run from tests/fixtures/esptool/."""

    def load(name: str) -> str:
        return (FIXTURE_DIR / "esptool" / name).read_text(encoding="utf-8")

    return load
