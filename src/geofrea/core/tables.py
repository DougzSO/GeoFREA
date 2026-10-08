"""Parquet tables with a Pydantic row schema and a `schema_version` (A-07).

Every table the pipeline writes goes through `write_table`: the columns are checked against a Pydantic row model (required
columns present; unexpected columns only if the model allows extras, which is how technology-dependent columns are declared),
a sample of the rows is validated, and the schema version is stored in the Parquet file metadata so a reader can refuse a table
written under another contract. Values are written as they are.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ValidationError

SCHEMA_VERSION_KEY = b"geofrea_schema_version"
SCHEMA_NAME_KEY = b"geofrea_row_schema"
_SAMPLE_ROWS = 200


class TableSchemaError(ValueError):
    """A table does not match its row schema, or carries another schema version (A-07, A-09)."""


def validate_columns(df: pd.DataFrame, row_model: type[BaseModel]) -> None:
    """Check required columns, unexpected columns and the types of a sample of rows against `row_model`.

    Raises:
        TableSchemaError: a required column is missing, an unexpected column is present (model without extras), or a sampled
            row does not validate.
    """
    fields = set(row_model.model_fields)
    required = {name for name, f in row_model.model_fields.items() if f.is_required()}
    missing = required - set(df.columns)
    if missing:
        raise TableSchemaError(f"{row_model.__name__}: missing columns {sorted(missing)}")
    extra = set(df.columns) - fields
    if extra and row_model.model_config.get("extra") != "allow":
        raise TableSchemaError(f"{row_model.__name__}: unexpected columns {sorted(extra)}")
    sample = df.head(_SAMPLE_ROWS).astype(object)
    sample = sample.where(sample.notna(), None)
    try:
        for record in sample.to_dict(orient="records"):
            row_model.model_validate(record)
    except ValidationError as exc:
        raise TableSchemaError(f"{row_model.__name__}: a row does not validate: {exc}") from exc


def table_metadata(
    schema: pa.Schema,
    schema_version: str,
    row_model: type[BaseModel],
    extra: dict[str, str] | None = None,
) -> pa.Schema:
    """`schema` with the schema version, the row-model name and any `extra` text entries added to its metadata."""
    meta = dict(schema.metadata or {})
    meta[SCHEMA_VERSION_KEY] = schema_version.encode()
    meta[SCHEMA_NAME_KEY] = row_model.__name__.encode()
    for key, value in (extra or {}).items():
        meta[key.encode()] = value.encode()
    return schema.with_metadata(meta)


def write_table(
    df: pd.DataFrame,
    path: Path,
    *,
    schema_version: str,
    row_model: type[BaseModel],
    compression: str = "snappy",
    extra_metadata: dict[str, str] | None = None,
) -> Path:
    """Validate `df` against `row_model` and write it as Parquet with the schema version in the file metadata.

    `extra_metadata` adds text entries to the Parquet metadata (for example the parameters a table was computed with).

    Implements: A-07.
    """
    validate_columns(df, row_model)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.cast(table_metadata(table.schema, schema_version, row_model, extra_metadata))
    pq.write_table(table, path, compression=compression)
    return path


def read_schema_version(path: Path) -> str | None:
    """The schema version stored in a Parquet file, or None if the file carries none."""
    meta = pq.read_schema(path).metadata or {}
    value = meta.get(SCHEMA_VERSION_KEY)
    return value.decode() if value is not None else None


def require_schema_version(path: Path, expected: str) -> None:
    """Raise `TableSchemaError` unless the table at `path` carries exactly `expected`."""
    found = read_schema_version(path)
    if found != expected:
        raise TableSchemaError(f"{path.name}: schema_version {found!r}, expected {expected!r}")
