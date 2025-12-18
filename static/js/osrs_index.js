
class OSRSIndex {
    constructor() {
        this.windowManager = window.windowManager;
        this.windowId = "osrs-index-window";
        this.buttonId = "osrs-index-button";
        this.titleId = "osrs-index-title-bar";
        this.closeBtnId = "close-osrs-index-button";
        this.endpoint = OSRSENDPOINT;
        window.superCombatsOpenState = false; 
        window.goadingRegensOpenState = false;
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
                } else {
                    console.warn(`Title bar with ID '${this.titleId}' not found`);
                }
                this.initClose(osrsWindow);
                this.initSuperCombats();
                this.initGoadingRegens();
            },
            onClose: () => {
                this.windowManager.enableWindowButtons(this.windowId);
                // Note: No unregisterWindow method exists, window manager handles cleanup automatically
            },
            escapeClosable: true
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

    initSuperCombats() {
        console.log("Initializing Super Combats window.");
        const scWindowId = "super-combats-window";
        const scContainerId = "super-combats-container";
        const superCombatsBtn = document.getElementById('super-combats-button');
        if (superCombatsBtn) {
            // Call WindowInitializer for Super Combats window
            new window.WindowInitializer(
                this.windowManager, 
                "superCombats",
                scWindowId,
                "super-combats-button",
                "super-combats-title-bar",
                "close-super-combats-button",
                SUPERCOMBATSENDPOINT,
                true
            );
            
            window.superCombatsBtn = superCombatsBtn;
            const windowManager = this.windowManager;
            windowManager.associateButton(scWindowId, superCombatsBtn);
            
            superCombatsBtn.addEventListener('click', async function() {
                console.log("Super Combats button clicked");
                if (window.superCombatsOpenState) {
                    console.log("Super Combats window is already open");
                    return;
                }
                try {
                    window.superCombatsOpenState = true;
                    windowManager.disableWindowButtons(scWindowId);
                    await window.superCombatsInstance.open();
                    const scContainer = document.getElementById(scContainerId);
                    if (scContainer) {
                        scContainer.style.maxWidth = '1200px';
                        scContainer.style.padding = `1px`;
                        // Wait for the DOM to update and CSS to apply
                        setTimeout(() => {
                            windowManager.centerWindow(scWindowId);
                        }, 100);
                    } else {
                        console.warn("Super Combats container not found");
                    }
                } catch (error) {
                    console.error("Error opening Super Combats window:", error);
                    window.superCombatsOpenState = false;
                }
            });
        } else {
            console.warn("Super Combats button not found");
        }
    }

    initGoadingRegens() {
        console.log("Initializing Goading Regens window.");
        const grWindowId = "goading-regens-window";
        const grContainerId = "goading-regens-container";
        const goadingRegensBtn = document.getElementById('goading-regens-button');
        if (goadingRegensBtn) {
            // Call WindowInitializer for Goading Regens window
            const goadingRegensInitializer = new window.WindowInitializer(
                this.windowManager,
                "goadingRegens",
                grWindowId,
                "goading-regens-button",
                "goading-regens-title-bar",
                "close-goading-regens-button",
                GOADINGREGENSENDPOINT
            );
            
            // Set the button globally for reference
            window.goadingRegensBtn = goadingRegensBtn;
            const windowManager = window.windowManager;
            windowManager.associateButton(grWindowId, goadingRegensBtn);

            goadingRegensBtn.addEventListener('click', async function() {
                console.log("Goading Regens button clicked");
                if (window.goadingRegensOpenState) {
                    console.log("Goading Regens window is already open");
                    return;
                }

                try {
                    window.goadingRegensOpenState = true;
                    windowManager.disableWindowButtons(grWindowId);
                    await window.goadingRegensInstance.open();
                    const grContainer = document.getElementById(grContainerId);
                    if (grContainer) {
                        grContainer.style.maxWidth = '1200px';
                        grContainer.style.padding = `1px`;
                        // Wait for the DOM to update and CSS to apply
                        setTimeout(() => {
                            windowManager.centerWindow(grWindowId);
                        }, 100);
                    } else {
                        console.warn("Goading Regens container not found");
                    }
                } catch (error) {
                    console.error("Error opening Goading Regens window:", error);
                    window.goadingRegensOpenState = false;
                }
            });
        } else {
            console.warn("Goading Regens button not found");
        }
    }

    checkIfOpen() {
        return document.getElementById(this.windowId) !== null;
    }
}

window.osrsIndex = new OSRSIndex();