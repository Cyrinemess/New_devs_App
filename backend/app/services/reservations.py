from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

MONEY_QUANTUM = Decimal("0.01")


def round_currency(value: Decimal) -> Decimal:
    """Round an exact database value to currency precision."""
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def month_bounds_utc(
    year: int, month: int, timezone_name: str
) -> tuple[datetime, datetime]:
    """Return a property's local calendar-month bounds as UTC instants."""
    property_timezone = ZoneInfo(timezone_name)
    start_local = datetime(year, month, 1, tzinfo=property_timezone)
    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=property_timezone)
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=property_timezone)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


async def calculate_monthly_revenue(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
    db_session=None,
) -> Decimal:
    """
    Calculates revenue for a specific month.
    """

    if not tenant_id:
        raise ValueError("tenant_id is required for revenue queries")

    from sqlalchemy import text

    owns_session = db_session is None
    if owns_session:
        from app.core.database_pool import db_pool

        await db_pool.initialize()
        db_session = db_pool.get_session()

    try:
        timezone_result = await db_session.execute(
            text(
                """
                SELECT timezone
                FROM properties
                WHERE id = :property_id AND tenant_id = :tenant_id
                """
            ),
            {"property_id": property_id, "tenant_id": tenant_id},
        )
        timezone_name = timezone_result.scalar_one_or_none()
        if timezone_name is None:
            return Decimal("0.00")

        start_date, end_date = month_bounds_utc(year, month, timezone_name)
        revenue_result = await db_session.execute(
            text(
                """
                SELECT COALESCE(SUM(total_amount), 0)
                FROM reservations
                WHERE property_id = :property_id
                  AND tenant_id = :tenant_id
                  AND check_in_date >= :start_date
                  AND check_in_date < :end_date
                """
            ),
            {
                "property_id": property_id,
                "tenant_id": tenant_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        total = Decimal(str(revenue_result.scalar_one()))
        return round_currency(total)
    finally:
        if owns_session:
            await db_session.close()


async def calculate_total_revenue(property_id: str, tenant_id: str) -> dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    if not tenant_id:
        raise ValueError("tenant_id is required for revenue queries")

    try:
        from app.core.database_pool import db_pool

        await db_pool.initialize()

        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text

                query = text("""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)

                result = await session.execute(
                    query, {"property_id": property_id, "tenant_id": tenant_id}
                )
                row = result.fetchone()

                if row:
                    total_revenue = round_currency(Decimal(str(row.total_revenue)))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": f"{total_revenue:.2f}",
                        "currency": "USD",
                        "count": row.reservation_count,
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0,
                    }
        else:
            raise RuntimeError("Database pool not available")

    except Exception as e:
        # Never substitute another tenant's hard-coded financial figures when
        # the database is unavailable. Failing closed is safer than returning
        # plausible but incorrect revenue data.
        raise RuntimeError("Revenue data is temporarily unavailable") from e
