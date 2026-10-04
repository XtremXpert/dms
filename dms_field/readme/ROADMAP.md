- Add drag & drop compatibility to the dms_tree mode
- Multiple selection support (e.g. cut several files and paste to
  another folder).

- Odoo 20.0: the jsTree/jQuery tree was replaced by a native OWL 3 tree
  (`DmsTree`). Not ported yet: cut / paste and moving nodes by drag and
  drop, the right-click context menu, remembering opened nodes, and
  searching inside the tree.
- `hr_dms_field` must patch `DmsTree.prototype.sanitizeDMSModel` (the tree
  no longer lives in `X2ManyField`).
