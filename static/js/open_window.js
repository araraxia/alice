
/**
 * OpenWindow - Loads HTML partials via AJAX and injects them into the page
 */
class OpenWindow {
    constructor(url, options = {}) {
        this.url = url;
        this.options = {
            containerId: options.containerId || null, // Optional container ID
            replaceContent: options.replaceContent || false, // Replace vs append
            onLoad: options.onLoad || null, // Callback after content loads
            onClose: options.onClose || null, // Callback when window closes
            onError: options.onError || null, // Error callback
            escapeClosable: options.escapeClosable || false, // Close on Escape key
            ...options
        };
        this.container = null;
        console.log(`OpenWindow initialized with URL: ${this.url}`);
    }

    /**
     * Fetch HTML partial and inject into page
     */
    async open(showLoading = true, disableBtnImmediately = false) {
        try {
            // Show loading state if needed
            if (showLoading) {
                this._showLoading();
            }

            // Make AJAX request
            const response = await fetch(this.url, {
                method: 'GET',
                headers: {
                    'Accept': 'text/html',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Check if response is JSON or plain HTML
            const contentType = response.headers.get('content-type');
            let htmlContent;
            
            if (contentType && contentType.includes('application/json')) {
                const jsonData = await response.json();
                // Handle JSON response with html property
                if (jsonData.html) {
                    htmlContent = jsonData.html;
                } else {
                    throw new Error('JSON response does not contain html property');
                }
            } else {
                // Handle plain HTML response
                htmlContent = await response.text();
            }
            
            // Inject content into page
            this._injectContent(htmlContent);
            
            // Hide loading state
            this._hideLoading();
            
            if (this.options.escapeClosable) {
                escapeWindowStack.push(this);
                console.debug('Added window to escapeWindowStack:', this);
            }

            // Execute callback if provided
            if (this.options.onLoad) {
                this.options.onLoad(this.container, htmlContent);
            }

            return this.container;

        } catch (error) {
            console.error('OpenWindow: Failed to load content', error);
            this._hideLoading();
            
            // Execute error callback if provided
            if (this.options.onError) {
                this.options.onError(error);
            } else {
                this._showError(error.message);
            }
            
            throw error;
        }
    }

    /**
     * Remove the injected content from the page
     */
    close() {
        if (this.container && this.container.parentNode) {
            // Call onClose callback before removing
            if (this.options.onClose && typeof this.options.onClose === 'function') {
                try {
                    this.options.onClose(this.container);
                } catch (error) {
                    console.error('Error in onClose callback:', error);
                }
            }
            
            this.container.parentNode.removeChild(this.container);
            this.container = null;
        }
    }

    /**
     * Inject HTML content into the page
     */
    _injectContent(htmlContent) {
        // Determine target container
        let targetContainer;
        
        if (this.options.containerId) {
            targetContainer = document.getElementById(this.options.containerId);
            if (!targetContainer) {
                throw new Error(`Container with ID '${this.options.containerId}' not found`);
            }
        } else {
            targetContainer = document.body;
        }

        if (this.options.replaceContent) {
            // Replace existing content
            targetContainer.innerHTML = htmlContent;
            this.container = targetContainer;
        } else {
            // Create new container and append
            this.container = document.createElement('div');
            this.container.className = 'open-window-content';
            this.container.innerHTML = htmlContent;
            targetContainer.appendChild(this.container);
        }

        // Execute any scripts in the loaded content
        this._executeScripts();
    }

    /**
     * Execute script tags in the loaded content
     */
    _executeScripts() {
        if (!this.container) return;

        const scripts = this.container.querySelectorAll('script');
        scripts.forEach(script => {
            const newScript = document.createElement('script');
            
            // Copy attributes
            Array.from(script.attributes).forEach(attr => {
                newScript.setAttribute(attr.name, attr.value);
            });
            
            // Copy content
            newScript.textContent = script.textContent;
            
            // Replace old script with new one to execute it
            script.parentNode.replaceChild(newScript, script);
        });
    }

    /**
     * Show loading indicator
     */
    _showLoading() {
        if (this.options.showLoading === false) return;
        
        // Create or update loading indicator
        let loader = document.getElementById('open-window-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'open-window-loader';
            loader.className = 'open-window-loader';
            loader.innerHTML = '<div class="loader-spinner"></div><span>Loading...</span>';
            document.body.appendChild(loader);
        }
        loader.style.display = 'block';
    }

    /**
     * Hide loading indicator
     */
    _hideLoading() {
        const loader = document.getElementById('open-window-loader');
        if (loader) {
            loader.style.display = 'none';
        }
    }

    /**
     * Show error message
     */
    _showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'open-window-error';
        errorDiv.innerHTML = `
            <div class="error-content">
                <h3>Error Loading Content</h3>
                <p>${message}</p>
                <button onclick="this.parentElement.parentElement.remove()">Close</button>
            </div>
        `;
        document.body.appendChild(errorDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 5000);
    }
}

// CSS styles for loading and error states
const openWindowStyles = `
.open-window-loader {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 20px;
    border-radius: 5px;
    z-index: 10000;
    display: none;
    text-align: center;
}

.loader-spinner {
    border: 3px solid #f3f3f3;
    border-top: 3px solid #3498db;
    border-radius: 50%;
    width: 30px;
    height: 30px;
    animation: spin 1s linear infinite;
    margin: 0 auto 10px;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.open-window-error {
    position: fixed;
    top: 20px;
    right: 20px;
    background: #f44336;
    color: white;
    padding: 15px;
    border-radius: 5px;
    z-index: 10001;
    max-width: 300px;
}

.open-window-error button {
    background: rgba(255, 255, 255, 0.2);
    border: none;
    color: white;
    padding: 5px 10px;
    border-radius: 3px;
    cursor: pointer;
    margin-top: 10px;
}

.open-window-content {
    /* Default styles for injected content */
}
`;

// Inject styles if not already present
if (!document.getElementById('open-window-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'open-window-styles';
    styleSheet.textContent = openWindowStyles;
    document.head.appendChild(styleSheet);
}

window.OpenWindow = OpenWindow;