import json

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..hooks import (
    ALLOW_DATABASE_PARAM,
    REPORT_PARAM,
    collect_report,
    pre_init_hook,
)


@tagged("post_install", "-at_install")
class TestStorageGuard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        """Prepare the test environment and the guard parameters."""
        super().setUpClass()
        cls.Storage = cls.env["dms.storage"]
        cls.Directory = cls.env["dms.directory"]
        cls.File = cls.env["dms.file"]
        cls.parameters = cls.env["ir.config_parameter"]
        cls.dms_module = cls.env["ir.module.module"].search(
            [("name", "=", "dms")], limit=1
        )
        cls.parameters.set_str("ir_attachment.location", "file")
        cls.parameters.set_str(ALLOW_DATABASE_PARAM, "0")

    def _database_storage(self, name="Guard test storage"):
        """Create a DMS storage that saves its files in the database."""
        return self.Storage.create({"name": name, "save_type": "database"})

    def _root_directory(self, storage, name="Guard root"):
        """Create a root directory in the given storage."""
        return self.Directory.create(
            {"name": name, "storage_id": storage.id, "is_root_directory": True}
        )

    def _file(self, directory, name="guard.txt", content="Z3VhcmQ="):
        """Create a small DMS file in the given directory."""
        return self.File.create(
            {"name": name, "directory_id": directory.id, "content": content}
        )

    def _problem_codes(self):
        """Return the codes of the problems found by the diagnosis."""
        return [problem["code"] for problem in collect_report(self.env)["problems"]]

    def test_report_flags_database_storage(self):
        """A storage saving files in the database is reported."""
        self._database_storage("Guard database storage")
        report = collect_report(self.env)
        problems = [
            problem
            for problem in report["problems"]
            if problem["code"] == "storage_database"
            and "Guard database storage" in problem["title"]
        ]
        self.assertTrue(problems, report["problems"])
        problem = problems[0]
        self.assertTrue(problem["details"])
        self.assertTrue(problem["remediation"])

    def test_report_flags_pending_migration(self):
        """A storage with files waiting for a migration is reported."""
        storage = self._database_storage("Guard pending storage")
        directory = self._root_directory(storage)
        self._file(directory)
        storage.write({"save_type": "file"})
        report = collect_report(self.env)
        problems = [
            problem
            for problem in report["problems"]
            if problem["code"] == "storage_pending_migration"
            and "Guard pending storage" in problem["title"]
        ]
        self.assertTrue(problems, report["problems"])
        storage_report = next(
            item for item in report["storages"] if item["id"] == storage.id
        )
        self.assertEqual(storage_report["pending_migrations"], 1)

    def test_pre_init_hook_skips_demo_database(self):
        """A demo database only logs the problems and installs."""
        self.dms_module.demo = True
        self._database_storage("Guard demo storage")
        pre_init_hook(self.env)  # must not raise on a demo database
        report = json.loads(self.parameters.get_str(REPORT_PARAM))
        self.assertTrue(report["problems"])

    def test_pre_init_hook_raises_in_production(self):
        """A production database refuses to install and explains why."""
        self.dms_module.demo = False
        self.parameters.set_str(ALLOW_DATABASE_PARAM, "0")
        self._database_storage("Guard blocking storage")
        with self.assertRaises(UserError) as error:
            pre_init_hook(self.env)
        message = str(error.exception)
        self.assertIn("Guard blocking storage", message)
        self.assertIn("Migrate", message)
        report = json.loads(self.parameters.get_str(REPORT_PARAM))
        self.assertTrue(report["problems"])

    def test_pre_init_hook_allows_explicit_override(self):
        """The allow parameter lets the installation proceed."""
        self.dms_module.demo = False
        self.parameters.set_str(ALLOW_DATABASE_PARAM, "1")
        self._database_storage("Guard allowed storage")
        pre_init_hook(self.env)  # explicitly allowed, must not raise
        report = json.loads(self.parameters.get_str(REPORT_PARAM))
        self.assertTrue(
            any(
                "Guard allowed storage" in problem["title"]
                for problem in report["problems"]
            ),
            report["problems"],
        )

    def test_pre_init_hook_passes_with_filestore_storage(self):
        """A clean filestore storage installs without error."""
        demo_storage = self.env.ref("dms.storage_demo", raise_if_not_found=False)
        if demo_storage:
            demo_storage.write({"save_type": "file"})
            demo_storage.action_storage_migrate()
        self.dms_module.demo = False
        self.parameters.set_str("ir_attachment.location", "file")
        report = collect_report(self.env)
        self.assertFalse(report["problems"], report["problems"])
        pre_init_hook(self.env)  # must not raise
        stored = json.loads(self.parameters.get_str(REPORT_PARAM))
        self.assertFalse(stored["problems"])

    def test_wizard_reports_problems(self):
        """The diagnostic screen shows the problems and can run again."""
        self._database_storage("Guard wizard storage")
        check = self.env["dms.storage.check"].create({})
        self.assertGreater(check.problem_count, 0)
        self.assertIn("Guard wizard storage", check.report_html)
        action = check.action_recheck()
        self.assertEqual(action["target"], "new")
        self.assertFalse(action["res_id"])
