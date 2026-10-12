import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.services import cache
from app.services.reservations import month_bounds_utc, round_currency


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, _ttl, value):
        self.values[key] = value


class RevenueRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_is_scoped_by_tenant(self):
        fake_redis = FakeRedis()

        async def calculate(property_id, tenant_id):
            return {
                "property_id": property_id,
                "tenant_id": tenant_id,
                "total": "10.00" if tenant_id == "tenant-a" else "20.00",
                "currency": "USD",
                "count": 1,
            }

        with patch.object(cache, "redis_client", fake_redis), patch(
            "app.services.reservations.calculate_total_revenue",
            new=AsyncMock(side_effect=calculate),
        ):
            tenant_a = await cache.get_revenue_summary("prop-001", "tenant-a")
            tenant_b = await cache.get_revenue_summary("prop-001", "tenant-b")

        self.assertEqual(tenant_a["total"], "10.00")
        self.assertEqual(tenant_b["total"], "20.00")
        self.assertEqual(
            set(fake_redis.values),
            {"revenue:tenant-a:prop-001", "revenue:tenant-b:prop-001"},
        )

    async def test_cache_rejects_a_mismatched_cached_tenant(self):
        fake_redis = FakeRedis()
        fake_redis.values["revenue:tenant-b:prop-001"] = json.dumps(
            {
                "property_id": "prop-001",
                "tenant_id": "tenant-a",
                "total": "999.00",
                "currency": "USD",
                "count": 1,
            }
        )
        replacement = {
            "property_id": "prop-001",
            "tenant_id": "tenant-b",
            "total": "20.00",
            "currency": "USD",
            "count": 1,
        }

        with patch.object(cache, "redis_client", fake_redis), patch(
            "app.services.reservations.calculate_total_revenue",
            new=AsyncMock(return_value=replacement),
        ):
            result = await cache.get_revenue_summary("prop-001", "tenant-b")

        self.assertEqual(result, replacement)

    def test_paris_month_boundaries_are_converted_to_utc(self):
        start, end = month_bounds_utc(2024, 3, "Europe/Paris")

        self.assertEqual(start, datetime(2024, 2, 29, 23, 0, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2024, 3, 31, 22, 0, tzinfo=timezone.utc))

    def test_currency_uses_decimal_half_up_rounding(self):
        self.assertEqual(round_currency(Decimal("10.125")), Decimal("10.13"))
        self.assertEqual(round_currency(Decimal("10.124")), Decimal("10.12"))


if __name__ == "__main__":
    unittest.main()
