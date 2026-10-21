const statusText = document.querySelector("#api-status");
const statusIndicator = document.querySelector("#status-indicator");

async function checkApiStatus() {
  try {
    const response = await fetch("http://127.0.0.1:5000/api/health", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error("API returned an unsuccessful response");
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

checkApiStatus();
