# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from odoo.addons.dms.tests.common import DocumentsBaseCase


@tagged("post_install", "-at_install")
class TestSyncDevice(DocumentsBaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.create_storage()
        cls.directory = cls.create_directory(storage=cls.storage)
        cls.other_directory = cls.create_directory(storage=cls.storage)
        cls.device = cls.env["dms.sync.device"].create(
            {"name": "Portable", "user_id": cls.dms_user.id}
        )
        cls.line = cls.env["dms.sync.scope.line"].create(
            {"device_id": cls.device.id, "directory_id": cls.directory.id}
        )
        cls.file = cls.create_file(directory=cls.directory)
        cls.outside_file = cls.create_file(directory=cls.other_directory)

    def test_a_new_device_defaults_to_two_way(self):
        self.assertEqual(self.line.mode, "two_way")
        self.assertTrue(self.line.enabled)

    def test_only_enabled_lines_are_in_scope(self):
        device = self.device.with_user(self.dms_user)
        self.assertEqual(device._scope_directories(), self.directory)
        self.line.enabled = False
        self.assertFalse(device._scope_directories())

    def test_get_scope_returns_the_profile_and_stamps_last_seen(self):
        device = self.device.with_user(self.dms_user)
        self.assertFalse(device.last_seen)
        profile = device.action_get_scope()
        self.assertEqual(profile["device"], "Portable")
        self.assertFalse(profile["paused"])
        self.assertEqual(profile["scope"][0]["directory_id"], self.directory.id)
        self.assertTrue(device.last_seen)

    def test_set_scope_edits_the_lines_of_the_owner(self):
        device = self.device.with_user(self.dms_user)
        device.action_set_scope(
            [
                {
                    "directory_id": self.directory.id,
                    "enabled": False,
                    "mode": "read_down",
                }
            ]
        )
        self.assertFalse(self.line.enabled)
        self.assertEqual(self.line.mode, "read_down")

    def test_set_scope_refuses_a_directory_out_of_scope(self):
        with self.assertRaises(AccessError):
            self.device.with_user(self.dms_user).action_set_scope(
                [
                    {
                        "directory_id": self.other_directory.id,
                        "enabled": True,
                        "mode": "two_way",
                    }
                ]
            )

    def test_set_scope_refuses_an_unknown_mode(self):
        with self.assertRaises(ValidationError):
            self.device.with_user(self.dms_user).action_set_scope(
                [
                    {
                        "directory_id": self.directory.id,
                        "enabled": True,
                        "mode": "bidirectional",
                    }
                ]
            )

    def test_a_device_cannot_be_used_by_another_user(self):
        with self.assertRaises(AccessError):
            self.device.with_user(self.dms_manager_user).action_get_scope()

    def test_list_sync_files_only_returns_files_in_scope(self):
        ids = [
            entry["id"]
            for entry in self.device.with_user(self.dms_user).action_list_sync_files()
        ]
        self.assertIn(self.file.id, ids)
        self.assertNotIn(self.outside_file.id, ids)

    def test_list_sync_files_exposes_the_checksum(self):
        entry = next(
            entry
            for entry in self.device.with_user(self.dms_user).action_list_sync_files()
            if entry["id"] == self.file.id
        )
        self.assertEqual(entry["checksum"], self.file.checksum)

    def test_get_file_returns_the_content(self):
        data = self.device.with_user(self.dms_user).action_get_file(self.file.id)
        self.assertEqual(data["name"], self.file.name)
        self.assertTrue(data["content"])

    def test_get_file_out_of_scope_is_refused(self):
        with self.assertRaises(AccessError):
            self.device.with_user(self.dms_user).action_get_file(
                self.outside_file.id
            )

    def test_get_a_missing_file_is_refused(self):
        with self.assertRaises(ValidationError):
            self.device.with_user(self.dms_user).action_get_file(10**8)

    def test_put_file_out_of_scope_is_refused(self):
        with self.assertRaises(AccessError):
            self.device.with_user(self.dms_user).action_put_file(
                self.other_directory.id, "refuse.txt", "ZGF0YQ==", False
            )

    def test_put_file_creates_then_overwrites(self):
        device = self.device.with_user(self.dms_user)
        created = device.action_put_file(
            self.directory.id, "note.txt", "ZGF0YQ==", False
        )
        dms_file = self.env["dms.file"].browse(created["id"])
        self.assertEqual(dms_file.name, "note.txt")
        updated = device.action_put_file(
            self.directory.id, "note.txt", "YXV0cmU=", False
        )
        self.assertEqual(updated["id"], dms_file.id)
        self.assertNotEqual(created["checksum"], updated["checksum"])

    def test_available_directories_apply_access_groups(self):
        restricted_group = self.env["dms.access.group"].create(
            {
                "name": "Restricted",
                "explicit_user_ids": [Command.set(self.dms_manager_user.ids)],
            }
        )
        restricted = self.env["dms.directory"].create(
            {
                "name": "Restricted directory",
                "is_root_directory": True,
                "storage_id": self.storage.id,
                "group_ids": [Command.set(restricted_group.ids)],
            }
        )
        offered = self.env["dms.sync.device"].with_user(
            self.dms_user
        ).action_available_directories()
        self.assertNotIn(restricted.id, [entry["id"] for entry in offered])
        self.env.invalidate_all()
        offered_manager = self.env["dms.sync.device"].with_user(
            self.dms_manager_user
        ).action_available_directories()
        self.assertIn(restricted.id, [entry["id"] for entry in offered_manager])

    def test_device_name_is_unique_per_user(self):
        with self.assertRaises(Exception):
            self.env["dms.sync.device"].create(
                {"name": "Portable", "user_id": self.dms_user.id}
            )
