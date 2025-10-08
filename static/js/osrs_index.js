
class OSRSIndex {
    constructor() {
        this.windowManager = window.windowManager;
        this.windowId = "osrs-index-window";
        this.buttonId = "osrs-index-button";
        this.titleId = "osrs-index-title-bar";
        this.closeBtnId = "close-osrs-index-button";
        this.endpoint = OSRSENDPOINT;
    }

    async openWindow() {
        const osrsWindow = new window.OpenWindow(this.endpoint, {
            onLoad: (container, html) => {
                console.log('OSRS tools window loaded successfully.');
                container.classList.add('draggable-window');
                container.id = this.windowId;
                
                // Associate the button with the window
                const button = document.getElementById(this.buttonId);
                if (button) {
                    this.windowManager.associateButton(this.windowId, button);
                }
                
                console.log('Opening OSRS tools window.');
                const titleBar = container.querySelector(`#${this.titleId}`);
                if (titleBar) {
                    this.windowManager.registerWindow(this.windowId, container, `#${this.titleId}`);
                    this.windowManager.disableWindowButtons(this.windowId);
                    this.windowManager.centerWindow(this.windowId);
                    this.windowManager.bringToFront(this.windowId);
                    this.initClose(osrsWindow);
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
        window.osrsWindow = osrsWindow;
    }

    initClose(osrsWindow) {
        // Set up close button
        console.log('Setting up close button for OSRS tools window.');
        const closeBtn = document.getElementById(this.closeBtnId);
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                console.log('Close button clicked for OSRS window');
                this.windowManager.enableWindowButtons(this.windowId);
                osrsWindow.close();
            });
        } else {
            console.warn(`Close button with ID '${this.closeBtnId}' not found`);
        }
    }

    checkIfOpen() {
        return document.getElementById(this.windowId) !== null;
    }
}

window.osrsIndex = new OSRSIndex();