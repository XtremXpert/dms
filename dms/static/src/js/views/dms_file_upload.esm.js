// /** ********************************************************************************
//     Copyright 2024 Subteno - Timothée Vannier (https://www.subteno.com).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/

// Odoo 20 / OWL 3 : useState -> proxy, useRef -> signal.ref() (t-ref="this.…"),
// useEffect n'a plus de dépendances : le dépôt de fichiers est branché au montage.
import {onMounted, onWillUnmount, proxy, signal} from "@odoo/owl";
import {useBus, useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

export function createFileDropZoneExtension() {
    return {
        setup() {
            super.setup(...arguments);
            this.dragState = proxy({showDragZone: false});
            const highlight = this.highlight.bind(this);
            const unhighlight = this.unhighlight.bind(this);
            const drop = this.onDrop.bind(this);
            let el = null;
            onMounted(() => {
                el = document.querySelector(".o_content");
                if (el) {
                    el.addEventListener("dragover", highlight);
                    el.addEventListener("dragleave", unhighlight);
                    el.addEventListener("drop", drop);
                }
            });
            onWillUnmount(() => {
                if (el) {
                    el.removeEventListener("dragover", highlight);
                    el.removeEventListener("dragleave", unhighlight);
                    el.removeEventListener("drop", drop);
                }
            });
        },

        highlight(ev) {
            ev.stopPropagation();
            ev.preventDefault();
            this.dragState.showDragZone = true;
        },

        unhighlight(ev) {
            ev.stopPropagation();
            ev.preventDefault();
            this.dragState.showDragZone = false;
        },

        async onDrop(ev) {
            ev.preventDefault();
            this.dragState.showDragZone = false;
            await this.env.bus.trigger("change_file_input", {
                files: ev.dataTransfer.files,
            });
        },
    };
}

export function createFileUploadExtension() {
    return {
        setup() {
            super.setup(...arguments);
            this.notification = useService("notification");
            this.http = useService("http");
            this.fileInputRef = signal.ref();

            useBus(this.env.bus, "change_file_input", async (ev) => {
                await this.uploadFiles(ev.detail.files);
            });
        },

        uploadDocument() {
            this.fileInputRef()?.click();
        },

        async onChangeFileInput() {
            const input = this.fileInputRef();
            if (!input) {
                return;
            }
            const files = [...input.files];
            // Vider le champ : sinon choisir à nouveau le même fichier ne
            // déclenche pas « change ».
            input.value = "";
            await this.uploadFiles(files);
        },

        _getUploadDirectoryId() {
            // Le répertoire vient du domaine de l'action ou du panneau de recherche.
            for (const item of this.props.domain || []) {
                if (
                    Array.isArray(item) &&
                    item.length === 3 &&
                    item[0] === "directory_id" &&
                    ["=", "child_of"].includes(item[1])
                ) {
                    return item[2];
                }
            }
            return false;
        },

        async uploadFiles(files) {
            if (!files || !files.length) {
                return;
            }
            const directory_id = this._getUploadDirectoryId();
            if (directory_id === false) {
                return this.notification.add(_t("You must select a directory first"), {
                    type: "danger",
                });
            }
            const fileData = await this.http.post(
                "/web/binary/upload_dms_file",
                {
                    csrf_token: odoo.csrf_token,
                    ufile: [...files],
                    directory_id: directory_id,
                },
                "text"
            );
            // La route renvoie une entrée par fichier ({error} ou {id, …}).
            const results = [].concat(JSON.parse(fileData));
            await this.model.load();
            for (const result of results) {
                if (result.error) {
                    this.notification.add(result.error, {type: "danger"});
                }
            }
        },
    };
}
