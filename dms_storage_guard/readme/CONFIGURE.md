The check runs before the installation and blocks it when a storage needs an
action. It is bypassed automatically on a database that uses demo data.

To install anyway on another database, set the system parameter
``dms_storage_guard.allow_database_storage`` to ``1``.
