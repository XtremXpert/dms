# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import base64

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user

from ..models.dms_file import dms_preview_category

PNG_PIXEL = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
PDF_DOCUMENT = base64.b64encode(
    b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
).decode()
TEXT_DOCUMENT = base64.b64encode(b"hello world\n").decode()
# A real office document is a zip archive; the guessed mime type is generic
# (application/zip) and the extension is what identifies the format.
ZIP_DOCUMENT = base64.b64encode(b"PK\x03\x04\x14\x00\x06\x00" + b"\x00" * 32).decode()


class TestDmsPreviewCategory(TransactionCase):
    def test_image(self):
        for mimetype in ("image/png", "image/jpeg", "image/svg+xml", "image/gif"):
            self.assertEqual(dms_preview_category(mimetype), "image", mimetype)

    def test_pdf(self):
        self.assertEqual(dms_preview_category("application/pdf"), "pdf")

    def test_text(self):
        for mimetype in (
            "text/plain",
            "text/csv",
            "text/html",
            "text/markdown",
            "application/json",
            "application/xml",
        ):
            self.assertEqual(dms_preview_category(mimetype), "text", mimetype)

    def test_video(self):
        self.assertEqual(dms_preview_category("video/mp4"), "video")

    def test_audio(self):
        self.assertEqual(dms_preview_category("audio/mpeg"), "audio")

    def test_office(self):
        # The guessed mime type of an office document is often generic, the
        # extension is what identifies the format.
        self.assertEqual(dms_preview_category("application/zip", "docx"), "office")
        self.assertEqual(
            dms_preview_category("application/octet-stream", "odt"), "office"
        )

    def test_other(self):
        self.assertEqual(dms_preview_category("application/zip", "zip"), "other")
        self.assertEqual(dms_preview_category(False, False), "other")


class TestDmsPreview(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        File = cls.env["dms.file"]
        cls.storage = cls.env["dms.storage"].create(
            {"name": "Preview storage", "save_type": "database"}
        )
        cls.access_group = cls.env["dms.access.group"].create(
            {
                "name": "Preview test group",
                "perm_create": True,
                "perm_write": True,
                "perm_unlink": True,
            }
        )
        cls.directory = cls.env["dms.directory"].create(
            {
                "name": "Preview directory",
                "storage_id": cls.storage.id,
                "is_root_directory": True,
                "group_ids": [(4, cls.access_group.id)],
            }
        )
        cls.dms_user = new_test_user(
            cls.env, login="dms-preview-user", groups="dms.group_dms_user"
        )
        cls.access_group.explicit_user_ids = [(4, cls.dms_user.id)]
        cls.text_file = File.create(
            {
                "name": "preview-notes.txt",
                "directory_id": cls.directory.id,
                "content": TEXT_DOCUMENT,
            }
        )
        cls.pdf_file = File.create(
            {
                "name": "preview-report.pdf",
                "directory_id": cls.directory.id,
                "content": PDF_DOCUMENT,
            }
        )
        cls.image_file = File.create(
            {
                "name": "preview-image.png",
                "directory_id": cls.directory.id,
                "content": PNG_PIXEL,
            }
        )
        cls.office_file = File.create(
            {
                "name": "preview-report.docx",
                "directory_id": cls.directory.id,
                "content": ZIP_DOCUMENT,
            }
        )

    def test_categories(self):
        self.assertEqual(self.text_file._dms_preview_category(), "text")
        self.assertEqual(self.pdf_file._dms_preview_category(), "pdf")
        self.assertEqual(self.image_file._dms_preview_category(), "image")
        self.assertEqual(self.office_file._dms_preview_category(), "office")

    def test_preview_data(self):
        data = self.text_file.get_dms_preview_data()
        self.assertEqual(data["id"], self.text_file.id)
        self.assertEqual(data["category"], "text")
        self.assertEqual(data["directory_id"], self.directory.id)
        self.assertEqual(data["directory_name"], self.directory.complete_name)
        self.assertIn("download=true", data["urls"]["download"])
        self.assertIn("download=false", data["urls"]["content"])
        self.assertIn(
            f"/dms/file/render_text/{self.text_file.id}", data["urls"]["text"]
        )
        if "oo_is_viewable" in self.env["dms.file"]._fields:
            # onlyoffice_odoo_dms is installed: the dialog gets the editor URL.
            self.assertEqual(
                data["onlyoffice"]["url"],
                f"/onlyoffice/dms/editor/{self.text_file.id}",
            )
        else:
            self.assertFalse(data["onlyoffice"])
        if "version_count" in self.env["dms.file"]._fields:
            # dms_versions (hermes) is installed: the version history is
            # reported to the dialog, even when the file has none yet.
            self.assertEqual(data["versions"], {"count": 0})
        else:
            self.assertFalse(data["versions"])

    def test_share_link(self):
        link = self.text_file.get_dms_preview_share_link()
        self.assertIn("/mail/view?", link)
        self.assertIn("model=dms.file", link)
        self.assertIn(f"res_id={self.text_file.id}", link)
        self.assertIn("access_token=", link)

    def test_capabilities_write_user(self):
        capabilities = self.text_file.get_dms_preview_data()["capabilities"]
        for key in (
            "can_preview",
            "can_print",
            "can_edit",
            "can_share",
            "can_download",
            "can_lock",
            "can_archive",
            "can_delete",
            "can_move",
        ):
            self.assertTrue(capabilities[key], key)
        self.assertFalse(capabilities["can_unlock"])
        self.assertFalse(capabilities["can_unarchive"])

    def test_capabilities_office_has_no_native_preview(self):
        capabilities = self.office_file.get_dms_preview_data()["capabilities"]
        self.assertFalse(capabilities["can_preview"])
        self.assertFalse(capabilities["can_print"])
        self.assertTrue(capabilities["can_download"])

    def test_capabilities_read_only_user(self):
        user = new_test_user(
            self.env, login="dms-preview-reader", groups="dms.group_dms_user"
        )
        self.env["dms.access.group"].create(
            {
                "name": "Preview read only",
                "explicit_user_ids": [(4, user.id)],
                "directory_ids": [(4, self.directory.id)],
            }
        )
        capabilities = self.text_file.with_user(user).get_dms_preview_data()[
            "capabilities"
        ]
        for key in ("can_download", "can_share", "can_preview", "can_print"):
            self.assertTrue(capabilities[key], key)
        for key in ("can_edit", "can_lock", "can_archive", "can_delete", "can_move"):
            self.assertFalse(capabilities[key], key)

    def test_capabilities_locked_by_another_user(self):
        self.text_file.lock()
        capabilities = self.text_file.with_user(self.dms_user).get_dms_preview_data()[
            "capabilities"
        ]
        self.assertTrue(capabilities["can_download"])
        self.assertFalse(capabilities["can_edit"])
        self.assertFalse(capabilities["can_unlock"])
        self.assertFalse(capabilities["can_delete"])
        self.assertFalse(capabilities["can_lock"])

    def test_action_edit_falls_back_to_the_form(self):
        action = self.text_file.action_dms_preview_edit()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "dms.file")
        self.assertEqual(action["res_id"], self.text_file.id)
        self.assertEqual(action["views"], [[False, "form"]])

    def test_action_edit_locked_file(self):
        self.text_file.lock()
        with self.assertRaises(UserError):
            self.text_file.with_user(self.dms_user).action_dms_preview_edit()

    def test_action_details(self):
        action = self.text_file.action_dms_preview_details()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_id"], self.text_file.id)

    def test_action_share(self):
        action = self.text_file.action_dms_preview_share()
        self.assertEqual(action["res_model"], "wizard.dms.share")
        self.assertEqual(action["context"]["active_model"], "dms.file")
        self.assertEqual(action["context"]["active_id"], self.text_file.id)

    def test_action_move(self):
        action = self.text_file.action_dms_preview_move()
        self.assertEqual(action["res_model"], "wizard.dms.file.move")
        self.assertEqual(action["context"]["active_ids"], self.text_file.ids)

    def test_onlyoffice_is_optional(self):
        # Without onlyoffice_odoo_dms, the integration reports itself as absent
        # and the edit action stays a regular form action.
        if "oo_is_viewable" in self.env["dms.file"]._fields:
            self.skipTest("onlyoffice_odoo_dms is installed")
        self.assertFalse(self.text_file._dms_preview_onlyoffice_info())
        with self.assertRaises(UserError):
            self.text_file.action_dms_preview_onlyoffice()
