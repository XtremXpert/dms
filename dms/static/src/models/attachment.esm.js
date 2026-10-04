// /** ********************************************************************************
//     Copyright 2024 Subteno - Timothée Vannier (https://www.subteno.com).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Attachment} from "@mail/core/common/attachment_model";
import {patch} from "@web/core/utils/patch";
import {url} from "@web/core/utils/urls";

// Records of dms.file are shown in the file viewer as if they were attachments:
// their content must be served from the dms.file record, not from ir.attachment.
patch(Attachment.prototype, {
    get isDmsFile() {
        return this.model_name === "dms.file";
    },
    get urlRoute() {
        if (this.isDmsFile) {
            return "/web/content";
        }
        return super.urlRoute;
    },
    get urlQueryParams() {
        if (this.isDmsFile) {
            return {
                model: "dms.file",
                id: this.id,
                field: "content",
                filename_field: "name",
            };
        }
        return super.urlQueryParams;
    },
    // Text preview: /mail/attachment/render_text expects an ir.attachment, so
    // the id of a dms.file would show (or refuse) another attachment.
    get textThumbnailUrl() {
        if (this.isDmsFile && this.id > 0) {
            return url(`/dms/file/render_text/${this.id}`, {head: "1"});
        }
        return super.textThumbnailUrl;
    },
    get defaultSource() {
        if (this.isDmsFile && this.isText) {
            return url(`/dms/file/render_text/${this.id}`);
        }
        return super.defaultSource;
    },
});
