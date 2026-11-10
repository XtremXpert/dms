The DMS addons can keep the content of a document in the database, in the
Odoo filestore or in existing attachments. The filestore is content-addressed:
identical contents are stored once, while the database mode duplicates every
copy in PostgreSQL and in its backups.

On a database that already holds documents, installing a storage-related
module without checking the storage mode hides silent costs: a larger
database, heavier backups, slower restores, and files whose storage type no
longer matches the storage configuration.
