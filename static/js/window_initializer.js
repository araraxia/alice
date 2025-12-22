
/**
 * WindowInitializer class to manage the lifecycle of a window
 * including opening, closing, and associating with buttons.
 * Assumes existence of a global window manager and OpenWindow class.
 * @param {Object} windowManager - The global window manager instance.
 * @param {string} windowName - The name of the window (used for global reference).
 * @param {string} windowId - The unique ID for the window container.
 * @param {string} containerId - The ID of the window container element.
 * @param {string} buttonId - The ID of the button that opens the window.
 * @param {string} titleBarId - The ID of the title bar element within the window.
 * @param {string} closeBtnId - The ID of the close button within the window.
 * @param {string} endpoint - The URL endpoint to load the window content from.
 * @param {boolean} escapeClosable - Whether the window can be closed with the Escape key.
 * @param {string} maxWidth - The maximum width of the window container.
 * @param {string} maxHeight - The maximum height of the window container.
 * @param {string} padding - The padding to apply to the window container.
 */

class WindowInitializer {
    constructor(
        windowManager,
        windowName,
        windowId,
        containerId,
        buttonId,
        titleBarId,
        closeBtnId,
        endpoint,
        escapeClosable = false,
        maxWidth = '1200px',
        maxHeight = '1090px',
        padding = '1px'
    ) {
        this.windowManager = windowManager;
        this.windowName = windowName;
        this.windowId = windowId;
        this.containerId = containerId;
        this.buttonId = buttonId;
        this.titleId = titleBarId;
        this.closeBtnId = closeBtnId;
        this.endpoint = endpoint;
        this.escapeClosable = escapeClosable;
        this.maxWidth = maxWidth;
        this.maxHeight = maxHeight;
        this.padding = padding;
        this.init();
    }

    init() {
        const newWindow = new window.OpenWindow(this.endpoint, {
            onLoad: (container, html) => {
                console.log(`${this.windowId} loaded successfully.`);
                container.classList.add('draggable-window');
                container.id = this.windowId;

                // Associate the button with the window

                console.log(`Opening ${this.windowId}.`);
                const titleBar = container.querySelector(`#${this.titleId}`);
                if (titleBar) {
                    this.windowManager.registerWindow(this.windowId, container, `#${this.titleId}`);
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
            },
            escapeClosable: this.escapeClosable
        });

        // Store the window instance globally for reference
        window[`${this.windowName}Instance`] = newWindow;
    }

    assignOpenButton(buttonId) {
        const button = document.getElementById(buttonId);
        if (button) {
            this.windowManager.associateButton(this.windowId, button);
            button.addEventListener('click', async function() {
                console.log(`Opening ${this.windowId} via button click.`);
                if (window.openStates[this.windowName]) {
                    console.log(`${this.windowId} is already open`);
                    return;
                }
                try {
                    window.openStates[this.windowName] = true;
                    this.windowManager.disableWindowButtons(this.windowId);
                    // CONTINUE FROM HERE
                    await window[`${this.windowName}Instance`].open();
                    const container = document.getElementById(this.containerId);
                    if (container) {
                        container.style.maxWidth = this.maxWidth;
                        container.style.maxHeight = this.maxHeight;
                        container.style.padding = this.padding;
                        setTimeout(() => {
                            this.windowManager.centerWindow(this.windowId);
                            this.windowManager.bringToFront(this.windowId);
                        }, 100);
                    } else {
                        console.warn(`Container with ID '${this.containerId}' not found`);
                        window.openStates[this.windowName] = false;
                        this.windowManager.enableWindowButtons(this.windowId);
                    }
                } catch (error) {
                    console.error(`Error opening ${this.windowId}:`, error);
                    window.openStates[this.windowName] = false;
                    this.windowManager.enableWindowButtons(this.windowId);
                }
            })
        } else {
            console.warn(`Button with ID '${buttonId}' not found`);
        }
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