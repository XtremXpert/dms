# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Les droits DMS sont calculés en SQL sur des relations stockées
(groupes complets des dossiers, utilisateurs des groupes d'accès) : une
modification faite dans la même transaction doit être vue sans flush explicite.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user
from odoo.tools import mute_logger

from .common import DocumentsBaseCase


class TestAccessWithoutFlush(DocumentsBaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.create_storage(save_type="database")
        cls.other_user = new_test_user(
            cls.env, login="dms-other", groups="dms.group_dms_user"
        )

    def _new_group(self, users, name="Groupe même transaction", **perms):
        return self.access_group_model.create(
            {
                "name": name,
                "perm_create": True,
                "perm_write": True,
                "perm_unlink": True,
                "explicit_user_ids": [Command.set(users.ids)],
                **perms,
            }
        )

    def _new_directory(self, group):
        return self.directory_model.create(
            {
                "name": f"Dossier {group.name}",
                "is_root_directory": True,
                "storage_id": self.storage.id,
                "group_ids": [Command.set(group.ids)],
            }
        )

    def test_group_directory_file_same_transaction(self):
        user = new_test_user(self.env, login="dms-fresh", groups="dms.group_dms_user")
        directory = self._new_directory(self._new_group(user))
        file = self.file_model.with_user(user).create(
            {
                "name": "nouveau.txt",
                "directory_id": directory.id,
                "content": self.content_base64(),
            }
        )
        self.assertTrue(file.with_user(user).permission_read)
        self.assertIn(directory, self.directory_model.with_user(user).search([]))

    def test_user_added_to_group_sees_directory(self):
        directory = self._new_directory(self._new_group(self.dms_user))
        self.env.flush_all()
        self.assertNotIn(
            directory, self.directory_model.with_user(self.other_user).search([])
        )
        directory.group_ids.explicit_user_ids = [Command.link(self.other_user.id)]
        self.assertIn(
            directory, self.directory_model.with_user(self.other_user).search([])
        )
        self.assertTrue(directory.with_user(self.other_user).has_access("read"))

    def test_user_removed_from_group_loses_access(self):
        group = self._new_group(self.dms_user | self.other_user)
        directory = self._new_directory(group)
        self.env.flush_all()
        group.explicit_user_ids = [Command.unlink(self.other_user.id)]
        self.assertNotIn(
            directory, self.directory_model.with_user(self.other_user).search([])
        )
        self.assertFalse(directory.with_user(self.other_user).has_access("read"))

    def test_permission_change_applies_immediately(self):
        group = self._new_group(self.other_user)
        directory = self._new_directory(group)
        self.env.flush_all()
        vals = {"directory_id": directory.id, "content": self.content_base64()}
        files = self.file_model.with_user(self.other_user)
        # Garde (passait déjà avant to_flush) ; témoin : création acceptée
        # tant que le droit est actif.
        files.create(dict(vals, name="accepté.txt"))
        group.perm_create = False
        with (
            mute_logger("odoo.addons.base.models.ir_access"),
            self.assertRaises(AccessError),
        ):
            files.create(dict(vals, name="refusé.txt"))

    def test_no_access_group_means_no_access(self):
        # Garde du filtered_domain en sudo (Odoo 20 évalue has_access en sudo).
        directory = self._new_directory(self._new_group(self.dms_user))
        as_other = directory.with_user(self.other_user)
        self.assertTrue(directory.with_user(self.dms_user).has_access("read"))
        self.assertFalse(as_other.has_access("read"))
        self.assertFalse(as_other.has_access("write"))
        with (
            mute_logger("odoo.addons.base.models.ir_access"),
            self.assertRaises(AccessError),
        ):
            as_other.check_access("read")

    def test_tag_panel_counts_only_readable_files(self):
        category = self.category_model.create({"name": "Catégorie panneau"})
        tag = self.tag_model.create(
            {"name": "Confidentiel", "category_id": category.id}
        )
        visible = self._new_directory(self._new_group(self.other_user))
        private = self._new_directory(self._new_group(self.dms_user, name="Privé"))
        for i, directory in enumerate((visible, private, private)):
            self.file_model.create(
                {
                    "name": f"fichier-{i}.txt",
                    "directory_id": directory.id,
                    "content": self.content_base64(),
                    "tag_ids": [Command.link(tag.id)],
                }
            )

        def count(user, **kwargs):
            values = self.file_model.with_user(user).search_panel_select_multi_range(
                "tag_ids", **kwargs
            )
            return {v["id"]: v["count"] for v in values}

        self.assertEqual(count(self.other_user).get(tag.id), 1)
        self.assertEqual(count(self.dms_user).get(tag.id), 2)
        self.assertNotIn(
            tag.id,
            count(self.other_user, category_domain=[("directory_id", "=", private.id)]),
        )
