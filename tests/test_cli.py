import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from servicetrack.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.database = str(
            Path(self.directory.name) / "servicetrack.db"
        )

    def tearDown(self):
        self.directory.cleanup()

    def run_command(self, *arguments):
        output = io.StringIO()

        with redirect_stdout(output):
            result = main([
                "--db",
                self.database,
                *arguments,
            ])

        self.assertEqual(result, 0)
        return json.loads(output.getvalue())

    def assert_command_error(self, arguments, expected_message):
        output = io.StringIO()
        errors = io.StringIO()

        with redirect_stdout(output), redirect_stderr(errors):
            with self.assertRaises(SystemExit) as caught:
                main([
                    "--db",
                    self.database,
                    *arguments,
                ])

        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn(expected_message, errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def create_vehicle(self, name="My Bike"):
        result = self.run_command("add-vehicle", name)
        return str(result["vehicle_id"])

    def test_empty_vehicle_list(self):
        self.assertEqual(self.run_command("vehicles"), [])

    def test_create_and_list_vehicle(self):
        vehicle_id = self.create_vehicle("  Honda Activa  ")

        self.assertEqual(
            self.run_command("vehicles"),
            [{
                "id": int(vehicle_id),
                "name": "Honda Activa",
            }],
        )

    def test_complete_vehicle_service_workflow(self):
        vehicle_id = self.create_vehicle()

        result = self.run_command(
            "add-service",
            vehicle_id,
            "--date", date.today().isoformat(),
            "--km", "10000",
            "--notes", "Oil and filter changed",
        )

        history = self.run_command("history", vehicle_id)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], result["service_id"])
        self.assertEqual(history[0]["odometer_km"], 10000)
        self.assertEqual(
            history[0]["notes"],
            "Oil and filter changed",
        )

        status = self.run_command(
            "status",
            vehicle_id,
            "--current-km", "15000",
            "--interval-km", "5000",
            "--interval-days", "180",
        )

        self.assertTrue(status["is_due"])
        self.assertEqual(status["remaining_km"], 0)
        self.assertEqual(status["next_service_km"], 15000)

    def test_status_uses_latest_service_date_not_insertion_order(self):
        vehicle_id = self.create_vehicle()

        self.run_command(
            "add-service",
            vehicle_id,
            "--date", "2020-03-01",
            "--km", "15000",
        )
        self.run_command(
            "add-service",
            vehicle_id,
            "--date", "2020-01-01",
            "--km", "10000",
        )

        status = self.run_command(
            "status",
            vehicle_id,
            "--current-km", "16000",
            "--interval-km", "5000",
            "--interval-days", "180",
        )

        self.assertEqual(status["next_service_km"], 20000)
        self.assertEqual(status["remaining_km"], 4000)
        self.assertEqual(
            status["next_service_date"],
            "2020-08-28",
        )
        self.assertTrue(status["is_due"])

    def test_accepts_zero_mileage(self):
        vehicle_id = self.create_vehicle()

        self.run_command(
            "add-service",
            vehicle_id,
            "--date", date.today().isoformat(),
            "--km", "0",
        )

        status = self.run_command(
            "status",
            vehicle_id,
            "--current-km", "0",
            "--interval-km", "5000",
            "--interval-days", "180",
        )

        self.assertEqual(status["remaining_km"], 5000)
        self.assertFalse(status["is_due"])

    def test_rejects_blank_vehicle_name(self):
        self.assert_command_error(
            ["add-vehicle", "   "],
            "Vehicle name must be non-empty text",
        )

    def test_rejects_invalid_and_noncanonical_dates(self):
        vehicle_id = self.create_vehicle()

        for value in (
            "invalid",
            "2020-02-30",
            "20200101",
            "2020-01-01T12:00:00",
        ):
            with self.subTest(value=value):
                self.assert_command_error(
                    [
                        "add-service",
                        vehicle_id,
                        "--date", value,
                        "--km", "1000",
                    ],
                    "YYYY-MM-DD",
                )

        self.assertEqual(
            self.run_command("history", vehicle_id),
            [],
        )

    def test_rejects_future_service_date(self):
        vehicle_id = self.create_vehicle()
        tomorrow = date.today() + timedelta(days=1)

        self.assert_command_error(
            [
                "add-service",
                vehicle_id,
                "--date", tomorrow.isoformat(),
                "--km", "1000",
            ],
            "cannot be in the future",
        )

    def test_rejects_missing_vehicle(self):
        self.assert_command_error(
            ["history", "999"],
            "Vehicle does not exist",
        )

    def test_status_requires_service_history(self):
        vehicle_id = self.create_vehicle()

        self.assert_command_error(
            [
                "status",
                vehicle_id,
                "--current-km", "1000",
                "--interval-km", "5000",
                "--interval-days", "180",
            ],
            "Record a service",
        )

    def test_rejects_current_mileage_below_last_service(self):
        vehicle_id = self.create_vehicle()

        self.run_command(
            "add-service",
            vehicle_id,
            "--date", "2020-01-01",
            "--km", "10000",
        )

        self.assert_command_error(
            [
                "status",
                vehicle_id,
                "--current-km", "9999",
                "--interval-km", "5000",
                "--interval-days", "180",
            ],
            "current_km cannot be below last_service_km",
        )

    def test_rejects_zero_service_intervals(self):
        vehicle_id = self.create_vehicle()

        self.run_command(
            "add-service",
            vehicle_id,
            "--date", "2020-01-01",
            "--km", "10000",
        )

        for interval_km, interval_days in (("0", "180"), ("5000", "0")):
            with self.subTest(
                interval_km=interval_km,
                interval_days=interval_days,
            ):
                self.assert_command_error(
                    [
                        "status",
                        vehicle_id,
                        "--current-km", "10000",
                        "--interval-km", interval_km,
                        "--interval-days", interval_days,
                    ],
                    "must be at least 1",
                )

    def test_rejects_oversized_storage_integers(self):
        vehicle_id = self.create_vehicle()
        oversized = str(2**63)

        self.assert_command_error(
            [
                "add-service",
                vehicle_id,
                "--date", "2020-01-01",
                "--km", oversized,
            ],
            "odometer_km must be at most",
        )

        self.assert_command_error(
            ["history", oversized],
            "vehicle_id must be at most",
        )

    def test_rejects_non_integer_argument(self):
        self.assert_command_error(
            ["history", "abc"],
            "invalid int value",
        )

    def test_requires_subcommand(self):
        self.assert_command_error([], "required")

    def test_requires_service_arguments(self):
        vehicle_id = self.create_vehicle()

        self.assert_command_error(
            ["add-service", vehicle_id],
            "required",
        )

    def test_database_error_has_nonzero_exit_and_no_traceback(self):
        invalid_path = str(
            Path(self.directory.name) / "missing" / "services.db"
        )

        output = io.StringIO()
        errors = io.StringIO()

        with redirect_stdout(output), redirect_stderr(errors):
            with self.assertRaises(SystemExit) as caught:
                main([
                    "--db",
                    invalid_path,
                    "vehicles",
                ])

        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("Error:", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_help_does_not_create_database(self):
        output = io.StringIO()

        with redirect_stdout(output):
            with self.assertRaises(SystemExit) as caught:
                main([
                    "--db",
                    self.database,
                    "--help",
                ])

        self.assertEqual(caught.exception.code, 0)
        self.assertIn("add-vehicle", output.getvalue())
        self.assertFalse(Path(self.database).exists())

    def test_module_entry_point(self):
        project_root = Path(__file__).resolve().parents[1]

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "servicetrack",
                "--db",
                self.database,
                "vehicles",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=15,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()