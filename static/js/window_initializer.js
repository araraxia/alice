
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