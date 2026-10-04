# Copyright 2017-2019 MuK IT GmbH
# Copyright 2026 Tecnativa - Víctor Martínez
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
import logging
import unicodedata

from werkzeug.exceptions import BadRequest

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.tools import BinaryBytes, str2bool
from odoo.tools.misc import replace_exceptions

from odoo.addons.mail.controllers.attachment import AttachmentController
from odoo.addons.web.controllers.binary import clean

_logger = logging.getLogger(__name__)


class OnboardingController(http.Controller):
    @http.route("/config/dms.forbidden_extensions", type="jsonrpc", auth="user")
    def forbidden_extensions(self, **_kwargs):
        params = request.env["ir.config_parameter"].sudo()
        return {
            "forbidden_extensions": params.get_str(
                "dms.forbidden_extensions", default=""
            )
        }

    @http.route("/web/binary/upload_dms_file", type="http", auth="user")
    def upload_dms_file(self, ufile, directory_id, callback=None):
        """Similar to the web upload_attachment() method, but customized to
        directly create dms.file records.

        Odoo 20 : réponse JSON (application/json) ; l'ancien mode ``callback``
        renvoyait un script jQuery, qui n'existe plus dans le client web.
        """
        directory_id = int(directory_id)
        Model = request.env["dms.file"]
        args = []
        for uploaded in request.httprequest.files.getlist("ufile"):
            filename = uploaded.filename
            if request.httprequest.user_agent.browser == "safari":
                # Safari sends NFD UTF-8 (where é is composed by 'e' and [accent])
                # we need to send it the same stuff, otherwise it'll fail
                filename = unicodedata.normalize("NFD", uploaded.filename)
            try:
                # Un savepoint par fichier : sans lui, une contrainte en échec
                # (ex. nom déjà pris) laissait un dms.file vide en base.
                with request.env.cr.savepoint():
                    dms_file = Model.create(
                        {
                            "directory_id": directory_id,
                            "name": filename,
                            # passer par « content » : taille, somme de contrôle
                            # et type de stockage (base, fichier, pièce jointe)
                            "content": BinaryBytes(uploaded.read()),
                        }
                    )
            except AccessError:
                args.append(
                    {
                        "error": request.env._(
                            "You are not allowed to upload a file here."
                        )
                    }
                )
            except UserError as e:
                args.append({"error": str(e)})
            except Exception:
                # Erreur inattendue (stockage, disque…) : la tracer pour
                # l'administrateur au lieu de l'avaler silencieusement.
                _logger.exception(
                    "DMS upload failed: %s in directory %s", filename, directory_id
                )
                args.append(
                    {
                        "error": request.env._(
                            "Unexpected error while uploading %s.", clean(filename)
                        )
                    }
                )
            else:
                args.append(
                    {
                        "filename": clean(filename),
                        "mimetype": dms_file.mimetype,
                        "id": dms_file.id,
                        "size": dms_file.size,
                    }
                )
        return request.make_json_response(args)


class DmsFileRenderController(http.Controller):
    @http.route(
        "/dms/file/render_text/<int:file_id>",
        type="http",
        auth="user",
        readonly=True,
    )
    def dms_file_render_text(self, file_id, head=False, **_kwargs):
        """Odoo 20 : la visionneuse rend les fichiers texte via
        /mail/attachment/render_text/<id>, qui attend un ir.attachment ;
        avec l'id d'un dms.file elle afficherait une autre pièce jointe.
        Même rendu, mais sur dms.file et avec ses droits."""
        with replace_exceptions(AccessError, MissingError, by=request.not_found()):
            record = request.env["dms.file"].browse(file_id)
            record.check_access("read")
            mimetype = record.mimetype
            content = bytes(record.content or b"")
        if mimetype not in AttachmentController.SUPPORTED_TEXT_MIMETYPES:
            raise BadRequest(f"bad document mimetype: {mimetype}")
        head = str2bool(head, False)
        if mimetype == "text/html" or (mimetype == "application/json" and not head):
            stream = request.env["ir.binary"]._get_stream_from(record, "content")
            stream.public = False
            return stream.get_response(
                as_attachment=False,
                content_security_policy="default-src 'none'; sandbox;",
            )
        if head:
            content = content[: AttachmentController.TEXTUAL_THUMBNAIL_SIZE]
        response = request.render(
            "mail.content_text", {"content": content.decode(errors="replace")}
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; font-src 'self'; sandbox;"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
