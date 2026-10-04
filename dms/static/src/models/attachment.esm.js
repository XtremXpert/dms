// /** ********************************************************************************
//     Copyright 2024 Subteno - Timothée Vannier (https://www.subteno.com).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Attachment} from "@mail/core/common/attachment_model";
import {patch} from "@web/core/utils/patch";
import {url} from "@web/core/utils/urls";

// Odoo 20 : defaultSource (image, PDF, YouTube…) et downloadUrl dérivent tous de
// urlRoute ; les fichiers DMS sont servis depuis le champ « content » de dms.file.
patch(Attachment.prototype, {
    get urlRoute() {
        if (this.model_name === "dms.file" && !(this.uploading && this.tmpUrl)) {
            return this.isImage
                ? `/web/image/dms.file/${this.id}/content`
                : `/web/content/dms.file/${this.id}/content`;
        }
        return super.urlRoute;
    },
    // Aperçu texte : /mail/attachment/render_text attend un ir.attachment.
    get textThumbnailUrl() {
        if (this.model_name === "dms.file" && this.id > 0) {
            return url(`/dms/file/render_text/${this.id}`, {head: "1"});
        }
        return super.textThumbnailUrl;
    },
    get defaultSource() {
        if (this.model_name === "dms.file" && this.isText) {
            return url(`/dms/file/render_text/${this.id}`);
        }
        return super.defaultSource;
    },
});
