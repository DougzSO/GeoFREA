"""Parquet tables carry a row schema and a schema_version (A-07)."""

from __future__ import annotations

import pandas as pd
import pyarrow.parquet as pq
import pytest
from pydantic import BaseModel, ConfigDict

from geofrea.core.tables import (
    TableSchemaError,
    read_schema_version,
    require_schema_version,
    validate_columns,
    write_table,
)


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: int
    value: float
    label: str | None


class _OpenRow(_Row):
    model_config = ConfigDict(extra="allow")


def _df() -> pd.DataFrame:
    return pd.DataFrame({"cell_id": [1, 2], "value": [0.5, 1.5], "label": pd.array(["a", None], dtype="string")})


@pytest.mark.unit
def test_write_table_stores_the_schema_version_and_leaves_values_unchanged(tmp_path):
    path = write_table(_df(), tmp_path / "t.parquet", schema_version="1.2", row_model=_Row)
    assert read_schema_version(path) == "1.2"
    assert pq.read_schema(path).metadata[b"geofrea_row_schema"] == b"_Row"
    back = pd.read_parquet(path)
    assert back["value"].tolist() == [0.5, 1.5] and back["cell_id"].tolist() == [1, 2]
    require_schema_version(path, "1.2")
    with pytest.raises(TableSchemaError, match="expected '2.0'"):
        require_schema_version(path, "2.0")


@pytest.mark.unit
def test_a_table_without_a_version_reads_as_none(tmp_path):
    _df().to_parquet(tmp_path / "plain.parquet", index=False)
    assert read_schema_version(tmp_path / "plain.parquet") is None
    with pytest.raises(TableSchemaError):
        require_schema_version(tmp_path / "plain.parquet", "1.0")


@pytest.mark.unit
def test_missing_unexpected_and_ill_typed_columns_are_rejected_extras_only_when_allowed():
    with pytest.raises(TableSchemaError, match="missing columns"):
        validate_columns(_df().drop(columns="value"), _Row)
    with pytest.raises(TableSchemaError, match="unexpected columns"):
        validate_columns(_df().assign(extra=1), _Row)
    validate_columns(_df().assign(extra=1), _OpenRow)
    with pytest.raises(TableSchemaError, match="does not validate"):
        validate_columns(_df().assign(value="not a number"), _Row)
