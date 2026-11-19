# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models
from odoo.exceptions import UserError

# Mime types the browser can render natively. They mirror the lists used by the
# web client file viewer, so that the dialog and the rest of Odoo agree on what
# is previewable.
DMS_PREVIEW_IMAGE_MIMETYPES = frozenset(
    {
        "image/bmp",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/svg+xml",
        "image/tiff",
        "image/webp",
        "image/x-icon",
    }
)

# ``dms.file/render_text`` only accepts the mime types supported by
# ``mail`` (it reuses the attachment text viewer), keep both lists in sync.
DMS_PREVIEW_TEXT_MIMETYPES = frozenset(
    {
        "application/javascript",
        "application/json",
        "application/xml",
        "text/css",
        "text/csv",
        "text/html",
        "text/markdown",
        "text/plain",
        "text/xml",
    }
)

# Office formats have no native browser preview: they get a placeholder unless
# ONLYOFFICE is installed. The extension is used because the guessed mime type
# of an office document is often "application/zip" or "application/octet-stream".
DMS_PREVIEW_OFFICE_EXTENSIONS = frozenset(
    {
        "csv",
        "doc",
        "docm",
        "docx",
        "dot",
        "dotm",
        "dotx",
        "epub",
        "fodp",
        "fods",
        "fodt",
        "htm",
        "html",
        "key",
        "numbers",
        "odg",
        "odp",
        "ods",
        "odt",
        "otp",
        "ots",
        "ott",
        "pages",
        "pdf",
        "pot",
        "potm",
        "potx",
        "pps",
        "ppsm",
        "ppsx",
        "ppt",
        "pptm",
        "pptx",
        "rtf",
        "sxi",
        "sxc",
        "sxw",
        "vsdm",
        "vsdx",
        "vssm",
        "vssx",
        "vstm",
        "vstx",
        "wps",
        "wpt",
        "xls",
        "xlsb",
        "xlsm",
        "xlsx",
        "xlt",
        "xltm",
        "xltx",
    }
)


def dms_preview_category(mimetype, extension=""):
    """Rendering family of a file, from its mime type and its extension.

    One of ``image``, ``pdf``, ``text``, ``video``, ``audio``, ``office`` or
    ``other``. Pure function, so the classification is testable on its own.
    """
    mimetype = (mimetype or "").lower()
    extension = (extension or "").lower().strip(".")
    if mimetype in DMS_PREVIEW_IMAGE_MIMETYPES:
        return "image"
    if mimetype == "application/pdf":
        return "pdf"
    if mimetype in DMS_PREVIEW_TEXT_MIMETYPES:
        return "text"
    if mimetype.startswith("video/"):
        return "video"
    if mimetype.startswith("audio/"):
        return "audio"
    # Office formats are recognized by extension: their guessed mime type is
    # often "application/zip" or "application/octet-stream".
    if extension in DMS_PREVIEW_OFFICE_EXTENSIONS:
        return "office"
    return "other"


class DmsFile(models.Model):
    _inherit = "dms.file"

    # ----------------------------------------------------------
    # Classification
    # ----------------------------------------------------------

    def _dms_preview_extension(self):
        self.ensure_one()
        name = self.name or ""
        extension = self.extension or name.rpartition(".")[2]
        return extension.strip(".").lower()

    def _dms_preview_category(self):
        """Rendering family of the file, see :func:`dms_preview_category`."""
        self.ensure_one()
        return dms_preview_category(self.mimetype, self._dms_preview_extension())

    # ----------------------------------------------------------
    # ONLYOFFICE (optional integration)
    # ----------------------------------------------------------

    def _dms_preview_onlyoffice_info(self):
        """Return the ONLYOFFICE capabilities of the file, if available.

        ``onlyoffice_odoo_dms`` adds the ``oo_*`` fields to ``dms.file``; the
        dialog only needs to know whether the format can be opened in the
        editor. Modules are loaded together, so the fields are present on the
        model exactly when the integration module is installed: this stays a
        soft dependency, no import is made.
        """
        self.ensure_one()
        if "oo_is_viewable" not in self._fields:
            return False
        return {
            "viewable": bool(self.oo_is_viewable),
            "editable": bool(self.oo_is_editable),
            "url": f"/onlyoffice/dms/editor/{self.id}",
        }

    def _dms_preview_versions_info(self):
        """Version history, when ``dms_versions`` (hermes) is installed.

        Same soft integration as ONLYOFFICE: the module adds ``version_count``
        to ``dms.file``, the field presence is the capability test.
        """
        self.ensure_one()
        if "version_count" not in self._fields:
            return False
        return {"count": self.version_count}

    def _dms_preview_onlyoffice_action(self, mode):
        self.ensure_one()
        is_edit = mode == "edit"
        return {
            "type": "ir.actions.client",
            "tag": "onlyoffice_dms.editor",
            "name": self.env._("Edit in ONLYOFFICE")
            if is_edit
            else self.env._("Preview in ONLYOFFICE"),
            "context": {"file_id": self.id, "mode": mode},
        }

    # ----------------------------------------------------------
    # Capabilities
    # ----------------------------------------------------------

    def _dms_preview_locked_by_other(self):
        self.ensure_one()
        return bool(self.is_locked and not self.is_lock_editor)

    def _dms_preview_capabilities(self):
        """Actions the current user may run on the file from the dialog."""
        self.ensure_one()
        category = self._dms_preview_category()
        can_write = (
            bool(self.permission_write) and not self._dms_preview_locked_by_other()
        )
        can_read = bool(self.permission_read)
        return {
            "can_preview": can_read and category not in ("office", "other"),
            "can_print": can_read and category in ("image", "pdf", "text"),
            "can_edit": can_write,
            "can_share": can_read,
            "can_download": can_read,
            "can_lock": can_write and not self.is_locked,
            "can_unlock": bool(self.is_lock_editor),
            "can_archive": can_write and self.active,
            "can_unarchive": can_write and not self.active,
            "can_delete": bool(self.permission_unlink)
            and not self._dms_preview_locked_by_other(),
            "can_move": can_write,
        }

    # ----------------------------------------------------------
    # Data for the dialog
    # ----------------------------------------------------------

    def _dms_preview_urls(self):
        self.ensure_one()
        base = (
            f"/web/content?id={self.id}&field=content"
            "&model=dms.file&filename_field=name"
        )
        urls = {
            "content": f"{base}&download=false",
            "download": f"{base}&download=true",
        }
        category = self._dms_preview_category()
        if category == "image":
            urls["image"] = f"/web/image/dms.file/{self.id}/content"
        elif category == "text":
            # ``dms`` serves text through a sandboxed page, never raw HTML.
            urls["text"] = f"/dms/file/render_text/{self.id}"
        return urls

    def get_dms_preview_data(self):
        """Everything the preview dialog needs, in a single round trip."""
        self.ensure_one()
        self.check_access("read")
        capabilities = self._dms_preview_capabilities()
        return {
            "id": self.id,
            "name": self.name,
            "mimetype": self.mimetype or "",
            "extension": self.extension or "",
            "category": self._dms_preview_category(),
            "human_size": self.human_size or "",
            "icon_url": self.icon_url,
            "directory_id": self.directory_id.id,
            "directory_name": self.directory_id.complete_name
            or self.directory_id.display_name,
            "create_uid_name": self.create_uid.display_name,
            "create_date": fields.Datetime.to_string(self.create_date),
            "write_date": fields.Datetime.to_string(self.write_date),
            "active": self.active,
            "is_locked": self.is_locked,
            "locked_by_name": self.locked_by.display_name,
            "tags": [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in self.tag_ids
            ],
            "capabilities": capabilities,
            "onlyoffice": self._dms_preview_onlyoffice_info(),
            "versions": self._dms_preview_versions_info(),
            "urls": self._dms_preview_urls(),
        }

    def get_dms_preview_share_link(self):
        """Portal link of the file, with its access token."""
        self.ensure_one()
        self.check_access("read")
        return self.get_base_url() + self._get_share_url(redirect=True)

    # ----------------------------------------------------------
    # Actions
    # ----------------------------------------------------------

    def action_dms_preview_details(self):
        """Open the regular form view of the file."""
        self.ensure_one()
        return self._dms_preview_form_action(self.env._("Details"))

    def action_dms_preview_edit(self):
        """Edit the file: ONLYOFFICE when it can, its Odoo form otherwise."""
        self.ensure_one()
        self.check_access("write")
        if self._dms_preview_locked_by_other():
            raise UserError(self.env._("The file is locked by another user."))
        onlyoffice = self._dms_preview_onlyoffice_info()
        if onlyoffice and onlyoffice["editable"]:
            return self._dms_preview_onlyoffice_action("edit")
        return self._dms_preview_form_action(self.env._("Edit"))

    def action_dms_preview_onlyoffice(self):
        """Preview the file in ONLYOFFICE (view only)."""
        self.ensure_one()
        self.check_access("read")
        onlyoffice = self._dms_preview_onlyoffice_info()
        if not onlyoffice or not onlyoffice["viewable"]:
            raise UserError(self.env._("This file cannot be previewed in ONLYOFFICE."))
        return self._dms_preview_onlyoffice_action("view")

    def action_dms_preview_share(self):
        """Open the portal share wizard for the file."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "dms.wizard_dms_file_share_action"
        )
        action["context"] = {
            "active_model": self._name,
            "active_id": self.id,
            "active_ids": self.ids,
        }
        return action

    def action_dms_preview_move(self):
        """Open the move wizard for that single file."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "dms.wizard_dms_file_move_act_window"
        )
        action["context"] = {
            "active_model": self._name,
            "active_id": self.id,
            "active_ids": self.ids,
        }
        return action

    def _dms_preview_form_action(self, name):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": self._name,
            "res_id": self.id,
            "views": [[False, "form"]],
            "target": "current",
        }
