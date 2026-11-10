# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "DMS Storage Guard",
    "summary": "Check the DMS storages before installing",
    "version": "20.0.1.0.0",
    "license": "LGPL-3",
    "author": "XtremXpert,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/dms",
    "depends": ["dms"],
    "data": [
        "security/ir.access.csv",
        "views/dms_storage_check_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "installable": True,
}
