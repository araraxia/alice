
/**
 * WindowInitializer class to manage the lifecycle of a window
 * including opening, closing, and associating with buttons.
 * Assumes existence of a global window manager and OpenWindow class.
 * @param {Object} windowManager - The global window manager instance.
 * @param {string} windowName - The name of the window (used for global reference).
 * @param {string} windowId - The unique ID for the window container.
 * @param {string} buttonId - The ID of the button that opens the window.
 * @param {string} titleBarId - The ID of the title bar element within the window.
 * @param {string} closeBtnId - The ID of the close button within the window.
 * @param {string} endpoint - The URL endpoint to load the window content from.
 * 
 */

class WindowInitializer {
    constructor(
        windowManager,
        windowName,
        windowId,
        buttonId,
        titleBarId,
        closeBtnId,
        endpoint,
    ) {
        this.windowManager = windowManager;
        this.windowName = windowName;
        this.windowId = windowId;
        this.buttonId = buttonId;
        this.titleId = titleBarId;
        this.closeBtnId = closeBtnId;
        this.endpoint = endpoint;

        this.init();
    }

    init() {
        const newWindow = new window.OpenWindow(this.endpoint, {
            onLoad: (container, html) => {
                console.log(`${this.windowId} loaded successfully.`);
                container.classList.add('draggable-window');
                container.id = this.windowId;

                // Associate the button with the window
                const button = document.getElementById(this.buttonId);
                if (button) {
                    this.windowManager.associateButton(this.windowId, button);
                }

                console.log(`Opening ${this.windowId}.`);
                const titleBar = container.querySelector(`#${this.titleId}`);
                if (titleBar) {
                    this.windowManager.registerWindow(this.windowId, container, `#${this.titleId}`);
                    this.windowManager.disableWindowButtons(this.windowId);
                    this.windowManager.centerWindow(this.windowId);
                    this.windowManager.bringToFront(this.windowId);
                    this.initClose(newWindow);
                } else {
                    console.warn(`Title bar with ID '${this.titleId}' not found`);
                }
            },
            onClose: () => {
                this.windowManager.enableWindowButtons(this.windowId);
                // Note: No unregisterWindow method exists, window manager handles cleanup automatically
            }
        });

        // Store the window instance globally for reference
        window[`${this.windowName}Instance`] = newWindow;
    }

    initClose(windowInstance) {
        // Set up close button
        console.log(`Setting up close button for ${this.windowId}.`);
        const closeBtn = document.getElementById(this.closeBtnId);
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                console.log(`Close button clicked for ${this.windowId}`);
                this.windowManager.enableWindowButtons(this.windowId);
                windowInstance.close();
            });
        } else {
            console.warn(`Close button with ID '${this.closeBtnId}' not found`);
        }
    }
}

window.WindowInitializer = WindowInitializer;