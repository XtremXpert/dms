# Copyright 2026 XtremXpert
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

"""Pre-installation guard for the DMS document storages.

DMS can keep the content of its files in the database, in the filestore or in
existing attachments.  Only the filestore mode is content-addressed: identical
contents are stored once, while the database mode duplicates every copy in
PostgreSQL (and in its backups).

This module refuses to install while documents are still stored in the
database, or while files are waiting for a storage migration, and explains how
to fix the storage first.  The same diagnosis is available from a dedicated
screen once the module is installed.
"""

import json
import logging
import os

from odoo import fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

REPORT_PARAM = "dms_storage_guard.last_report"
ALLOW_DATABASE_PARAM = "dms_storage_guard.allow_database_storage"
ATTACHMENT_LOCATION_PARAM = "ir_attachment.location"

MIGRATION_STEPS = (
    "Documents > Configuration > System > Storages: open the storage, set "
    "'Storage Type' to 'Filestore' when it is 'Database', then run the "
    "'Migrate' action. It rewrites every file of the storage, so plan it when "
    "the users are idle."
)

LOCATION_STEPS = (
    "Remove the 'ir_attachment.location' system parameter (or set it to "
    "'file') in Settings > Technical > Parameters > System Parameters."
)

FILESTORE_STEPS = (
    "Make the filestore directory writable by the Odoo user (for example "
    "'chown odoo: /var/lib/odoo/filestore/<database>') and retry."
)


def _storage_report(env):
    """Return one description dict per DMS storage."""
    File = env["dms.file"].with_context(active_test=False)
    storages = []
    for storage in env["dms.storage"].search([]):
        storages.append(
            {
                "id": storage.id,
                "name": storage.name,
                "save_type": storage.save_type,
                "files": File.search_count([("storage_id", "=", storage.id)]),
                "pending_migrations": File.search_count(
                    [
                        ("storage_id", "=", storage.id),
                        ("require_migration", "=", True),
                    ]
                ),
            }
        )
    return storages


def collect_report(env):
    """Diagnose the DMS storages and return a JSON-serialisable report."""
    # su: read every storage, file and parameter whatever the caller rights.
    env = env(su=True)
    problems = []
    location = (
        (env["ir.config_parameter"].get_str(ATTACHMENT_LOCATION_PARAM) or "file")
        .strip()
        .lower()
    )
    if location == "db":
        problems.append(
            {
                "code": "attachment_location",
                "title": "Attachments are stored in the database",
                "details": (
                    "The 'ir_attachment.location' system parameter is set to "
                    "'db': every attachment is written to PostgreSQL, where "
                    "identical contents are duplicated. The filestore "
                    "deduplication is disabled."
                ),
                "remediation": LOCATION_STEPS,
            }
        )
    else:
        filestore = env["ir.attachment"]._filestore()
        writable = True
        try:
            os.makedirs(filestore, exist_ok=True)
            writable = os.access(filestore, os.W_OK)
        except OSError:
            writable = False
        if not writable:
            problems.append(
                {
                    "code": "filestore_not_writable",
                    "title": "The filestore directory is not writable",
                    "details": (
                        f"The filestore directory '{filestore}' cannot be "
                        "written by the Odoo user."
                    ),
                    "remediation": FILESTORE_STEPS,
                }
            )
    storages = _storage_report(env)
    for storage in storages:
        if storage["save_type"] == "database":
            problems.append(
                {
                    "code": "storage_database",
                    "title": (
                        f"Storage '{storage['name']}' stores its files in the database"
                    ),
                    "details": (
                        f"{storage['files']} file(s) of this storage are stored in "
                        "PostgreSQL, where identical contents are duplicated."
                    ),
                    "remediation": MIGRATION_STEPS,
                }
            )
        elif storage["pending_migrations"]:
            problems.append(
                {
                    "code": "storage_pending_migration",
                    "title": (
                        f"Storage '{storage['name']}' has files waiting for a migration"
                    ),
                    "details": (
                        f"{storage['pending_migrations']} file(s) of this storage "
                        "are not stored in the storage type they should be."
                    ),
                    "remediation": MIGRATION_STEPS,
                }
            )
    return {
        "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
        "attachment_location": location,
        "storages": storages,
        "problems": problems,
    }


def format_problems(report):
    """Human readable message explaining every problem and its remediation."""
    lines = [
        (
            "DMS Storage Guard cannot be installed: "
            f"{len(report['problems'])} problem(s) were found in the document storage."
        ),
        "",
    ]
    for problem in report["problems"]:
        lines.extend(
            [
                f"- {problem['title']}",
                f"  {problem['details']}",
                f"  To fix it: {problem['remediation']}",
                "",
            ]
        )
    lines.append(
        "Fix the problems above, then retry the installation. To install "
        "anyway (demo or test database), set the system parameter "
        "'dms_storage_guard.allow_database_storage' to '1'."
    )
    return "\n".join(lines)


def pre_init_hook(env):
    """Refuse the installation while the documents are not deduplicated."""
    # su: the install hook must see every storage without DMS access.
    env = env(su=True)
    report = collect_report(env)
    env["ir.config_parameter"].set_str(
        REPORT_PARAM, json.dumps(report, ensure_ascii=False)
    )
    if not report["problems"]:
        _logger.info("DMS Storage Guard: no storage problem found.")
        return
    dms_module = env["ir.module.module"].search([("name", "=", "dms")], limit=1)
    if dms_module.demo:
        _logger.warning(
            "DMS Storage Guard: %s problem(s) found, installation allowed "
            "because the database uses demo data.",
            len(report["problems"]),
        )
        return
    allowed = (
        (env["ir.config_parameter"].get_str(ALLOW_DATABASE_PARAM) or "").strip().lower()
    )
    if allowed in ("1", "true", "yes", "on"):
        _logger.warning(
            "DMS Storage Guard: %s problem(s) found, installation explicitly "
            "allowed by the '%s' system parameter.",
            len(report["problems"]),
            ALLOW_DATABASE_PARAM,
        )
        return
    raise UserError(format_problems(report))
