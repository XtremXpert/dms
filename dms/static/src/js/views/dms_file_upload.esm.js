/*
    Portage Odoo 20 / Owl 3 : proxy() au lieu de useState, signal.ref() au lieu
    de useRef, useEffect à dépendances implicites.
*/
import {proxy, signal, useEffect} from "@odoo/owl";
import {useBus, useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

export function createFileDropZoneExtension() {
    return {
        setup() {
            super.setup(...arguments);
            this.dragState = proxy({
                showDragZone: false,
            });
            useEffect(() => {
                const el = document.querySelector(".o_content");
                if (!el) {
                    return;
                }
                const highlight = this.highlight.bind(this);
                const unhighlight = this.unhighlight.bind(this);
                const drop = this.onDrop.bind(this);
                el.addEventListener("dragover", highlight);
                el.addEventListener("dragleave", unhighlight);
                el.addEventListener("drop", drop);
                return () => {
                    el.removeEventListener("dragover", highlight);
                    el.removeEventListener("dragleave", unhighlight);
                    el.removeEventListener("drop", drop);
                };
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
            super.setup();
            this.notification = useService("notification");
            this.orm = useService("orm");
            this.http = useService("http");
            this.fileInput = signal.ref();
            useBus(this.env.bus, "change_file_input", async (ev) => {
                this.fileInput().files = ev.detail.files;
                await this.onChangeFileInput();
            });
        },
        uploadDocument() {
            this.fileInput().click();
        },
        async onChangeFileInput() {
            const self = this;
            const controllerID = this.actionService.currentController.jsId;
            let directory_id = false;
            if (this.props.domain) {
                for (const domain_item of this.props.domain) {
                    if (domain_item.length === 3) {
                        if (
                            domain_item[0] === "directory_id" &&
                            ["=", "child_of"].includes(domain_item[1])
                        ) {
                            directory_id = domain_item[2];
                        }
                    }
                }
            }
            if (directory_id === false) {
                self.actionService.restore(controllerID);
                return self.notification.add(_t("You must select a directory first"), {
                    type: "danger",
                });
            }
            const params = {
                csrf_token: odoo.csrf_token,
                ufile: [...this.fileInput().files],
                directory_id: directory_id,
            };
            const fileData = await this.http.post(
                "/web/binary/upload_dms_file",
                params,
                "text"
            );
            const result = JSON.parse(fileData);
            if (result.error) {
                throw new Error(result.error);
            }
            self.actionService.restore(controllerID);
        },
    };
}
