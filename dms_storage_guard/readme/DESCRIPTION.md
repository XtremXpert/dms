DMS can keep the content of its files in the database, in the Odoo filestore
or in existing attachments linked to a record. Only the filestore is
content-addressed: identical files share the same physical file, while the
database mode duplicates every copy in PostgreSQL and in its backups.

This module adds a pre-installation guard: it refuses to install while a DMS
storage still keeps its files in the database, or while files are waiting for
a storage migration, and explains how to migrate them first. Once installed,
the same diagnosis is available from a dedicated screen.
