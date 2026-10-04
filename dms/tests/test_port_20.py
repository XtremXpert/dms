# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Régressions propres au port Odoo 20."""

from odoo.tests import Form, HttpCase, new_test_user, tagged

from .common import DocumentsBaseCase
from .sample_files import SAMPLES


class TestOnchangeKeepsDefaults(DocumentsBaseCase):
    def test_new_directory_keeps_default_parent(self):
        """_compute_permissions ne doit pas vider le cache d'un enregistrement
        en cours d'édition : le parent par défaut doit survivre à l'onchange."""
        storage = self.create_storage()
        parent = self.create_directory(storage=storage)
        form = Form(
            self.directory_model.with_user(self.dms_user).with_context(
                default_parent_id=parent.id
            )
        )
        self.assertEqual(form.parent_id, parent)
        self.assertEqual(form.storage_id, storage)
        form.name = "Enfant"
        child = form.save()
        self.assertEqual(child.parent_id, parent)


@tagged("post_install", "-at_install")
class TestRenderText(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env,
            login="dms-render",
            password="dms-render",
            groups="dms.group_dms_user",
        )
        cls.outsider = new_test_user(
            cls.env,
            login="dms-outsider",
            password="dms-outsider",
            groups="dms.group_dms_user",
        )
        group = cls.env["dms.access.group"].create(
            {
                "name": "Rendu texte",
                "perm_create": True,
                "explicit_user_ids": [(6, 0, cls.user.ids)],
            }
        )
        storage = cls.env["dms.storage"].create(
            {"name": "Rendu texte", "save_type": "database"}
        )
        directory = cls.env["dms.directory"].create(
            {
                "name": "Rendu texte",
                "is_root_directory": True,
                "storage_id": storage.id,
                "group_ids": [(6, 0, group.ids)],
            }
        )
        cls.file = cls.env["dms.file"].create(
            {
                "name": "note.txt",
                "directory_id": directory.id,
                "content": "Qm9uam91ciBkbXM=",  # « Bonjour dms »
            }
        )

    def test_render_text(self):
        url = f"/dms/file/render_text/{self.file.id}"
        self.authenticate("dms-render", "dms-render")
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Bonjour dms", response.text)
        self.assertIn("sandbox", response.headers["Content-Security-Policy"])

    def test_render_text_without_access(self):
        self.authenticate("dms-outsider", "dms-outsider")
        response = self.url_open(f"/dms/file/render_text/{self.file.id}")
        self.assertEqual(response.status_code, 404)

    def test_upload_json_response(self):
        """Réponse en application/json ; un doublon renvoie une erreur sans
        bloquer les autres fichiers ni laisser de dms.file vide."""
        self.authenticate("dms-render", "dms-render")
        directory = self.file.directory_id
        response = self.url_open(
            "/web/binary/upload_dms_file",
            data={"directory_id": directory.id, "csrf_token": self.csrf_token()},
            files=[
                ("ufile", ("note.txt", b"doublon", "text/plain")),
                ("ufile", ("nouveau.txt", b"nouveau", "text/plain")),
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers["Content-Type"])
        duplicate, created = response.json()
        self.assertIn("error", duplicate)
        self.assertEqual(created["filename"], "nouveau.txt")
        names = directory.file_ids.mapped("name")
        self.assertEqual(sorted(names), ["note.txt", "nouveau.txt"])


@tagged("post_install", "-at_install")
class TestUploadCommonTypes(HttpCase):
    """Envoi réel (route /web/binary/upload_dms_file) des types de fichiers
    les plus courants, en stockage base de données et en stockage fichier."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env,
            login="dms-types",
            password="dms-types",
            groups="dms.group_dms_user",
        )
        group = cls.env["dms.access.group"].create(
            {
                "name": "Types courants",
                "perm_create": True,
                "explicit_user_ids": [(6, 0, cls.user.ids)],
            }
        )
        cls.directories = {}
        for save_type in ("database", "file"):
            storage = cls.env["dms.storage"].create(
                {"name": f"Types {save_type}", "save_type": save_type}
            )
            cls.directories[save_type] = cls.env["dms.directory"].create(
                {
                    "name": f"Types {save_type}",
                    "is_root_directory": True,
                    "storage_id": storage.id,
                    "group_ids": [(6, 0, group.ids)],
                }
            )

    def _upload(self, directory):
        response = self.url_open(
            "/web/binary/upload_dms_file",
            data={"directory_id": directory.id, "csrf_token": self.csrf_token()},
            files=[
                ("ufile", (name, data, "application/octet-stream"))
                for name, (data, _mimetypes) in SAMPLES.items()
            ],
        )
        self.assertEqual(response.status_code, 200)
        return {item["filename"]: item for item in response.json()}

    def test_upload_common_types(self):
        self.authenticate("dms-types", "dms-types")
        for save_type, directory in self.directories.items():
            results = self._upload(directory)
            for name, (data, mimetypes) in SAMPLES.items():
                with self.subTest(storage=save_type, file=name):
                    self.assertIn(name, results, results)
                    self.assertNotIn("error", results[name])
                    record = self.env["dms.file"].browse(results[name]["id"])
                    self.assertIn(record.mimetype, mimetypes)
                    self.assertEqual(record.size, len(data))
                    self.assertEqual(record.save_type, save_type)
                    self.assertEqual(bytes(record.content), data)
                    download = self.url_open(
                        f"/web/content/dms.file/{record.id}/content?download=true"
                    )
                    self.assertEqual(download.status_code, 200)
                    self.assertEqual(download.content, data)
