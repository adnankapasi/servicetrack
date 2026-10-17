import sqlite3
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from servicetrack.storage import ServiceStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.store = ServiceStore(":memory:")
        self.vehicle_id = self.store.add_vehicle("Family Car")

    def tearDown(self):
        self.store.close()

    def add_service(self, service_date, odometer_km, notes=""):
        return self.store.add_service(
            self.vehicle_id,
            service_date,
            odometer_km,
            notes,
        )

    def test_vehicle_name_is_trimmed(self):
        vehicle_id = self.store.add_vehicle("  Scooter  ")

        self.assertIn(
            {"id": vehicle_id, "name": "Scooter"},
            self.store.list_vehicles(),
        )

    def test_rejects_invalid_vehicle_names(self):
        for name in ("", "   ", None, 123):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.store.add_vehicle(name)

        self.assertEqual(len(self.store.list_vehicles()), 1)

    def test_existing_vehicle_without_services_has_empty_history(self):
        self.assertEqual(
            self.store.service_history(self.vehicle_id),
            [],
        )

    def test_service_details_are_saved(self):
        service_id = self.add_service(
            date(2020, 1, 1),
            10000,
            "  Oil and filter changed  ",
        )

        self.assertEqual(
            self.store.service_history(self.vehicle_id),
            [
                {
                    "id": service_id,
                    "vehicle_id": self.vehicle_id,
                    "service_date": "2020-01-01",
                    "odometer_km": 10000,
                    "notes": "Oil and filter changed",
                }
            ],
        )

    def test_history_is_newest_first_and_isolated_by_vehicle(self):
        other_vehicle = self.store.add_vehicle("Scooter")

        self.add_service(date(2020, 1, 1), 10000)
        self.add_service(date(2020, 6, 1), 15000)

        self.store.add_service(
            other_vehicle,
            date(2020, 7, 1),
            2000,
        )

        history = self.store.service_history(self.vehicle_id)

        self.assertEqual(
            [record["odometer_km"] for record in history],
            [15000, 10000],
        )
        self.assertTrue(
            all(
                record["vehicle_id"] == self.vehicle_id
                for record in history
            )
        )

    def test_accepts_zero_and_equal_mileage(self):
        self.add_service(date(2020, 1, 1), 0)
        self.add_service(date(2020, 2, 1), 0)

        history = self.store.service_history(self.vehicle_id)

        self.assertEqual(
            [record["odometer_km"] for record in history],
            [0, 0],
        )

    def test_accepts_consistent_backdated_record(self):
        self.add_service(date(2020, 1, 1), 10000)
        self.add_service(date(2020, 3, 1), 15000)
        self.add_service(date(2020, 2, 1), 12000)

        history = self.store.service_history(self.vehicle_id)

        self.assertEqual(
            [record["odometer_km"] for record in history],
            [15000, 12000, 10000],
        )

    def test_rejects_mileage_below_earlier_service(self):
        self.add_service(date(2020, 1, 1), 10000)

        with self.assertRaisesRegex(ValueError, "Mileage conflicts"):
            self.add_service(date(2020, 2, 1), 9999)

        self.assertEqual(
            len(self.store.service_history(self.vehicle_id)),
            1,
        )

    def test_rejects_mileage_above_later_service(self):
        self.add_service(date(2020, 3, 1), 15000)

        with self.assertRaisesRegex(ValueError, "Mileage conflicts"):
            self.add_service(date(2020, 2, 1), 15001)

        self.assertEqual(
            len(self.store.service_history(self.vehicle_id)),
            1,
        )

    def test_same_date_requires_equal_mileage(self):
        self.add_service(date(2020, 1, 1), 10000, "Oil")
        second_id = self.add_service(
            date(2020, 1, 1),
            10000,
            "Tyres",
        )

        for mileage in (9999, 10001):
            with self.subTest(mileage=mileage):
                with self.assertRaisesRegex(
                    ValueError,
                    "Mileage conflicts",
                ):
                    self.add_service(date(2020, 1, 1), mileage)

        history = self.store.service_history(self.vehicle_id)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["id"], second_id)

    def test_rejects_invalid_mileage(self):
        for mileage in (-1, True, 1000.5, "1000", None):
            with self.subTest(mileage=mileage):
                with self.assertRaises(ValueError):
                    self.add_service(date(2020, 1, 1), mileage)

        self.assertEqual(
            self.store.service_history(self.vehicle_id),
            [],
        )

    def test_rejects_invalid_vehicle_ids(self):
        for vehicle_id in (0, -1, True, 1.5, "1", None):
            with self.subTest(vehicle_id=vehicle_id):
                with self.assertRaises(ValueError):
                    self.store.add_service(
                        vehicle_id,
                        date(2020, 1, 1),
                        1000,
                    )

                with self.assertRaises(ValueError):
                    self.store.service_history(vehicle_id)

    def test_rejects_missing_vehicle(self):
        with self.assertRaisesRegex(
            ValueError,
            "Vehicle does not exist",
        ):
            self.store.add_service(
                999,
                date(2020, 1, 1),
                1000,
            )

        with self.assertRaisesRegex(
            ValueError,
            "Vehicle does not exist",
        ):
            self.store.service_history(999)

    def test_rejects_invalid_date_types(self):
        invalid_dates = (
            "2020-01-01",
            None,
            datetime(2020, 1, 1, 12, 0),
        )

        for service_date in invalid_dates:
            with self.subTest(service_date=service_date):
                with self.assertRaisesRegex(
                    ValueError,
                    "service_date must be a date",
                ):
                    self.add_service(service_date, 1000)

    def test_accepts_today(self):
        self.add_service(date.today(), 1000)

        self.assertEqual(
            len(self.store.service_history(self.vehicle_id)),
            1,
        )

    def test_rejects_tomorrow(self):
        tomorrow = date.today() + timedelta(days=1)

        with self.assertRaisesRegex(
            ValueError,
            "cannot be in the future",
        ):
            self.add_service(tomorrow, 1000)

    def test_rejects_non_text_notes(self):
        for notes in (None, 123, True):
            with self.subTest(notes=notes):
                with self.assertRaisesRegex(
                    ValueError,
                    "notes must be text",
                ):
                    self.add_service(date(2020, 1, 1), 1000, notes)

    def test_sql_like_text_is_stored_as_data(self):
        text = "Car'); DROP TABLE vehicles; --"
        vehicle_id = self.store.add_vehicle(text)

        self.store.add_service(
            vehicle_id,
            date(2020, 1, 1),
            1000,
            text,
        )

        self.assertIn(
            {"id": vehicle_id, "name": text},
            self.store.list_vehicles(),
        )
        self.assertEqual(
            self.store.service_history(vehicle_id)[0]["notes"],
            text,
        )

    def test_store_remains_usable_after_failed_transaction(self):
        self.add_service(date(2020, 1, 1), 10000)

        with self.assertRaises(ValueError):
            self.add_service(date(2020, 2, 1), 9000)

        self.assertFalse(self.store.connection.in_transaction)

        self.add_service(date(2020, 2, 1), 11000)

        self.assertEqual(
            [
                record["odometer_km"]
                for record in self.store.service_history(self.vehicle_id)
            ],
            [11000, 10000],
        )

    def test_foreign_keys_are_enabled(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.connection:
                self.store.connection.execute(
                    """
                    INSERT INTO services(
                        vehicle_id, service_date, odometer_km, notes
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (999, "2020-01-01", 1000, ""),
                )

    def test_data_survives_reopening_database(self):
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "services.db")

            with ServiceStore(path) as store:
                vehicle_id = store.add_vehicle("Bike")
                store.add_service(
                    vehicle_id,
                    date(2020, 1, 1),
                    1000,
                    "First service",
                )

            with ServiceStore(path) as store:
                self.assertEqual(
                    store.list_vehicles(),
                    [{"id": vehicle_id, "name": "Bike"}],
                )

                history = store.service_history(vehicle_id)

                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["odometer_km"], 1000)
                self.assertEqual(history[0]["notes"], "First service")

    def test_context_manager_closes_connection_on_error(self):
        store = ServiceStore(":memory:")

        with self.assertRaisesRegex(RuntimeError, "Example"):
            with store:
                raise RuntimeError("Example")

        with self.assertRaises(sqlite3.ProgrammingError):
            store.list_vehicles()


if __name__ == "__main__":
    unittest.main()