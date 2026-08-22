/**
 * CatLoader - Shared "loading" indicator shown as a draggable w98-style window
 * Preloads static/images/sleeping_cat_140x80.webp on page init so any module
 * can call CatLoader.show()/hide() with zero image latency.
 */
class CatLoader {
    constructor() {
        this.imageSrc = '/static/images/sleeping_cat_140x80.webp';
        this.instances = new Map(); // id -> instance record
        this._counter = 0;
        this._preload();
    }

    /**
     * Warm the browser image cache immediately so the first show() call
     * never has to wait on the network.
     */
    _preload() {
        this.image = new Image();
        this.image.src = this.imageSrc;
    }

    /**
     * Show a loader window. Calling show() again with the same id reuses
     * and re-sizes the existing window instead of creating a new one, so
     * callers can freely call show() on every fetch without leaking windows.
     * @param {Object} options
     * @param {number} [options.width=140]
     * @param {number} [options.height=80]
     * @param {string} [options.title='Loading...']
     * @param {string} [options.id='default'] - unique id if multiple loaders may be shown at once
     * @param {boolean} [options.closeable=false]
     * @returns {string} the loader id, pass to hide()
     */
    show(options = {}) {
        const {
            width = 140,
            height = 80,
            title = 'Loading...',
            id = 'default',
            closeable = false,
        } = options;

        let instance = this.instances.get(id);
        if (!instance) {
            instance = this._create(id, closeable);
            this.instances.set(id, instance);
        }

        instance.titleEl.textContent = title;
        instance.img.style.width = width + 'px';
        instance.img.style.height = height + 'px';

        instance.container.style.display = 'flex';
        instance.container.style.visibility = 'hidden';

        if (window.windowManager) {
            if (!instance.registered) {
                window.windowManager.registerWindow(instance.windowId, instance.container, `#${instance.windowId}-title-bar`);
                instance.registered = true;
            }
            window.windowManager.centerWindow(instance.windowId);
            window.windowManager.bringToFront(instance.windowId);
        } else {
            // Window manager not loaded (unexpected) - just center with CSS
            instance.container.style.left = '50%';
            instance.container.style.top = '50%';
            instance.container.style.transform = 'translate(-50%, -50%)';
            instance.container.style.visibility = 'visible';
        }

        return id;
    }

    /**
     * Hide a loader window previously shown with the given id.
     * @param {string} [id='default']
     */
    hide(id = 'default') {
        const instance = this.instances.get(id);
        if (!instance) return;

        if (window.windowManager && instance.registered) {
            window.windowManager.hideWindow(instance.windowId);
        } else {
            instance.container.style.display = 'none';
        }
    }

    /**
     * Whether a loader with the given id is currently visible.
     * @param {string} [id='default']
     */
    isVisible(id = 'default') {
        const instance = this.instances.get(id);
        return !!instance && instance.container.style.display !== 'none';
    }

    _create(id, closeable) {
        const windowId = `cat-loader-${id}-${this._counter++}`;

        const container = document.createElement('div');
        container.id = windowId;
        container.className = 'draggable-window w98-window cat-loader-window';
        container.style.display = 'none';
        // Transient system indicator, not a real user window - keep it out of the taskbar entirely
        container.dataset.taskbarDeferred = 'true';

        container.innerHTML = `
            <div class="title-bar" id="${windowId}-title-bar">
                <h4>Loading...</h4>
                ${closeable ? `<button type="button" class="w98-button title-button cat-loader-close">X</button>` : ''}
            </div>
            <div class="cat-loader-body">
                <img class="cat-loader-image" src="${this.imageSrc}" alt="Loading" width="140" height="80" />
            </div>
        `;

        document.body.appendChild(container);

        const instance = {
            windowId,
            container,
            titleEl: container.querySelector('.title-bar h4'),
            img: container.querySelector('.cat-loader-image'),
            registered: false,
        };

        if (closeable) {
            container.querySelector('.cat-loader-close').addEventListener('click', () => this.hide(id));
        }

        return instance;
    }
}

// Instantiate immediately on script load so the image starts fetching at page init,
// well before any module needs to call show().
window.CatLoader = new CatLoader();
