from typing import Any

from app.data_source import CsvWarehouse


def extract_schema(warehouse: CsvWarehouse) -> list[dict[str, Any]]:
    connection = warehouse.connection()
    try:
        tables = connection.execute("SHOW TABLES").fetchall()
        result = []
        for (table_name,) in tables:
            columns = connection.execute(f'DESCRIBE "{table_name}"').fetchall()
            result.append({
                "table": table_name,
                "columns": [{"name": row[0], "type": row[1], "nullable": row[2]} for row in columns],
            })
        return result
    finally:
        connection.close()
