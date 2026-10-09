"""Parquet tables with a Pydantic row schema and a `schema_version` (A-07).

Every table the pipeline writes goes through `write_table`: the columns are checked against a Pydantic row model (required
columns present; unexpected columns only if the model allows extras, which is how technology-dependent columns are declared),
a sample of the rows is validated, and the schema version is stored in the Parquet file metadata so a reader can refuse a table
written under another contract. Values are written as they are.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

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


class TableWriter:
    """Writes one Parquet table in chunks, so the whole table never sits in memory (A-10).

    Each chunk is validated against `row_model` as `write_table` does; the first chunk fixes the schema, which carries the schema
    version and the `extra_metadata`. The rows go to `<path>.partial`, which replaces `path` only on a clean `close`; an exception inside
    the `with` block removes the partial file, so a failed run leaves no table that looks complete (A-09).

    Implements: A-07, A-10.
    """

    def __init__(
        self,
        path: Path,
        *,
        schema_version: str,
        row_model: type[BaseModel],
        compression: str = "snappy",
        extra_metadata: dict[str, str] | None = None,
        empty_frame: pd.DataFrame | None = None,
    ) -> None:
        self.path = Path(path)
        self._partial = self.path.with_name(self.path.name + ".partial")
        self._schema_version = schema_version
        self._row_model = row_model
        self._compression = compression
        self._extra = extra_metadata
        self._empty = empty_frame
        self._writer: pq.ParquetWriter | None = None
        self._schema: pa.Schema | None = None
        self.n_rows = 0

    def write(self, df: pd.DataFrame) -> None:
        """Append `df` as a row group."""
        validate_columns(df, self._row_model)
        table = pa.Table.from_pandas(df, preserve_index=False)
        if self._writer is None:
            self._schema = table_metadata(
                table.schema, self._schema_version, self._row_model, self._extra
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = pq.ParquetWriter(
                self._partial, self._schema, compression=self._compression
            )
        self._writer.write_table(table.cast(self._schema))
        self.n_rows += len(df)

    def close(self) -> Path:
        """Finish the file and move it to its final name; a writer that received no chunk writes `empty_frame` if it has one.

        Raises:
            TableSchemaError: nothing was written and no empty frame was given.
        """
        if self._writer is None:
            if self._empty is None:
                raise TableSchemaError(f"{self.path.name}: no rows written and no empty frame")
            self.write(self._empty)
        assert self._writer is not None
        self._writer.close()
        self._partial.replace(self.path)
        return self.path

    def abort(self) -> None:
        """Drop the partial file."""
        if self._writer is not None:
            self._writer.close()
        self._partial.unlink(missing_ok=True)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.abort()
        else:
            self.close()


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
