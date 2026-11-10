# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from markupsafe import Markup, escape

from odoo import api, fields, models

from ..hooks import collect_report


class DmsStorageCheck(models.TransientModel):
    _name = "dms.storage.check"
    _description = "DMS Storage Check"

    problem_count = fields.Integer(compute="_compute_report")
    status = fields.Char(compute="_compute_report")
    report_html = fields.Html(compute="_compute_report", sanitize=False)

    @api.depends()
    def _compute_report(self):
        for check in self:
            report = collect_report(check.env)
            check.problem_count = len(report["problems"])
            check.status = (
                "OK"
                if not report["problems"]
                else f"{len(report['problems'])} problem(s) found"
            )
            check.report_html = check._render_report(report)

    def _render_report(self, report):
        chunks = []
        if report["problems"]:
            chunks.append(
                '<div class="alert alert-warning" role="alert">'
                "<strong>The document storage needs attention.</strong>"
                "<ul>"
            )
            for problem in report["problems"]:
                chunks.append(
                    "<li><strong>{title}</strong><br/>{details}"
                    "<br/><em>To fix it: {remediation}</em></li>".format(
                        title=escape(problem["title"]),
                        details=escape(problem["details"]),
                        remediation=escape(problem["remediation"]),
                    )
                )
            chunks.append("</ul></div>")
        else:
            chunks.append(
                '<div class="alert alert-success" role="alert">'
                "All the DMS storages are stored in the filestore."
                "</div>"
            )
        chunks.append(
            '<table class="table table-sm">'
            "<thead><tr>"
            "<th>Storage</th><th>Storage type</th>"
            '<th class="text-end">Files</th>'
            '<th class="text-end">Pending migrations</th>'
            "</tr></thead><tbody>"
        )
        for storage in report["storages"]:
            chunks.append(
                "<tr><td>{name}</td><td>{save_type}</td>"
                '<td class="text-end">{files}</td>'
                '<td class="text-end">{pending}</td></tr>'.format(
                    name=escape(storage["name"]),
                    save_type=escape(storage["save_type"]),
                    files=storage["files"],
                    pending=storage["pending_migrations"],
                )
            )
        chunks.append("</tbody></table>")
        chunks.append(
            '<p class="text-muted small">Checked on {date} '
            "(ir_attachment.location = {location}).</p>".format(
                date=escape(report["generated_at"]),
                location=escape(report["attachment_location"]),
            )
        )
        return Markup("".join(chunks))

    def action_recheck(self):
        """Open a fresh check so the report is computed again."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "dms_storage_guard.action_dms_storage_check"
        )
        action["res_id"] = False
        action["target"] = "new"
        return action
