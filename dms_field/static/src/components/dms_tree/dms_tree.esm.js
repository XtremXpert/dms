/* Copyright 2024 Tecnativa - Carlos Roca
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */

// Odoo 20 : jQuery (et donc jsTree) n'existe plus. Arborescence DMS en OWL 3,
// autonome : elle charge elle-même stockages, répertoires et fichiers.
//   - mode fiche : resModel + resId -> répertoires liés à l'enregistrement ;
//   - mode liste : rootModel (dms.storage / dms.directory) + rootDomain.
import {Component, proxy, signal, t, useProps} from "@odoo/owl";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {FormViewDialog} from "@web/views/view_dialogs/form_view_dialog";
import {_t} from "@web/core/l10n/translation";
import {useFileViewer} from "@web/core/file_viewer/file_viewer_hook";
import {useLayoutEffect} from "@web/owl2/utils";
import {useService} from "@web/core/utils/hooks";

const DIRECTORY_FIELDS = [
    "name",
    "parent_id",
    "permission_read",
    "permission_create",
    "permission_write",
    "permission_unlink",
    "count_directories",
    "count_files",
    "count_total_directories",
    "count_total_files",
    "count_elements",
    "human_size",
    "icon_url",
];
const FILE_FIELDS = [
    "name",
    "mimetype",
    "human_size",
    "icon_url",
    "permission_read",
    "permission_create",
    "permission_write",
    "permission_unlink",
    "is_locked",
    "is_lock_editor",
];

const MIMETYPE_ICONS = [
    ["image", /^image\//],
    ["music_note", /^audio\//],
    ["movie", /^video\//],
    ["picture_as_pdf", /^application\/pdf$/],
    ["code", /^(text\/(html|javascript|css|xml)|application\/(javascript|json|xml))$/],
    ["inventory_2", /(zip|tar|rar|7z|compress|bzip2)/],
    ["article", /(word|opendocument\.text|rtf|msword)/],
    ["attach_file", /(sheet|excel|presentation|powerpoint)/],
];

export class DmsTree extends Component {
    static template = "dms_field.DmsTree";
    props = useProps({
        resModel: t.string().optional(),
        resId: t.or([t.number(), t.boolean()]).optional(),
        rootModel: t.string().optional(),
        rootDomain: t.array().optional(),
        readonly: t.boolean().optional(),
    });

    setup() {
        this.orm = useService("orm");
        this.http = useService("http");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.store = useService("mail.store");
        this.fileViewer = useFileViewer();
        this.fileInput = signal.ref();
        this.renameInput = signal.ref();
        this.state = proxy({
            roots: [],
            loaded: false,
            selected: null,
            renaming: null,
            renameValue: "",
            dropTarget: null,
            canCreateRecordDirectory: false,
        });
        useLayoutEffect(
            () => {
                this.reload();
            },
            () => [this.props.resModel, this.props.resId, this.props.rootModel]
        );
        // Focus du champ de renommage une fois rendu.
        useLayoutEffect(
            (input) => {
                if (input) {
                    input.focus();
                    input.select();
                }
            },
            () => [this.renameInput()]
        );
    }

    // ------------------------------------------------------------------
    // Chargement
    // ------------------------------------------------------------------

    /** Point d'extension (ex. hr_dms_field : hr.employee.public -> hr.employee). */
    sanitizeDMSModel(model) {
        return model;
    }

    get isRecordMode() {
        return Boolean(this.props.resModel);
    }

    async reload() {
        this.state.selected = null;
        this.state.renaming = null;
        let roots = [];
        let canCreate = false;
        if (this.isRecordMode) {
            if (this.props.resId) {
                const model = this.sanitizeDMSModel(this.props.resModel);
                const directories = await this.searchParents([
                    ["res_model", "=", model],
                    ["res_id", "=", this.props.resId],
                    ["storage_id.save_type", "!=", "attachment"],
                ]);
                roots = directories.map((d) => this.makeDirectoryNode(d, true));
                if (!roots.length && model !== "dms.field.template") {
                    canCreate =
                        (await this.orm.searchCount("dms.field.template", [
                            ["model", "=", model],
                        ])) > 0;
                }
            }
        } else if (this.props.rootModel === "dms.directory") {
            const directories = await this.searchParents(this.props.rootDomain || []);
            roots = directories.map((d) => this.makeDirectoryNode(d));
        } else {
            const storages = await this.orm.searchRead(
                "dms.storage",
                this.props.rootDomain || [],
                ["name", "count_storage_directories"]
            );
            roots = storages.map((s) => this.makeStorageNode(s));
        }
        this.state.roots = roots;
        this.state.canCreateRecordDirectory = canCreate;
        this.state.loaded = true;
        // Comme avant (open_all de jsTree) : déplier le premier niveau.
        for (const node of this.state.roots) {
            if (node.hasChildren) {
                await this.toggle(node, true);
            }
        }
    }

    searchParents(domain) {
        return this.orm.call("dms.directory", "search_read_parents", [], {
            domain,
            fields: DIRECTORY_FIELDS,
        });
    }

    async loadChildren(node) {
        let children = [];
        if (node.model === "dms.storage") {
            const directories = await this.searchParents([["storage_id", "=", node.id]]);
            children = directories.map((d) => this.makeDirectoryNode(d));
        } else if (node.model === "dms.directory") {
            const [directories, files] = await Promise.all([
                this.orm.searchRead(
                    "dms.directory",
                    [["parent_id", "=", node.id]],
                    DIRECTORY_FIELDS,
                    {order: "name"}
                ),
                this.orm.searchRead(
                    "dms.file",
                    [["directory_id", "=", node.id]],
                    FILE_FIELDS,
                    {order: "name"}
                ),
            ]);
            children = [
                ...directories.map((d) => this.makeDirectoryNode(d)),
                ...files.map((f) => this.makeFileNode(f)),
            ];
        }
        node.children = children;
        node.hasChildren = children.length > 0;
    }

    makeStorageNode(storage) {
        return {
            key: `dms.storage_${storage.id}`,
            model: "dms.storage",
            id: storage.id,
            name: storage.name,
            data: storage,
            hasChildren: storage.count_storage_directories > 0,
            children: null,
            open: false,
            perms: {read: true, create: false, write: false, unlink: false},
        };
    }

    makeDirectoryNode(directory, isRecordRoot = false) {
        return {
            key: `dms.directory_${directory.id}`,
            model: "dms.directory",
            id: directory.id,
            name: directory.name,
            data: directory,
            hasChildren: directory.count_directories + directory.count_files > 0,
            children: null,
            open: false,
            // Le répertoire racine d'une fiche est géré par le modèle de champ :
            // ni renommage ni suppression depuis l'arbre (comme en 18.0).
            isRecordRoot,
            perms: {
                read: directory.permission_read,
                create: directory.permission_create,
                write: directory.permission_write && !isRecordRoot,
                unlink: directory.permission_unlink && !isRecordRoot,
            },
        };
    }

    makeFileNode(file) {
        const unlocked = !file.is_locked || file.is_lock_editor;
        return {
            key: `dms.file_${file.id}`,
            model: "dms.file",
            id: file.id,
            name: file.name,
            data: file,
            hasChildren: false,
            children: [],
            open: false,
            perms: {
                read: file.permission_read,
                create: false,
                write: file.permission_write && unlocked,
                unlink: file.permission_unlink && unlocked,
            },
        };
    }

    // ------------------------------------------------------------------
    // Affichage
    // ------------------------------------------------------------------

    get readonly() {
        return Boolean(this.props.readonly);
    }

    /** Odoo 20 : icônes Material Symbols (sous-ensemble livré par web). */
    iconName(node) {
        if (node.model === "dms.storage") {
            return "database";
        }
        if (node.model === "dms.directory") {
            return "folder";
        }
        const mimetype = node.data.mimetype || "";
        for (const [icon, pattern] of MIMETYPE_ICONS) {
            if (pattern.test(mimetype)) {
                return icon;
            }
        }
        return "description";
    }

    isSelected(node) {
        return this.state.selected?.key === node.key;
    }

    async toggle(node, forceOpen = false) {
        if (!node.hasChildren) {
            return;
        }
        if (node.open && !forceOpen) {
            node.open = false;
            return;
        }
        if (node.children === null) {
            await this.loadChildren(node);
        }
        node.open = true;
    }

    select(node) {
        if (this.state.renaming && this.state.renaming.key !== node.key) {
            this.state.renaming = null;
        }
        this.state.selected = node;
    }

    onNodeDblClick(node) {
        if (node.model === "dms.file") {
            this.preview(node);
        } else {
            this.toggle(node);
        }
    }

    // ------------------------------------------------------------------
    // Actions
    // ------------------------------------------------------------------

    /** Recharge les enfants d'un répertoire (ou toute l'arborescence). */
    async refresh(node) {
        if (!node) {
            return this.reload();
        }
        if (node.model === "dms.storage") {
            node.children = null;
            node.hasChildren = true;
            return this.toggle(node, true);
        }
        const [fresh] = await this.orm.read(node.model, [node.id], DIRECTORY_FIELDS);
        if (fresh) {
            Object.assign(node, this.makeDirectoryNode(fresh, node.isRecordRoot), {
                children: null,
            });
        }
        await this.toggle(node, true);
        if (this.state.selected?.key === node.key) {
            this.state.selected = node;
        }
    }

    findParent(target, nodes = this.state.roots, parent = null) {
        for (const node of nodes) {
            if (node.key === target.key) {
                return parent;
            }
            if (node.children) {
                const found = this.findParent(target, node.children, node);
                if (found !== undefined) {
                    return found;
                }
            }
        }
        return undefined;
    }

    async createRecordDirectory() {
        await this.orm.call("dms.field.template", "create_dms_directory", [], {
            context: {
                res_model: this.sanitizeDMSModel(this.props.resModel),
                res_id: this.props.resId,
            },
        });
        await this.reload();
    }

    addDirectory(node) {
        this.dialog.add(FormViewDialog, {
            resModel: "dms.directory",
            title: _t("Add Directory: %s", node.name),
            context: {default_parent_id: node.id, default_parent_directory_id: node.id},
            onRecordSaved: () => this.refresh(node),
        });
    }

    addFile(node) {
        this.dialog.add(FormViewDialog, {
            resModel: "dms.file",
            title: _t("Add File: %s", node.name),
            context: {default_directory_id: node.id},
            onRecordSaved: () => this.refresh(node),
        });
    }

    openRecord(node) {
        this.dialog.add(FormViewDialog, {
            resModel: node.model,
            resId: node.id,
            title: _t("Open: %s", node.name),
            onRecordSaved: () => this.refresh(this.findParent(node)),
        });
    }

    startRename(node) {
        this.state.renaming = node;
        this.state.renameValue = node.name;
    }

    onRenameInput(ev) {
        this.state.renameValue = ev.target.value;
    }

    async onRenameKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            await this.confirmRename();
        } else if (ev.key === "Escape") {
            this.state.renaming = null;
        }
    }

    async confirmRename() {
        const node = this.state.renaming;
        const name = (this.state.renameValue || "").trim();
        this.state.renaming = null;
        if (!node || !name || name === node.name) {
            return;
        }
        try {
            await this.orm.write(node.model, [node.id], {name});
            node.name = name;
            node.data.name = name;
        } catch (error) {
            this.notification.add(error.data?.message || String(error), {
                type: "danger",
            });
        }
    }

    remove(node) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Delete"),
            body: _t("Delete “%s”?", node.name),
            confirmLabel: _t("Delete"),
            confirm: async () => {
                await this.orm.unlink(node.model, [node.id]);
                if (this.state.selected?.key === node.key) {
                    this.state.selected = null;
                }
                await this.refresh(this.findParent(node));
            },
            cancel: () => {},
        });
    }

    preview(node) {
        const attachment = this.store["ir.attachment"].insert({
            id: node.id,
            filename: node.name,
            name: node.name,
            mimetype: node.data.mimetype,
            model_name: "dms.file",
        });
        this.fileViewer.open(attachment);
    }

    downloadUrl(node) {
        return `/web/content/dms.file/${node.id}/content?download=true`;
    }

    // ------------------------------------------------------------------
    // Envoi de fichiers (bouton ou glisser-déposer sur un répertoire)
    // ------------------------------------------------------------------

    pickFiles() {
        this.fileInput()?.click();
    }

    async onFileInputChange(ev) {
        const node = this.state.selected;
        const files = [...ev.target.files];
        ev.target.value = "";
        if (node && files.length) {
            await this.upload(node, files);
        }
    }

    canDropOn(node) {
        return !this.readonly && node.model === "dms.directory" && node.perms.create;
    }

    onDragOver(ev, node) {
        if (!this.canDropOn(node) || !ev.dataTransfer?.types?.includes("Files")) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.state.dropTarget = node.key;
    }

    onDragLeave(ev, node) {
        if (this.state.dropTarget === node.key && !ev.currentTarget.contains(ev.relatedTarget)) {
            this.state.dropTarget = null;
        }
    }

    async onDrop(ev, node) {
        if (!this.canDropOn(node)) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.state.dropTarget = null;
        const files = [...(ev.dataTransfer?.files || [])];
        if (files.length) {
            await this.upload(node, files);
        }
    }

    async upload(node, files) {
        let results = [];
        try {
            const response = await this.http.post(
                "/web/binary/upload_dms_file",
                {csrf_token: odoo.csrf_token, ufile: files, directory_id: node.id},
                "text"
            );
            results = JSON.parse(response);
        } catch (error) {
            this.notification.add(error.message || _t("An error occurred during the upload"), {
                type: "danger",
            });
            return;
        }
        const errors = results.filter((r) => r.error);
        for (const {error} of errors) {
            this.notification.add(error, {type: "danger"});
        }
        if (results.length > errors.length) {
            this.notification.add(
                _t("%s file(s) uploaded", results.length - errors.length),
                {type: "success"}
            );
        }
        await this.refresh(node);
        this.select(node);
    }
}
