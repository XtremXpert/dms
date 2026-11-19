/**
 * Copyright 2026 XtremXpert
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 */

import {getDmsPreviewRecordIds, openDmsFilePreview} from "./dms_preview_dialog.esm";
import {FileKanbanRecord} from "@dms/js/views/file_kanban_record.esm";
import {FileKanbanRenderer} from "@dms/js/views/file_kanban_renderer.esm";
import {FileKanbanView} from "@dms/js/views/file_kanban_view.esm";
import {FileListRenderer} from "@dms/js/views/file_list_renderer.esm";
import {FileListView} from "@dms/js/views/file_list_view.esm";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

/**
 * Kanban card of the DMS file views: a click anywhere on the card opens the
 * preview dialog instead of the form view. The form stays reachable through
 * the "Details" action of the dialog and the dropdown menu of the card.
 */
export class DmsPreviewKanbanRecord extends FileKanbanRecord {
    setup() {
        super.setup(...arguments);
        this.dmsPreviewDialog = useService("dialog");
    }

    onGlobalClick(ev, newWindow) {
        const isPreviewIcon = Boolean(ev.target.closest(".o_kanban_dms_file_preview"));
        const hasSelection = (this.props.getSelection?.() || []).length > 0;
        if (
            newWindow ||
            ev.altKey ||
            hasSelection ||
            (!this.props.forceGlobalClick && this.props.openAction) ||
            (!isPreviewIcon && ev.target.closest(this.constructor.CANCEL_GLOBAL_CLICK))
        ) {
            return super.onGlobalClick(ev, newWindow);
        }
        return this.openDmsPreview();
    }

    openDmsPreview() {
        const record = this.props.record;
        return openDmsFilePreview(this.dmsPreviewDialog, {
            fileId: record.resId,
            fileIds: getDmsPreviewRecordIds(record.model.root),
            reload: () => record.model.load(),
        });
    }
}

export class DmsPreviewKanbanRenderer extends FileKanbanRenderer {}

DmsPreviewKanbanRenderer.components = {
    ...FileKanbanRenderer.components,
    KanbanRecord: DmsPreviewKanbanRecord,
};

export const DmsPreviewKanbanView = {
    ...FileKanbanView,
    Renderer: DmsPreviewKanbanRenderer,
    // Read the template at render time: other modules extend the buttons of
    // the regular DMS views (ONLYOFFICE creates documents from there).
    get buttonTemplate() {
        return FileKanbanView.buttonTemplate;
    },
};

registry.category("views").add("dms_preview_kanban", DmsPreviewKanbanView);

/**
 * List rows of the DMS file views: same behaviour as the kanban cards.
 */
export class DmsPreviewListRenderer extends FileListRenderer {
    setup() {
        super.setup(...arguments);
        this.dmsPreviewDialog = useService("dialog");
    }

    async onCellClicked(record, column, ev, newWindow) {
        if (
            newWindow ||
            ev.altKey ||
            this.props.list.selection.length > 0 ||
            ev.target.closest(
                "a, button, input, select, textarea, .o_list_record_remove"
            )
        ) {
            return super.onCellClicked(record, column, ev, newWindow);
        }
        return this.openDmsPreview(record);
    }

    openDmsPreview(record) {
        return openDmsFilePreview(this.dmsPreviewDialog, {
            fileId: record.resId,
            fileIds: getDmsPreviewRecordIds(this.props.list),
            reload: () => this.props.list.model.load(),
        });
    }
}

export const DmsPreviewListView = {
    ...FileListView,
    Renderer: DmsPreviewListRenderer,
    get buttonTemplate() {
        return FileListView.buttonTemplate;
    },
};

registry.category("views").add("dms_preview_list", DmsPreviewListView);
