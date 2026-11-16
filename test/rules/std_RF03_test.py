"""Tests for RF03 fixes around value sources (UNNEST, generate_series).

The YAML cases in ``test/fixtures/rules/std_rule_cases/RF03.yml`` cover the
rule's own view of the fixes. These tests pin down the end-to-end contract:
the unsafe fix is gone, the violations are still reported, and safe fixes in
the same situations still happen.
"""

import pytest

from sqlfluff.core import FluffConfig, Linter


def _lint(sql: str, single_table_references: str) -> tuple[str, list[str]]:
    cfg = FluffConfig(
        overrides={"dialect": "postgres", "rules": "RF03"},
        configs={
            "rules": {
                "references.consistent": {
                    "single_table_references": single_table_references,
                }
            }
        },
    )
    linted = Linter(config=cfg).lint_string(sql, fix=True)
    fixed_sql, _ = linted.fix_string()
    return fixed_sql, [v.description for v in linted.violations]


@pytest.mark.parametrize(
    "value_source",
    [
        # PostgreSQL names the output column of a scalar table function after
        # the alias, so ``k`` below is the outer ``unnest`` column.
        "unnest(ARRAY[1, 2]) AS k",
        # generate_series() behaves the same way.
        "generate_series(1, 3) AS k",
        # The column is declared separately from the alias.
        "unnest(ARRAY[1, 2]) AS u (k)",
    ],
)
@pytest.mark.parametrize("single_table_references", ["qualified", "consistent"])
def test__rules__std_RF03_does_not_qualify_outer_value_source(
    value_source: str, single_table_references: str
) -> None:
    """RF03 must not add a qualifier that binds to the wrong table.

    In PostgreSQL, ``SELECT k FROM unnest(...) AS k`` exposes ``k`` as the
    outer column. The subquery's ``k`` therefore binds to the enclosing
    query, not to ``widget``. Qualifying it turns a working query into one
    that fails with ``column w.k does not exist`` (or, worse, silently
    compares against ``widget.k`` when that column happens to exist).
    """
    sql = (
        f"SELECT k FROM {value_source}\n"
        "WHERE NOT EXISTS (SELECT 1 FROM widget AS w WHERE w.id = k)\n"
    )
    fixed_sql, descriptions = _lint(sql, single_table_references)

    # The fix is gone: the reference still binds to the outer column.
    assert fixed_sql == sql
    # The style problem is still reported.
    assert descriptions
    assert all("Unqualified reference 'k'" in d for d in descriptions)


def test__rules__std_RF03_keeps_safe_unqualifying_fix() -> None:
    """Removing qualifiers is still safe and still applied.

    Unqualified names resolve to the inner table first, so turning ``w.id``
    into ``id`` can't change which table the value comes from.
    """
    sql = (
        "SELECT k FROM unnest(ARRAY[1, 2]) AS k\n"
        "WHERE NOT EXISTS (SELECT 1 FROM widget AS w WHERE w.id = 1)\n"
    )
    expected = sql.replace("w.id = 1", "id = 1")
    fixed_sql, descriptions = _lint(sql, "unqualified")

    assert fixed_sql == expected
    assert descriptions == ["Qualified reference 'w.id' found in single table select."]


def test__rules__std_RF03_keeps_safe_qualifying_fix() -> None:
    """A source the subquery can't see doesn't block the existing fix.

    A plain derived table can't see the FROM clause of the query which holds
    it, so ``x`` belongs to ``widget`` and can be safely qualified.
    """
    sql = (
        "SELECT k FROM unnest(ARRAY[1, 2]) AS k,\n"
        "(SELECT (SELECT 1 FROM widget AS w WHERE w.id = x) AS c) AS d\n"
    )
    expected = sql.replace("w.id = x", "w.id = w.x")
    fixed_sql, descriptions = _lint(sql, "consistent")

    assert fixed_sql == expected
    assert descriptions
