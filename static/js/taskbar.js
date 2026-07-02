class Taskbar {
    constructor() {
        this.bar = document.getElementById('taskbar');
        this.startBtn = document.getElementById('taskbar-start');
        this.buttons = new Map(); // windowId → <button>

        if (!this.bar) return;
        this._waitForWindowManager();
    }

    _waitForWindowManager() {
        if (typeof windowManager !== 'undefined' && windowManager) {
            this._init();
        } else {
            setTimeout(() => this._waitForWindowManager(), 50);
        }
    }

    _init() {
        // Start button toggles index_container
        if (this.startBtn) {
            this.startBtn.addEventListener('click', () => {
                const visible = windowManager.isWindowVisible('index_container');
                const active  = windowManager.activeWindowId === 'index_container';
                if (visible && active) {
                    windowManager.hideWindow('index_container');
                } else if (!visible) {
                    windowManager.showWindow('index_container');
                } else {
                    windowManager.bringToFront('index_container');
                }
            });
        }

        // New window registered
        document.addEventListener('windowRegistered', e => {
            if (e.detail.windowId === 'index_container') {
                this._syncStartButton();
                return;
            }
            // Skip windows marked to appear only after first open
            const win = windowManager.windows.get(e.detail.windowId);
            if (win && win.container && 'taskbarDeferred' in win.container.dataset) return;
            this._addButton(e.detail.windowId, e.detail.label);
        });

        // Window removed from DOM
        document.addEventListener('windowUnregistered', e => {
            if (e.detail.windowId !== 'index_container') {
                this._removeButton(e.detail.windowId);
            }
        });

        // Active window changed
        document.addEventListener('windowActivated', e => {
            this._syncActiveState(e.detail.windowId);
        });

        // Window hidden (minimised)
        document.addEventListener('windowHidden', e => {
            const windowId = e.detail.windowId;
            if (windowId === 'index_container') {
                this._syncStartButton();
                return;
            }
            const win = windowManager.windows.get(windowId);
            if (win && win.container && 'taskbarDeferred' in win.container.dataset) {
                // Deferred windows disappear from the taskbar when closed
                this._removeButton(windowId);
            } else {
                const btn = this.buttons.get(windowId);
                if (btn) {
                    btn.classList.remove('taskbar-btn-active');
                    btn.classList.add('taskbar-btn-minimized');
                }
            }
        });

        // Window shown (restored, or deferred window shown for the first time)
        document.addEventListener('windowShown', e => {
            const windowId = e.detail.windowId;
            if (windowId === 'index_container') {
                this._syncStartButton();
                return;
            }
            if (!this.buttons.has(windowId)) {
                // Deferred window being shown — add its button (keep the attribute for close-removal)
                const win = windowManager.windows.get(windowId);
                if (win && win.container) {
                    this._addButton(windowId, this._labelFrom(win.container));
                    this._syncActiveState(windowManager.activeWindowId);
                }
            } else {
                const btn = this.buttons.get(windowId);
                if (btn) btn.classList.remove('taskbar-btn-minimized');
            }
        });

        // Sync windows already registered before Taskbar was created
        windowManager.windows.forEach((win, windowId) => {
            if (windowId === 'index_container') return;
            if (win.container && 'taskbarDeferred' in win.container.dataset) return;
            const label = this._labelFrom(win.container);
            this._addButton(windowId, label);
            if (!windowManager.isWindowVisible(windowId)) {
                const btn = this.buttons.get(windowId);
                if (btn) btn.classList.add('taskbar-btn-minimized');
            }
        });

        this._syncActiveState(windowManager.activeWindowId);
        this._syncStartButton();
    }

    _labelFrom(container) {
        if (!container) return 'Window';
        const h4 = container.querySelector('.title-bar h4');
        return h4 ? h4.textContent.trim() : 'Window';
    }

    _addButton(windowId, label) {
        if (this.buttons.has(windowId)) return;
        const btn = document.createElement('button');
        btn.className = 'w98-button taskbar-window-btn';
        btn.textContent = label || 'Window';
        btn.title = label || 'Window';
        btn.addEventListener('click', () => {
            const visible = windowManager.isWindowVisible(windowId);
            const active  = windowManager.activeWindowId === windowId;
            if (visible && active) {
                windowManager.hideWindow(windowId);
            } else if (!visible) {
                windowManager.showWindow(windowId);
            } else {
                windowManager.bringToFront(windowId);
            }
        });
        this.bar.appendChild(btn);
        this.buttons.set(windowId, btn);
    }

    _removeButton(windowId) {
        const btn = this.buttons.get(windowId);
        if (btn) {
            btn.remove();
            this.buttons.delete(windowId);
        }
    }

    _syncActiveState(activeId) {
        this.buttons.forEach((btn, id) => {
            const isActive = id === activeId;
            btn.classList.toggle('taskbar-btn-active', isActive);
            if (isActive) btn.classList.remove('taskbar-btn-minimized');
        });
        this._syncStartButton();
    }

    _syncStartButton() {
        if (!this.startBtn) return;
        const visible = windowManager.isWindowVisible('index_container');
        const active  = windowManager.activeWindowId === 'index_container';
        this.startBtn.classList.toggle('taskbar-btn-active',    visible && active);
        this.startBtn.classList.toggle('taskbar-btn-minimized', !visible);
    }
}

window.Taskbar = Taskbar;
