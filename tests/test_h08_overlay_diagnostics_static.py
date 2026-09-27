"""Static regression checks for fault-safe viewport overlay diagnostics."""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_overlay_gpu_failures_are_visible_and_throttled() -> None:
    source = (ROOT / "dan_form" / "ui" / "overlay.py").read_text(encoding="utf-8")
    failure = source.split("    except Exception:", 1)[1]
    assert "_OVERLAY_CACHE.clear()" in failure
    assert "_LOGGER.exception(" in failure
    assert "if not _DRAW_ERROR_REPORTED:" in failure
    assert "_DRAW_ERROR_REPORTED = True" in failure
    assert "_DRAW_ERROR_REPORTED = False" in source
