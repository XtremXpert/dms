/**
 * Copyright 2026 XtremXpert
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 */

import {deserializeDateTime, formatDateTime} from "@web/core/l10n/dates";
import {url} from "@web/core/utils/urls";

/**
 * Format the UTC datetime strings returned by ``get_dms_preview_data`` in the
 * user's locale and timezone.
 *
 * @param {String} value
 * @returns {String}
 */
export function formatDmsPreviewDate(value) {
    if (!value) {
        return "";
    }
    try {
        return formatDateTime(deserializeDateTime(value));
    } catch {
        return "";
    }
}

/**
 * URL of the PDF.js viewer for a PDF file.
 *
 * @param {String} contentUrl
 * @returns {String}
 */
export function dmsPdfViewerUrl(contentUrl) {
    // PDF.js expects an absolute URL in the "file" parameter: a relative one is
    // treated as a local path and encoded again, which ends up as a 404.
    const file = encodeURIComponent(url(contentUrl));
    return url(`/web/static/lib/pdfjs/web/viewer.html?file=${file}`);
}

/**
 * Open the PDF.js viewer of the file and trigger its print button.
 *
 * @param {Object} data
 */
function printDmsPreviewPdf(data) {
    const win = window.open(dmsPdfViewerUrl(data.urls.content), "_blank");
    if (!win) {
        return;
    }
    let attempts = 0;
    const timer = window.setInterval(() => {
        attempts += 1;
        try {
            const button = win.document.querySelector("#printButton");
            if (button) {
                window.clearInterval(timer);
                button.click();
                return;
            }
        } catch {
            // The viewer document is not reachable yet, retry on next tick.
        }
        if (attempts >= 50) {
            window.clearInterval(timer);
        }
    }, 200);
}

/**
 * Print the file in a new window.
 *
 * Images and text files are rendered in a blank window and printed directly.
 * Browsers cannot print a PDF from JavaScript reliably: open the PDF.js viewer
 * of the file and click its print button once it is ready, which also prints
 * every page (instead of the single page visible on screen).
 *
 * @param {Object} data payload returned by ``get_dms_preview_data``
 */
export function printDmsPreview(data) {
    if (!data) {
        return;
    }
    if (data.category === "pdf") {
        printDmsPreviewPdf(data);
        return;
    }
    const win = window.open("", "_blank");
    if (!win) {
        return;
    }
    win.document.title = data.name || "";
    win.document.body.style.margin = "0";
    if (data.category === "image") {
        const image = win.document.createElement("img");
        image.style.cssText = "display:block;margin:auto;max-width:100%;";
        image.onload = () => {
            win.focus();
            win.print();
        };
        image.src = data.urls.image;
        win.document.body.appendChild(image);
    } else if (data.category === "text") {
        const frame = win.document.createElement("iframe");
        frame.style.cssText = "border:0;width:100vw;height:100vh;";
        frame.onload = () => {
            win.focus();
            frame.contentWindow.print();
        };
        frame.src = data.urls.text;
        win.document.body.appendChild(frame);
    }
}
