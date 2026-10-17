import unittest
from datetime import date

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


if __name__ == "__main__":
    unittest.main()