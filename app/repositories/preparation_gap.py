from sqlalchemy import Date, func, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import FunctionElement

from app.models.property_listing import PropertyListing


def venue_gap(venue_id):
    sibling = aliased(PropertyListing)
    return (
        select(func.coalesce(func.max(sibling.preparation_days), 0))
        .where(
            sibling.venue_id == venue_id,
            sibling.offer_type == "short_stay",
            sibling.booking_enabled.is_(True),
        )
        .correlate_except(sibling)
        .scalar_subquery()
    )


class ShiftDays(FunctionElement):
    type = Date()
    inherit_cache = True


@compiles(ShiftDays, "postgresql")
def postgres_shift(element, compiler, **kw):
    day, amount = element.clauses
    return f"({compiler.process(day, **kw)} + {compiler.process(amount, **kw)})"


@compiles(ShiftDays, "sqlite")
def sqlite_shift(element, compiler, **kw):
    day, amount = element.clauses
    return (
        f"date({compiler.process(day, **kw)}, "
        f"CAST({compiler.process(amount, **kw)} AS TEXT) || ' days')"
    )
