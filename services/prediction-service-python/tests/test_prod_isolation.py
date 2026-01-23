"""Guards to keep production prediction code isolated from backtest assets.

These checks ensure production modules do not reference backtest datasets or
testing packages at runtime. They are intentionally lightweight so they can
run in CI without dependencies beyond the standard library.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"


def _iter_py_files(base: Path) -> list[Path]:
    return [p for p in base.rglob("*.py") if ".venv" not in p.parts]


def test_no_testing_imports_in_prod_code():
    """Production code must not import from the testing package."""

    forbidden = ("import testing", "from testing")
    offenders: list[str] = []

    for path in _iter_py_files(APP_DIR):
        content = path.read_text(encoding="utf-8", errors="ignore")
        if any(tok in content for tok in forbidden):
            offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, f"testing imports found in prod code: {offenders}"


def test_no_backtest_paths_in_prod_code():
    """Production code must not read backtest datasets or manifests."""

    forbidden_paths = (
        "manifests/canonical_training_data_master",
        "backtest_datasets/",
    )

    # Specific files are allowed to mention the legacy alias blob for
    # cross-validation, but nowhere else.
    allowed_files = {
        Path("app/validation_gate.py"),
        Path("app/canonical/team_resolution_service.py"),
    }

    offenders: list[str] = []

    for path in _iter_py_files(APP_DIR):
        rel = path.relative_to(ROOT)
        content = path.read_text(encoding="utf-8", errors="ignore")
        if rel in allowed_files:
            continue
        if any(fp in content for fp in forbidden_paths):
            offenders.append(str(rel))

    assert not offenders, f"Backtest dataset references found in prod code: {offenders}"
