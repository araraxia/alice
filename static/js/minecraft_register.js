// Re-executed every time the registration window is injected, so avoid top-level declarations.
(() => {
    function initMinecraftRegisterForm(form) {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const submitButton = form.querySelector('[type="submit"]');
            if (submitButton) submitButton.disabled = true;
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                });
                handleResponse(form, await response.json());
            } catch (error) {
                console.error("Minecraft registration failed:", error);
                showStatus(form, "Something went wrong. Please try again later.");
            } finally {
                if (submitButton && !form.dataset.done) submitButton.disabled = false;
            }
        });
    }

    function handleResponse(form, result) {
        if (result.html) {
            // Validation errors - swap in the re-rendered form
            const tempDiv = document.createElement("div");
            tempDiv.innerHTML = result.html;
            const newForm = tempDiv.querySelector(".mc-register-form");
            if (newForm) {
                form.parentNode.replaceChild(newForm, form);
                initMinecraftRegisterForm(newForm);
                return;
            }
        }
        if (result.status === "success" || result.status === "pending") {
            form.dataset.done = "1";
            form.querySelectorAll("input:not([type=hidden]), textarea, [type=submit]")
                .forEach((el) => (el.disabled = true));
        }
        showStatus(form, result.message || "Registration failed. Please try again later.");
    }

    function showStatus(form, message) {
        const status = form.querySelector(".mc-reg-status");
        if (status) {
            status.textContent = message;
            status.hidden = false;
        } else {
            alert(message);
        }
    }

    const form = document.querySelector("#minecraft-register-container .mc-register-form");
    if (form) initMinecraftRegisterForm(form);
})();
