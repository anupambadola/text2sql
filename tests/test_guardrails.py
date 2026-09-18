from app.guardrails import check_query


def test_adds_limit_to_select():
    result = check_query("SELECT * FROM customers")
    assert result.allowed
    assert "LIMIT 1000" in result.sql


def test_blocks_writes():
    result = check_query("DELETE FROM orders")
    assert not result.allowed
    assert "destructive" in result.warnings[0].lower()


def test_rejects_multiple_statements():
    result = check_query("SELECT 1; DROP TABLE customers")
    assert not result.allowed
