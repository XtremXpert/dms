# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
import base64

from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.dms.tests.common import DocumentsBaseCase


@tagged("post_install", "-at_install")
class TestFileVersions(DocumentsBaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.create_storage()
        cls.directory = cls.create_directory(storage=cls.storage)
        cls.file = cls.create_file(directory=cls.directory, content=cls._b64(b"v1"))

    @classmethod
    def _b64(cls, data):
        return base64.b64encode(data).decode()

    def _change_content(self, data):
        self.file.write({"content": self._b64(data)})
        self.file.invalidate_recordset(["content", "checksum"])

    def test_content_of_a_new_file_is_not_archived(self):
        self.assertFalse(self.file.version_ids)

    def test_first_change_archives_the_outgoing_content(self):
        outgoing_checksum = self.file.checksum
        self._change_content(b"v2")
        self.assertEqual(len(self.file.version_ids), 1)
        version = self.file.version_ids
        self.assertEqual(bytes(version.content), b"v1")
        self.assertEqual(version.checksum, outgoing_checksum)
        self.assertEqual(version.origin, "update")

    def test_second_change_keeps_the_whole_chain(self):
        self._change_content(b"v2")
        self._change_content(b"v3")
        self.assertEqual(len(self.file.version_ids), 2)
        archived = sorted(bytes(version.content) for version in self.file.version_ids)
        self.assertEqual(archived, [b"v1", b"v2"])

    def test_writing_the_same_content_archives_nothing(self):
        self._change_content(b"v2")
        versions = len(self.file.version_ids)
        self._change_content(b"v2")
        self.assertEqual(len(self.file.version_ids), versions)

    def test_archiving_freezes_the_metadata_of_the_outgoing_content(self):
        name = self.file.name
        self._change_content(b"v2")
        version = self.file.version_ids
        self.assertEqual(version.name, name)
        self.assertEqual(version.mimetype, self.file.mimetype)
        self.assertEqual(version.size, self.file.size)

    def test_restore_writes_the_archived_content_back(self):
        self._change_content(b"v2")
        version = self.file.version_ids
        version.action_restore()
        self.file.invalidate_recordset(["content", "checksum"])
        self.assertEqual(bytes(self.file.content), b"v1")
        # The content that was replaced by the restore is archived as well
        self.assertEqual(len(self.file.version_ids), 2)
        restore_version = self.file.version_ids.filtered(
            lambda v: v.origin == "restore"
        )
        self.assertEqual(len(restore_version), 1)
        self.assertEqual(bytes(restore_version.content), b"v2")

    def test_restoring_the_current_content_changes_nothing(self):
        """Once restored, the version IS the current content: restoring it
        again is a no-op, it must not archive itself again."""
        self._change_content(b"v2")
        version = self.file.version_ids
        version.action_restore()
        self.file.invalidate_recordset(["content", "checksum"])
        self.assertEqual(bytes(self.file.content), b"v1")
        versions = len(self.file.version_ids)
        result = version.action_restore()
        self.assertEqual(result["params"]["type"], "info")
        self.assertEqual(len(self.file.version_ids), versions)

    def test_version_count_follows_the_chain(self):
        self.assertEqual(self.file.version_count, 0)
        self._change_content(b"v2")
        self.assertEqual(self.file.version_count, 1)

    def test_a_dms_user_cannot_purge_versions(self):
        self._change_content(b"v2")
        version = self.file.version_ids
        with self.assertRaises(AccessError):
            version.with_user(self.dms_user).unlink()

    def test_a_dms_manager_can_purge_versions(self):
        self._change_content(b"v2")
        version = self.file.version_ids
        version.with_user(self.dms_manager_user).unlink()
        self.assertFalse(self.file.version_ids)
