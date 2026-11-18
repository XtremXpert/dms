# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


def post_init_hook(env):
    """Keep a single Documents tab on contacts.

    ``dms_field`` ships its own contact form view as demo data. When that
    demo view is loaded, this module would add a second tab: deactivate it.
    """
    demo_view = env.ref("dms_field.view_partner_form", raise_if_not_found=False)
    if demo_view:
        demo_view.active = False
