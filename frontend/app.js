const statusText = document.querySelector("#api-status");
const statusIndicator = document.querySelector("#status-indicator");
const registrationForm = document.querySelector("#registration-form");
const formMessage = document.querySelector("#form-message");
const registerButton = document.querySelector("#register-button");

async function checkApiStatus() {
  try {
    const response = await fetch("/api/health", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("API unavailable");
    const result = await response.json();
    statusText.textContent = result.status === "ok" ? "Backend API is running" : "Backend API is unavailable";
    statusIndicator.classList.toggle("is-online", result.status === "ok");
    statusIndicator.classList.toggle("is-offline", result.status !== "ok");
  } catch (_error) {
    statusText.textContent = "Backend API is not reachable. Start the backend to connect.";
    statusIndicator.classList.remove("is-online");
    statusIndicator.classList.add("is-offline");
  }
}

registrationForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  formMessage.textContent = "";
  formMessage.classList.remove("is-success", "is-error");
  const payload = Object.fromEntries(new FormData(registrationForm).entries());
  registerButton.disabled = true;
  registerButton.textContent = "Creating account…";
  try {
    const response = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    formMessage.textContent = result.message || "Registration could not be completed.";
    formMessage.classList.add(response.ok ? "is-success" : "is-error");
    if (response.ok) registrationForm.reset();
  } catch (_error) {
    formMessage.textContent = "Unable to contact the server. Please try again.";
    formMessage.classList.add("is-error");
  } finally {
    registerButton.disabled = false;
    registerButton.textContent = "Create account";
  }
});

checkApiStatus();
