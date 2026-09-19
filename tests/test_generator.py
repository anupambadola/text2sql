from app.generator import QueryGenerator


def test_invalid_tables_are_detected():
    schema = [{"table": "department"}]
    invalid = QueryGenerator._invalid_tables("SELECT * FROM tourist_attractions", schema)
    assert invalid == ["tourist_attractions"]
