/**
 * Theme Manager — handles the theme manager window and theme preview.
 * Manages loading CSS from disk, applying it live, and saving/loading
 * server-side theme files.
 */
class ThemeManager {
  constructor() {
    this._liveOverride   = null;  // <style id="live-theme-override">
    this._loadedContent  = null;  // full CSS file content (if any)
    this._loadedFilename = null;
    this._tokenOverrides = {};    // { "--token": "#rrggbb" } from color editor
    this._ceCurrentToken = null;  // token currently open in color editor

    this._bindManager();
  }

  // ── Live CSS override ─────────────────────────────────────────────────────

  applyCSS(css, filename) {
    this._loadedContent  = css;
    this._loadedFilename = filename || null;
    this._rebuildOverride();
    this._updateFileInfo();
    this._updateSaveButton();
  }

  resetToDefault() {
    this._loadedContent  = null;
    this._loadedFilename = null;
    this._tokenOverrides = {};
    this._rebuildOverride();
    this._updateFileInfo();
    this._updateSaveButton();
  }

  get hasOverride() {
    return !!(this._loadedContent || Object.keys(this._tokenOverrides).length);
  }

  _rebuildOverride() {
    if (!this._liveOverride) {
      this._liveOverride = document.createElement("style");
      this._liveOverride.id = "live-theme-override";
      document.head.appendChild(this._liveOverride);
    }
    const tokenEntries = Object.entries(this._tokenOverrides);
    const tokenCSS = tokenEntries.length
      ? `:root {\n${tokenEntries.map(([k, v]) => `  ${k}: ${v};`).join("\n")}\n}`
      : "";
    this._liveOverride.textContent = [this._loadedContent || "", tokenCSS]
      .filter(Boolean).join("\n");
  }

  // ── Color token editor ────────────────────────────────────────────────────

  // ── Color editor window (created on demand in <body>) ─────────────────────

  _ensureColorEditorWindow() {
    if (document.getElementById("tp-color-editor")) return;

    const win = document.createElement("div");
    win.id = "tp-color-editor";
    win.className = "draggable-window w98-window tp-color-editor-win";
    win.style.cssText = "display:none; position:fixed; width:296px;";
    win.innerHTML = `
      <div class="window-content">
        <div class="title-bar" id="tp-ce-title-bar">
          <h4 style="font-family:'Courier New',monospace;font-size:11px;font-weight:bold;" id="tp-ce-token-name"></h4>
          <button id="tp-ce-close" class="w98-button title-button">X</button>
        </div>
        <div class="tp-ce-body">
          <div id="tp-ce-preview" class="tp-ce-preview-box"></div>
          <div class="tp-ce-controls">
            <div class="tp-ce-row">
              <label class="tp-ce-lbl">Hex</label>
              <input type="text" id="tp-ce-hex" class="w98-input tp-ce-hex-input" maxlength="7" placeholder="#rrggbb" spellcheck="false">
            </div>
            <div class="tp-ce-row">
              <label class="tp-ce-lbl">R</label>
              <input type="range" id="tp-ce-r" min="0" max="255" class="tp-ce-slider">
              <input type="number" id="tp-ce-rn" min="0" max="255" class="w98-input tp-ce-num">
            </div>
            <div class="tp-ce-row">
              <label class="tp-ce-lbl">G</label>
              <input type="range" id="tp-ce-g" min="0" max="255" class="tp-ce-slider">
              <input type="number" id="tp-ce-gn" min="0" max="255" class="w98-input tp-ce-num">
            </div>
            <div class="tp-ce-row">
              <label class="tp-ce-lbl">B</label>
              <input type="range" id="tp-ce-b" min="0" max="255" class="tp-ce-slider">
              <input type="number" id="tp-ce-bn" min="0" max="255" class="w98-input tp-ce-num">
            </div>
            <div class="tp-ce-row" style="justify-content:flex-end;margin-top:2px;">
              <button class="w98-button" id="tp-ce-reset" style="padding:1px 8px;">Reset Token</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(win);

    if (window.windowManager) {
      window.windowManager.registerWindow("tp-color-editor", win, "#tp-ce-title-bar");
    }

    this._bindColorEditorEvents();
  }

  openColorEditor(tokenName, anchorEl) {
    this._ensureColorEditorWindow();

    const raw = getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim();
    const hex = this._parseToHex(raw);
    if (!hex) return; // gradient or non-color — skip silently

    this._ceCurrentToken = tokenName;
    document.getElementById("tp-ce-token-name").textContent = tokenName;

    // Highlight active swatch
    document.querySelectorAll(".tp-swatch-active").forEach((el) => el.classList.remove("tp-swatch-active"));
    anchorEl?.classList.add("tp-swatch-active");

    this._setCEColor(hex);

    const editor = document.getElementById("tp-color-editor");
    if (editor.style.display === "none" && anchorEl) {
      // Position next to the swatch on first open; let the user drag it after
      const rect  = anchorEl.getBoundingClientRect();
      const edW   = 300;
      const edH   = 220;
      let left = rect.right + 12;
      let top  = rect.top  - 20;
      if (left + edW > window.innerWidth  - 8) left = rect.left - edW - 12;
      if (top  + edH > window.innerHeight - 8) top  = window.innerHeight - edH - 8;
      if (top < 8) top = 8;
      editor.style.left = `${Math.max(8, left)}px`;
      editor.style.top  = `${top}px`;
    }

    editor.style.display = "";
    window.windowManager?.bringToFront("tp-color-editor");
  }

  _setCEColor(hex) {
    const [r, g, b] = this._hexToRgb(hex);
    document.getElementById("tp-ce-hex").value = hex;
    document.getElementById("tp-ce-preview").style.background = hex;
    document.getElementById("tp-ce-r").value  = r;
    document.getElementById("tp-ce-g").value  = g;
    document.getElementById("tp-ce-b").value  = b;
    document.getElementById("tp-ce-rn").value = r;
    document.getElementById("tp-ce-gn").value = g;
    document.getElementById("tp-ce-bn").value = b;
    this._updateSliderGradients(r, g, b);
  }

  _applyTokenOverride(tokenName, hex) {
    this._tokenOverrides[tokenName] = hex;
    this._rebuildOverride();
    // Update the swatch box live
    const box = document.querySelector(`[data-token="${tokenName}"]`);
    if (box) box.style.background = hex;
  }

  _resetTokenOverride(tokenName) {
    delete this._tokenOverrides[tokenName];
    this._rebuildOverride();
    // Read value now that override is gone
    const raw = getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim();
    const hex = this._parseToHex(raw);
    // Restore swatch
    const box = document.querySelector(`[data-token="${tokenName}"]`);
    if (box) box.style.background = `var(${tokenName})`;
    if (hex) this._setCEColor(hex);
  }

  // ── Swatch click wiring (called after preview DOM is injected) ───────────

  _initPreviewInteractivity() {
    const grid = document.getElementById("tp-swatch-grid");
    if (!grid || grid.dataset.ceInit) return; // idempotent
    grid.dataset.ceInit = "1";

    grid.addEventListener("click", (e) => {
      const box = e.target.closest("[data-token]");
      if (box) this.openColorEditor(box.dataset.token, box);
    });
  }

  // ── Color editor event wiring (called once when editor window is created) ─

  _bindColorEditorEvents() {
    const hexEl = document.getElementById("tp-ce-hex");
    const rEl   = document.getElementById("tp-ce-r");
    const gEl   = document.getElementById("tp-ce-g");
    const bEl   = document.getElementById("tp-ce-b");
    const rnEl  = document.getElementById("tp-ce-rn");
    const gnEl  = document.getElementById("tp-ce-gn");
    const bnEl  = document.getElementById("tp-ce-bn");

    const fromHex = () => {
      const val = hexEl.value.trim();
      if (/^#[0-9a-fA-F]{6}$/.test(val)) {
        this._setCEColor(val);
        if (this._ceCurrentToken) this._applyTokenOverride(this._ceCurrentToken, val);
      }
    };

    const fromSliders = () => {
      const r = +rEl.value, g = +gEl.value, b = +bEl.value;
      const hex = this._rgbToHex(r, g, b);
      rnEl.value = r; gnEl.value = g; bnEl.value = b;
      hexEl.value = hex;
      document.getElementById("tp-ce-preview").style.background = hex;
      this._updateSliderGradients(r, g, b);
      if (this._ceCurrentToken) this._applyTokenOverride(this._ceCurrentToken, hex);
    };

    const fromNumbers = () => {
      const r = Math.max(0, Math.min(255, +rnEl.value || 0));
      const g = Math.max(0, Math.min(255, +gnEl.value || 0));
      const b = Math.max(0, Math.min(255, +bnEl.value || 0));
      const hex = this._rgbToHex(r, g, b);
      rEl.value = r; gEl.value = g; bEl.value = b;
      hexEl.value = hex;
      document.getElementById("tp-ce-preview").style.background = hex;
      this._updateSliderGradients(r, g, b);
      if (this._ceCurrentToken) this._applyTokenOverride(this._ceCurrentToken, hex);
    };

    hexEl.addEventListener("input",  fromHex);
    hexEl.addEventListener("change", fromHex);
    [rEl, gEl, bEl].forEach((s) => s.addEventListener("input", fromSliders));
    [rnEl, gnEl, bnEl].forEach((n) => n.addEventListener("input", fromNumbers));

    document.getElementById("tp-ce-reset").addEventListener("click", () => {
      if (this._ceCurrentToken) this._resetTokenOverride(this._ceCurrentToken);
    });

    document.getElementById("tp-ce-close").addEventListener("click", () => {
      document.getElementById("tp-color-editor").style.display = "none";
      document.querySelectorAll(".tp-swatch-active").forEach((el) => el.classList.remove("tp-swatch-active"));
      this._ceCurrentToken = null;
    });
  }

  // ── Color conversion helpers ──────────────────────────────────────────────

  _parseToHex(cssValue) {
    // Browsers report computed colors as rgb(r, g, b)
    const m = cssValue.match(/^rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)/);
    if (m) return this._rgbToHex(+m[1], +m[2], +m[3]);
    // Also handle hex literals (in case value comes from override, not computed)
    if (/^#[0-9a-fA-F]{6}$/.test(cssValue)) return cssValue;
    if (/^#[0-9a-fA-F]{3}$/.test(cssValue)) {
      const [, r, g, b] = cssValue;
      return `#${r}${r}${g}${g}${b}${b}`;
    }
    return null;
  }

  _hexToRgb(hex) {
    return [
      parseInt(hex.slice(1, 3), 16),
      parseInt(hex.slice(3, 5), 16),
      parseInt(hex.slice(5, 7), 16),
    ];
  }

  _rgbToHex(r, g, b) {
    return "#" + [r, g, b].map((n) =>
      Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0")
    ).join("");
  }

  _updateSliderGradients(r, g, b) {
    document.getElementById("tp-ce-r").style.background =
      `linear-gradient(to right, rgb(0,${g},${b}), rgb(255,${g},${b}))`;
    document.getElementById("tp-ce-g").style.background =
      `linear-gradient(to right, rgb(${r},0,${b}), rgb(${r},255,${b}))`;
    document.getElementById("tp-ce-b").style.background =
      `linear-gradient(to right, rgb(${r},${g},0), rgb(${r},${g},255))`;
  }

  // ── Manager window wiring ─────────────────────────────────────────────────

  _bindManager() {
    document.addEventListener("themeManagerReady", () => this._initManagerUI());
  }

  _initManagerUI() {
    const fileInput = document.getElementById("tm-file-input");
    const resetBtn  = document.getElementById("tm-reset-btn");
    const saveBtn   = document.getElementById("tm-save-btn");
    const saveInput = document.getElementById("tm-save-name");

    if (!fileInput) return; // manager not in DOM yet

    fileInput.addEventListener("change", (e) => this._onFileSelect(e));
    resetBtn.addEventListener("click", () => this._onReset());

    if (saveBtn) {
      saveBtn.addEventListener("click", () => this._onSave());
      saveInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") this._onSave();
      });
    }

    this._updateFileInfo();
    this._updateSaveButton();
    this._loadFileList();
  }

  // ── File-from-disk ────────────────────────────────────────────────────────

  _onFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    const MAX = 51200;
    if (file.size > MAX) {
      this._setStatus("tm-load-status", `File too large (max ${MAX / 1024} KB).`, "err");
      return;
    }

    const reader = new FileReader();
    reader.onload = (ev) => {
      this.applyCSS(ev.target.result, file.name);
      this._setStatus("tm-load-status", `Applied: ${file.name} (${this._fmtSize(file.size)})`, "ok");
      const nameInput = document.getElementById("tm-save-name");
      if (nameInput && !nameInput.value) nameInput.value = file.name;
    };
    reader.readAsText(file);
  }

  _onReset() {
    this.resetToDefault();
    this._setStatus("tm-load-status", "Reset to default theme.", "ok");
    const fi = document.getElementById("tm-file-input");
    if (fi) fi.value = "";
  }

  // ── Save to server ────────────────────────────────────────────────────────

  async _onSave() {
    const nameInput = document.getElementById("tm-save-name");
    const filename  = (nameInput?.value || "").trim();

    if (!filename) {
      this._setStatus("tm-save-status", "Enter a filename.", "err");
      return;
    }
    if (!filename.endsWith(".css")) {
      this._setStatus("tm-save-status", "Filename must end in .css", "err");
      return;
    }
    const saveContent = this._liveOverride?.textContent?.trim() || "";
    if (!saveContent) {
      this._setStatus("tm-save-status", "No theme loaded. Load or edit a CSS file first.", "err");
      return;
    }

    const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ?? "";
    try {
      const res = await fetch("/theme/files", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({ filename, content: saveContent }),
      });
      const data = await res.json();
      if (!res.ok) {
        this._setStatus("tm-save-status", data.error || "Save failed.", "err");
        return;
      }
      this._setStatus("tm-save-status", `Saved as "${data.filename}".`, "ok");
      this._loadFileList();
    } catch {
      this._setStatus("tm-save-status", "Network error.", "err");
    }
  }

  // ── File list ─────────────────────────────────────────────────────────────

  async _loadFileList() {
    const tbody = document.getElementById("tm-file-tbody");
    if (!tbody) return;

    try {
      const res = await fetch("/theme/files");
      if (res.status === 401) {
        return; // not logged in — template already hides the section
      }
      const files = await res.json();
      if (!Array.isArray(files) || files.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="tm-empty">No saved themes yet.</td></tr>';
        return;
      }
      tbody.innerHTML = files.map((f) => `
        <tr data-id="${f.id}">
          <td>${this._escHtml(f.filename)}</td>
          <td>${this._fmtSize(f.file_size)}</td>
          <td>${this._fmtDate(f.updated_at)}</td>
          <td>
            <div class="tm-actions">
              <button class="w98-button" style="padding:.2rem .5rem;min-width:0;"
                onclick="window.themeManager._loadSaved(${f.id})">Load</button>
              <button class="w98-button" style="padding:.2rem .5rem;min-width:0;"
                onclick="window.themeManager._downloadSaved(${f.id},'${this._escAttr(f.filename)}')">&#8595;</button>
              <button class="w98-button" style="padding:.2rem .5rem;min-width:0;"
                onclick="window.themeManager._deleteSaved(${f.id})">Del</button>
            </div>
          </td>
        </tr>
      `).join("");
    } catch {
      this._setStatus("tm-list-status", "Failed to load file list.", "err");
    }
  }

  async _loadSaved(id) {
    try {
      const res  = await fetch(`/theme/files/${id}`);
      const data = await res.json();
      if (!res.ok) { this._setStatus("tm-list-status", data.error || "Load failed.", "err"); return; }
      this.applyCSS(data.content, data.filename);
      const ni = document.getElementById("tm-save-name");
      if (ni) ni.value = data.filename;
      this._setStatus("tm-list-status", `Loaded "${data.filename}".`, "ok");
    } catch {
      this._setStatus("tm-list-status", "Network error.", "err");
    }
  }

  _downloadSaved(id, filename) {
    fetch(`/theme/files/${id}`)
      .then((r) => r.json())
      .then((d) => { if (d.content) this._triggerDownload(d.content, filename); });
  }

  async openPreview() {
    try {
      await window.themePreviewWindowInstance?.open();
      document.dispatchEvent(new CustomEvent("themePreviewInjected"));
    } catch {}
  }

  downloadCurrent(defaultUrl) {
    const overrideContent = this._liveOverride?.textContent?.trim();
    if (overrideContent) {
      this._triggerDownload(overrideContent, this._loadedFilename || "my-theme.css");
      this._setDlStatus("Downloaded.");
    } else {
      fetch(defaultUrl)
        .then((r) => r.text())
        .then((css) => {
          this._triggerDownload(css, "theme-default.css");
          this._setDlStatus("Downloaded default theme.");
        })
        .catch(() => this._setDlStatus("Download failed."));
    }
  }

  _triggerDownload(content, filename) {
    const blob = new Blob([content], { type: "text/css" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  _setDlStatus(msg) {
    const el = document.getElementById("tp-dl-status");
    if (!el) return;
    el.textContent = msg;
    el.className   = "tm-status ok";
    setTimeout(() => { if (el.textContent === msg) el.textContent = ""; }, 4000);
  }

  async _deleteSaved(id) {
    if (!confirm("Delete this theme file?")) return;
    const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ?? "";
    try {
      const res  = await fetch(`/theme/files/${id}`, {
        method: "DELETE",
        headers: { "X-CSRFToken": csrf },
      });
      const data = await res.json();
      if (!res.ok) { this._setStatus("tm-list-status", data.error || "Delete failed.", "err"); return; }
      this._setStatus("tm-list-status", "Deleted.", "ok");
      this._loadFileList();
    } catch {
      this._setStatus("tm-list-status", "Network error.", "err");
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  _updateFileInfo() {
    const el = document.getElementById("tm-file-info");
    const rb = document.getElementById("tm-reset-btn");
    if (!el) return;
    const activeContent = this._liveOverride?.textContent?.trim();
    if (activeContent) {
      const size = new TextEncoder().encode(activeContent).length;
      el.textContent = `Active: ${this._loadedFilename || "custom"} (${this._fmtSize(size)})`;
      if (rb) rb.disabled = false;
    } else {
      el.textContent = "No custom theme loaded.";
      if (rb) rb.disabled = true;
    }
  }

  _updateSaveButton() {
    const btn = document.getElementById("tm-save-btn");
    if (!btn) return;
    const hasContent = !!(this._liveOverride?.textContent?.trim());
    btn.disabled = !hasContent;
    btn.title    = hasContent ? "" : "Load or edit a CSS file first";
  }

  _setStatus(id, msg, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent  = msg;
    el.className    = `tm-status ${cls}`;
    setTimeout(() => { if (el.textContent === msg) el.textContent = ""; }, 5000);
  }

  _fmtSize(bytes) {
    return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;
  }

  _fmtDate(iso) {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  }

  _escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  _escAttr(s) {
    return s.replace(/'/g, "\\'");
  }
}

// Instantiate globally so inline onclick handlers can reach it
window.themeManager = new ThemeManager();

// Signal when the manager DOM is loaded (called by WindowInitializer after inject)
document.addEventListener("themeManagerInjected", () => {
  document.dispatchEvent(new CustomEvent("themeManagerReady"));
  window.themeManager._initManagerUI();
});

// Wire color editor when preview DOM is ready
document.addEventListener("themePreviewInjected", () => {
  window.themeManager._initPreviewInteractivity();
});

// ── Style Gallery ─────────────────────────────────────────────────────────────

class ThemeGallery {
  constructor() {
    this._sort  = "rating";
    this._order = "desc";
    this._bindGallery();
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  setSort(col) {
    if (this._sort === col) {
      this._order = this._order === "desc" ? "asc" : "desc";
    } else {
      this._sort  = col;
      this._order = col === "rating" ? "desc" : "desc";
    }
    this._updateSortUI();
    this.refresh();
  }

  toggleOrder() {
    this._order = this._order === "desc" ? "asc" : "desc";
    this._updateSortUI();
    this.refresh();
  }

  async refresh() {
    const tbody = document.getElementById("tg-tbody");
    if (!tbody) return;
    this._setStatus("Loading…", "");

    try {
      const res  = await fetch(`/theme/gallery/files?sort=${this._sort}&order=${this._order}`);
      const rows = await res.json();
      if (!Array.isArray(rows) || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="tm-empty">No themes in the gallery yet.</td></tr>';
        this._setStatus("", "");
        return;
      }
      tbody.innerHTML = rows.map((r) => this._renderRow(r)).join("");
      this._bindVoteButtons();
      this._setStatus("", "");
    } catch {
      this._setStatus("Failed to load gallery.", "err");
    }
  }

  // ── Internals ──────────────────────────────────────────────────────────────

  _bindGallery() {
    document.addEventListener("themeGalleryInjected", () => this._initGalleryUI());
  }

  _initGalleryUI() {
    const win = document.getElementById("theme-gallery-container");
    this._isAuth = win?.dataset.auth === "true";
    this._updateSortUI();
    this.refresh();
  }

  _renderRow(r) {
    const date    = new Date(r.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    const upCls   = r.my_vote === 1  ? "w98-button tm-vote-btn tm-vote-active" : "w98-button tm-vote-btn";
    const downCls = r.my_vote === -1 ? "w98-button tm-vote-btn tm-vote-active" : "w98-button tm-vote-btn";
    const scoreSign = r.rating > 0 ? `+${r.rating}` : `${r.rating}`;

    const voteHtml = this._isAuth
      ? `<button class="${upCls}"   data-id="${r.id}" data-vote="1"  title="${r.upvotes} up">&#9650;</button>
         <span class="tm-score">${scoreSign}</span>
         <button class="${downCls}" data-id="${r.id}" data-vote="-1" title="${r.downvotes} down">&#9660;</button>`
      : `<span class="tm-score" title="${r.upvotes}▲ ${r.downvotes}▼">${scoreSign}</span>`;

    return `
      <tr data-theme-id="${r.id}">
        <td class="tm-col-filename">${this._escHtml(r.filename)}</td>
        <td class="tm-col-author">${this._escHtml(r.author)}</td>
        <td class="tm-col-votes">${voteHtml}</td>
        <td class="tm-col-score tm-score-cell">${r.upvotes}▲ ${r.downvotes}▼</td>
        <td class="tm-col-date">${date}</td>
        <td class="tm-col-actions">
          <button class="w98-button tg-load-btn" data-id="${r.id}" data-name="${this._escAttr(r.filename)}"
            style="padding:.2rem .5rem;min-width:0;">Load</button>
        </td>
      </tr>`;
  }

  _bindVoteButtons() {
    const tbody = document.getElementById("tg-tbody");
    if (!tbody) return;

    tbody.querySelectorAll(".tm-vote-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id    = parseInt(btn.dataset.id);
        const value = parseInt(btn.dataset.vote);
        this._vote(id, value, btn.closest("tr"));
      });
    });

    tbody.querySelectorAll(".tg-load-btn").forEach((btn) => {
      btn.addEventListener("click", () => this._loadTheme(parseInt(btn.dataset.id), btn.dataset.name));
    });
  }

  async _vote(themeId, value, row) {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ?? "";
    try {
      const res  = await fetch(`/theme/gallery/${themeId}/rate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ value }),
      });
      const data = await res.json();
      if (!res.ok) {
        this._setStatus(data.error || "Vote failed.", "err");
        return;
      }
      this._updateRowVote(row, data);
    } catch {
      this._setStatus("Network error.", "err");
    }
  }

  _updateRowVote(row, data) {
    const upBtn   = row.querySelector('[data-vote="1"]');
    const downBtn = row.querySelector('[data-vote="-1"]');
    const scoreEl = row.querySelector(".tm-score");
    const detailEl = row.querySelector(".tm-score-cell");

    if (upBtn)    upBtn.className   = data.my_vote === 1  ? "w98-button tm-vote-btn tm-vote-active" : "w98-button tm-vote-btn";
    if (downBtn)  downBtn.className = data.my_vote === -1 ? "w98-button tm-vote-btn tm-vote-active" : "w98-button tm-vote-btn";
    if (scoreEl)  scoreEl.textContent = data.rating > 0 ? `+${data.rating}` : `${data.rating}`;
    if (detailEl) detailEl.textContent = `${data.upvotes}▲ ${data.downvotes}▼`;
  }

  async _loadTheme(id, filename) {
    try {
      const res  = await fetch(`/theme/gallery/${id}/content`);
      const data = await res.json();
      if (!res.ok || !data.content) {
        this._setStatus(data.error || "Load failed.", "err");
        return;
      }
      window.themeManager.applyCSS(data.content, data.filename);
      this._setStatus(`Applied: ${data.filename}`, "ok");
    } catch {
      this._setStatus("Network error.", "err");
    }
  }

  _updateSortUI() {
    const ratingBtn = document.getElementById("tg-sort-rating");
    const dateBtn   = document.getElementById("tg-sort-date");
    const orderBtn  = document.getElementById("tg-sort-order");

    if (ratingBtn) ratingBtn.className = `w98-button tm-sort-btn${this._sort === "rating" ? " tm-sort-active" : ""}`;
    if (dateBtn)   dateBtn.className   = `w98-button tm-sort-btn${this._sort === "date"   ? " tm-sort-active" : ""}`;
    if (orderBtn)  orderBtn.textContent = this._order === "desc" ? "▼" : "▲";
  }

  _setStatus(msg, cls) {
    const el = document.getElementById("tg-status");
    if (!el) return;
    el.textContent = msg;
    el.className   = `tm-status ${cls}`;
    if (msg) setTimeout(() => { if (el.textContent === msg) el.textContent = ""; }, 5000);
  }

  _escHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  _escAttr(s) {
    return String(s).replace(/'/g, "\\'");
  }
}

window.themeGallery = new ThemeGallery();

document.addEventListener("themeGalleryInjected", () => {
  window.themeGallery._initGalleryUI();
});
