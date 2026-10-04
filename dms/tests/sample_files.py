# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Petits fichiers réalistes des types les plus courants, générés en mémoire
(pas de binaires dans le dépôt) pour les tests d'envoi."""

import base64
import io
import zipfile

from PIL import Image


def _image(fmt, mode="RGB"):
    buffer = io.BytesIO()
    Image.new(mode, (8, 8), (200, 30, 30)).save(buffer, fmt)
    return buffer.getvalue()


def _zip(entries, first=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if first:
            # OpenDocument : « mimetype » doit être la première entrée, non compressée
            archive.writestr(
                zipfile.ZipInfo(first[0]), first[1], compress_type=zipfile.ZIP_STORED
            )
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _ooxml(main_part, content_type):
    return _zip(
        {
            "[Content_Types].xml": (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                'content-types"><Override PartName="/' + main_part + '" '
                'ContentType="' + content_type + '"/></Types>'
            ),
            "_rels/.rels": "<Relationships/>",
            main_part: "<root/>",
        }
    )


def _odf(mimetype, extra):
    return _zip(
        {"content.xml": "<office:document-content/>", **extra},
        first=("mimetype", mimetype),
    )


# Odoo restreint les encodeurs Pillow (pas de WEBP) : image fixe 1x1.
WEBP = base64.b64decode("UklGRiIAAABXRUJQVlA4TBEAAAAvAAAAAAfQ//73v/+BiOh/AAA=")

PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)

# nom de fichier -> (contenu, types MIME acceptés)
SAMPLES = {
    "facture.pdf": (PDF, {"application/pdf"}),
    "photo.jpg": (_image("JPEG"), {"image/jpeg"}),
    "capture.png": (_image("PNG"), {"image/png"}),
    "anim.gif": (_image("GIF", "P"), {"image/gif"}),
    "image.webp": (WEBP, {"image/webp"}),
    "lettre.docx": (
        _ooxml(
            "word/document.xml",
            "application/vnd.openxmlformats-officedocument.wordprocessingml"
            ".document.main+xml",
        ),
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ),
    "budget.xlsx": (
        _ooxml(
            "xl/workbook.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml"
            ".sheet.main+xml",
        ),
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ),
    "presentation.pptx": (
        _ooxml(
            "ppt/presentation.xml",
            "application/vnd.openxmlformats-officedocument.presentationml"
            ".presentation.main+xml",
        ),
        {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ),
    "texte.odt": (
        _odf("application/vnd.oasis.opendocument.text", {}),
        {"application/vnd.oasis.opendocument.text"},
    ),
    "calcul.ods": (
        _odf("application/vnd.oasis.opendocument.spreadsheet", {}),
        {"application/vnd.oasis.opendocument.spreadsheet"},
    ),
    "export.csv": (
        "date;montant;libellé\n2026-10-04;12,50;café\n".encode(),
        {"text/csv", "text/plain"},
    ),
    "notes.txt": ("Liste d'épicerie : œufs, pain\n".encode(), {"text/plain"}),
    "archive.zip": (_zip({"a.txt": "a"}), {"application/zip"}),
    "musique.mp3": (
        b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x64" + b"\x00" * 400,
        {"audio/mpeg"},
    ),
    "video.mp4": (
        b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 400,
        {"video/mp4"},
    ),
}
