# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "DMS Preview",
    "summary": "Preview DMS files in a dialog with contextual actions",
    "version": "20.0.1.1.0",
    "category": "Document Management",
    "license": "LGPL-3",
    "website": "https://github.com/OCA/dms",
    "author": "XtremXpert, Odoo Community Association (OCA)",
    "depends": ["dms"],
    "data": [
        "views/dms_file_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "dms_preview/static/src/js/dms_preview_utils.esm.js",
            "dms_preview/static/src/js/dms_preview_dialog.esm.js",
            "dms_preview/static/src/js/dms_preview_views.esm.js",
            "dms_preview/static/src/js/dms_preview_dialog.xml",
            "dms_preview/static/src/scss/dms_preview.scss",
        ],
    },
    "installable": True,
    "application": False,
}
