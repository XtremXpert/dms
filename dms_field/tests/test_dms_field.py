# Copyright 2020 Creu Blanca
# Copyright 2024 Tecnativa - Víctor Martínez
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests import new_test_user
from odoo.tools import mute_logger

from odoo.addons.base.tests.common import BaseCommon


class TestDmsField(BaseCommon):
    # Odoo 20 : BaseCommon bascule chaque test sur un utilisateur de test ; ces
    # tests préparent leurs données en superutilisateur, comme en 18.0.
    _test_user_groups = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))
        cls.user_a = new_test_user(cls.env, login="test-user-a")
        cls.group = cls.env["res.groups"].create(
            {"name": "Test group", "user_ids": [(4, cls.user_a.id)]}
        )
        cls.user_b = new_test_user(cls.env, login="test-user-b")
        cls.template = cls.env.ref("dms_field.field_template_partner")
        cls.template.group_ids.group_ids = [(4, cls.group.id)]
        cls.template.group_ids.explicit_user_ids = [(4, cls.user_b.id)]
        cls.storage = cls.template.storage_id
        cls.directory = cls.template.dms_directory_ids
        cls.subdirectory_1 = cls.env["dms.directory"].create(
            {
                "name": "Test subdirectory 1",
                "parent_id": cls.directory.id,
                "storage_id": cls.storage.id,
            }
        )
        cls.subdirectory_2 = cls.env["dms.directory"].create(
            {
                "name": "Test subdirectory 2",
                "parent_id": cls.directory.id,
                "storage_id": cls.storage.id,
            }
        )
        cls.partner = (
            cls.env["res.partner"]
            .with_context(skip_track_dms_field_template=True)
            .create({"name": "DEMO Partner"})
        )

    def _create_directory_vals(self, record):
        return {
            "storage_id": self.storage.id,
            "is_root_directory": True,
            "name": record.display_name,
            "res_model": record._name,
            "res_id": record.id,
        }

    def test_check_constrain_multi_directory(self):
        self.env["dms.directory"].create(self._create_directory_vals(self.partner))
        with self.assertRaises(ValidationError):
            self.env["dms.directory"].create(self._create_directory_vals(self.partner))

    def test_check_constrain_not_root(self):
        directory = self.env["dms.directory"].create(
            self._create_directory_vals(self.partner)
        )
        with self.assertRaises(ValidationError):
            self.env["dms.directory"].create(
                {
                    "parent_id": directory.id,
                    "name": "Second Directory",
                    "res_model": self.partner._name,
                    "res_id": self.partner.id,
                }
            )

    def test_js_tree(self):
        self.assertTrue(
            any(
                r["id"] == f"storage_{self.storage.id}"
                for r in self.storage.get_js_tree_data()
            )
        )

    def test_dms_access_group_constrains_dms_field_ref(self):
        group = self.env["dms.access.group"].create(
            {
                "name": "Test 1",
                "dms_field_ref": f"{self.partner._name},{self.partner.id}",
            }
        )
        with self.assertRaises(UserError):
            group.copy({"name": "Test 2"})

    def test_dms_access_group_company_dms_field_ref_01(self):
        self.partner.company_id = False
        group = self.env["dms.access.group"].create(
            {
                "name": "Test 1",
                "dms_field_ref": f"{self.partner._name},{self.partner.id}",
            }
        )
        self.assertFalse(group.company_id)

    def test_dms_access_group_company_dms_field_ref_02(self):
        self.company = self.env.company
        self.partner.company_id = self.company
        group = self.env["dms.access.group"].create(
            {
                "name": "Test 1",
                "dms_field_ref": f"{self.partner._name},{self.partner.id}",
            }
        )
        self.assertEqual(group.company_id, self.company)

    def test_template_directory(self):
        self.assertTrue(self.template.dms_directory_ids)
        self.assertIn(
            self.template.group_ids, self.template.dms_directory_ids.group_ids
        )
        # The template directory is not a root: it lives under the directory
        # that gathers the directories of the model.
        self.assertEqual(
            self.template.dms_directory_ids.parent_id,
            self.template._get_root_directory(),
        )

    def test_root_directory_groups_records(self):
        """The directories of the records are grouped in one directory."""
        root_directory = self.template._get_root_directory()
        self.assertEqual(root_directory.name, self.template._get_root_directory_name())
        self.assertTrue(root_directory.is_root_directory)
        self.assertFalse(root_directory.res_model)
        self.assertFalse(root_directory.parent_id)
        self.assertEqual(root_directory.group_ids, self.template.group_ids)
        partner_1 = self.env["res.partner"].create({"name": "Grouped 1"})
        partner_1.invalidate_model()
        self.assertEqual(partner_1.dms_directory_ids.parent_id, root_directory)
        partner_2 = self.env["res.partner"].create({"name": "Grouped 2"})
        partner_2.invalidate_model()
        self.assertEqual(partner_2.dms_directory_ids.parent_id, root_directory)
        # One single root directory is created for the model.
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

    def test_root_directory_reused_when_template_directory_named_after_model(self):
        """A template directory already named after the model is a valid root.

        Upgraded databases keep the template directory created in install mode
        at the storage root: it is reused instead of raising on the name.
        """
        template_directory = self.directory
        root_directory = self.template._get_root_directory()
        root_name = root_directory.name
        template_directory.write({"parent_id": False, "is_root_directory": True})
        root_directory.unlink()
        template_directory.write({"name": root_name})
        self.assertEqual(self.template._get_root_directory(), template_directory)

    def test_root_directory_skipped_with_model_ids(self):
        """A storage restricted to its models keeps the record directories at
        the root: a directory without a record would break its constraint."""
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
        """Directories linked to a record are never copied as template
        structure."""
        record_directory = self.env["dms.directory"].create(
            {
                "name": "A record directory",
                "parent_id": self.directory.id,
                "storage_id": self.storage.id,
                "res_model": self.partner._name,
                "res_id": self.partner.id,
            }
        )
        partner = self.env["res.partner"].create({"name": "Copied structure"})
        partner.invalidate_model()
        child_names = partner.dms_directory_ids.child_directory_ids.mapped("name")
        self.assertNotIn(record_directory.name, child_names)
        self.assertIn(self.subdirectory_1.name, child_names)
        self.assertIn(self.subdirectory_2.name, child_names)

    @mute_logger("odoo.models.unlink")
    def test_creation_process_01(self):
        self.assertFalse(self.partner.dms_directory_ids)
        template = self.env["dms.field.template"].with_context(
            res_model=self.partner._name, res_id=self.partner.id
        )
        template.create_dms_directory()
        self.partner.invalidate_model()
        self.assertEqual(self.partner.dms_directory_ids.name, self.partner.display_name)
        child_names = self.partner.dms_directory_ids.mapped("child_directory_ids.name")
        directory_0 = self.partner.dms_directory_ids[0]
        self.assertEqual(directory_0.parent_id, self.template._get_root_directory())
        self.assertFalse(directory_0.is_root_directory)
        self.assertFalse(directory_0.inherit_group_ids)
        self.assertIn(self.template.group_ids, directory_0.group_ids)
        self.assertIn(self.group, directory_0.group_ids.group_ids)
        self.assertIn(self.partner, directory_0.mapped("group_ids.dms_field_ref"))
        group_custom = directory_0.group_ids.filtered("dms_field_ref")
        self.assertTrue(group_custom.perm_create)
        self.assertTrue(group_custom.perm_write)
        self.assertTrue(group_custom.perm_unlink)
        self.assertIn(self.user_b, directory_0.group_ids.explicit_user_ids)
        self.assertIn(self.user_a, directory_0.group_ids.users)
        self.assertIn(self.user_b, directory_0.group_ids.users)
        self.assertIn(self.subdirectory_1.name, child_names)
        self.assertIn(self.subdirectory_2.name, child_names)
        with self.assertRaises(ValidationError):
            template.create_dms_directory()
        # Remove folder: El grupo de acceso todavía existe
        old_groups = directory_0.group_ids
        directory_0.unlink()
        dms_field_ref_value = f"{self.partner._name},{self.partner.id}"
        total = self.env["dms.access.group"].search_count(
            [("dms_field_ref", "=", dms_field_ref_value)]
        )
        self.assertEqual(total, 1)
        # Create directory again (access groups are the same)
        template.create_dms_directory()
        self.partner.invalidate_model()
        directory_0 = self.partner.dms_directory_ids[0]
        self.assertEqual(directory_0.group_ids, old_groups)

    def test_creation_process_01_with_parent(self):
        self.assertFalse(self.partner.dms_directory_ids)
        self.template.parent_directory_id = self.template.storage_id.root_directory_ids[
            :1
        ]
        template = self.env["dms.field.template"].with_context(
            res_model=self.partner._name, res_id=self.partner.id
        )
        template.create_dms_directory()
        self.partner.invalidate_model()
        self.assertEqual(self.partner.dms_directory_ids.name, self.partner.display_name)
        directory_0 = self.partner.dms_directory_ids[0]
        self.assertEqual(directory_0.parent_id, self.template.parent_directory_id)
        self.assertFalse(directory_0.is_root_directory)
        self.assertFalse(directory_0.inherit_group_ids)
        self.assertIn(self.template.group_ids, directory_0.group_ids)
        self.assertIn(self.group, directory_0.group_ids.group_ids)
        self.assertIn(self.user_b, directory_0.group_ids.explicit_user_ids)
        self.assertIn(self.user_a, directory_0.group_ids.users)
        self.assertIn(self.user_b, directory_0.group_ids.users)

    def test_creation_process_02(self):
        partner_1 = self.env["res.partner"].create({"name": "Test partner 1"})
        partner_1.invalidate_model()
        directory_1 = partner_1.dms_directory_ids[0]
        self.assertEqual(directory_1.parent_id, self.template._get_root_directory())
        self.assertFalse(directory_1.is_root_directory)
        self.assertFalse(directory_1.inherit_group_ids)
        partner_2 = (
            self.env["res.partner"]
            .with_context(skip_track_dms_field_template=True)
            .create({"name": "Test partner 2"})
        )
        partner_2.invalidate_model()
        self.assertFalse(partner_2.dms_directory_ids)

    def test_creation_process_02_with_parent(self):
        self.template.parent_directory_id = self.template.storage_id.root_directory_ids[
            :1
        ]
        partner_1 = self.env["res.partner"].create({"name": "Test partner 1"})
        partner_1.invalidate_model()
        directory_1 = partner_1.dms_directory_ids[0]
        self.assertEqual(directory_1.parent_id, self.template.parent_directory_id)
        self.assertFalse(directory_1.is_root_directory)
        self.assertFalse(directory_1.inherit_group_ids)
        partner_2 = (
            self.env["res.partner"]
            .with_context(skip_track_dms_field_template=True)
            .create({"name": "Test partner 2"})
        )
        partner_2.invalidate_model()
        self.assertFalse(partner_2.dms_directory_ids)

    def test_creation_process_03(self):
        self.template.directory_format_name = "{{object.name}}-{{object.ref}}"
        partner_1 = self.env["res.partner"].create(
            {"name": "TEST-PARTNER1", "ref": "CUSTOM-REF"}
        )
        partner_1.invalidate_model()
        self.assertEqual(
            partner_1.dms_directory_ids.name, f"{partner_1.name}-{partner_1.ref}"
        )

    def test_parents(self):
        directory = self.env["dms.directory"].create(
            self._create_directory_vals(self.partner)
        )
        self.assertEqual(
            directory.search_read_parents([("id", "=", directory.id)], fields=["id"])[
                0
            ],
            {"id": directory.id},
        )
        self.assertEqual(
            directory.search_read_parents(
                [("id", "=", directory.id)], fields=["id", "name"]
            )[0],
            {"id": directory.id, "name": directory.name},
        )
        self.assertIn(
            {"id": directory.id, "name": directory.name},
            directory.search_read_parents(fields=["id", "name"]),
        )

    def test_child_values(self):
        """Values of the child directory in the template
        are propagated to the new directories."""
        # Arrange
        partner = self.partner
        access_group = self.env["dms.access.group"].create(
            {
                "name": "Test Access group",
            }
        )
        child_dir = self.subdirectory_1
        child_dir.inherit_group_ids = False
        child_dir.group_ids = access_group

        # Act
        self.env["dms.field.template"].with_context(
            res_model=partner._name,
            res_id=partner.id,
        ).create_dms_directory()

        # Assert
        partner.invalidate_model()
        new_subdirectory_1 = partner.dms_directory_ids.child_directory_ids.filtered(
            lambda d, dir_name=child_dir.name: d.name == dir_name
        )
        self.assertFalse(new_subdirectory_1.inherit_group_ids)
        self.assertEqual(new_subdirectory_1.group_ids, access_group)

        new_subdirectory_2 = partner.dms_directory_ids.child_directory_ids.filtered(
            lambda d, dir_name=self.subdirectory_2.name: d.name == dir_name
        )
        self.assertTrue(new_subdirectory_2.inherit_group_ids)
        self.assertIn(self.group, new_subdirectory_2.complete_group_ids.group_ids)

    def test_parents_hidden_parent(self):
        """Un sous-répertoire dont le parent n'est pas dans le résultat est
        lui-même de premier niveau (le parent pourrait être illisible)."""
        root = self.env["dms.directory"].create(
            self._create_directory_vals(self.partner)
        )
        child = self.env["dms.directory"].create(
            {"name": "Enfant", "parent_id": root.id, "storage_id": self.storage.id}
        )
        Directory = self.env["dms.directory"]
        self.assertEqual(Directory.search_parents([("id", "in", child.ids)]), child)
        self.assertEqual(
            Directory.search_parents([("id", "in", (root | child).ids)]), root
        )
        self.assertEqual(
            Directory.search_parents([("id", "in", (root | child).ids)], count=True), 1
        )
        self.assertFalse(Directory.search_parents([("id", "in", [])]))

    def test_form_view_embeds_dms_list(self):
        """La sous-vue <dms_list> du champ est analysée avec dms.directory."""
        arch = self.env["res.partner"].get_views([(False, "form")])["views"]["form"][
            "arch"
        ]
        self.assertIn("<dms_list", arch)
        # Vue livrée en données (pas seulement en démo).
        self.assertTrue(self.env.ref("dms_field.view_partner_form", False))
        views = self.env["dms.storage"].get_views([(False, "dms_list")])
        self.assertIn("dms_list", views["views"])

    def test_form_without_directory_access(self):
        """Un interne sans accès au répertoire d'un contact peut ouvrir la
        fiche : la sous-vue dms_list ne lit aucun champ des répertoires."""
        template = self.env["dms.field.template"].with_context(
            res_model=self.partner._name, res_id=self.partner.id
        )
        directory = template.create_dms_directory()
        outsider = new_test_user(self.env, login="test-outsider")
        form = (
            self.env["res.partner"]
            .with_user(outsider)
            .get_views([(False, "form")])["views"]["form"]["arch"]
        )
        # Le client construit sa spécification de lecture depuis la sous-vue :
        # aucun champ -> aucun read sur les répertoires (ids seulement).
        subview = etree.fromstring(form).xpath(
            "//field[@name='dms_directory_ids']/dms_list"
        )
        self.assertTrue(subview)
        self.assertFalse(subview[0].xpath(".//field"))
        result = self.partner.with_user(outsider).web_read({"dms_directory_ids": {}})
        self.assertEqual(result[0]["dms_directory_ids"], directory.ids)
        self.assertFalse(
            self.env["dms.directory"]
            .with_user(outsider)
            .search([("id", "=", directory.id)])
        )

    def test_storage_without_models_can_change_type(self):
        """Un stockage sans modèle lié garde des répertoires « libres » et
        peut changer de type (ex. base de données -> fichier)."""
        storage = self.env["dms.storage"].create(
            {"name": "Stockage libre", "save_type": "database"}
        )
        self.env["dms.directory"].create(
            {
                "name": "Racine libre",
                "is_root_directory": True,
                "storage_id": storage.id,
                "group_ids": [(6, 0, self.template.group_ids.ids)],
            }
        )
        storage.write({"save_type": "file"})
        self.assertEqual(storage.save_type, "file")

    def test_storage_models_inconsistent_directory(self):
        """Avec des modèles liés, une racine d'un autre modèle est refusée."""
        directory = self.env["dms.directory"].create(
            self._create_directory_vals(self.partner)
        )
        with self.assertRaises(ValidationError):
            directory.storage_id.model_ids = self.env.ref("base.model_res_users")
