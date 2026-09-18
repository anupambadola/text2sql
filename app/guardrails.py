from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Parenthesis
from sqlparse.tokens import DML, Keyword


@dataclass
class GuardrailResult:
    allowed: bool
    sql: str
    warnings: list[str]


BLOCKED_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"}


def _depth(token) -> int:
    if not isinstance(token, Parenthesis):
        return 0
    return 1 + max((_depth(child) for child in token.tokens), default=0)


def check_query(sql: str, max_rows: int = 1000, max_depth: int = 3) -> GuardrailResult:
    statements = sqlparse.parse(sql)
    warnings: list[str] = []
    if len(statements) != 1:
        return GuardrailResult(False, sql, ["Exactly one SQL statement is required."])
    statement = statements[0]
    first = next((token for token in statement.tokens if not token.is_whitespace), None)
    if not first or first.ttype is not DML or first.value.upper() != "SELECT":
        return GuardrailResult(False, sql, ["Only SELECT queries are allowed."])
    normalized = sql.upper()
    for keyword in BLOCKED_KEYWORDS:
        if any(token.value.upper() == keyword for token in statement.flatten() if token.ttype in (DML, Keyword)):
            return GuardrailResult(False, sql, [f"Blocked destructive operation: {keyword}."])
    if max((_depth(token) for token in statement.tokens), default=0) > max_depth:
        return GuardrailResult(False, sql, [f"Subquery depth exceeds the limit of {max_depth}."])
    if " LIMIT " not in f" {normalized} ":
        sql = sql.rstrip().rstrip(";") + f" LIMIT {max_rows}"
        warnings.append(f"A LIMIT {max_rows} clause was added by the guardrail.")
    return GuardrailResult(True, sql, warnings)
