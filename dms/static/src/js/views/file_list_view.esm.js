// /** ********************************************************************************
//     Copyright 2020 Creu Blanca
//     Copyright 2017-2019 MuK IT GmbH
//     Copyright 2024 Subteno - Timothée Vannier (https://www.subteno.com).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/

import {
    createFileDropZoneExtension,
    createFileUploadExtension,
} from "./dms_file_upload.esm";
import {FileListController} from "./file_list_controller.esm";
import {FileListRenderer} from "./file_list_renderer.esm";
import {listView} from "@web/views/list/list_view";
import {patch} from "@web/core/utils/patch";
import {registry} from "@web/core/registry";

// Odoo 20 : contrôleur dédié (l'envoi ne doit pas toucher toutes les vues liste)
patch(FileListController.prototype, createFileUploadExtension());
patch(FileListRenderer.prototype, createFileDropZoneExtension());
FileListRenderer.template = "dms.ListRenderer";

export const FileListView = {
    ...listView,
    buttonTemplate: "dms.ListButtons",
    Controller: FileListController,
    Renderer: FileListRenderer,
};

registry.category("views").add("file_list", FileListView);
