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


def _migration_steps(env):
    """Remediation shown when a storage is not in the expected mode."""
    return env._(
        "Documents > Configuration > System > Storages: open the storage, set "
        "'Storage Type' to 'Filestore' when it is 'Database', then run the "
        "'Migrate' action. It rewrites every file of the storage, so plan it "
        "when the users are idle."
    )


def _location_steps(env):
    """Remediation shown when the attachment location is the database."""
    return env._(
        "Remove the 'ir_attachment.location' system parameter (or set it to "
        "'file') in Settings > Technical > Parameters > System Parameters."
    )


def _filestore_steps(env):
    """Remediation shown when the filestore directory is not writable."""
    return env._(
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


def collect_space(env):
    """Statistics about the DMS files and the filestore deduplication."""
    # su: read every file and attachment whatever the caller rights.
    env = env(su=True)
    env.cr.execute("SELECT count(*), coalesce(sum(size), 0) FROM dms_file WHERE active")
    files, logical_size = env.cr.fetchone()
    env.cr.execute(
        "SELECT count(*), coalesce(sum(size), 0) FROM dms_file "
        "WHERE active AND content_binary IS NOT NULL"
    )
    database_files, database_size = env.cr.fetchone()
    env.cr.execute(
        """
        SELECT count(DISTINCT f.id), coalesce(sum(f.size), 0)
        FROM dms_file f
        JOIN ir_attachment a
          ON a.res_model = 'dms.file' AND a.res_id = f.id
         AND a.res_field = 'content_file'
        WHERE f.active AND a.store_fname IS NOT NULL
        """
    )
    filestore_files, filestore_logical_size = env.cr.fetchone()
    env.cr.execute(
        """
        SELECT count(*), coalesce(sum(size), 0)
        FROM (
            SELECT a.store_fname, max(a.file_size) AS size
            FROM ir_attachment a
            JOIN dms_file f ON f.id = a.res_id AND a.res_model = 'dms.file'
            WHERE a.res_field = 'content_file'
              AND a.store_fname IS NOT NULL
            GROUP BY a.store_fname
        ) stored
        """
    )
    physical_files, physical_size = env.cr.fetchone()
    logical_size = int(logical_size or 0)
    filestore_logical_size = int(filestore_logical_size or 0)
    physical_size = int(physical_size or 0)
    return {
        "files": files,
        "logical_size": logical_size,
        "database_files": database_files,
        "database_size": int(database_size or 0),
        "filestore_files": filestore_files,
        "filestore_logical_size": filestore_logical_size,
        "physical_files": physical_files,
        "physical_size": physical_size,
        "saved_size": max(filestore_logical_size - physical_size, 0),
    }


def collect_duplicates(env, limit=20):
    """Documents sharing the same content (same checksum)."""
    # su: read every file whatever the caller rights.
    env = env(su=True)
    env.cr.execute(
        """
        SELECT checksum, count(*) AS copies, max(size) AS size
        FROM dms_file
        WHERE active AND checksum IS NOT NULL
        GROUP BY checksum
        HAVING count(*) > 1
        ORDER BY count(*) DESC, max(size) DESC
        LIMIT %s
        """,
        (limit,),
    )
    duplicates = []
    for checksum, copies, size in env.cr.fetchall():
        size = int(size or 0)
        duplicates.append(
            {
                "checksum": checksum,
                "copies": copies,
                "size": size,
                "wasted": size * (copies - 1),
            }
        )
    return duplicates


def check_filestore(env, limit=20):
    """Compare the filestore attachments with the files really on disk."""
    # su: read every attachment whatever the caller rights.
    env = env(su=True)
    filestore = env["ir.attachment"]._filestore()
    env.cr.execute(
        "SELECT DISTINCT store_fname FROM ir_attachment WHERE store_fname IS NOT NULL"
    )
    referenced = {row[0] for row in env.cr.fetchall()}
    missing = sorted(
        name for name in referenced if not os.path.isfile(os.path.join(filestore, name))
    )
    present = 0
    orphans = []
    for dirpath, dirnames, filenames in os.walk(filestore):
        relative = os.path.relpath(dirpath, filestore)
        if relative == ".":
            relative = ""
        if relative.split(os.sep)[0] in ("checklist", "upload"):
            dirnames[:] = []
            continue
        for name in filenames:
            path = "/".join(filter(None, (relative.replace(os.sep, "/"), name)))
            present += 1
            if path not in referenced:
                orphans.append(path)
    orphans.sort()
    return {
        "filestore": filestore,
        "referenced": len(referenced),
        "present": present,
        "missing": missing[:limit],
        "missing_count": len(missing),
        "orphans": orphans[:limit],
        "orphan_count": len(orphans),
        "ok": not missing,
    }


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
                "title": env._("Attachments are stored in the database"),
                "details": env._(
                    "The 'ir_attachment.location' system parameter is set to "
                    "'db': every attachment is written to PostgreSQL, where "
                    "identical contents are duplicated. The filestore "
                    "deduplication is disabled."
                ),
                "remediation": _location_steps(env),
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
                    "title": env._("The filestore directory is not writable"),
                    "details": env._(
                        "The filestore directory %(path)s cannot be written by "
                        "the Odoo user.",
                        path=filestore,
                    ),
                    "remediation": _filestore_steps(env),
                }
            )
    storages = _storage_report(env)
    for storage in storages:
        if storage["save_type"] == "database":
            problems.append(
                {
                    "code": "storage_database",
                    "title": env._(
                        "Storage %(name)s stores its files in the database",
                        name=f"'{storage['name']}'",
                    ),
                    "details": env._(
                        "%(count)s file(s) of this storage are stored in "
                        "PostgreSQL, where identical contents are duplicated.",
                        count=storage["files"],
                    ),
                    "remediation": _migration_steps(env),
                }
            )
        elif storage["pending_migrations"]:
            problems.append(
                {
                    "code": "storage_pending_migration",
                    "title": env._(
                        "Storage %(name)s has files waiting for a migration",
                        name=f"'{storage['name']}'",
                    ),
                    "details": env._(
                        "%(count)s file(s) of this storage are not stored in the "
                        "storage type they should be.",
                        count=storage["pending_migrations"],
                    ),
                    "remediation": _migration_steps(env),
                }
            )
    return {
        "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
        "attachment_location": location,
        "storages": storages,
        "problems": problems,
    }


def format_problems(env, report):
    """Human readable message explaining every problem and its remediation."""
    lines = [
        env._(
            "DMS Storage Guard cannot be installed: %(count)s problem(s) were "
            "found in the document storage.",
            count=len(report["problems"]),
        ),
        "",
    ]
    for problem in report["problems"]:
        lines.extend(
            [
                f"- {problem['title']}",
                f"  {problem['details']}",
                env._(
                    "  To fix it: %(remediation)s", remediation=problem["remediation"]
                ),
                "",
            ]
        )
    lines.append(
        env._(
            "Fix the problems above, then retry the installation. To install "
            "anyway (demo or test database), set the system parameter "
            "'dms_storage_guard.allow_database_storage' to '1'."
        )
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
    raise UserError(format_problems(env, report))
