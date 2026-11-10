No external dependency.

The module refuses to install while a DMS storage keeps its files in the
database, or while files are waiting for a storage migration, and explains how
to migrate them first (Documents > Configuration > System > Storages).

On a database that uses demo data, the check only logs a warning so the module
can still be installed for tests. To install anyway on another database, set
the system parameter ``dms_storage_guard.allow_database_storage`` to ``1``.
