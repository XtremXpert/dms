Deliver the *Documents* tab on contacts in the module data instead of demo
data only.

Without this module, `dms_field` ships its contact form view as demo data: a
production database with a field template on contacts shows no tab at all.
The tab is reserved to the `dms.group_dms_user` group, since it reads
`dms.directory` records.
