# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    "name": "DMS Field: Partner Documents",
    "summary": "Documents tab on contacts delivered in data, not only in demo",
    "version": "20.0.1.0.0",
    "category": "Document Management",
    "website": "https://github.com/OCA/dms",
    "author": "XtremXpert, Odoo Community Association (OCA)",
    "license": "LGPL-3",
    "depends": ["dms_field"],
    "data": ["views/res_partner_views.xml"],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
