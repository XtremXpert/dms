# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.tests import new_test_user

from odoo.addons.base.tests.common import BaseCommon


class TestPartnerDocuments(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_partner_form = (
            cls.env["res.partner"].get_views([(False, "form")])["views"]["form"]["arch"]
        )
        cls.dms_user = new_test_user(
            cls.env,
            login="test-dms-user",
            groups="base.group_user,dms.group_dms_user",
        )
        cls.other_user = new_test_user(
            cls.env, login="test-other-user", groups="base.group_user"
        )

    def test_tab_is_delivered_in_data(self):
        view = self.env.ref("dms_field_partner_documents.view_partner_form")
        self.assertTrue(view)
        self.assertIn('mode="dms_list"', self.admin_partner_form)

    def test_tab_is_restricted_to_dms_users(self):
        arch = (
            self.env["res.partner"]
            .with_user(self.dms_user)
            .get_views([(False, "form")])["views"]["form"]["arch"]
        )
        self.assertIn('mode="dms_list"', arch)
        arch = (
            self.env["res.partner"]
            .with_user(self.other_user)
            .get_views([(False, "form")])["views"]["form"]["arch"]
        )
        self.assertNotIn('mode="dms_list"', arch)

    def test_single_tab_with_demo_data(self):
        demo_view = self.env.ref("dms_field.view_partner_form", False)
        if demo_view:
            self.assertFalse(demo_view.active)
