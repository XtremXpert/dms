# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.dms.tests.common import DocumentsBaseCase


@tagged("post_install", "-at_install")
class TestFileRequest(DocumentsBaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.create_storage()
        cls.directory = cls.create_directory(storage=cls.storage)
        cls.request = cls.env["dms.file.request"].create(
            {
                "name": "Pièce d'identité",
                "directory_id": cls.directory.id,
                "requested_to_id": cls.dms_user.id,
                "requested_by_id": cls.dms_manager_user.id,
            }
        )

    def _create_uploaded_file(self, request, name="piece.pdf"):
        return self.env["dms.file"].create(
            {
                "name": name,
                "directory_id": request.directory_id.id,
                "content": self.content_base64(),
                "request_id": request.id,
            }
        )

    def test_a_new_request_waits_for_a_document(self):
        self.assertEqual(self.request.state, "submitted")
        self.assertFalse(self.request.file_id)
        self.assertEqual(self.request.requested_by_id, self.dms_manager_user)

    def test_the_target_gets_a_reminder_activity(self):
        activity = self.request.activity_ids
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.dms_user)

    def test_the_deadline_update_moves_the_reminder(self):
        self.request.deadline = "2030-01-31"
        self.assertEqual(
            self.request.activity_ids.date_deadline.isoformat(), "2030-01-31"
        )

    def test_upload_action_presets_directory_and_request(self):
        action = self.request.action_upload()
        self.assertEqual(action["res_model"], "dms.file")
        self.assertEqual(
            action["context"]["default_directory_id"], self.directory.id
        )
        self.assertEqual(action["context"]["default_request_id"], self.request.id)

    def test_uploading_a_file_moves_the_request_to_uploaded(self):
        dms_file = self._create_uploaded_file(self.request)
        self.assertEqual(self.request.state, "uploaded")
        self.assertEqual(self.request.file_id, dms_file)

    def test_the_first_upload_wins(self):
        first = self._create_uploaded_file(self.request, name="premier.pdf")
        second = self._create_uploaded_file(self.request, name="second.pdf")
        self.assertEqual(self.request.file_id, first)
        self.assertNotEqual(self.request.file_id, second)

    def test_validate_requires_an_uploaded_document(self):
        with self.assertRaises(UserError):
            self.request.action_validate()

    def test_validate_accepts_the_document(self):
        self._create_uploaded_file(self.request)
        self.request.action_validate()
        self.assertEqual(self.request.state, "done")

    def test_a_done_request_can_no_longer_be_cancelled(self):
        self._create_uploaded_file(self.request)
        self.request.action_validate()
        with self.assertRaises(UserError):
            self.request.action_cancel()

    def test_refuse_then_reopen_clears_the_document(self):
        self._create_uploaded_file(self.request)
        self.request.action_refuse()
        self.assertEqual(self.request.state, "refused")
        self.request.action_reopen()
        self.assertEqual(self.request.state, "submitted")
        self.assertFalse(self.request.file_id)

    def test_reopen_requires_a_refused_or_cancelled_request(self):
        with self.assertRaises(UserError):
            self.request.action_reopen()

    def test_upload_action_requires_a_pending_request(self):
        self._create_uploaded_file(self.request)
        with self.assertRaises(UserError):
            self.request.action_upload()

    def test_requested_to_domain_uses_an_existing_field(self):
        """The field domain is evaluated by the form: it must be valid."""
        field = self.env["dms.file.request"]._fields["requested_to_id"]
        domain = field.domain
        if callable(domain):
            domain = domain(self.env["dms.file.request"])
        # A domain on a renamed/removed field raises here, not in the UI
        self.env["res.users"].search(domain)
