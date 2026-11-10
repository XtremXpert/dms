# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from markupsafe import Markup, escape

from odoo import api, fields, models

from ..hooks import collect_report


class DmsStorageCheck(models.TransientModel):
    _name = "dms.storage.check"
    _description = "DMS Storage Check"

    problem_count = fields.Integer(string="Problems", compute="_compute_report")
    status = fields.Char(compute="_compute_report")
    report_html = fields.Html(
        string="Report", compute="_compute_report", sanitize=False
    )

    @api.depends()
    def _compute_report(self):
        for check in self:
            report = collect_report(check.env)
            count = len(report["problems"])
            check.problem_count = count
            check.status = (
                check.env._("OK")
                if not count
                else check.env._("%(count)s problem(s) found", count=count)
            )
            check.report_html = check._render_report(report)

    def _render_report(self, report):
        env = self.env
        chunks = []
        if report["problems"]:
            chunks.append(
                '<div class="alert alert-warning" role="alert">'
                f"<strong>{escape(env._('The document storage needs attention.'))}"
                "</strong><ul>"
            )
            for problem in report["problems"]:
                chunks.append(
                    "<li><strong>{title}</strong><br/>{details}"
                    "<br/><em>{remediation}</em></li>".format(
                        title=escape(problem["title"]),
                        details=escape(problem["details"]),
                        remediation=escape(
                            env._(
                                "To fix it: %(remediation)s",
                                remediation=problem["remediation"],
                            )
                        ),
                    )
                )
            chunks.append("</ul></div>")
        else:
            chunks.append(
                '<div class="alert alert-success" role="alert">'
                f"{escape(env._('All the DMS storages are stored in the filestore.'))}"
                "</div>"
            )
        headers = (
            env._("Storage"),
            env._("Storage type"),
            env._("Files"),
            env._("Pending migrations"),
        )
        chunks.append(
            '<table class="table table-sm"><thead><tr>'
            f"<th>{escape(headers[0])}</th><th>{escape(headers[1])}</th>"
            '<th class="text-end">{headers[2]}</th>'
            '<th class="text-end">{headers[3]}</th>'
            "</tr></thead><tbody>".format(
                headers=tuple(escape(header) for header in headers)
            )
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
        checked = env._(
            "Checked on %(date)s (ir_attachment.location = %(location)s).",
            date=report["generated_at"],
            location=report["attachment_location"],
        )
        chunks.append(f'<p class="text-muted small">{escape(checked)}</p>')
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
