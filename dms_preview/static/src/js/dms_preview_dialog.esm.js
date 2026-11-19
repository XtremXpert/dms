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
import {browser} from "@web/core/browser/browser";
import {downloadFile} from "@web/core/network/download";
import {hidePDFJSButtons} from "@web/core/utils/pdfjs";
import {useFileViewer} from "@web/core/file_viewer/file_viewer_hook";
import {useHotkey} from "@web/core/hotkeys/hotkey_hook";
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
        this.store = useService("mail.store");
        this.fileViewer = useFileViewer();
        this.requestId = 0;
        this.state = proxy({
            data: null,
            loading: true,
            error: "",
            editing: false,
            fullscreen: false,
            onlyofficeLoaded: false,
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
            no_preview: _t("No preview available for this file type."),
            locked: _t("Locked"),
            see_details: _t("Download the file or open its details."),
            finish_editing: _t("Finish editing"),
            expand: _t("Expand the window"),
            reduce: _t("Reduce the window"),
            open_viewer: _t("Open in the viewer"),
            copy_link: _t("Copy the share link"),
            link_copied: _t("Link copied to the clipboard."),
            link_error: _t("The link could not be copied."),
        };
        onWillStart(() => this.load(this.props.fileId));
        useHotkey("arrowleft", () => this.onHotkeyPrevious(), {
            bypassEditableProtection: true,
        });
        useHotkey("arrowright", () => this.onHotkeyNext(), {
            bypassEditableProtection: true,
        });
    }

    // ----------------------------------------------------------
    // Data
    // ----------------------------------------------------------

    async load(fileId) {
        const requestId = ++this.requestId;
        this.state.loading = true;
        this.state.error = "";
        this.state.editing = false;
        this.state.onlyofficeLoaded = false;
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
        return this.ids.length > 1 && !this.state.editing;
    }

    get dialogSize() {
        return this.state.fullscreen ? "fs" : "xl";
    }

    get isEditing() {
        return this.state.editing;
    }

    get showOnlyoffice() {
        return (
            Boolean(this.onlyoffice.url) &&
            (this.state.editing ||
                (this.category === "office" && this.onlyoffice.viewable))
        );
    }

    get onlyofficeUrl() {
        const mode = this.state.editing ? "edit" : "view";
        return `${this.onlyoffice.url}?mode=${mode}`;
    }

    get canOpenViewer() {
        return (
            !this.state.editing &&
            ["image", "pdf", "text", "video", "audio"].includes(this.category)
        );
    }

    get versionCount() {
        return (this.state.data && this.state.data.versions?.count) || 0;
    }

    get versionsLabel() {
        return _t("Versions (%s)", this.versionCount);
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
        if (ids.length < 2 || this.state.editing) {
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

    onHotkeyPrevious() {
        if (this.env.dialogData?.isActive) {
            return this.goTo(-1);
        }
    }

    onHotkeyNext() {
        if (this.env.dialogData?.isActive) {
            return this.goTo(1);
        }
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

    onOnlyofficeLoaded() {
        this.state.onlyofficeLoaded = true;
    }

    onToggleFullscreen() {
        this.state.fullscreen = !this.state.fullscreen;
    }

    openViewer() {
        // The native file viewer brings the zoom, rotation and print of the
        // regular Odoo viewer; the dms attachment patch serves the file.
        const data = this.state.data;
        const attachment = this.store["ir.attachment"].insert({
            id: data.id,
            filename: data.name,
            name: data.name,
            mimetype: data.mimetype,
            model_name: "dms.file",
        });
        this.fileViewer.open(attachment);
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

    onEdit() {
        if (this.onlyoffice.editable) {
            // Edit in place: the dialog shows the ONLYOFFICE editor.
            this.state.editing = true;
            this.state.onlyofficeLoaded = false;
            return;
        }
        return this.openForm("action_dms_preview_edit");
    }

    async onFinishEditing() {
        this.state.editing = false;
        this.state.onlyofficeLoaded = false;
        await this.refresh();
    }

    async openForm(actionName) {
        const fileId = this.state.data.id;
        this.props.close();
        await this.action.doActionButton({
            name: actionName,
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

    async onCopyLink() {
        const link = await this.orm.call("dms.file", "get_dms_preview_share_link", [
            [this.state.data.id],
        ]);
        try {
            await browser.navigator.clipboard.writeText(link);
            this.notification.add(this.labels.link_copied);
        } catch {
            this.notification.add(this.labels.link_error, {type: "danger"});
        }
    }

    async onVersions() {
        await this.openForm("action_view_versions");
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
