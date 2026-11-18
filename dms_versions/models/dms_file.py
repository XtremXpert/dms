# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

"""Versioning hook on dms.file: archive before the content changes."""

import logging

from odoo import api, fields, models
from odoo.tools.binary import BinaryBytes

_logger = logging.getLogger(__name__)

# The fields that actually carry the bytes, depending on the storage type.
_CONTENT_FIELDS = {"content_binary", "content_file"}


class DmsFile(models.Model):
    _inherit = "dms.file"

    version_ids = fields.One2many("dms.file.version", "file_id", string="Versions")
    version_count = fields.Integer(compute="_compute_version_count")

    @api.depends("version_ids")
    def _compute_version_count(self):
        # sudo: the count follows the file's own access, it leaks nothing
        # beyond "this file has N versions".
        for dms_file in self:
            dms_file.version_count = len(dms_file.sudo().version_ids)

    @api.model_create_multi
    def create(self, vals_list):
        """Creating a file is not a change of an existing content.

        The inverse of the computed `content` field writes through
        `content_binary` while the file is being created: archiving there
        would store the new content as a version of itself."""
        return super(
            DmsFile, self.with_context(dms_creating_file=True)
        ).create(vals_list)

    def write(self, vals):
        """Archive the current content before a new one lands.

        The inverse of the computed `content` field writes through
        `content_binary` or `content_file`: watching those keys covers
        every path (form edit, upload, restore, API). Writing `content`
        runs the inverse, which writes those keys again: the flag stops
        the chain after the first archive."""
        in_use = self.env.context
        if _CONTENT_FIELDS & set(vals) and not in_use.get("dms_creating_file"):
            if not in_use.get("dms_archiving"):
                # Rebind: super() must see the flag, the inverse runs inside it
                self = self.with_context(dms_archiving=True)
                self._archive_versions(vals)
        return super().write(vals)

    def _outgoing_content(self):
        """The bytes currently stored, before the incoming write lands.

        Reading the computed `content` field here is not possible: its cache
        already holds the value being written, so the archive would store the
        new content as a version of the old one. The stored fields are still
        untouched when the hook runs."""
        self.ensure_one()
        record = self.sudo()
        if record.content_file:
            return bytes(record.content_file)
        if record.content_binary:
            return bytes(record.content_binary)
        if record.attachment_id:
            return bytes(record.attachment_id.raw)
        return False

    def _archive_versions(self, vals):
        Version = self.env["dms.file.version"].sudo()
        new_checksum = vals.get("checksum")
        for dms_file in self:
            old = dms_file._outgoing_content()
            if not old:
                continue
            # Same content re-written: nothing to archive.
            if new_checksum and new_checksum == dms_file.checksum:
                continue
            # The archive stores the bytes as an attachment; the version
            # itself is created with the metadata of the outgoing content.
            # bytes(): `old` is a lazy proxy on the live attachment — it
            # must be frozen NOW, before super().write() replaces the
            # attachment's raw content in place.
            Version.create({
                "file_id": dms_file.id,
                "name": dms_file.name,
                "extension": dms_file.extension,
                "mimetype": dms_file.mimetype,
                "checksum": dms_file.checksum,
                "size": dms_file.size,
                "content": BinaryBytes(old),
                "origin": "restore" if self.env.context.get("dms_version_restore")
                else "update",
            })
            _logger.info("dms.file %s: version archivée (checksum %s)",
                         dms_file.id, dms_file.checksum)

    def action_view_versions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Versions — %s" % self.name,
            "res_model": "dms.file.version",
            "view_mode": "list,form",
            "domain": [("file_id", "=", self.id)],
            "context": {"default_file_id": self.id},
        }
