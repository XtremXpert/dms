# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.tests import new_test_user

from odoo.addons.base.tests.common import BaseCommon
from odoo.addons.dms_field.tests.common import DmsFieldTestMixin


class TestModelDirectory(DmsFieldTestMixin, BaseCommon):
    _test_user_groups = ()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.template = cls._create_partner_template()
        cls.directory = cls.template.dms_directory_ids

    def _create_partner(self, name):
        partner = self.env["res.partner"].create({"name": name})
        partner.invalidate_recordset(["dms_directory_ids"])
        return partner

    def test_template_directory_is_not_a_root(self):
        self.assertEqual(
            self.directory.parent_id, self.template._get_root_directory()
        )
        self.assertFalse(self.directory.is_root_directory)

    def test_root_directory_gathers_records(self):
        root_directory = self.template._get_root_directory()
        self.assertEqual(
            root_directory.name, self.template._get_root_directory_name()
        )
        self.assertTrue(root_directory.is_root_directory)
        self.assertFalse(root_directory.res_model)
        self.assertFalse(root_directory.parent_id)
        partner_1 = self._create_partner("Grouped 1")
        partner_1.invalidate_recordset(["dms_directory_ids"])
        partner_1.with_context(test_dms_field=True).dms_directory_ids.invalidate_recordset()
        self.assertEqual(partner_1.dms_directory_ids.parent_id, root_directory)
        partner_2 = self._create_partner("Grouped 2")
        partner_2.invalidate_recordset(["dms_directory_ids"])
        self.assertEqual(partner_2.dms_directory_ids.parent_id, root_directory)
        self.assertEqual(
            self.env["dms.directory"].search_count(
                [
                    ("storage_id", "=", self.storage.id),
                    ("parent_id", "=", False),
                    ("name", "=", root_directory.name),
                ]
            ),
            1,
        )

    def test_root_directory_reused_when_template_dir_is_named_after_model(self):
        template_directory = self.directory
        root_directory = self.template._get_root_directory()
        root_name = root_directory.name
        template_directory.write({"parent_id": False, "is_root_directory": True})
        root_directory.unlink()
        template_directory.write({"name": root_name})
        self.assertEqual(self.template._get_root_directory(), template_directory)

    def test_root_directory_skipped_for_storages_restricted_to_models(self):
        storage = self.env["dms.storage"].create(
            {
                "name": "Storage with models",
                "save_type": "database",
                "model_ids": [(6, 0, [self.env.ref("base.model_res_users").id])],
            }
        )
        template = self.env["dms.field.template"].create(
            {
                "name": "Users",
                "storage_id": storage.id,
                "model_id": self.env.ref("base.model_res_users").id,
                "group_ids": [(6, 0, self.template.group_ids.ids)],
            }
        )
        self.assertFalse(template._get_root_directory())
        user = new_test_user(self.env, login="test-user-model-directory")
        directory = template.with_context(
            res_model="res.users", res_id=user.id
        ).create_dms_directory()
        self.assertTrue(directory.is_root_directory)
        self.assertFalse(directory.parent_id)
        self.assertEqual(directory.storage_id, storage)

    def test_child_directories_ignore_record_directories(self):
        holder = (
            self.env["res.partner"]
            .with_context(skip_track_dms_field_template=True)
            .create({"name": "Holder"})
        )
        record_directory = self.env["dms.directory"].create(
            {
                "name": "A record directory",
                "parent_id": self.directory.id,
                "storage_id": self.storage.id,
                "res_model": "res.partner",
                "res_id": holder.id,
            }
        )
        self.env["dms.directory"].create(
            {
                "name": "Template child",
                "parent_id": self.directory.id,
                "storage_id": self.storage.id,
            }
        )
        partner = self._create_partner("Copied structure")
        child_names = partner.dms_directory_ids.child_directory_ids.mapped("name")
        self.assertIn("Template child", child_names)
        self.assertNotIn(record_directory.name, child_names)
