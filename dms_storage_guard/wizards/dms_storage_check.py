# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.tools import human_size

from ..hooks import check_filestore, collect_duplicates, collect_report, collect_space


def _format_size(value):
    """Human readable size, ``0`` for an empty size (human_size returns False)."""
    return human_size(value) if value else "0"


class DmsStorageCheck(models.TransientModel):
    _name = "dms.storage.check"
    _description = "DMS Storage Check"

    problem_count = fields.Integer(compute="_compute_report")
    status = fields.Char(compute="_compute_report")
    report_html = fields.Html(compute="_compute_report", sanitize=False)

    @api.depends()
    def _compute_report(self):
        for check in self:
            env = check.env
            report = collect_report(env)
            count = len(report["problems"])
            check.problem_count = count
            check.status = (
                env._("OK")
                if not count
                else env._("%(count)s problem(s) found", count=count)
            )
            chunks = [check._render_report(report)]
            chunks.append(check._render_space(collect_space(env)))
            chunks.append(check._render_duplicates(collect_duplicates(env)))
            chunks.append(check._render_integrity(check_filestore(env)))
            check.report_html = Markup("".join(chunks))

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
        return "".join(chunks)

    def _render_space(self, space):
        env = self.env
        rows = (
            (env._("DMS files"), str(space["files"])),
            (
                env._("Files stored in the database"),
                "{} ({})".format(
                    space["database_files"], _format_size(space["database_size"])
                ),
            ),
            (
                env._("Files stored in the filestore"),
                "{} ({})".format(
                    space["filestore_files"],
                    _format_size(space["filestore_logical_size"]),
                ),
            ),
            (
                env._("Files on disk"),
                "{} ({})".format(
                    space["physical_files"], _format_size(space["physical_size"])
                ),
            ),
            (env._("Space saved by deduplication"), _format_size(space["saved_size"])),
        )
        cells = "".join(
            f"<tr><td>{escape(label)}</td>"
            f"<td class='text-end'>{escape(str(value))}</td></tr>"
            for label, value in rows
        )
        return (
            f"<h5 class='mt-4'>{escape(env._('Space and deduplication'))}</h5>"
            f"<table class='table table-sm'><tbody>{cells}</tbody></table>"
        )

    def _render_duplicates(self, duplicates):
        env = self.env
        chunks = [f"<h5 class='mt-4'>{escape(env._('Duplicate documents'))}</h5>"]
        if not duplicates:
            chunks.append(f"<p>{escape(env._('No duplicate document.'))}</p>")
            return "".join(chunks)
        chunks.append(
            "<table class='table table-sm'><thead><tr>"
            f"<th>{escape(env._('Checksum'))}</th>"
            f"<th class='text-end'>{escape(env._('Copies'))}</th>"
            f"<th class='text-end'>{escape(env._('Size'))}</th>"
            f"<th class='text-end'>{escape(env._('Wasted space'))}</th>"
            "</tr></thead><tbody>"
        )
        for duplicate in duplicates:
            chunks.append(
                "<tr><td><code>{checksum}</code></td>"
                "<td class='text-end'>{copies}</td>"
                "<td class='text-end'>{size}</td>"
                "<td class='text-end'>{wasted}</td></tr>".format(
                    checksum=escape(duplicate["checksum"]),
                    copies=duplicate["copies"],
                    size=escape(_format_size(duplicate["size"])),
                    wasted=escape(_format_size(duplicate["wasted"])),
                )
            )
        chunks.append("</tbody></table>")
        return "".join(chunks)

    def _render_integrity(self, integrity):
        env = self.env
        chunks = [f"<h5 class='mt-4'>{escape(env._('Filestore integrity'))}</h5>"]
        details = env._(
            "%(referenced)s attachment(s) referenced, %(present)s file(s) on disk.",
            referenced=integrity["referenced"],
            present=integrity["present"],
        )
        if integrity["ok"]:
            chunks.append(
                '<div class="alert alert-success" role="alert">'
                f"{escape(env._('All the attachments are present in the filestore.'))}"
                f"<br/>{escape(details)}</div>"
            )
        else:
            chunks.append(
                '<div class="alert alert-warning" role="alert">'
                "<strong>"
                f"{escape(env._('Some attachments are missing from the filestore.'))}"
                f"</strong><br/>{escape(details)}<ul>"
            )
            chunks.extend(
                f"<li><code>{escape(name)}</code></li>" for name in integrity["missing"]
            )
            chunks.append("</ul></div>")
        if integrity["orphan_count"]:
            orphans = env._(
                "%(count)s unreferenced file(s) on disk (waiting for the "
                "filestore garbage collection).",
                count=integrity["orphan_count"],
            )
            chunks.append(f"<p>{escape(orphans)}</p>")
        return "".join(chunks)

    def action_recheck(self):
        """Open a fresh check so the report is computed again."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "dms_storage_guard.action_dms_storage_check"
        )
        action["res_id"] = False
        action["target"] = "new"
        return action
