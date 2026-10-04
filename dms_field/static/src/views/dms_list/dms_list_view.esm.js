/* Copyright 2024 Tecnativa - Carlos Roca
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */
// Odoo 20 / OWL 3 : la vue « dms_list » n'utilise plus de modèle relationnel ni
// jsTree ; le contrôleur affiche le composant DmsTree sur le domaine de l'action.
import {Component, t, useProps} from "@odoo/owl";
import {DmsListArchParser} from "./dms_list_arch_parser.esm";
import {DmsTree} from "../../components/dms_tree/dms_tree.esm";
import {Layout} from "@web/search/layout";
import {registry} from "@web/core/registry";
import {standardViewProps} from "@web/views/standard_view_props";

export class DmsListController extends Component {
    static template = "dms_field.View";
    static components = {Layout, DmsTree};
    props = useProps({...standardViewProps, archInfo: t.object().optional()});
}

export const dmsListView = {
    type: "dms_list",
    Controller: DmsListController,
    ArchParser: DmsListArchParser,
    searchMenuTypes: [],

    props(genericProps, view) {
        const {ArchParser} = view;
        const {arch, relatedModels, resModel} = genericProps;
        const archInfo = new ArchParser().parse(arch, relatedModels, resModel);
        return {...genericProps, archInfo};
    },
};

registry.category("views").add("dms_list", dmsListView);
