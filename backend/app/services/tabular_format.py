"""Safe, format-aware tabular dataset IO used by upload, repair, and export flows."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

SUPPORTED_FORMATS = {"csv", "xlsx", "xls", "json"}
MEDIA_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "json": "application/json",
}


def format_from_path(path: str) -> str:
    extension = Path(path).suffix.lower().lstrip(".")
    if extension not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported dataset format: {extension or 'unknown'}")
    return extension


def capture_format_metadata(path: str) -> Dict[str, Any]:
    """Capture stable serialization details without treating an extension as metadata."""
    file_format = format_from_path(path)
    metadata: Dict[str, Any] = {"format": file_format, "media_type": MEDIA_TYPES[file_format]}

    if file_format == "csv":
        metadata.update({"encoding": "utf-8", "delimiter": ",", "quotechar": '"', "line_terminator": "\n"})
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as source:
                sample = source.read(8192)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            metadata.update({"encoding": "utf-8-sig", "delimiter": dialect.delimiter, "quotechar": dialect.quotechar})
        except (OSError, UnicodeDecodeError, csv.Error):
            pass
    elif file_format in {"xlsx", "xls"}:
        try:
            metadata["sheet_name"] = pd.ExcelFile(path).sheet_names[0]
        except Exception:
            metadata["sheet_name"] = 0
    elif file_format == "json":
        metadata["orient"] = "records"

    return metadata


def read_tabular(path: str, metadata: Optional[Dict[str, Any]] = None, nrows: Optional[int] = None) -> pd.DataFrame:
    metadata = metadata or capture_format_metadata(path)
    file_format = metadata.get("format") or format_from_path(path)
    if file_format == "csv":
        return pd.read_csv(
            path,
            nrows=nrows,
            encoding=metadata.get("encoding", "utf-8"),
            sep=metadata.get("delimiter", ","),
            quotechar=metadata.get("quotechar", '"'),
        )
    if file_format in {"xlsx", "xls"}:
        return pd.read_excel(path, sheet_name=metadata.get("sheet_name", 0), nrows=nrows)
    return pd.read_json(path, orient=metadata.get("orient", "records"), nrows=nrows)


def write_tabular(df: pd.DataFrame, path: str, metadata: Dict[str, Any]) -> None:
    """Write a dataframe using the selected source format; never silently change it."""
    file_format = metadata.get("format") or format_from_path(path)
    if file_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported output format: {file_format}")

    if file_format == "csv":
        df.to_csv(
            path,
            index=False,
            encoding=metadata.get("encoding", "utf-8"),
            sep=metadata.get("delimiter", ","),
            quotechar=metadata.get("quotechar", '"'),
            lineterminator=metadata.get("line_terminator", "\n"),
        )
    elif file_format == "xlsx":
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=str(metadata.get("sheet_name") or "Sheet1")[:31])
    elif file_format == "xls":
        try:
            df.to_excel(path, index=False, sheet_name=str(metadata.get("sheet_name") or "Sheet1")[:31], engine="xlwt")
        except Exception as exc:
            raise ValueError("Saving repaired .xls files requires the xlwt package (or equivalent writer). No format conversion was performed.") from exc
    else:
        df.to_json(path, orient=metadata.get("orient", "records"), date_format="iso", force_ascii=False)


def verify_round_trip(expected_df: pd.DataFrame, path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Reopen a generated artifact and check structural compatibility before publishing it."""
    reopened = read_tabular(path, metadata)
    if list(reopened.columns) != list(expected_df.columns):
        raise ValueError("Serialized output changed the column names or column order")
    if len(reopened) != len(expected_df):
        raise ValueError("Serialized output changed the row count")
    return {"row_count": len(reopened), "column_count": len(reopened.columns), "format": metadata["format"]}


def filename_for_version(dataset_name: str, version_number: int, file_format: str) -> str:
    safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in dataset_name).strip("_")
    return f"{safe_name or 'dataset'}_v{version_number}.{file_format}"
