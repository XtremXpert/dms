# Copyright 2020 Creu Blanca
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    type = fields.Selection(selection_add=[("dms_list", "DMS Tree")])

    def _get_view_info(self):
        res = super()._get_view_info()
        res["dms_list"] = {"icon": "folder"}
        return res

    def _postprocess_tag_field(self, node, name_manager, node_info):
        """Odoo 20 ne traite comme sous-vues que form/list/graph/kanban/calendar :
        une sous-vue <dms_list> d'un champ x2many doit aussi être analysée avec
        le modèle lié, sinon ses champs seraient cherchés sur le modèle parent."""
        res = super()._postprocess_tag_field(node, name_manager, node_info)
        field = name_manager.model._fields.get(node.get("name") or "")
        if field and field.relational:
            for child in node:
                if child.tag == "dms_list":
                    node_info["children"] = []
                    self._postprocess_view(
                        child,
                        field.comodel_name,
                        editable=node_info["editable"],
                        node_info=node_info,
                    )
        return res
