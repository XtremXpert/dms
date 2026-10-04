// License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//
// Envoi de fichiers vers /web/binary/upload_dms_file, partagé par les vues
// Fichiers (dms) et l'arborescence des fiches (dms_field).
// Le service « http » d'Odoo 20 ne lève une erreur que pour 413 et 502 : une
// autre réponse en erreur (ex. 408 si l'envoi marque une pause trop longue)
// renvoyait du HTML, et JSON.parse produisait une erreur incompréhensible.
import {_t} from "@web/core/l10n/translation";

export class DmsUploadError extends Error {}

function messageForStatus(status) {
    switch (status) {
        case 408:
            return _t(
                "The upload was interrupted because the connection was too slow. Please try again."
            );
        case 413:
            return _t("The file is too large to be uploaded.");
        case 403:
            return _t("You are not allowed to upload a file here.");
        case 502:
        case 503:
        case 504:
            return _t("The server is unavailable. Please try again in a moment.");
        default:
            return _t("The upload failed (HTTP error %s).", status);
    }
}

/**
 * Envoie les fichiers dans le répertoire et renvoie une entrée par fichier
 * ({id, filename, …} ou {error}). Lève DmsUploadError avec un message lisible
 * si la requête elle-même échoue.
 */
export async function uploadDmsFiles(http, directoryId, files) {
    let response = null;
    try {
        response = await http.post(
            "/web/binary/upload_dms_file",
            {
                csrf_token: odoo.csrf_token,
                ufile: [...files],
                directory_id: directoryId,
            },
            "response"
        );
    } catch (error) {
        // Le service lève pour 413 / 502, ou fetch échoue (réseau coupé).
        const status = /too large/i.test(error.message) ? 413 : 502;
        throw new DmsUploadError(messageForStatus(status), {cause: error});
    }
    if (!response.ok) {
        throw new DmsUploadError(messageForStatus(response.status));
    }
    try {
        return [].concat(await response.json());
    } catch (error) {
        throw new DmsUploadError(_t("Unexpected response from the server."), {
            cause: error,
        });
    }
}
