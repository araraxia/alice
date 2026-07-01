/**
 * BlogManager – drives the blog window (list → post → editor).
 * Attached to the window partial loaded by WindowInitializer.
 */

if (typeof BlogManager === "undefined") {
  window.BlogManager = class BlogManager {
    constructor() {
      this.windowId = "blog-window";
      this.container = document.getElementById("blog-container");
      this.main = document.getElementById("blog-main");
      this.contentArea = document.getElementById("blog-content-area");
      this.currentPage = 1;
      this.currentYear = null;
      this.currentMonth = null;
      this.currentAuthor = null;

      this._editorWindow = null;
      this._editorAutoSaveTimer = null;
      this._previewDebounce = null;

      this._init();
    }

    // -----------------------------------------------------------------------
    // Init
    // -----------------------------------------------------------------------
    _init() {
      this._bindClose();
      this._bindSidebar();
      this._bindPostList();
      this._bindWriteButton();
    }

    _bindClose() {
      const closeBtn = document.getElementById("close-blog-button");
      if (closeBtn) {
        closeBtn.addEventListener("click", () => {
          if (window.blogWindowInstance) window.blogWindowInstance.close();
        });
      }
    }

    // -----------------------------------------------------------------------
    // Sidebar: month / author filters
    // -----------------------------------------------------------------------
    _bindSidebar() {
      const sidebar = document.querySelector(".blog-sidebar");
      if (!sidebar) return;

      sidebar.addEventListener("click", (e) => {
        const link = e.target.closest(".blog-sidebar-link");
        if (!link) return;
        e.preventDefault();

        // Deactivate all
        sidebar
          .querySelectorAll(".blog-sidebar-link")
          .forEach((l) => l.classList.remove("active"));
        link.classList.add("active");

        const year = link.dataset.filterYear
          ? parseInt(link.dataset.filterYear)
          : null;
        const month = link.dataset.filterMonth
          ? parseInt(link.dataset.filterMonth)
          : null;
        const author = link.dataset.filterAuthor || null;

        this.currentYear = year;
        this.currentMonth = month;
        this.currentAuthor = author;
        this.currentPage = 1;

        this._loadPostList();
      });
    }

    // -----------------------------------------------------------------------
    // Post list click delegation (titles + pagination)
    // -----------------------------------------------------------------------
    _bindPostList() {
      if (!this.main) return;
      this.main.addEventListener("click", (e) => {
        // Post title
        const titleLink = e.target.closest(".blog-post-title-link");
        if (titleLink) {
          e.preventDefault();
          this._loadPost(titleLink.dataset.postId);
          return;
        }
        // Pagination
        const pageBtn = e.target.closest("[data-page]");
        if (pageBtn && !pageBtn.disabled) {
          this.currentPage = parseInt(pageBtn.dataset.page);
          this._loadPostList();
          return;
        }
        // Back button (inside post view)
        if (e.target.closest("#blog-back-to-list")) {
          this._loadPostList();
          return;
        }
        // Edit button (inside post view)
        const editBtn = e.target.closest("#blog-edit-btn");
        if (editBtn) {
          this._openEditor(editBtn.dataset.editUrl, editBtn.dataset.postId);
          return;
        }
        // Delete button (inside post view)
        const deleteBtn = e.target.closest("#blog-delete-btn");
        if (deleteBtn) {
          this._deletePost(
            deleteBtn.dataset.postId,
            deleteBtn.dataset.deleteUrl,
          );
          return;
        }
      });
    }

    _bindWriteButton() {
      const btn = document.getElementById("blog-write-btn");
      if (!btn) return;
      btn.addEventListener("click", () => {
        this._openEditor(btn.dataset.writeUrl, null);
      });
    }

    // -----------------------------------------------------------------------
    // Load post list via fetch
    // -----------------------------------------------------------------------
    async _loadPostList() {
      const params = new URLSearchParams({ page: this.currentPage });
      if (this.currentYear) params.set("year", this.currentYear);
      if (this.currentMonth) params.set("month", this.currentMonth);
      if (this.currentAuthor) params.set("author", this.currentAuthor);

      try {
        const res = await fetch(`/blog/window?${params.toString()}`, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const html = await res.text();
        // Replace the whole window content
        const temp = document.createElement("div");
        temp.innerHTML = html;
        const newMain = temp.querySelector("#blog-main");
        if (newMain && this.main) {
          this.main.innerHTML = newMain.innerHTML;
        }
      } catch (err) {
        console.error("[blog.js] Failed to load post list", err);
      }
    }

    // -----------------------------------------------------------------------
    // Load single post
    // -----------------------------------------------------------------------
    async _loadPost(postId) {
      try {
        const res = await fetch(
          `/blog/window/post/${encodeURIComponent(postId)}`,
          {
            headers: { "X-Requested-With": "XMLHttpRequest" },
          },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const html = await res.text();
        if (this.contentArea) this.contentArea.innerHTML = html;
      } catch (err) {
        console.error("[blog.js] Failed to load post", err);
      }
    }

    // -----------------------------------------------------------------------
    // Editor window
    // -----------------------------------------------------------------------
    async _openEditor(editorUrl, postId) {
      if (!editorUrl) return;
      if (this._editorWindow) {
        this._editorWindow.close();
        this._editorWindow = null;
      }

      const editorWindow = new window.OpenWindow(editorUrl, {
        onLoad: (container) => {
          container.classList.add("draggable-window", "w98-window");
          container.id = "blog-editor-window";
          container.style.maxWidth = "900px";
          container.style.maxHeight = "85vh";
          container.style.minWidth = "640px";
          container.style.minHeight = "480px";

          const titleBar = container.querySelector("#blog-editor-title-bar");
          if (titleBar && window.windowManager) {
            window.windowManager.registerWindow(
              "blog-editor-window",
              container,
              "#blog-editor-title-bar",
            );
            window.windowManager.centerWindow("blog-editor-window");
            window.windowManager.bringToFront("blog-editor-window");
          }

          this._initEditor(container, postId);
        },
        escapeClosable: true,
      });

      this._editorWindow = editorWindow;
      await editorWindow.open();
    }

    _initEditor(container, postId) {
      const titleInput = container.querySelector("#blog-editor-title");
      const bodyArea = container.querySelector("#blog-editor-body");
      const preview = container.querySelector("#blog-editor-preview");
      const statusEl = container.querySelector("#blog-editor-status");
      const editorContainer = container.querySelector(".blog-editor-container");
      const writeUrl = editorContainer?.dataset.writeUrl;
      const editUrl = editorContainer?.dataset.editUrl;
      const draftUrl = editorContainer?.dataset.draftUrl;
      const previewUrl = editorContainer?.dataset.previewUrl;
      const resolvedPostId = editorContainer?.dataset.postId || postId;

      // Live preview
      if (bodyArea && preview) {
        bodyArea.addEventListener("input", () => {
          clearTimeout(this._previewDebounce);
          this._previewDebounce = setTimeout(() => {
            this._fetchPreview(bodyArea.value, preview, previewUrl);
          }, 400);
        });
        // Render initial value if editing
        if (bodyArea.value.trim()) {
          this._fetchPreview(bodyArea.value, preview, previewUrl);
        }
      }

      // Auto-save draft every 30 s if editing an existing post
      if (resolvedPostId && draftUrl && titleInput && bodyArea) {
        this._editorAutoSaveTimer = setInterval(() => {
          this._saveDraft(draftUrl, titleInput.value, bodyArea.value, statusEl);
        }, 30000);
      }

      // Save draft button
      const draftBtn = container.querySelector("#blog-save-draft-btn");
      if (draftBtn && resolvedPostId && draftUrl) {
        draftBtn.addEventListener("click", () => {
          this._saveDraft(
            draftUrl,
            titleInput?.value,
            bodyArea?.value,
            statusEl,
          );
        });
      } else if (draftBtn) {
        // New post: save as draft means publish with draft action
        draftBtn.addEventListener("click", () => {
          this._submitPost(
            "draft",
            titleInput?.value,
            bodyArea?.value,
            writeUrl,
            editUrl,
            resolvedPostId,
            statusEl,
          );
        });
      }

      // Publish button
      const publishBtn = container.querySelector("#blog-publish-btn");
      if (publishBtn) {
        publishBtn.addEventListener("click", () => {
          this._submitPost(
            "publish",
            titleInput?.value,
            bodyArea?.value,
            writeUrl,
            editUrl,
            resolvedPostId,
            statusEl,
          );
        });
      }

      // Close button
      const closeBtn = container.querySelector("#close-blog-editor-button");
      if (closeBtn) {
        closeBtn.addEventListener("click", () => {
          clearInterval(this._editorAutoSaveTimer);
          this._editorAutoSaveTimer = null;
          if (this._editorWindow) {
            this._editorWindow.close();
            this._editorWindow = null;
          }
        });
      }
    }

    async _fetchPreview(markdown, previewEl, previewUrl) {
      if (!previewUrl) return;
      try {
        const csrfToken = document
          .querySelector('meta[name="csrf-token"]')
          ?.getAttribute("content");
        const res = await fetch(previewUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
          },
          body: JSON.stringify({ body: markdown }),
        });
        if (!res.ok) return;
        const data = await res.json();
        previewEl.innerHTML = data.html || "";
      } catch (err) {
        console.warn("[blog.js] Preview fetch failed", err);
      }
    }

    async _saveDraft(draftUrl, title, body, statusEl) {
      if (!draftUrl) return;
      try {
        const csrfToken = document
          .querySelector('meta[name="csrf-token"]')
          ?.getAttribute("content");
        const res = await fetch(draftUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
          },
          body: JSON.stringify({ title, body }),
        });
        const data = await res.json();
        if (statusEl) {
          statusEl.textContent =
            data.status === "success"
              ? `Draft saved ${new Date().toLocaleTimeString()}`
              : "Auto-save failed";
        }
      } catch (err) {
        console.warn("[blog.js] Draft save failed", err);
      }
    }

    async _submitPost(
      action,
      title,
      body,
      writeUrl,
      editUrl,
      postId,
      statusEl,
    ) {
      const url = postId ? editUrl : writeUrl;
      if (!url) return;

      const csrfToken = document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content");
      try {
        const res = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
          },
          body: JSON.stringify({ title, body, action }),
        });
        const data = await res.json();
        if (data.status === "success") {
          if (statusEl) {
            statusEl.textContent =
              action === "publish" ? "Published!" : "Saved as draft.";
          }
          // Refresh post list and close editor after a short delay
          setTimeout(() => {
            clearInterval(this._editorAutoSaveTimer);
            this._editorAutoSaveTimer = null;
            if (this._editorWindow) {
              this._editorWindow.close();
              this._editorWindow = null;
            }
            this._loadPostList();
          }, 800);
        } else {
          if (statusEl)
            statusEl.textContent = data.message || "Error saving post.";
        }
      } catch (err) {
        console.error("[blog.js] Submit post failed", err);
        if (statusEl) statusEl.textContent = "Network error.";
      }
    }

    // -----------------------------------------------------------------------
    // Delete post
    // -----------------------------------------------------------------------
    async _deletePost(postId, deleteUrl) {
      if (!confirm("Delete this post?")) return;
      const csrfToken = document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content");
      try {
        const res = await fetch(deleteUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
          },
        });
        const data = await res.json();
        if (data.status === "success") {
          this._loadPostList();
        } else {
          alert(data.message || "Delete failed.");
        }
      } catch (err) {
        console.error("[blog.js] Delete failed", err);
      }
    }

    destroy() {
      clearInterval(this._editorAutoSaveTimer);
    }
  };
}
