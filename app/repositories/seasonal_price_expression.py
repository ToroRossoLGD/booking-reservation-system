"""Database-side date pricing so filtering/counting precede pagination.

Uses the same non-overlapping, checkout-exclusive ranges as nightly_pricing.
Only bound SQLAlchemy expressions enter SQL; no user input is interpolated.
"""

from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement


class StayTotal(FunctionElement):
    type = BigInteger()
    inherit_cache = True


def inputs(element, compiler, **kw):
    names = ("rates", "base", "arrival", "departure")
    return ", ".join(
        f"{compiler.process(value, **kw)} AS {name}"
        for value, name in zip(element.clauses, names)
    )


@compiles(StayTotal, "sqlite")
def sqlite_total(element, compiler, **kw):
    args = inputs(element, compiler, **kw)
    return f"""(SELECT pricing_input.base *
        CAST(julianday(pricing_input.departure)
             - julianday(pricing_input.arrival) AS INTEGER)
        + COALESCE((SELECT SUM(
            CAST(julianday(min(json_extract(season.value, '$.end'),
                              pricing_input.departure))
                 - julianday(max(json_extract(season.value, '$.start'),
                                 pricing_input.arrival)) AS INTEGER)
            * (json_extract(season.value, '$.price_cents') - pricing_input.base))
          FROM json_each(pricing_input.rates) AS season
          WHERE json_extract(season.value, '$.start') < pricing_input.departure
            AND json_extract(season.value, '$.end') > pricing_input.arrival), 0)
        FROM (SELECT {args}) AS pricing_input)"""


@compiles(StayTotal, "postgresql")
def postgres_total(element, compiler, **kw):
    args = inputs(element, compiler, **kw)
    return f"""(SELECT pricing_input.base *
        (pricing_input.departure - pricing_input.arrival)
        + COALESCE((SELECT SUM(
            (LEAST(CAST(season.value->>'end' AS DATE), pricing_input.departure)
             - GREATEST(CAST(season.value->>'start' AS DATE), pricing_input.arrival))
            * (CAST(season.value->>'price_cents' AS BIGINT) - pricing_input.base))
          FROM json_array_elements(pricing_input.rates) AS season(value)
          WHERE CAST(season.value->>'start' AS DATE) < pricing_input.departure
            AND CAST(season.value->>'end' AS DATE) > pricing_input.arrival), 0)
        FROM (SELECT {args}) AS pricing_input)"""
