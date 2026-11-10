# Copyright 2024 Tecnativa - Víctor Martínez
# Copyright 2025 Simone Rubino - PyTech
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DmsFieldTemplate(models.Model):
    _name = "dms.field.template"
    _inherit = "dms.field.mixin"
    _description = "Dms Field Template"

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        store=True,
        index=True,
    )
    storage_id = fields.Many2one(
        comodel_name="dms.storage",
        domain=[("save_type", "!=", "attachment")],
        string="Storage",
    )
    parent_directory_id = fields.Many2one(
        comodel_name="dms.directory",
        domain="[('storage_id', '=', storage_id)]",
        string="Parent directory",
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        domain=[("transient", "=", False), ("model", "!=", "dms.field.template")],
        index=True,
    )
    model = fields.Char(
        compute="_compute_model", compute_sudo=True, store=True, string="Model name"
    )
    group_ids = fields.Many2many(
        comodel_name="dms.access.group",
        string="Groups",
    )
    user_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        domain="[('model_id', '=', model_id),('relation', '=', 'res.users')]",
        string="User field",
    )
    directory_format_name = fields.Char(
        string="Directory format name",
        default="{{object.display_name}}",
        help="""You can set expressions to be used for the directory name,
        e.g.: {{object.name}}""",
    )

    @api.depends("model_id")
    def _compute_model(self):
        for item in self:
            item.model = item.model_id.model

    def _get_template_from_model(self, model):
        return self.search([("model", "=", model)], limit=1)

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

    @api.model_create_multi
    def create(self, vals_list):
        """Create dms directory automatically in the creation in install mode."""
        result = super().create(vals_list)
        if self.env.context.get("install_mode"):
            for item in result:
                item_ctx = item.with_context(res_model=item._name, res_id=item.id)
                item_ctx.create_dms_directory()
        return result

    @api.model
    def create_dms_directory(self):
        """According to the model, create the directory linked to that record
        and the subdirectories."""
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

    def _copy_files_from_directory(self, directory, new_directory):
        for file in directory.file_ids:
            file.copy({"directory_id": new_directory.id})

    def _prepare_autogenerated_group(self, record):
        group_name = self.env._(
            "Autogenerated group from %(model)s (%(name)s) #%(id)s",
            model=record._description,
            name=record.display_name,
            id=record.id,
        )
        vals = {
            "name": group_name,
            # We need to set all the permissions so that the user can manage their
            # documents (directories and files)
            "perm_create": True,
            "perm_write": True,
            "perm_unlink": True,
            "dms_field_ref": f"{record._name},{record.id}",
            "explicit_user_ids": [(5, 0)],
        }
        # Apply sudo() because the user may not have permissions to access
        # ir.model.fields.
        user_field = self.sudo().user_field_id
        if user_field:
            user = record[user_field.name]
            if user:
                vals["explicit_user_ids"] += [(4, user.id)]
        return vals

    def _get_autogenerated_group(self, record):
        """Get the existing auto-generated group or create a new one.
        The permissions of the auto-generated group should be changed
        to make sure you have the correct data.
        """
        group_model = self.env["dms.access.group"]
        group_ref = group_model._get_item_from_dms_field_ref(record)
        if group_ref:
            group_ref.write(self._prepare_autogenerated_group(record))
            return group_ref
        # Create the autogenerated group linked to the record
        return group_model.create(self._prepare_autogenerated_group(record))

    def _prepare_child_directory_vals(self, parent, template_child_directory):
        """Values to create child directories on the record.

        :param parent: Directory already created from the template for the record
        :param template_child_directory: Directory in the template directories structure
        """
        return {
            "name": template_child_directory.name,
            "is_root_directory": False,
            "parent_id": parent.id,
            "inherit_group_ids": template_child_directory.inherit_group_ids,
            "group_ids": [
                fields.Command.link(group.id)
                for group in template_child_directory.group_ids
            ],
        }

    def _create_child_directories(self, parent, directory):
        # Create child directories (all leves) + files
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

    @api.constrains("model_id")
    def _check_model_id(self):
        for template in self:
            if self.env["dms.field.template"].search(
                [("model_id", "=", template.model_id.id), ("id", "!=", template.id)]
            ):
                raise UserError(
                    self.env._("There is already a template created for this model.")
                )
