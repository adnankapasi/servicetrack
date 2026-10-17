import unittest
from datetime import date, datetime

from servicetrack.scheduling import calculate_service_status


class SchedulingTests(unittest.TestCase):
    def calculate(self, **changes):
        values = {
            "current_km": 12000,
            "last_service_km": 10000,
            "last_service_date": date(2026, 1, 1),
            "interval_km": 5000,
            "interval_days": 180,
            "today": date(2026, 2, 1),
        }
        values.update(changes)
        return calculate_service_status(**values)

    def test_service_not_due(self):
        status = self.calculate()
        self.assertFalse(status.is_due)
        self.assertEqual(status.next_service_km, 15000)
        self.assertEqual(status.remaining_km, 3000)
        self.assertEqual(status.next_service_date, date(2026, 6, 30))

    def test_due_at_exact_mileage(self):
        self.assertTrue(self.calculate(current_km=15000).is_due)

    def test_due_at_exact_date(self):
        status = self.calculate(today=date(2026, 6, 30))
        self.assertTrue(status.is_due)
        self.assertEqual(status.remaining_days, 0)

    def test_overdue_mileage_remains_negative(self):
        status = self.calculate(current_km=15500)
        self.assertEqual(status.remaining_km, -500)

    def test_overdue_date_remains_negative(self):
        status = self.calculate(today=date(2026, 7, 5))

        self.assertEqual(status.remaining_days, -5)
        self.assertTrue(status.is_due)
        self.assertEqual(status.remaining_km, 3000)

    def test_rejects_invalid_values(self):
        invalid_cases = [
            {"current_km": -1},
            {"current_km": 9999},
            {"interval_km": 0},
            {"interval_days": 0},
            {"current_km": True},
            {"current_km": 12000.5},
            {"last_service_date": date(2027, 1, 1)},
        ]
        for changes in invalid_cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.calculate(**changes)

    def test_accepts_service_date_equal_to_today(self):
        status = self.calculate(
            last_service_date=date(2026, 2, 1),
            today=date(2026, 2, 1),
        )

        self.assertEqual(status.remaining_days, 180)
        self.assertFalse(status.is_due)

    def test_rejects_service_date_one_day_in_future(self):
        with self.assertRaisesRegex(ValueError, "cannot be in the future"):
            self.calculate(
                last_service_date=date(2026, 2, 2),
                today=date(2026, 2, 1),
            )

    def test_rejects_non_date_today(self):
        with self.assertRaisesRegex(ValueError, "today must be a date"):
            self.calculate(today="2026-02-01")

    def test_rejects_datetime_arguments(self):
        cases = [
            {"today": datetime(2026, 2, 1, 12, 0)},
            {"last_service_date": datetime(2026, 1, 1, 12, 0)},
        ]

        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, "must be a date"):
                    self.calculate(**changes)

    def test_rejects_negative_last_service_mileage(self):
        with self.assertRaisesRegex(
            ValueError, "last_service_km must be at least 0"
        ):
            self.calculate(last_service_km=-1)

    def test_rejects_service_date_overflow(self):
        with self.assertRaisesRegex(
            ValueError, "exceeds the supported date range"
        ):
            self.calculate(
                last_service_date=date.max,
                today=date.max,
                interval_days=1,
            )

    def test_none_today_uses_current_date(self):
        actual_today = date.today()

        status = self.calculate(
            last_service_date=actual_today,
            today=None,
        )

        # Allow for the unlikely case that midnight occurs during the test.
        today_after = date.today()
        expected_remaining_days = {
            180,
            180 - (today_after - actual_today).days,
        }

        self.assertIn(status.remaining_days, expected_remaining_days)
        self.assertEqual(status.remaining_km, 3000)
        self.assertFalse(status.is_due)


if __name__ == "__main__":
    unittest.main()