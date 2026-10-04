/* Copyright 2024 Tecnativa - Carlos Roca
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */
// Odoo 20 : seul le gabarit de X2ManyField est étendu (branche mode="dms_list") ;
// le composant DmsTree charge ses données, sans toucher au setup() du champ.
import {DmsTree} from "../../../components/dms_tree/dms_tree.esm";
import {X2ManyField} from "@web/views/fields/x2many/x2many_field";

X2ManyField.components = {...X2ManyField.components, DmsTree};
