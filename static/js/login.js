
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
            console.log("Login successful, reinabling login button.");
            window.windowManager.enableWindowButtons('login-modal');
            console.log("Closing login window.");
            window.loginWindow.close();
            this.loginToLogoutButton(window.loginButton);
        } else {
            this.showErrors(result.errors);
        }
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