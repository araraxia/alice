
class OSRSIndex {
    constructor() {
        this.windowManager = window.windowManager;
        this.windowId = "osrs-index-window";
        this.buttonId = "osrs-index-button";
        this.titleId = "osrs-index-title-bar";
        this.closeBtnId = "close-osrs-index-button";
        this.endpoint = OSRSENDPOINT;
    }

    async fetchHtml() {
        console.log('Fetching OSRS tools from ', this.endpoint);
        const response = await fetch(this.endpoint);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.status === 'success' && data.html) {
            return data.html;
        }
    }

    async initHtml() {
        if (this.checkIfOpen()) {
            console.log('OSRS tools window is already open, bringing to front.');
            this.windowManager.bringToFront(this.windowId);
        } else {
            console.log('OSRS tools window is not open, creating new window.');
            await this.initOsrs();
        }
    }

    async initOsrs() {
        window.osrsWindow = new window.openWindow(this.endpoint, {
            onLoad: (container, html) => {
                console.log('OSRS tools window loaded successfully.');
                container.classList.add('draggable-window');
                container.classList.add('w98-window');
                container.classList.add('medium-window');
                container.id = this.windowId;
                container.style.display = 'none'; // Initially hide the window
            }
        });

        const html = await this.fetchHtml();
        if (html) {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = html.trim();
            const osrsWindow = tempDiv.firstChild;
            if (osrsWindow, html) {
                console.log('OSRS tools window created successfully, making draggable.');
                osrsWindow.classList.add('draggable-window');
                osrsWindow.classList.add('w98-window');
                osrsWindow.classList.add('medium-window');
                osrsWindow.style.display = 'none'; // Initially hide the window
                osrsWindow.id = this.windowId;
                document.body.appendChild(osrsWindow);
                this.registerElements();
            } else {
                console.error('Failed to create OSRS tools window: No valid HTML element found.');
            }
        } else {
            console.error('Failed to load OSRS tools HTML content.');
        }

    }

    openWindow() {
        this.windowManager.disableWindowButtons(this.windowId);
        if (this.checkIfOpen()) {
            console.log('Preventing new window propagation, OSRS tools window already open');
            this.windowManager.bringToFront(this.windowId);
            return;
        } else {
            console.log('Opening OSRS tools window.');
            this.windowManager.registerWindow(this.windowId, window.osrsWindow, this.titleId);
            this.windowManager.centerWindow(this.windowId);
            this.windowManager.bringToFront(this.windowId);
            window.osrsWindow.style.display = 'block'; // Show the window
        }
    }

    registerElements() {
        console.log('Registering OSRS tools window with WindowManager.');
        this.windowManager.associateButton(this.buttonId, this.windowId);
        this.initClose();
    }

    initClose() {
        // Set up close button
        console.log('Setting up close button for OSRS tools window.');
        const closeBtn = document.getElementById('close-osrs-index-button');
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                this.windowManager.hideWindow(this.windowId);
                setTimeout(() => {
                    window.osrsWindow.remove();
                    this.windowManager.unregisterWindow(this.windowId);
                }, 300); // Delay to allow any closing animations
            });
        }
    }

    checkIfOpen() {
        return document.getElementById(this.windowId) !== null;
    }
}

window.osrsIndex = new OSRSIndex();