The file views of the Document Management System (kanban and list) open the
regular form view when a file is clicked. For a document management system
this is one step too many: the user wants to see the document, and the actions
they need depend on the type of the file.

This module replaces that action with a preview dialog. The document is shown
inside the dialog (image, PDF, text, video or audio) next to the actions the
file and the current user allow: download, edit, print, share, lock, archive,
move or delete.

When ``onlyoffice_odoo_dms`` is installed, office documents are previewed and
edited in ONLYOFFICE without leaving the dialog, and the version history added
by ``dms_versions`` is one click away.
