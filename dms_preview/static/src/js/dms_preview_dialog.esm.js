/**
 * Copyright 2026 XtremXpert
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 */

import {Component, onWillStart, proxy, t, useProps} from "@odoo/owl";
import {
    dmsPdfViewerUrl,
    formatDmsPreviewDate,
    printDmsPreview,
} from "./dms_preview_utils.esm";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {Dialog} from "@web/core/dialog/dialog";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";
import {_t} from "@web/core/l10n/translation";
import {downloadFile} from "@web/core/network/download";
import {hidePDFJSButtons} from "@web/core/utils/pdfjs";
import {useService} from "@web/core/utils/hooks";

/**
 * Collect the ids of the records loaded by a view, in their display order.
 *
 * Used to navigate between the files of the current folder without closing
 * the dialog. Only the loaded page is known (grouped views included).
 *
 * @param {Object} modelRoot root data point of the relational model
 * @returns {number[]}
 */
export function getDmsPreviewRecordIds(modelRoot) {
    if (!modelRoot) {
        return [];
    }
    let records = [];
    if (modelRoot.groups?.length) {
        records = modelRoot.groups.flatMap((group) => [...(group.records || [])]);
    } else if (modelRoot.records) {
        records = [...modelRoot.records];
    }
    return records.filter((record) => record.resId).map((record) => record.resId);
}

export class DmsFilePreviewDialog extends Component {
    static template = "dms_preview.DmsFilePreviewDialog";
    static components = {Dialog, Dropdown, DropdownItem};

    props = useProps({
        fileId: t.number(),
        fileIds: t.array().optional(() => []),
        reload: t.function().optional(),
        close: t.function(),
    });

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.requestId = 0;
        this.state = proxy({
            data: null,
            loading: true,
            error: "",
        });
        this.labels = {
            download: _t("Download"),
            edit: _t("Edit"),
            print: _t("Print"),
            share: _t("Share"),
            more: _t("More actions"),
            details: _t("Details"),
            move: _t("Move"),
            lock: _t("Lock"),
            unlock: _t("Unlock"),
            archive: _t("Archive"),
            unarchive: _t("Restore"),
            delete: _t("Delete"),
            cancel: _t("Cancel"),
            previous: _t("Previous file"),
            next: _t("Next file"),
            onlyoffice_preview: _t("Preview in ONLYOFFICE"),
            no_preview: _t("No preview available for this file type."),
            locked: _t("Locked"),
            see_details: _t("Download the file or open its details."),
        };
        onWillStart(() => this.load(this.props.fileId));
    }

    // ----------------------------------------------------------
    // Data
    // ----------------------------------------------------------

    async load(fileId) {
        const requestId = ++this.requestId;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("dms.file", "get_dms_preview_data", [
                [fileId],
            ]);
            if (requestId === this.requestId) {
                this.state.data = data;
            }
        } catch (error) {
            if (requestId === this.requestId) {
                this.state.error = error.message || _t("The file could not be loaded.");
            }
        } finally {
            if (requestId === this.requestId) {
                this.state.loading = false;
            }
        }
    }

    async refresh() {
        const fileId = this.state.data.id;
        await Promise.all([this.load(fileId), this.props.reload?.()]);
    }

    async closeAndReload() {
        this.props.close();
        await this.props.reload?.();
    }

    // ----------------------------------------------------------
    // Getters used by the template
    // ----------------------------------------------------------

    get data() {
        return this.state.data;
    }

    get dialogTitle() {
        return this.state.data ? this.state.data.name : "";
    }

    get capabilities() {
        return this.state.data ? this.state.data.capabilities : {};
    }

    get category() {
        return this.state.data ? this.state.data.category : "";
    }

    get onlyoffice() {
        return (this.state.data && this.state.data.onlyoffice) || {};
    }

    get tags() {
        return (this.state.data && this.state.data.tags) || [];
    }

    get ids() {
        const ids = [...(this.props.fileIds || [])];
        if (!ids.includes(this.props.fileId)) {
            ids.unshift(this.props.fileId);
        }
        return ids;
    }

    get canNavigate() {
        return this.ids.length > 1;
    }

    get pdfViewerUrl() {
        if (this.category !== "pdf" || !this.state.data) {
            return "";
        }
        return dmsPdfViewerUrl(this.state.data.urls.content);
    }

    get metaText() {
        const data = this.state.data;
        if (!data) {
            return "";
        }
        const parts = [];
        if (data.human_size) {
            parts.push(data.human_size);
        }
        if (data.mimetype) {
            parts.push(data.mimetype);
        }
        if (data.directory_name) {
            parts.push(data.directory_name);
        }
        const modified = formatDmsPreviewDate(data.write_date);
        if (modified) {
            parts.push(_t("Modified on %s", modified));
        }
        return parts.join(" · ");
    }

    // ----------------------------------------------------------
    // Navigation
    // ----------------------------------------------------------

    async goTo(delta) {
        const ids = this.ids;
        if (ids.length < 2) {
            return;
        }
        const currentId = this.state.data ? this.state.data.id : this.props.fileId;
        let index = ids.indexOf(currentId);
        if (index === -1) {
            index = 0;
        }
        const target = ids[(index + delta + ids.length) % ids.length];
        await this.load(target);
    }

    onPrevious() {
        return this.goTo(-1);
    }

    onNext() {
        return this.goTo(1);
    }

    // ----------------------------------------------------------
    // Preview helpers
    // ----------------------------------------------------------

    onPdfLoaded(ev) {
        // The download button of the viewer is redundant with ours, keep the
        // print button so that a PDF can be printed from the dialog.
        hidePDFJSButtons(ev.target, {hideDownload: true});
    }

    // ----------------------------------------------------------
    // Actions
    // ----------------------------------------------------------

    onDownload() {
        downloadFile(this.state.data.urls.download);
    }

    onPrint() {
        printDmsPreview(this.state.data);
    }

    async onEdit() {
        const fileId = this.state.data.id;
        this.props.close();
        await this.action.doActionButton({
            name: "action_dms_preview_edit",
            type: "object",
            resModel: "dms.file",
            resId: fileId,
            onClose: () => this.props.reload?.(),
        });
    }

    async onDetails() {
        const fileId = this.state.data.id;
        this.props.close();
        await this.action.doActionButton({
            name: "action_dms_preview_details",
            type: "object",
            resModel: "dms.file",
            resId: fileId,
            onClose: () => this.props.reload?.(),
        });
    }

    async onShare() {
        await this.action.doActionButton({
            name: "action_dms_preview_share",
            type: "object",
            resModel: "dms.file",
            resId: this.state.data.id,
        });
    }

    async onMove() {
        await this.action.doActionButton({
            name: "action_dms_preview_move",
            type: "object",
            resModel: "dms.file",
            resId: this.state.data.id,
            onClose: () => this.refresh(),
        });
    }

    async onOnlyofficePreview() {
        const fileId = this.state.data.id;
        this.props.close();
        await this.action.doActionButton({
            name: "action_dms_preview_onlyoffice",
            type: "object",
            resModel: "dms.file",
            resId: fileId,
        });
    }

    async onToggleLock() {
        const data = this.state.data;
        const method = data.is_locked ? "unlock" : "lock";
        await this.orm.call("dms.file", method, [[data.id]]);
        this.notification.add(
            data.is_locked
                ? _t("The file is now unlocked.")
                : _t("The file is now locked.")
        );
        await this.refresh();
    }

    onArchive() {
        const data = this.state.data;
        const method = data.active ? "action_archive" : "action_unarchive";
        const body = data.active
            ? _t('Archive "%s"?', data.name)
            : _t('Restore "%s"?', data.name);
        this.dialog.add(ConfirmationDialog, {
            body,
            confirmLabel: data.active ? this.labels.archive : this.labels.unarchive,
            cancelLabel: this.labels.cancel,
            cancel: () => undefined,
            confirm: async () => {
                await this.orm.call("dms.file", method, [[data.id]]);
                await this.closeAndReload();
            },
        });
    }

    onDelete() {
        const data = this.state.data;
        this.dialog.add(ConfirmationDialog, {
            title: this.labels.delete,
            body: _t('Delete "%s"? This cannot be undone.', data.name),
            confirmLabel: this.labels.delete,
            confirmClass: "btn-danger",
            cancelLabel: this.labels.cancel,
            cancel: () => undefined,
            confirm: async () => {
                await this.orm.unlink("dms.file", [data.id]);
                await this.closeAndReload();
            },
        });
    }
}

/**
 * Open the preview dialog for a file.
 *
 * @param {Object} dialogService
 * @param {Object} params
 * @param {Number} params.fileId file to display first
 * @param {number[]} [params.fileIds] files of the current page, for navigation
 * @param {Function} [params.reload] reload the underlying view
 */
export function openDmsFilePreview(dialogService, {fileId, fileIds, reload}) {
    dialogService.add(DmsFilePreviewDialog, {fileId, fileIds, reload});
}
