/**
 * VizData AI — Frontend Application Logic (v3 Sheets UI)
 */

const API = window.location.origin;

// ═══ STATE ═══
let state = {
    sheetId: null,
    sheetData: null,
    isDataLoading: false,
    isAnalyticsLoading: false,
    activeBot: 'data' // 'data' or 'analytics'
};

// ═══ DOM ELEMENTS ═══
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// App Screens
const homeScreen = $("#homeScreen");
const sheetsApp = $("#sheetsApp");

// Upload / Create
const fileInput = $("#fileInput");
const dropOverlay = $("#dropOverlay");
const createModal = $("#createModal");
const createOverlay = $("#createOverlay");
const datasetNameInput = $("#datasetName");
const datasetColumnsInput = $("#datasetColumns");
const loadingOverlay = $("#loadingOverlay");
const loadingText = $("#loadingText");

// Menu / Toolbar
const sheetFilename = $("#sheetFilename");
const sidebarToggle = $("#sidebarToggle");
const cellRef = $("#cellRef");
const formulaInput = $("#formulaInput");

// Sidebar
const chatSidebar = $("#chatSidebar");
const sidebarClose = $("#sidebarClose");
const tabData = $("#tabData");
const tabAnalytics = $("#tabAnalytics");
const dataChatPane = $("#dataChatPane");
const analyticsChatPane = $("#analyticsChatPane");

// Grid
const gridHead = $("#gridHead");
const gridBody = $("#gridBody");
const emptyGrid = $("#emptyGrid");
const sheetGrid = $("#sheetGrid");

// Chat UI - Data
const dataMessages = $("#dataMessages");
const dataForm = $("#dataForm");
const dataInput = $("#dataInput");
const dataSend = $("#dataSend");
const dataTyping = $("#dataTyping");

// Chat UI - Analytics
const analyticsMessages = $("#analyticsMessages");
const analyticsForm = $("#analyticsForm");
const analyticsInput = $("#analyticsInput");
const analyticsSend = $("#analyticsSend");
const analyticsTyping = $("#analyticsTyping");

// Bottom Footer
const sheetTabName = $("#sheetTabName");
const sheetDims = $("#sheetDims");

// Charts
const chartModal = $("#chartModal");
const chartImage = $("#chartImage");

// ═══════════════════════════════════════════
// SIDEBAR & TABS
// ═══════════════════════════════════════════

function toggleSidebar(forceState) {
    const isOpen = chatSidebar.classList.contains("open");
    const newState = forceState !== undefined ? forceState : !isOpen;

    if (newState) {
        chatSidebar.classList.remove("closed");
        chatSidebar.classList.add("open");
        sidebarToggle.classList.remove("inactive");
    } else {
        chatSidebar.classList.remove("open");
        chatSidebar.classList.add("closed");
        sidebarToggle.classList.add("inactive");
    }
}

sidebarToggle.addEventListener("click", () => toggleSidebar());
sidebarClose.addEventListener("click", () => toggleSidebar(false));

function switchBotTab(bot) {
    state.activeBot = bot;
    if (bot === 'data') {
        tabData.classList.add("active");
        tabAnalytics.classList.remove("active");
        dataChatPane.classList.add("active");
        analyticsChatPane.classList.remove("active");
        setTimeout(() => dataInput.focus(), 50);
    } else {
        tabAnalytics.classList.add("active");
        tabData.classList.remove("active");
        analyticsChatPane.classList.add("active");
        dataChatPane.classList.remove("active");
        setTimeout(() => analyticsInput.focus(), 50);
    }
}

tabData.addEventListener("click", () => switchBotTab('data'));
tabAnalytics.addEventListener("click", () => switchBotTab('analytics'));

// ═══════════════════════════════════════════
// HOME FLOWS (UPLOAD / CREATE)
// ═══════════════════════════════════════════

// Home button
$("#goHome").addEventListener("click", () => {
    if (confirm("Go back to home screen? Current session will be lost.")) {
        sheetsApp.classList.add("hidden");
        homeScreen.classList.remove("hidden");
        state.sheetId = null;
        state.sheetData = null;
        fileInput.value = "";
    }
});

// Drag & Drop
document.addEventListener("dragover", (e) => { e.preventDefault(); dropOverlay.classList.remove("hidden"); });
dropOverlay.addEventListener("dragleave", (e) => {
    if (!dropOverlay.contains(e.relatedTarget)) dropOverlay.classList.add("hidden");
});
dropOverlay.addEventListener("drop", (e) => {
    e.preventDefault(); dropOverlay.classList.add("hidden");
    if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", (e) => {
    if (e.target.files[0]) uploadFile(e.target.files[0]);
});

async function uploadFile(file) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["csv", "xlsx", "xls"].includes(ext)) return alert("Please upload a CSV or XLSX file.");

    showLoading("Processing your file...");
    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch(`${API}/upload`, { method: "POST", body: formData });
        if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
        const data = await res.json();

        state.sheetId = data.sheet_id;
        state.sheetData = data;

        initSheetsApp(data);
    } catch (err) { alert("Upload error: " + err.message); }
    finally { hideLoading(); }
}

// Create Dataset
$("#cardCreate").addEventListener("click", () => {
    createModal.classList.remove("hidden");
    datasetNameInput.value = ""; datasetColumnsInput.value = "";
    datasetNameInput.focus();
});
$("#createCancel").addEventListener("click", () => createModal.classList.add("hidden"));
$("#createOverlay").addEventListener("click", () => createModal.classList.add("hidden"));

$("#createConfirm").addEventListener("click", async () => {
    const name = datasetNameInput.value.trim() || "untitled";
    const colStr = datasetColumnsInput.value.trim();
    const columns = colStr ? colStr.split(",").map(c => c.trim()).filter(Boolean) : [];

    createModal.classList.add("hidden");
    showLoading("Creating dataset...");

    try {
        const res = await fetch(`${API}/create`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, columns }),
        });
        if (!res.ok) throw new Error("Failed to create");
        const data = await res.json();

        state.sheetId = data.sheet_id;
        state.sheetData = data;

        initSheetsApp(data);

        addMessage(dataMessages, `🎉 Dataset **"${data.filename}"** created!\nTell me what to add next (e.g. "Add 5 rows of sample employee data").`, "bot");
    } catch (err) { alert("Error: " + err.message); }
    finally { hideLoading(); }
});

function initSheetsApp(data) {
    homeScreen.classList.add("hidden");
    sheetsApp.classList.remove("hidden");
    toggleSidebar(true);
    switchBotTab('data');

    sheetFilename.textContent = data.filename;
    sheetTabName.textContent = data.filename.split('.')[0];

    renderGrid(data.column_names, data.preview || data.data || []);
    updateDims(data.rows || (data.data ? data.data.length : 0), data.columns || data.column_names.length);
}

// ═══════════════════════════════════════════
// MENU BAR ACTIONS
// ═══════════════════════════════════════════

$("#menuDownload").addEventListener("click", (e) => {
    e.preventDefault();
    if (!state.sheetId) return;
    window.open(`${API}/download/${state.sheetId}`, '_blank');
});

$("#menuHomeLink").addEventListener("click", (e) => {
    e.preventDefault();
    $("#goHome").click();
});

$("#menuClearCell").addEventListener("click", (e) => {
    e.preventDefault();
    const selected = $(".data-cell.selected");
    if (!selected) return alert("Please select a cell first.");
    selected.textContent = "";
    selected.focus();
    selected.blur(); // Trigger the blur event to save
});

$("#menuToggleChat").addEventListener("click", (e) => {
    e.preventDefault();
    sidebarToggle.click();
});

$("#menuAddRow").addEventListener("click", (e) => {
    e.preventDefault();
    switchBotTab('data');
    toggleSidebar(true);
    sendQuery('data', "Add a new empty row at the bottom.");
});

$("#menuAddCol").addEventListener("click", (e) => {
    e.preventDefault();
    switchBotTab('data');
    toggleSidebar(true);
    sendQuery('data', "Add a new empty column.");
});

// ═══════════════════════════════════════════
// SPREADSHEET GRID LOGIC
// ═══════════════════════════════════════════

function getColLetter(index) {
    let letter = "";
    while (index >= 0) {
        letter = String.fromCharCode((index % 26) + 65) + letter;
        index = Math.floor(index / 26) - 1;
    }
    return letter;
}

function renderGrid(columns, data) {
    if (!columns || columns.length === 0) {
        sheetGrid.classList.add("hidden");
        emptyGrid.classList.remove("hidden");
        return;
    }

    emptyGrid.classList.add("hidden");
    sheetGrid.classList.remove("hidden");

    // Header A, B, C...
    let headHTML = `<tr><th class="corner-cell"></th>`;
    columns.forEach((_, i) => { headHTML += `<th>${getColLetter(i)}</th>`; });
    headHTML += `</tr>`;
    gridHead.innerHTML = headHTML;

    // Data rows
    let bodyHTML = "";

    // Dataset Column Names as Row 1
    bodyHTML += `<tr><td class="row-header" style="background: var(--bg-secondary);">1</td>`;
    columns.forEach((col, cIdx) => {
        bodyHTML += `<td class="data-cell header-row-cell" contenteditable="false" style="font-weight:600; background:var(--bg-secondary);" data-row="1" data-col="${getColLetter(cIdx)}" data-val="${esc(col)}" title="${esc(col)}">${esc(col)}</td>`;
    });
    bodyHTML += `</tr>`;

    data.forEach((row, rIdx) => {
        bodyHTML += `<tr><td class="row-header">${rIdx + 2}</td>`;
        columns.forEach((col, cIdx) => {
            const val = row[col] !== null && row[col] !== undefined ? String(row[col]) : "";
            bodyHTML += `<td class="data-cell" contenteditable="true" data-row="${rIdx + 2}" data-col="${getColLetter(cIdx)}" data-ridx="${rIdx}" data-cidx="${cIdx}" data-val="${esc(val)}" title="${esc(val)}">${esc(val)}</td>`;
        });
        bodyHTML += `</tr>`;
    });
    gridBody.innerHTML = bodyHTML;

    // Attach Cell Click Listeners
    $$(".data-cell").forEach(cell => {
        cell.addEventListener("click", function () {
            // Deselect previous
            $$(".data-cell.selected").forEach(c => c.classList.remove("selected"));
            // Select current
            this.classList.add("selected");

            const r = this.getAttribute("data-row");
            const c = this.getAttribute("data-col");
            const v = this.getAttribute("data-val");

            cellRef.textContent = `${c}${r}`;
            formulaInput.value = v;
        });

        // Save on blur
        cell.addEventListener("blur", async function () {
            const newVal = this.textContent.trim();
            const oldVal = this.getAttribute("data-val");
            if (newVal === oldVal) return; // no change

            const rIdx = parseInt(this.getAttribute("data-ridx"));
            const cIdx = parseInt(this.getAttribute("data-cidx"));

            try {
                const res = await fetch(`${API}/update_cell`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ sheet_id: state.sheetId, row_idx: rIdx, col_idx: cIdx, value: newVal })
                });
                if (!res.ok) throw new Error("Update failed");
                this.setAttribute("data-val", newVal);
                this.title = newVal;

                // Update formula bar if still selected
                if (this.classList.contains("selected")) {
                    formulaInput.value = newVal;
                }
            } catch (err) {
                console.error(err);
                this.textContent = oldVal; // revert
                alert("Failed to save cell edit.");
            }
        });

        // Handle Enter key to save (prevents newline)
        cell.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                e.preventDefault();
                this.blur();
            }
        });
    });

    // Select A1 initially if exists
    const firstCell = $(".data-cell");
    if (firstCell) firstCell.click();
}

function updateDims(rows, cols) {
    sheetDims.textContent = `${rows} rows × ${cols} cols`;
}

// ═══════════════════════════════════════════
// CHAT LOGIC (BOTH BOTS)
// ═══════════════════════════════════════════

function sendQuery(bot, msg) {
    if (bot === 'data') {
        addMessage(dataMessages, msg, "user");
        dataInput.value = "";
        setLoading("data", true);

        fetch(`${API}/chat/data`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sheet_id: state.sheetId, message: msg }),
        }).then(res => res.json()).then(data => {
            addMessage(dataMessages, data.response, "bot");
            if (data.sheet_updated && data.sheet_data) {
                renderGrid(data.sheet_data.column_names, data.sheet_data.data);
                updateDims(data.sheet_data.total_rows, data.sheet_data.total_columns);
                addMessage(dataMessages, "✅ Grid updated!", "bot");
            }
        }).catch(err => addMessage(dataMessages, "❌ Error: " + err.message, "bot"))
            .finally(() => setLoading("data", false));

    } else {
        addMessage(analyticsMessages, msg, "user");
        analyticsInput.value = "";
        setLoading("analytics", true);

        fetch(`${API}/chat/analytics`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sheet_id: state.sheetId, message: msg }),
        }).then(res => res.json()).then(data => {
            addMessage(analyticsMessages, data.response, "bot");
            if (data.charts && data.charts.length > 0) {
                data.charts.forEach(b64 => addChartMessage(analyticsMessages, b64));
            }
        }).catch(err => addMessage(analyticsMessages, "❌ Error: " + err.message, "bot"))
            .finally(() => setLoading("analytics", false));
    }
}

dataForm.addEventListener("submit", (e) => { e.preventDefault(); const m = dataInput.value.trim(); if (m && !state.isDataLoading) sendQuery('data', m); });
analyticsForm.addEventListener("submit", (e) => { e.preventDefault(); const m = analyticsInput.value.trim(); if (m && !state.isAnalyticsLoading) sendQuery('analytics', m); });

function addMessage(container, text, type) {
    const div = document.createElement("div");
    div.className = `message ${type === "user" ? "user-message" : "bot-message"}`;
    div.innerHTML = `<div class="message-content">${type === "bot" ? formatBot(text) : esc(text)}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function addChartMessage(container, base64) {
    const div = document.createElement("div");
    div.className = "message bot-message";
    div.innerHTML = `<div class="message-content"><img class="chart-thumb" src="data:image/png;base64,${base64}" alt="Chart" onclick="openChart(this.src)"></div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function formatBot(text) {
    if (!text) return "";
    let html = esc(text).replace(/\n/g, "<br>").replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    return html.replace(/`(.*?)`/g, `<code style="background:rgba(139,92,246,0.12);padding:1px 4px;border-radius:3px;font-family:var(--font-mono);">$1</code>`);
}

function esc(text) { const d = document.createElement("div"); d.textContent = text; return d.innerHTML; }

function setLoading(type, loading) {
    if (type === "data") {
        state.isDataLoading = loading; dataTyping.classList.toggle("hidden", !loading);
        dataSend.disabled = loading; dataInput.disabled = loading;
    } else {
        state.isAnalyticsLoading = loading; analyticsTyping.classList.toggle("hidden", !loading);
        analyticsSend.disabled = loading; analyticsInput.disabled = loading;
    }
}

// UI Utilities
function showLoading(text) { loadingText.textContent = text || "Processing..."; loadingOverlay.classList.remove("hidden"); }
function hideLoading() { loadingOverlay.classList.add("hidden"); }

// Chart Modal
window.openChart = function (src) { chartImage.src = src; chartModal.classList.remove("hidden"); };
$("#chartClose").addEventListener("click", () => chartModal.classList.add("hidden"));
$("#chartOverlay").addEventListener("click", () => chartModal.classList.add("hidden"));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { chartModal.classList.add("hidden"); createModal.classList.add("hidden"); } });
