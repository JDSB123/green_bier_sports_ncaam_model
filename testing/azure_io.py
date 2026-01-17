"""Azure-only helpers for reading/writing canonical data blobs."""

from __future__ import annotations

from typing import Any

from testing.azure_data_reader import get_azure_reader


def read_csv(blob_path: str, **pandas_kwargs):
    """Read a CSV blob into a DataFrame."""
    return get_azure_reader().read_csv(blob_path, **pandas_kwargs)


def read_csv_chunks(blob_path: str, **pandas_kwargs):
    """Stream a CSV blob in chunks."""
    return get_azure_reader().read_csv_chunks(blob_path, **pandas_kwargs)


def read_json(blob_path: str) -> Any:
    """Read a JSON blob into a Python object."""
    return get_azure_reader().read_json(blob_path)


def read_text(blob_path: str, encoding: str = "utf-8") -> str:
    """Read a text blob."""
    return get_azure_reader().read_text(blob_path, encoding=encoding)


def upload_bytes(
    blob_path: str,
    content: bytes,
    content_type: str | None = None,
    overwrite: bool = True,
    tags: dict[str, str] | None = None,
) -> None:
    """Upload raw bytes to Azure Blob Storage."""
    return get_azure_reader().upload_bytes(
        blob_path,
        content,
        content_type=content_type,
        overwrite=overwrite,
        tags=tags,
    )


def upload_text(
    blob_path: str,
    text: str,
    encoding: str = "utf-8",
    content_type: str | None = None,
    overwrite: bool = True,
    tags: dict[str, str] | None = None,
) -> None:
    """Upload text to Azure Blob Storage."""
    return get_azure_reader().upload_text(
        blob_path,
        text,
        encoding=encoding,
        content_type=content_type,
        overwrite=overwrite,
        tags=tags,
    )


def write_json(
    blob_path: str,
    payload: Any,
    indent: int = 2,
    sort_keys: bool = False,
    overwrite: bool = True,
    tags: dict[str, str] | None = None,
) -> None:
    """Serialize and upload JSON to Azure Blob Storage."""
    return get_azure_reader().write_json(
        blob_path,
        payload,
        indent=indent,
        sort_keys=sort_keys,
        overwrite=overwrite,
        tags=tags,
    )


def write_csv(
    blob_path: str,
    df,
    overwrite: bool = True,
    tags: dict[str, str] | None = None,
    **pandas_kwargs,
) -> None:
    """Serialize and upload a DataFrame as CSV to Azure Blob Storage."""
    return get_azure_reader().write_csv(
        blob_path,
        df,
        overwrite=overwrite,
        tags=tags,
        **pandas_kwargs,
    )


def list_files(prefix: str = "", pattern: str | None = None):
    """List blob paths under a prefix."""
    return get_azure_reader().list_files(prefix, pattern=pattern)


def blob_exists(blob_path: str) -> bool:
    """Check if a blob exists."""
    return get_azure_reader().blob_exists(blob_path)


def set_blob_tags(blob_path: str, tags: dict[str, str] | None) -> None:
    """Set Azure Blob Storage tags for an existing blob."""
    return get_azure_reader().set_blob_tags(blob_path, tags)
