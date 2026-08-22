
/**
 * OpenWindow - Loads HTML partials via AJAX and injects them into the page
 */
class OpenWindow {
    constructor(url, options = {}) {
        this.url = url;
        this.isHtmlString = this._isHtmlString(url);
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
        console.log(`OpenWindow initialized with ${this.isHtmlString ? 'HTML string' : 'URL: ' + this.url}`);
    }

    /**
     * Detect if input is HTML string or URL
     */
    _isHtmlString(input) {
        if (typeof input !== 'string') return false;
        
        // Check if it looks like a URL (starts with /, http://, https://, or contains protocol)
        if (input.startsWith('/') || input.startsWith('http://') || input.startsWith('https://') || input.includes('://')) {
            return false;
        }
        
        // Check if it contains HTML tags
        return input.trim().startsWith('<') || /<[a-z][\s\S]*>/i.test(input);
    }

    /**
     * Fetch HTML partial and inject into page (or inject HTML string directly)
     */
    async open(showLoading = true, disableBtnImmediately = false) {
        try {
            let htmlContent;

            if (this.isHtmlString) {
                // HTML string provided directly - no need to fetch
                if (showLoading) {
                    this._showLoading();
                }
                
                htmlContent = this.url; // The "url" is actually the HTML string
                
                // Small delay to show loading state briefly (optional)
                await new Promise(resolve => setTimeout(resolve, 50));
                
                this._hideLoading();
            } else {
                // URL provided - fetch content via AJAX
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
                
                this._hideLoading();
            }
            
            // Inject content into page
            this._injectContent(htmlContent);
            
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
        window.CatLoader?.show({ id: 'open-window' });
    }

    /**
     * Hide loading indicator
     */
    _hideLoading() {
        window.CatLoader?.hide('open-window');
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

// CSS styles for error state (loading indicator now comes from CatLoader)
const openWindowStyles = `
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