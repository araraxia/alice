/**
 * Window Manager - Universal Draggable Window System
 * Provides a centralized way to manage all draggable windows
 */

class WindowManager {
    constructor() {
        this.windows = new Map();
        this.windowButtons = new Map(); // Track buttons associated with windows
        this.currentMaxZIndex = 10; // Track the current maximum z-index
        this.activeWindowId = null; // Track the currently active window
        this.init();
    }

    init() {
        // Automatically discover and register all draggable windows on page load
        document.addEventListener('DOMContentLoaded', () => {
            this.autoDiscoverWindows();
        });
    }

    /**
     * Automatically discover all elements with 'draggable-window' class
     */
    autoDiscoverWindows() {
        const draggableElements = document.querySelectorAll('.draggable-window');
        
        draggableElements.forEach(element => {
            const titleBar = element.querySelector('.title-bar');
            if (titleBar) {
                const windowId = element.id || `window-${this.windows.size}`;
                this.registerWindow(windowId, element, titleBar);
            }
        });

        // Set the first visible window as active
        if (this.windows.size > 0 && !this.activeWindowId) {
            this._findAndSetNextActiveWindow();
        }
        
        // Dispatch an event to signal that windowManager is ready
        document.dispatchEvent(new CustomEvent('windowManagerReady', { detail: { manager: this } }));
    }

    /**
     * Register a window for drag functionality
     * @param {string} windowId - Unique identifier for the window
     * @param {HTMLElement|string} container - Container element or selector
     * @param {string} titleBarSelector - Title bar selector (optional, defaults to '.title-bar')
     * @param {Object} options - Additional options
     */
    registerWindow(windowId, container, titleBarSelector = '.title-bar', options = {}) {
        const dragWindow = new DragWindow(container, titleBarSelector);
        
        if (dragWindow.container) {
            this.windows.set(windowId, {
                dragWindow,
                container: dragWindow.container,
                titleBar: dragWindow.titleBar,
                options: {
                    centerOnLoad: options.centerOnLoad || false,
                    closeable: options.closeable || false,
                    minimizable: options.minimizable || false,
                    ...options
                }
            });

            // Apply initial options
            if (options.centerOnLoad) {
                dragWindow.center();
            }

            // Set up automatic window activation for this window
            this._setupWindowActivation(windowId);

            console.log(`Window '${windowId}' registered successfully`);
            return dragWindow;
        } else {
            console.warn(`Failed to register window '${windowId}'`);
            return null;
        }
    }

    /**
     * Set up automatic window activation for a specific window
     * @param {string} windowId - Window identifier
     * @private
     */
    _setupWindowActivation(windowId) {
        const window = this.getWindow(windowId);
        if (!window || !window.container) return;

        // Bring window to front on any mouse interaction
        const bringToFrontEvents = ['mousedown', 'click'];
        bringToFrontEvents.forEach(eventType => {
            window.container.addEventListener(eventType, (e) => {
                // Only bring to front if the window isn't already active
                if (this.activeWindowId !== windowId) {
                    this.bringToFront(windowId);
                }
            }, true); // Use capture phase to ensure it fires first
        });

        // Also bring to front when clicking on title bar specifically
        if (window.titleBar) {
            window.titleBar.addEventListener('mousedown', () => {
                this.bringToFront(windowId);
            });
        }

        // Bring to front when any input element inside the window is focused
        const inputElements = window.container.querySelectorAll('input, textarea, select, button');
        inputElements.forEach(input => {
            input.addEventListener('focus', () => {
                this.bringToFront(windowId);
            });
        });
    }

    /**
     * Associate a button with a window for state management
     * @param {string} windowId - Window identifier
     * @param {HTMLElement|string} button - Button element or selector
     */
    associateButton(windowId, button) {
        const buttonElement = typeof button === 'string' ? document.querySelector(button) : button;
        
        if (buttonElement) {
            if (!this.windowButtons.has(windowId)) {
                this.windowButtons.set(windowId, []);
            }
            this.windowButtons.get(windowId).push({
                element: buttonElement,
                originalDisabled: buttonElement.disabled,
                originalText: buttonElement.textContent,
                originalClass: buttonElement.className
            });
            
            console.log(`Button associated with window '${windowId}'`);
        } else {
            console.warn(`Button not found for window '${windowId}'`);
        }
    }

    /**
     * Disable all buttons associated with a window
     * @param {string} windowId - Window identifier
     */
    disableWindowButtons(windowId) {
        const buttons = this.windowButtons.get(windowId);
        if (buttons) {
            buttons.forEach(buttonInfo => {
                buttonInfo.element.disabled = true;
                buttonInfo.element.classList.add('window-open');
                // Optionally change button text to indicate window is open
                if (buttonInfo.element.textContent && !buttonInfo.element.textContent.includes('(Open)')) {
                    buttonInfo.element.textContent = buttonInfo.originalText + ' (Open)';
                }
            });
            console.log(`Disabled ${buttons.length} button(s) for window '${windowId}'`);
        } else {
            console.log(`No buttons found for window '${windowId}'`);
        }
    }

    /**
     * Re-enable all buttons associated with a window
     * @param {string} windowId - Window identifier
     */
    enableWindowButtons(windowId) {
        const buttons = this.windowButtons.get(windowId);
        if (buttons) {
            buttons.forEach(buttonInfo => {
                buttonInfo.element.disabled = buttonInfo.originalDisabled;
                buttonInfo.element.classList.remove('window-open');
                buttonInfo.element.textContent = buttonInfo.originalText;
            });
            console.log(`Enabled ${buttons.length} button(s) for window '${windowId}'`);
        } else {
            console.log(`No buttons found for window '${windowId}'`);
        }
    }

    /**
     * Get a registered window
     * @param {string} windowId - Window identifier
     */
    getWindow(windowId) {
        const window = this.windows.get(windowId);
        if (!window) {
            console.warn(`Window '${windowId}' not found`);
        }
        return window;
    }

    /**
     * Show a window
     * @param {string} windowId - Window identifier
     */
    showWindow(windowId) {
        const window = this.getWindow(windowId);
        if (window && window.container) {
            window.container.style.display = 'block';
            this.disableWindowButtons(windowId);
            
            // Automatically bring to front when shown
            this.bringToFront(windowId);
            
            // Trigger custom event for window shown
            const event = new CustomEvent('windowShown', { 
                detail: { windowId, window } 
            });
            document.dispatchEvent(event);
            
            return true;
        }
        return false;
    }

    /**
     * Hide a window
     * @param {string} windowId - Window identifier
     */
    hideWindow(windowId) {
        const window = this.getWindow(windowId);
        if (window && window.container) {
            window.container.style.display = 'none';
            window.container.classList.remove('active-window');
            this.enableWindowButtons(windowId);
            
            // Clear active window if this was the active one
            if (this.activeWindowId === windowId) {
                this.activeWindowId = null;
                
                // Find the next highest window to make active
                this._findAndSetNextActiveWindow();
            }
            
            // Trigger custom event for window hidden
            const event = new CustomEvent('windowHidden', { 
                detail: { windowId, window } 
            });
            document.dispatchEvent(event);
            
            return true;
        }
        return false;
    }

    /**
     * Find the window with the highest z-index and set it as active
     * @private
     */
    _findAndSetNextActiveWindow() {
        let highestZIndex = 0;
        let nextActiveWindowId = null;
        
        this.windows.forEach((window, windowId) => {
            if (window.container && window.container.style.display !== 'none') {
                const zIndex = parseInt(window.container.style.zIndex) || 10;
                if (zIndex > highestZIndex) {
                    highestZIndex = zIndex;
                    nextActiveWindowId = windowId;
                }
            }
        });
        
        if (nextActiveWindowId) {
            const nextWindow = this.getWindow(nextActiveWindowId);
            if (nextWindow && nextWindow.container) {
                this.activeWindowId = nextActiveWindowId;
                nextWindow.container.classList.add('active-window');
                console.log(`Window '${nextActiveWindowId}' is now active with z-index ${highestZIndex}`);
            }
        }
    }

    /**
     * Get the currently active window ID
     */
    getActiveWindowId() {
        return this.activeWindowId;
    }

    /**
     * Toggle window visibility
     * @param {string} windowId - Window identifier
     */
    toggleWindow(windowId) {
        const window = this.getWindow(windowId);
        if (window && window.container) {
            const isVisible = window.container.style.display !== 'none';
            if (isVisible) {
                this.hideWindow(windowId);
            } else {
                this.showWindow(windowId);
            }
            return !isVisible;
        }
        return false;
    }

    /**
     * Set up a button to control a window with automatic state management
     * @param {HTMLElement|string} button - Button element or selector
     * @param {string} windowId - Window identifier
     * @param {Object} options - Additional options
     */
    setupWindowButton(button, windowId, options = {}) {
        const buttonElement = typeof button === 'string' ? document.querySelector(button) : button;
        
        if (!buttonElement) {
            console.warn(`Button not found for window '${windowId}'`);
            return false;
        }

        // Associate the button with the window
        this.associateButton(windowId, buttonElement);

        // Set up click handler
        buttonElement.addEventListener('click', () => {
            console.log(`Button clicked for window '${windowId}', toggle: ${options.toggle}`);
            if (options.toggle) {
                this.toggleWindow(windowId);
            } else {
                this.showWindow(windowId);
            }
        });

        console.log(`Window button '${buttonElement.id || buttonElement.textContent || 'unnamed'}' set up for window '${windowId}'`);
        return true;
    }

    /**
     * Check if a window is currently visible
     * @param {string} windowId - Window identifier
     */
    isWindowVisible(windowId) {
        const window = this.getWindow(windowId);
        if (window && window.container) {
            return window.container.style.display !== 'none';
        }
        return false;
    }

    /**
     * Get window visibility status and button states
     * @param {string} windowId - Window identifier
     */
    getWindowStatus(windowId) {
        const window = this.getWindow(windowId);
        const buttons = this.windowButtons.get(windowId);
        
        return {
            exists: !!window,
            visible: this.isWindowVisible(windowId),
            buttonCount: buttons ? buttons.length : 0,
            buttonsDisabled: buttons ? buttons.some(b => b.element.disabled) : false
        };
    }

    /**
     * Center a window
     * @param {string} windowId - Window identifier
     */
    centerWindow(windowId) {
        console.log(`Centering window '${windowId}'`);
        const window = this.getWindow(windowId);
        if (window && window.dragWindow) {
            window.dragWindow.center();
            return true;
        }
        return false;
    }

    /**
     * Bring window to front and set as active
     * @param {string} windowId - Window identifier
     */
    bringToFront(windowId) {
        const window = this.getWindow(windowId);
        if (window && window.container) {
            // Only update z-index if this window isn't already the active one
            if (this.activeWindowId !== windowId) {
                this.currentMaxZIndex += 1;
                window.container.style.zIndex = this.currentMaxZIndex;
                
                // Remove active class from previous active window
                if (this.activeWindowId) {
                    const prevWindow = this.getWindow(this.activeWindowId);
                    if (prevWindow && prevWindow.container) {
                        prevWindow.container.classList.remove('active-window');
                    }
                }
                
                // Set new active window
                this.activeWindowId = windowId;
                window.container.classList.add('active-window');
                
                // Trigger custom event for window activation
                const event = new CustomEvent('windowActivated', { 
                    detail: { windowId, window, zIndex: this.currentMaxZIndex } 
                });
                document.dispatchEvent(event);
                
                console.log(`Window '${windowId}' brought to front with z-index ${this.currentMaxZIndex}`);
            }
            return true;
        }
        return false;
    }

    /**
     * Create a new window element with predefined classes
     * @param {string} windowId - Unique identifier for the window
     * @param {Object} config - Window configuration
     */
    createWindow(windowId, config = {}) {
        const {
            title = 'New Window',
            content = '',
            size = 'medium', // small, medium, large
            position = 'centered', // top-left, top-right, bottom-left, bottom-right, centered
            closeable = true,
            className = ''
        } = config;

        // Create window structure
        const windowElement = document.createElement('div');
        windowElement.id = windowId;
        windowElement.className = `draggable-window ${size}-window ${position} ${className}`;

        windowElement.innerHTML = `
            <div class="window-content">
                <div class="title-bar" id="${windowId}-title-bar">
                    <h4>${title}</h4>
                    ${closeable ? `<button id="${windowId}-close-button" class="w98-button title-button">X</button>` : ''}
                </div>
                <div class="window-body">
                    ${content}
                </div>
            </div>
        `;

        // Add to page
        document.body.appendChild(windowElement);

        // Register with window manager
        const dragWindow = this.registerWindow(windowId, windowElement, '.title-bar', {
            closeable,
            centerOnLoad: position === 'centered'
        });

        // Set up close button if closeable
        if (closeable) {
            const closeButton = windowElement.querySelector(`#${windowId}-close-button`);
            if (closeButton) {
                closeButton.addEventListener('click', () => {
                    this.hideWindow(windowId);
                });
            }
        }

        return dragWindow;
    }

    /**
     * Get information about all windows and their z-index ordering
     */
    getWindowZIndexOrder() {
        const windowOrder = [];
        
        this.windows.forEach((window, windowId) => {
            if (window.container) {
                const zIndex = parseInt(window.container.style.zIndex) || 10;
                const isVisible = window.container.style.display !== 'none';
                const isActive = windowId === this.activeWindowId;
                
                windowOrder.push({
                    windowId,
                    zIndex,
                    isVisible,
                    isActive,
                    element: window.container
                });
            }
        });
        
        // Sort by z-index (highest first)
        windowOrder.sort((a, b) => b.zIndex - a.zIndex);
        
        return windowOrder;
    }

    /**
     * Get all registered window IDs
     */
    getWindowIds() {
        return Array.from(this.windows.keys());
    }

    /**
     * Set up common window controls (close buttons, etc.)
     */
    setupWindowControls() {
        this.windows.forEach((window, windowId) => {
            // Set up close button if it exists
            const closeButton = window.container.querySelector('.close-button, [id*="close"]');
            if (closeButton && window.options.closeable !== false) {
                closeButton.addEventListener('click', () => {
                    this.hideWindow(windowId);
                });
            }

            // Bring window to front on any mouse interaction
            const bringToFrontEvents = ['mousedown', 'click', 'focus'];
            bringToFrontEvents.forEach(eventType => {
                window.container.addEventListener(eventType, (e) => {
                    // Only bring to front if the window isn't already active
                    if (this.activeWindowId !== windowId) {
                        this.bringToFront(windowId);
                    }
                }, true); // Use capture phase to ensure it fires first
            });

            // Also bring to front when clicking on title bar specifically
            if (window.titleBar) {
                window.titleBar.addEventListener('mousedown', () => {
                    this.bringToFront(windowId);
                });
            }

            // Bring to front when any input element inside the window is focused
            const inputElements = window.container.querySelectorAll('input, textarea, select, button');
            inputElements.forEach(input => {
                input.addEventListener('focus', () => {
                    this.bringToFront(windowId);
                });
            });
        });
    }
}

// Create global instance
const windowManager = new WindowManager();

// Make WindowManager available globally
window.WindowManager = WindowManager;
window.windowManager = windowManager;