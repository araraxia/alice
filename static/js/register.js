class RegisterFormHandler {
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
            console.log("Registration successful!");
            window.windowManager.enableWindowButtons('register-window');
            console.log("Closing register window.");
            window.registerContainerInstance.close();
            // Show success message
            alert("Registration successful! Please check your email to verify your account.");
        } else {
            console.error("Registration failed:", result);
            // If there's HTML returned with errors, update the form
            if (result.html) {
                // Update the form with the error-containing HTML
                const container = document.getElementById('register-container');
                if (container) {
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = result.html;
                    const newForm = tempDiv.querySelector('.register-form');
                    const oldForm = container.querySelector('.register-form');
                    if (newForm && oldForm) {
                        oldForm.parentNode.replaceChild(newForm, oldForm);
                        // Re-initialize the form handler
                        new RegisterFormHandler(newForm);
                    }
                }
            } else if (result.message) {
                alert("Registration failed: " + result.message);
            } else {
                this.showErrors(result.errors || {});
            }
        }
    }

    showErrors(errors) {
        // Clear existing error messages
        const existingErrors = this.form.querySelectorAll(".error-messages");
        existingErrors.forEach(el => el.remove());

        for (const [field, messages] of Object.entries(errors)) {
            const fieldElement = this.form.querySelector(`[name="${field}"]`);
            if (fieldElement) {
                const errorContainer = document.createElement("div");
                errorContainer.classList.add("error-messages");
                messages.forEach((message) => {
                    const errorMessage = document.createElement("p");
                    errorMessage.style.color = "red";
                    errorMessage.textContent = message;
                    errorContainer.appendChild(errorMessage);
                });
                fieldElement.parentElement.appendChild(errorContainer);
            }
        }
    }
}

const registerForm = document.querySelector(".register-form");
if (registerForm) {
    document.dispatchEvent(new CustomEvent('registerInjected', {
        detail: {
            form: registerForm,
            formHandler: new RegisterFormHandler(registerForm)
        }
    }));
}
