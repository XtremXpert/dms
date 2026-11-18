Gather the directories created for a record under one directory per model
instead of creating a root directory per record.

Without this module, the directories of the records pile up at the root of
the storage and are reported as a flat list of empty root directories. With
it, the directory of a record is created under a root directory named after
the model, created on first use.

An explicitly configured *Parent directory* on the template keeps precedence.
Storages restricted to some models (`model_ids`) keep the previous behaviour,
because they do not accept a root directory without a linked record.
