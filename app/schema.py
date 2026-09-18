from typing import Any

from app.data_source import CsvWarehouse


def extract_schema(warehouse: CsvWarehouse) -> list[dict[str, Any]]:
    try:
        connection = warehouse.connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            tables = cursor.fetchall()
        result = []
        for (table_name,) in tables:
            with connection.cursor() as cursor:
                cursor.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position", (table_name,))
                columns = cursor.fetchall()
            result.append({
                "table": table_name,
                "columns": [{"name": row[0], "type": row[1], "nullable": row[2]} for row in columns],
            })
        return result
    except Exception:
        return []
    finally:
        if "connection" in locals():
            connection.close()
