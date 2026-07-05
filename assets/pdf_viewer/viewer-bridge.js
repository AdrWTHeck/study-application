/* viewer-bridge.js — PDF.js rendering + QWebChannel bridge */
"use strict";

// ── State ─────────────────────────────────────────────────────────────────────
var pdfDoc      = null;
var currentPage = 1;
var totalPages  = 0;
var currentScale = 1.5;
var pageAnnots  = [];           // [{xref, rect:{x0,y0,x1,y1}}] normalized 0..1
var bridge      = null;         // QWebChannel bridge object (set after handshake)
var renderTask  = null;         // active PDF.js render task (for cancellation)

// ── Bridge init ───────────────────────────────────────────────────────────────
new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.bridge;
});

// ── PDF loading ───────────────────────────────────────────────────────────────

window.loadPdfBase64 = function(b64, targetPage) {
    // Decode base64 → Uint8Array → PDF.js document
    var raw = atob(b64);
    var buf = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);

    if (renderTask) { renderTask.cancel(); renderTask = null; }

    pdfjsLib.getDocument({ data: buf }).promise.then(function(doc) {
        pdfDoc     = doc;
        totalPages = doc.numPages;
        currentPage = Math.max(1, Math.min(targetPage || 1, totalPages));
        document.getElementById("loadingMsg").style.display = "none";
        renderPage(currentPage);
    }).catch(function(err) {
        document.getElementById("loadingMsg").textContent = "Error: " + err.message;
    });
};

// ── Page rendering ────────────────────────────────────────────────────────────

function renderPage(pageNum) {
    if (!pdfDoc) return;
    pageNum = Math.max(1, Math.min(pageNum, totalPages));
    currentPage = pageNum;

    if (renderTask) { renderTask.cancel(); renderTask = null; }

    pdfDoc.getPage(pageNum).then(function(page) {
        var viewport = page.getViewport({ scale: currentScale });
        var container = document.getElementById("viewerContainer");
        container.innerHTML = "";

        var wrapper = document.createElement("div");
        wrapper.className = "page-wrapper";
        container.appendChild(wrapper);

        var canvas = document.createElement("canvas");
        canvas.width  = viewport.width;
        canvas.height = viewport.height;
        wrapper.appendChild(canvas);
        wrapper.style.width  = viewport.width  + "px";
        wrapper.style.height = viewport.height + "px";

        var ctx = canvas.getContext("2d");
        renderTask = page.render({ canvasContext: ctx, viewport: viewport });

        renderTask.promise.then(function() {
            renderTask = null;
            return page.getTextContent();
        }).then(function(textContent) {
            buildTextLayer(wrapper, textContent, viewport);
            buildAnnotLayer(wrapper, pageAnnots, viewport);
        }).catch(function() { renderTask = null; });
    });
}

function buildTextLayer(wrapper, textContent, viewport) {
    var div = document.createElement("div");
    div.className = "textLayer";
    div.style.setProperty("--scale-factor", viewport.scale);
    wrapper.appendChild(div);

    var task = pdfjsLib.renderTextLayer({
        textContentSource: textContent,
        container: div,
        viewport: viewport,
        textDivs: [],
    });
    if (task && task.promise) task.promise.catch(function() {});
}

function buildAnnotLayer(wrapper, annots, viewport) {
    if (!annots || !annots.length) return;

    var layer = document.createElement("div");
    layer.style.cssText =
        "position:absolute;top:0;left:0;width:" + viewport.width +
        "px;height:" + viewport.height + "px;pointer-events:none;";
    wrapper.appendChild(layer);

    annots.forEach(function(a) {
        var r = a.rect;
        var hit = document.createElement("div");
        hit.style.cssText = [
            "position:absolute",
            "pointer-events:auto",
            "cursor:pointer",
            "left:"   + (r.x0 * viewport.width)           + "px",
            "top:"    + (r.y0 * viewport.height)           + "px",
            "width:"  + ((r.x1 - r.x0) * viewport.width)  + "px",
            "height:" + ((r.y1 - r.y0) * viewport.height) + "px",
        ].join(";");
        hit.addEventListener("contextmenu", function(e) {
            e.preventDefault();
            e.stopPropagation();
            if (bridge) bridge.showContextMenu("", "[]", parseInt(a.xref), currentPage - 1);
        });
        layer.appendChild(hit);
    });
}

// ── Python-callable API ───────────────────────────────────────────────────────

window.goToPage = function(pageNum) {
    renderPage(pageNum);
    if (bridge) bridge.onPageChanged(pageNum);
};

window.setZoom = function(scale) {
    currentScale = Math.max(0.5, Math.min(scale, 4.0));
    if (pdfDoc) renderPage(currentPage);
};

window.setPageAnnotations = function(annots) {
    pageAnnots = Array.isArray(annots) ? annots : [];
    if (pdfDoc) renderPage(currentPage);
};

// Called by Python before reloading with new bytes — no-op, loadPdfBase64 handles it.
window.reloadCurrentPage = function() {};

// ── Selection rect helpers ────────────────────────────────────────────────────

// Collapse per-span rects into one wide rect per visual line.
// Two rects are on the same line when vertical-center distance < 60 % of line height.
// This mirrors merge_line_rects() in reader_view.py — both must stay in sync.
function mergeLineRects(rects) {
    if (rects.length <= 1) return rects;
    rects.sort(function(a, b) {
        return a.y0 !== b.y0 ? a.y0 - b.y0 : a.x0 - b.x0;
    });
    var merged = [];
    var cur = { x0: rects[0].x0, y0: rects[0].y0,
                x1: rects[0].x1, y1: rects[0].y1 };
    for (var i = 1; i < rects.length; i++) {
        var r = rects[i];
        var curMid = (cur.y0 + cur.y1) / 2;
        var rMid   = (r.y0  + r.y1)  / 2;
        var lineH  = Math.max(cur.y1 - cur.y0, r.y1 - r.y0);
        if (Math.abs(rMid - curMid) < lineH * 0.6) {
            cur.x0 = Math.min(cur.x0, r.x0);
            cur.x1 = Math.max(cur.x1, r.x1);
            cur.y0 = Math.min(cur.y0, r.y0);
            cur.y1 = Math.max(cur.y1, r.y1);
        } else {
            merged.push(cur);
            cur = { x0: r.x0, y0: r.y0, x1: r.x1, y1: r.y1 };
        }
    }
    merged.push(cur);
    return merged;
}

// Diagnostic: call via Python runJavaScript("debugSelRects()", cb) to inspect
// raw vs merged rect counts without needing DevTools open.
window.debugSelRects = function() {
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return "{}";
    var range = sel.getRangeAt(0);
    var wrapper = document.querySelector(".page-wrapper");
    if (!wrapper) return "{}";
    var wr = wrapper.getBoundingClientRect();
    var raw = [];
    var rects = range.getClientRects();
    for (var i = 0; i < rects.length; i++) {
        var r = rects[i];
        if (r.width >= 1 && r.height >= 1)
            raw.push({ x0: (r.left - wr.left) / wr.width,
                       y0: (r.top  - wr.top)  / wr.height,
                       x1: (r.right  - wr.left) / wr.width,
                       y1: (r.bottom - wr.top)  / wr.height });
    }
    return JSON.stringify({
        rawCount:    raw.length,
        mergedCount: mergeLineRects(raw.slice()).length,
        wrapperW:    Math.round(wr.width),
        wrapperH:    Math.round(wr.height)
    });
};

// ── Right-click → bridge ──────────────────────────────────────────────────────

document.addEventListener("contextmenu", function(e) {
    if (e.defaultPrevented) return;   // annot-hit already handled it
    e.preventDefault();

    var sel = window.getSelection();
    var text = sel ? sel.toString().trim() : "";
    var selRects = [];

    // Capture DOM bounding boxes of the selection so Python can annotate by
    // position rather than re-searching the PDF text stream by string content.
    if (sel && sel.rangeCount > 0 && text) {
        var range = sel.getRangeAt(0);
        var wrapper = document.querySelector(".page-wrapper");
        if (wrapper) {
            var wr = wrapper.getBoundingClientRect();
            if (wr.width > 0 && wr.height > 0) {
                var rects = range.getClientRects();
                for (var i = 0; i < rects.length; i++) {
                    var r = rects[i];
                    if (r.width < 1 || r.height < 1) continue;   // skip empty boundary rects
                    selRects.push({
                        x0: (r.left   - wr.left) / wr.width,
                        y0: (r.top    - wr.top)  / wr.height,
                        x1: (r.right  - wr.left) / wr.width,
                        y1: (r.bottom - wr.top)  / wr.height
                    });
                }
            }
        }
    }

    selRects = mergeLineRects(selRects);   // collapse per-word → per-line
    if (bridge) bridge.showContextMenu(text, JSON.stringify(selRects), -1, -1);
});

document.addEventListener("copy", function(e) {
    var sel = window.getSelection();
    if (!sel || !sel.toString().trim()) return;
    var text = sel.toString();
    // Preserve paragraph structure: double (or more) newlines are genuine section
    // breaks; single newlines are visual line-wraps within a paragraph.
    var clean = text
        .replace(/\r\n/g, "\n")
        .replace(/\n{2,}/g, "\0PARA\0")   // mark real paragraph / section gaps
        .replace(/\n/g, " ")               // collapse visual line-wraps to space
        .replace(/\0PARA\0/g, "\n\n")      // restore paragraph breaks
        .replace(/[ \t]{2,}/g, " ")        // collapse multiple spaces within lines
        .trim();
    e.clipboardData.setData("text/plain", clean);
    e.preventDefault();
});

// ── In-viewer find bar ────────────────────────────────────────────────────────

var findMatches = [], findIndex = -1, findHL = null;

window.openFindBar = function() {
    document.getElementById("findBar").classList.add("visible");
    document.getElementById("findInput").focus();
};

document.getElementById("findClose").addEventListener("click", function() {
    document.getElementById("findBar").classList.remove("visible");
    if (findHL) { findHL.style.background = ""; findHL = null; }
});
document.getElementById("findNext").addEventListener("click", function() { findStep(1); });
document.getElementById("findPrev").addEventListener("click", function() { findStep(-1); });
document.getElementById("findInput").addEventListener("input", function() { runFind(this.value); });
document.getElementById("findInput").addEventListener("keydown", function(e) {
    if (e.key === "Enter") findStep(e.shiftKey ? -1 : 1);
    if (e.key === "Escape") document.getElementById("findClose").click();
});

function runFind(q) {
    if (findHL) { findHL.style.background = ""; findHL = null; }
    findMatches = []; findIndex = -1;
    if (!q || !q.trim()) { setFindStatus(""); return; }
    document.querySelectorAll(".textLayer span").forEach(function(s) {
        if (s.textContent.toLowerCase().indexOf(q.toLowerCase()) >= 0) findMatches.push(s);
    });
    setFindStatus(findMatches.length + " result" + (findMatches.length !== 1 ? "s" : ""));
    if (findMatches.length) findStep(1);
}

function findStep(dir) {
    if (!findMatches.length) return;
    if (findHL) findHL.style.background = "";
    findIndex = (findIndex + dir + findMatches.length) % findMatches.length;
    findHL = findMatches[findIndex];
    findHL.style.background = "rgba(255,165,0,0.55)";
    findHL.scrollIntoView({ behavior: "smooth", block: "center" });
    setFindStatus((findIndex + 1) + " / " + findMatches.length);
}

function setFindStatus(msg) { document.getElementById("findStatus").textContent = msg; }

document.addEventListener("keydown", function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "f") { e.preventDefault(); window.openFindBar(); }
});

// ── Annotation keyboard shortcuts ─────────────────────────────────────────────
// H = highlight  U = underline  S = strikeout
// Only fires when text is selected; skipped while typing in the find bar.
document.addEventListener("keydown", function(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (!bridge) return;
    // Don't steal keystrokes from the find-bar input
    if (document.activeElement === document.getElementById("findInput")) return;

    var key = e.key.toLowerCase();
    if (key !== "h" && key !== "u" && key !== "s") return;

    var sel = window.getSelection();
    var text = sel ? sel.toString().trim() : "";
    if (!text) return;   // require an active selection

    e.preventDefault();

    var selRects = [];
    if (sel.rangeCount > 0) {
        var range = sel.getRangeAt(0);
        var wrapper = document.querySelector(".page-wrapper");
        if (wrapper) {
            var wr = wrapper.getBoundingClientRect();
            if (wr.width > 0 && wr.height > 0) {
                var rects = range.getClientRects();
                for (var i = 0; i < rects.length; i++) {
                    var r = rects[i];
                    if (r.width >= 1 && r.height >= 1)
                        selRects.push({
                            x0: (r.left   - wr.left) / wr.width,
                            y0: (r.top    - wr.top)  / wr.height,
                            x1: (r.right  - wr.left) / wr.width,
                            y1: (r.bottom - wr.top)  / wr.height
                        });
                }
            }
        }
    }
    selRects = mergeLineRects(selRects);

    var mode = key === "h" ? "highlight" : key === "u" ? "underline" : "strikeout";
    bridge.quickAnnotate(text, JSON.stringify(selRects), mode, currentPage - 1);
});
