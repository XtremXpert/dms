# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.dms.tests.common import DocumentsBaseCase


@tagged("post_install", "-at_install")
class TestFileWizards(DocumentsBaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.create_storage()
        cls.source = cls.create_directory(storage=cls.storage)
        cls.target = cls.create_directory(storage=cls.storage)
        cls.file_1 = cls.create_file(directory=cls.source)
        cls.file_2 = cls.create_file(directory=cls.source)
        cls.tag = cls.tag_model.create({"name": "Contrat"})

    def _move_wizard(self, files, directory):
        return self.env["dms.file.move.wizard"].create(
            {
                "file_ids": [(6, 0, files.ids)],
                "directory_id": directory.id,
            }
        )

    def test_move_moves_every_selected_file(self):
        wizard = self._move_wizard(self.file_1 | self.file_2, self.target)
        wizard.action_move()
        self.assertEqual(self.file_1.directory_id, self.target)
        self.assertEqual(self.file_2.directory_id, self.target)

    def test_move_skips_files_already_in_the_target(self):
        self.file_2.directory_id = self.target
        wizard = self._move_wizard(self.file_1 | self.file_2, self.target)
        result = wizard.action_move()
        self.assertIn("1 fichier(s)", result["params"]["message"])

    def test_move_without_files_is_refused(self):
        with self.assertRaises(UserError):
            self._move_wizard(self.env["dms.file"], self.target).action_move()

    def test_move_requires_a_dms_user(self):
        with self.assertRaises(AccessError):
            self.env["dms.file.move.wizard"].with_user(self.user).create(
                {
                    "file_ids": [(6, 0, self.file_1.ids)],
                    "directory_id": self.target.id,
                }
            )

    def test_move_requires_write_access_on_the_files(self):
        """A DMS user without the file access group cannot move it."""
        outsider = self.env["res.users"].create(
            {
                "name": "Outsider",
                "login": "dms-outsider-ux",
                "group_ids": [
                    (6, 0, [self.env.ref("base.group_user").id,
                            self.env.ref("dms.group_dms_user").id])
                ],
            }
        )
        with self.assertRaises(AccessError):
            # Reading the files is already refused: the wizard cannot be fed
            wizard = self.env["dms.file.move.wizard"].with_user(outsider).create(
                {
                    "file_ids": [(6, 0, self.file_1.ids)],
                    "directory_id": self.target.id,
                }
            )
            wizard.action_move()

    def _tag_wizard(self, files, tags):
        return self.env["dms.file.tag.wizard"].create(
            {
                "file_ids": [(6, 0, files.ids)],
                "tag_ids": [(6, 0, tags.ids)],
            }
        )

    def test_tag_adds_the_tags_to_every_file(self):
        self._tag_wizard(self.file_1 | self.file_2, self.tag).action_tag()
        self.assertIn(self.tag, self.file_1.tag_ids)
        self.assertIn(self.tag, self.file_2.tag_ids)

    def test_tag_is_idempotent(self):
        self._tag_wizard(self.file_1, self.tag).action_tag()
        self._tag_wizard(self.file_1, self.tag).action_tag()
        self.assertEqual(len(self.file_1.tag_ids), 1)

    def test_tag_without_tags_is_refused(self):
        with self.assertRaises(UserError):
            self._tag_wizard(self.file_1, self.env["dms.tag"]).action_tag()

    def test_tag_without_files_is_refused(self):
        with self.assertRaises(UserError):
            self._tag_wizard(self.env["dms.file"], self.tag).action_tag()
