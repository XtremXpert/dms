# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import api, models
from odoo.exceptions import ValidationError


class DmsFieldTemplate(models.Model):
    _inherit = "dms.field.template"

    def _get_root_directory_name(self):
        """Name of the directory that gathers the directories of the model."""
        self.ensure_one()
        return self.model_id.name or self.name

    def _get_root_directory(self):
        """Directory in which the directories of the records are created.

        By order of precedence:

        * the ``parent_directory_id`` explicitly configured on the template;
        * otherwise a root directory of the storage named after the model
          (created on first use), so that the directories of the records do
          not pile up at the root of the storage;
        * an empty recordset when no such directory can be used: a storage
          restricted to some models (``model_ids``) does not accept root
          directories not linked to a record.
        """
        self.ensure_one()
        if self.parent_directory_id:
            return self.parent_directory_id
        empty_directory = self.env["dms.directory"]
        if not self.storage_id or not self.model_id:
            return empty_directory
        if self.storage_id.model_ids:
            return empty_directory
        # sudo(): the directory that gathers the records of a model is shared
        # configuration, whatever the access groups of the user creating it.
        directory_model = self.env["dms.directory"].sudo()
        candidates = directory_model.search(
            [
                ("storage_id", "=", self.storage_id.id),
                ("parent_id", "=", False),
                ("is_root_directory", "=", True),
                ("name", "=", self._get_root_directory_name()),
            ]
        )
        # A template directory (created in install mode) may already hold that
        # name: it is a suitable root, and ``_create_child_directories`` keeps
        # its record children out of the copies.
        directory = candidates.filtered(lambda d: not d.res_model)[:1]
        if not directory:
            directory = candidates.filtered(
                lambda d: d.res_model == "dms.field.template"
            )[:1]
        if directory:
            return directory
        if candidates:
            # The name is already used by a directory of a record: keep the
            # previous behaviour rather than nesting records in it.
            return empty_directory
        return directory_model.create(
            {
                "name": self._get_root_directory_name(),
                "storage_id": self.storage_id.id,
                "is_root_directory": True,
                "group_ids": [(6, 0, self.group_ids.ids)],
            }
        )

    @api.model
    def create_dms_directory(self):
        """Create the directory linked to the record in the context.

        The directory of a record is created inside the directory that gathers
        the records of its model (see ``_get_root_directory``), unless the
        template configures a parent directory.
        """
        res_model = self.env.context.get("res_model")
        res_id = self.env.context.get("res_id")
        record = self.env[res_model].browse(res_id)
        directory_model = self.env["dms.directory"].sudo()
        if res_model == "dms.field.template":
            root_directory = record._get_root_directory()
            vals = {
                "storage_id": record.storage_id.id,
                "res_id": record.id,
                "res_model": record._name,
                "name": record.display_name,
                "group_ids": record.group_ids.ids,
            }
            if root_directory:
                vals.update(
                    {"parent_id": root_directory.id, "inherit_group_ids": False}
                )
            else:
                vals.update({"is_root_directory": True})
            return directory_model.create(vals)
        template = self._get_template_from_model(res_model).sudo()
        if not template:
            raise ValidationError(
                self.env._("There is no template linked to this model")
            )
        root_directory = template._get_root_directory()
        total_directories = directory_model.search_count(
            [
                ("parent_id", "=", root_directory.id),
                ("res_model", "=", res_model),
                ("res_id", "=", res_id),
                ("storage_id", "=", template.storage_id.id),
            ]
        )
        if total_directories > 0:
            raise ValidationError(
                self.env._("There is already a linked directory created.")
            )
        # Create root directory + files
        dms_directory_ids = template.dms_directory_ids
        new_directory = directory_model.create(
            template._prepare_directory_vals(dms_directory_ids, record)
        )
        self._copy_files_from_directory(dms_directory_ids, new_directory)
        # Create child directories
        self._create_child_directories(new_directory, dms_directory_ids)
        return new_directory

    def _create_child_directories(self, parent, directory):
        # Create child directories (all levels) + files
        directory_model = self.env["dms.directory"].sudo()
        # Directories linked to a record are not part of the template
        # structure: the template root directory may also hold the directories
        # of the records, they must not be copied in every new record.
        for child_directory in directory.child_directory_ids.filtered(
            lambda child: not child.res_model
        ):
            child = directory_model.create(
                self._prepare_child_directory_vals(parent, child_directory)
            )
            self._copy_files_from_directory(child_directory, child)
            self._create_child_directories(child, child_directory)

    def _prepare_directory_vals(self, directory, record):
        # Groups of the new directory will be those of the template + auto-generate
        groups = directory.group_ids or self.group_ids
        groups += self._get_autogenerated_group(record)
        directory_name = self.env["mail.render.mixin"]._render_template(
            self.directory_format_name,
            record._name,
            record.ids,
            engine="inline_template",
        )[record.id]
        root_directory = self._get_root_directory()
        vals = {
            "storage_id": (directory.storage_id or self.storage_id).id,
            "res_id": record.id,
            "res_model": record._name,
            "name": directory_name,
            "group_ids": [(4, group.id) for group in groups],
        }
        if root_directory:
            vals.update({"parent_id": root_directory.id, "inherit_group_ids": False})
        else:
            vals.update({"is_root_directory": True})
        return vals
