Click a file in a directory (kanban card or list row): a dialog shows the
content of the file and the actions available for its type.

- **Download** is always available.
- **Edit** opens the file in the ONLYOFFICE editor *inside* the dialog when
  ``onlyoffice_odoo_dms`` is installed and the format is editable there; the
  button becomes *Finish editing* and the content is reloaded when it is
  clicked. Otherwise the file form opens, from which the content can be
  replaced.
- Office documents are previewed in ONLYOFFICE inside the dialog too, when the
  integration module is installed.
- **Print** is offered for images, PDFs and text files.
- **Share** opens the portal share wizard of the file.
- The button with the arrows enlarges the dialog, the other one opens the
  native Odoo viewer (zoom, rotation, print) for images, PDFs, text, audio and
  video.
- The **More actions** menu holds Copy the share link, Versions (when
  ``dms_versions`` is installed), Details, Move, Lock/Unlock,
  Archive/Restore and Delete.
- The arrows on the sides of the preview, or the left and right keyboard
  keys, go to the previous or next file of the current page.

The form view remains reachable: *Details* in the dialog, *Open* in the card
dropdown, or any view that references the regular DMS views explicitly (for
example the file selector wizard).
