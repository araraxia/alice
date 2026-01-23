
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
        window.itemSearchOpenState = false;
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
                this.initItemSearch();
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
        const superCombatsInitializer = new window.WindowInitializer(
            this.windowManager,
            "superCombats",
            "super-combats-window",
            "super-combats-container",
            "super-combats-button",
            "super-combats-title-bar",
            "close-super-combats-button",
            SUPERCOMBATSENDPOINT,
            true,
            '1200px',
            '1090px',
            '1px'
        );
        superCombatsInitializer.assignOpenButton('super-combats-button');
    }

    initGoadingRegens() {
        console.log("Initializing Goading Regens window.");
        const goadingRegensInitializer = new window.WindowInitializer(
            this.windowManager,
            "goadingRegens",
            "goading-regens-window",
            "goading-regens-container",
            "goading-regens-button",
            "goading-regens-title-bar",
            "close-goading-regens-button",
            GOADINGREGENSENDPOINT,
            true,
            '950px',
            '700px',
            '1px'
        );
        goadingRegensInitializer.assignOpenButton('goading-regens-button');
    }

    initItemSearch() {
        console.log("Initializing Item Search window.");
        const itemSearchInitializer = new window.WindowInitializer(
            this.windowManager,
            "itemSearch",
            "item-search-window",
            "item-search-container",
            "item-search-button",
            "item-search-title-bar",
            "close-item-search-button",
            ITEMSEARCHENDPOINT,
            true,
            '600px',
            '700px',
            '1px'
        );
        itemSearchInitializer.assignOpenButton('item-search-button');
    }

    checkIfOpen() {
        return document.getElementById(this.windowId) !== null;
    }
}

window.osrsIndex = new OSRSIndex();