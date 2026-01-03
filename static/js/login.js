
class LoginFormHandler {
    constructor(form) {
        this.form = form;
        this.init();
    }

    init() {
        this.form.addEventListener("submit", (event) => {
            event.preventDefault();
            this.handleSubmit();
        });
    }

    async handleSubmit() {
        const formData = new FormData(this.form);
        const response = await fetch(this.form.action, {
            method: "POST",
            body: formData,
        });

        const result = await response.json();
        this.handleResponse(result);
    }

    handleResponse(result) {
        if (result.status === "success") {
            console.log("Login successful, enabling login button.");
            window.windowManager.enableWindowButtons('login-window');
            console.log("Closing login window.");
            window.loginContainerInstance.close();
            
            // Show success popup
            this.showSuccessPopup(result.message || "Login successful!");
            
            this.loginToLogoutButton(window.loginButton);
        } else {
            // Show error popup
            this.showErrorPopup(result.message || "Login failed. Please try again.");
        }
    }

    showSuccessPopup(message) {
        // Create success popup window
        const popup = document.createElement('div');
        popup.id = 'login-success-popup';
        popup.className = 'draggable-window small-window';
        popup.style.cssText = 'position: absolute; z-index: 1000; left: 50%; top: 50%; transform: translate(-50%, -50%);';
        
        popup.innerHTML = `
            <div class="window-content">
                <div class="title-bar">
                    <h4>Success</h4>
                    <button id="close-success-popup" class="w98-button title-button">X</button>
                </div>
                <div style="padding: 20px; text-align: center;">
                    <p style="color: green; font-weight: bold;">${message}</p>
                    <button id="success-ok-button" class="w98-button" style="margin-top: 10px;">OK</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(popup);
        
        // Register with window manager
        windowManager.registerWindow('login-success-popup', popup, '.title-bar');
        windowManager.centerWindow('login-success-popup');
        windowManager.bringToFront('login-success-popup');
        
        // Add close handlers
        const closeHandler = () => {
            popup.remove();
            // Reload the page to refresh the UI
            window.location.reload();
        };
        
        document.getElementById('close-success-popup').addEventListener('click', closeHandler);
        document.getElementById('success-ok-button').addEventListener('click', closeHandler);
    }

    showErrorPopup(message) {
        // Create error popup window
        const popup = document.createElement('div');
        popup.id = 'login-error-popup';
        popup.className = 'draggable-window small-window';
        popup.style.cssText = 'position: absolute; z-index: 1000; left: 50%; top: 50%; transform: translate(-50%, -50%);';
        
        popup.innerHTML = `
            <div class="window-content">
                <div class="title-bar">
                    <h4>Error</h4>
                    <button id="close-error-popup" class="w98-button title-button">X</button>
                </div>
                <div style="padding: 20px; text-align: center;">
                    <p style="color: red; font-weight: bold;">${message}</p>
                    <button id="error-ok-button" class="w98-button" style="margin-top: 10px;">OK</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(popup);
        
        // Register with window manager
        windowManager.registerWindow('login-error-popup', popup, '.title-bar');
        windowManager.centerWindow('login-error-popup');
        windowManager.bringToFront('login-error-popup');
        
        // Add close handlers
        const closeHandler = () => {
            popup.remove();
        };
        
        document.getElementById('close-error-popup').addEventListener('click', closeHandler);
        document.getElementById('error-ok-button').addEventListener('click', closeHandler);
    }

    loginToLogoutButton(loginButton) {
        loginButton.textContent = "Logout";
        // Remove the old login handler
        if (window.loginButton._loginHandler) {
            window.loginButton.removeEventListener("click", window.loginButton._loginHandler);
        }
        // Add logout handler with proper binding
        const logoutHandler = () => this.handleLogout();
        loginButton._logoutHandler = logoutHandler;
        loginButton.addEventListener("click", logoutHandler);
    }

    showErrors(errors) {
        for (const [field, messages] of Object.entries(errors)) {
            const fieldElement = this.form.querySelector(`[name="${field}"]`);
            const errorContainer = document.createElement("div");
            errorContainer.classList.add("error-messages");
            messages.forEach((message) => {
                const errorMessage = document.createElement("p");
                errorMessage.textContent = message;
                errorContainer.appendChild(errorMessage);
            });
            fieldElement.parentElement.appendChild(errorContainer);
        }
    }

    async handleLogout() {
        try {
            // Get logout URL from the login form's data attribute or construct it
            const logoutUrl = this.form.dataset.logoutUrl || '/fort/logout';
            
            const response = await fetch(logoutUrl, {
                method: "POST",
                credentials: "include",
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                this.logout(); // Do UI cleanup on successful logout
            } else {
                console.error("Logout failed:", response.status);
                alert("Logout failed. Please try again.");
            }
        } catch (error) {
            console.error("Logout error:", error);
            alert("Logout failed: " + error.message);
        }
    }

    logout() {
        console.log("Logging out...");
        // Reset button text
        window.loginButton.textContent = "Login";
        // Remove logout handler
        if (window.loginButton._logoutHandler) {
            window.loginButton.removeEventListener("click", window.loginButton._logoutHandler);
        }
        // Restore login functionality
        window.initLoginButton(window.loginButton);
    }
}

const loginForm = document.querySelector(".login-form");
document.dispatchEvent(new CustomEvent('loginInjected', {

    detail: {
        form: loginForm,
        formHandler: new LoginFormHandler(loginForm)
    }
}));