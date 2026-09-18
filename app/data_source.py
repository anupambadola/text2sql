from pathlib import Path
import re

import duckdb


def database_path(database_url: str) -> str:
    return database_url.removeprefix("duckdb:///")


def _safe_table_name(path: Path) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", path.stem).lower()
    return name or "dataset"


class CsvWarehouse:
    """Loads user-owned CSV files into a local analytical warehouse.

    CSVs containing text_query/sql_command are treated as RAG examples and are
    excluded from SQL tables. All other CSVs become queryable DuckDB tables.
    """

    def __init__(self, database_url: str, data_dir: str, examples_csv: str):
        self.path = database_path(database_url)
        self.data_dir = Path(data_dir)
        self.examples_csv = Path(examples_csv).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._load_csvs()

    def connection(self) -> duckdb.DuckDBPyConnection:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(self.path, read_only=False)

    def _load_csvs(self) -> None:
        connection = self.connection()
        try:
            for csv_path in self.data_dir.glob("*.csv"):
                if csv_path.resolve() == self.examples_csv:
                    continue
                table_name = _safe_table_name(csv_path)
                escaped_path = str(csv_path.resolve()).replace("'", "''")
                connection.execute(
                    f"CREATE OR REPLACE TABLE \"{table_name}\" AS SELECT * FROM read_csv_auto('{escaped_path}', header=true)"
                )
        finally:
            connection.close()