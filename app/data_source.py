import csv
from pathlib import Path
import re

import psycopg
from psycopg import sql


def _safe_table_name(path: Path) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", path.stem).lower()
    return name or "dataset"


def _column_type(values: list[str | None]) -> str:
    non_empty = [value for value in values if value not in (None, "")]
    if non_empty and all(re.fullmatch(r"[-+]?\d+", value) for value in non_empty):
        return "BIGINT"
    if non_empty:
        try:
            for value in non_empty:
                float(value)
            return "DOUBLE PRECISION"
        except ValueError:
            pass
    return "TEXT"


class CsvWarehouse:
    """Loads user-owned CSV files into PostgreSQL tables.

    CSVs containing text_query/sql_command are treated as RAG examples and are
    excluded from SQL tables. All other CSVs become queryable PostgreSQL tables.
    """

    def __init__(self, database_url: str, data_dir: str, examples_csv: str):
        self.database_url = database_url
        self.data_dir = Path(data_dir)
        self.examples_csv = Path(examples_csv).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._load_csvs()
        except psycopg.OperationalError:
            pass

    def connection(self):
        return psycopg.connect(self.database_url)

    def _load_csvs(self) -> None:
        connection = self.connection()
        try:
            for csv_path in self.data_dir.glob("*.csv"):
                if csv_path.resolve() == self.examples_csv:
                    continue
                table_name = _safe_table_name(csv_path)
                with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
                    rows = list(csv.DictReader(file))
                if not rows:
                    continue
                columns = list(rows[0])
                definitions = [sql.SQL("{} {}").format(sql.Identifier(column), sql.SQL(_column_type([row.get(column) for row in rows]))) for column in columns]
                with connection.cursor() as cursor:
                    cursor.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table_name)))
                    cursor.execute(sql.SQL("CREATE TABLE {} ({})").format(sql.Identifier(table_name), sql.SQL(", ").join(definitions)))
                    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(sql.Identifier(table_name), sql.SQL(", ").join(sql.Identifier(column) for column in columns), sql.SQL(", ").join(sql.Placeholder() for _ in columns))
                    cursor.executemany(statement, [[row.get(column) for column in columns] for row in rows])
            connection.commit()
        finally:
            connection.close()