#!/usr/bin/env python3
"""Download legacy Kaggle NCAA data for testing experiments.

- Uses the official Kaggle API (competition: March Machine Learning Mania).
- Places extracted CSVs under ``testing/data/kaggle``.
- Never commits the raw data; the folder is ignored by git.

The script is intentionally dependency-light so it can run inside the
existing tooling for this repository.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Iterable

# Optional dependency; only used to load a local .env file if present.
try:  # pragma: no cover - optional helper
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional helper
    load_dotenv = None  # type: ignore

KAGGLE_COMPETITION = "march-machine-learning-mania-2025"
REQUIRED_FILES: tuple[str, ...] = (
    "MRegularSeasonCompactResults.csv",
    "MRegularSeasonDetailedResults.csv",
    "MTeams.csv",
    "MTeamSpellings.csv",
    "MSeasons.csv",
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "testing" / "data" / "kaggle"
TMP_DIR = ROOT_DIR / "testing" / "data" / "tmp_kaggle_download"
ZIP_NAME = f"{KAGGLE_COMPETITION}.zip"


def _print_header() -> None:
    print("=" * 72)
    print(" Kaggle Dataset Downloader (Testing Branch)")
    print("=" * 72)
    print()


def _load_env_file() -> None:
    """Load a .env file when python-dotenv is available."""
    if load_dotenv is not None:
        env_path = ROOT_DIR / ".env"
        if env_path.exists():
            load_dotenv(env_path)


def _ensure_username_key() -> bool:
    """Ensure Kaggle expects either username/key or API token."""
    token = os.getenv("KAGGLE_API_TOKEN")
    username = os.getenv("KAGGLE_USERNAME")
    api_key = os.getenv("KAGGLE_KEY")

    if username and api_key:
        return True

    if token:
        # KaggleApi.authenticate will fall back to env vars when set.
        os.environ.setdefault("KAGGLE_USERNAME", "token")
        os.environ.setdefault("KAGGLE_KEY", token)
        return True

    default_json = Path.home() / ".kaggle" / "kaggle.json"
    if default_json.exists():
        with default_json.open("r", encoding="utf-8") as handle:
            creds = json.load(handle)
        os.environ.setdefault("KAGGLE_USERNAME", creds.get("username", ""))
        os.environ.setdefault("KAGGLE_KEY", creds.get("key", ""))
        return bool(os.environ.get("KAGGLE_USERNAME")) and bool(
            os.environ.get("KAGGLE_KEY")
        )

    return False


def _authenticate():
    try:
        from kaggle import KaggleApi
    except ImportError as exc:  # pragma: no cover - runtime dependency
        print("[ERROR] Missing dependency: kaggle")
        print("        Run 'pip install kaggle' and try again.")
        raise SystemExit(1) from exc

    api = KaggleApi()
    api.authenticate()
    return api


def _download_zip(api, force: bool) -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = TMP_DIR / ZIP_NAME

    if zip_path.exists() and not force:
        print(f"[SKIP] Using cached archive: {zip_path}")
        return zip_path

    print("[INFO] Downloading competition archive...")
    api.competition_download_files(
        KAGGLE_COMPETITION,
        path=TMP_DIR,
        quiet=False,
    )

    if not zip_path.exists():  # pragma: no cover - defensive
        raise SystemExit("Download reported success but archive is missing")

    return zip_path


def _extract_required(zip_path: Path, force: bool) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as archive:
        members = set(archive.namelist())
        missing = [name for name in REQUIRED_FILES if name not in members]
        if missing:
            raise SystemExit(
                "Archive missing expected files: " + ", ".join(missing)
            )

        for member in REQUIRED_FILES:
            target = DATA_DIR / member
            if target.exists() and not force:
                print(f"[SKIP] {member} already exists")
                continue

            print(f"[INFO] Extracting {member} -> {target}")
            with archive.open(member) as src, target.open("wb") as dst:
                dst.write(src.read())


def _verify_required(files: Iterable[str]) -> None:
    missing = [name for name in files if not (DATA_DIR / name).exists()]
    if missing:
        raise SystemExit(
            "Verification failed; missing files: " + ", ".join(missing)
        )


def _cleanup(force: bool) -> None:
    if force and TMP_DIR.exists():
        for entry in TMP_DIR.iterdir():
            if entry.is_file():
                entry.unlink(missing_ok=True)
        try:
            TMP_DIR.rmdir()
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download Kaggle historical data into testing/data/kaggle",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and overwrite existing files",
    )

    args = parser.parse_args(argv)

    _print_header()
    _load_env_file()

    if not _ensure_username_key():
        print("[ERROR] Kaggle credentials not found.")
        print("        Set KAGGLE_API_TOKEN or place kaggle.json in ~/.kaggle")
        return 1

    api = _authenticate()
    zip_path = _download_zip(api, args.force)
    _extract_required(zip_path, args.force)
    _verify_required(REQUIRED_FILES)
    _cleanup(args.force)

    print()
    print("=" * 72)
    print(" SUCCESS: Kaggle data is ready for testing workflows")
    print(" Location:", DATA_DIR)
    print("=" * 72)
    print("Run 'python -m testing.sources.kaggle_scores --season 2025 --sample 5'\n"
          "to preview the ingested results.")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
