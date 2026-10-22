const statusText = document.querySelector("#api-status");
const statusIndicator = document.querySelector("#status-indicator");
const registrationForm = document.querySelector("#registration-form");
const loginForm = document.querySelector("#login-form");
const formMessage = document.querySelector("#form-message");
const registerButton = document.querySelector("#register-button");
const loginButton = document.querySelector("#login-button");
const showLoginButton = document.querySelector("#show-login");
const showRegisterButton = document.querySelector("#show-register");
const accountPanel = document.querySelector("#account-panel");
const accountDetails = document.querySelector("#account-details");
const logoutButton = document.querySelector("#logout-button");

function showMessage(message, success = false) {
  formMessage.textContent = message;
  formMessage.classList.toggle("is-success", success);
  formMessage.classList.toggle("is-error", !success);
}

function showSignedIn(user) {
  loginForm.hidden = true;
  registrationForm.hidden = true;
  document.querySelector(".auth-tabs").hidden = true;
  accountPanel.hidden = false;
  accountDetails.textContent = `${user.full_name} (${user.email})`;
  formMessage.textContent = "";
}

function showAuthForm(mode) {
  const login = mode === "login";
  loginForm.hidden = !login;
  registrationForm.hidden = login;
  accountPanel.hidden = true;
  document.querySelector(".auth-tabs").hidden = false;
  showLoginButton.setAttribute("aria-pressed", String(login));
  showRegisterButton.setAttribute("aria-pressed", String(!login));
  formMessage.textContent = "";
  formMessage.classList.remove("is-success", "is-error");
}

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

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(loginForm).entries());
  loginButton.disabled = true;
  loginButton.textContent = "Signing in…";
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      showMessage(result.message || "Login failed.");
      return;
    }
    showSignedIn(result.user);
  } catch (_error) {
    showMessage("Unable to contact the server. Please try again.");
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "Login";
  }
});

registrationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
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
    if (!response.ok) {
      showMessage(result.message || "Registration could not be completed.");
      return;
    }
    registrationForm.reset();
    showAuthForm("login");
    showMessage("Account created. Please log in.", true);
    document.querySelector("#login-email").value = payload.email;
  } catch (_error) {
    showMessage("Unable to contact the server. Please try again.");
  } finally {
    registerButton.disabled = false;
    registerButton.textContent = "Create account";
  }
});

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  try {
    const response = await fetch("/api/logout", {
      method: "POST",
      headers: { Accept: "application/json" },
    });
    const result = await response.json();
    if (!response.ok) {
      showMessage(result.message || "Logout failed.");
      return;
    }
    loginForm.reset();
    showAuthForm("login");
    showMessage("You have been logged out.", true);
  } catch (_error) {
    showMessage("Unable to contact the server. Please try again.");
  } finally {
    logoutButton.disabled = false;
  }
});

showLoginButton.addEventListener("click", () => showAuthForm("login"));
showRegisterButton.addEventListener("click", () => showAuthForm("register"));

async function restoreSession() {
  try {
    const response = await fetch("/api/session", { headers: { Accept: "application/json" } });
    if (response.ok) {
      const result = await response.json();
      if (result.authenticated) showSignedIn(result.user);
    }
  } catch (_error) {
    // The API status indicator reports connection failures separately.
  }
}

checkApiStatus();
restoreSession();
