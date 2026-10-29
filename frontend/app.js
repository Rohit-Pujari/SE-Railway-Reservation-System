const statusText = document.querySelector("#api-status");
const statusIndicator = document.querySelector("#status-indicator");
const registrationForm = document.querySelector("#registration-form");
const loginForm = document.querySelector("#login-form");
const formMessage = document.querySelector("#form-message");
const registerButton = document.querySelector("#register-button");
const loginButton = document.querySelector("#login-button");
const logoutButton = document.querySelector("#logout-button");
const accountTabs = document.querySelector("#account-tabs");
const showLoginButton = document.querySelector("#show-login");
const showRegisterButton = document.querySelector("#show-register");
const accountPanel = document.querySelector("#account-panel");
const accountDetails = document.querySelector("#account-details");

const trainSearchForm = document.querySelector("#train-search-form");
const sourceStation = document.querySelector("#source-station");
const destinationStation = document.querySelector("#destination-station");
const journeyDate = document.querySelector("#journey-date");
const searchButton = document.querySelector("#search-button");
const searchMessage = document.querySelector("#search-message");
const searchResults = document.querySelector("#search-results");
const resultsSummary = document.querySelector("#results-summary");
const trainResultsList = document.querySelector("#train-results-list");

function setMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("is-error", isError);
  element.classList.toggle("is-success", !isError && Boolean(message));
}

function showAuthForm(mode) {
  const isLogin = mode === "login";
  registrationForm.hidden = isLogin;
  loginForm.hidden = !isLogin;
  accountPanel.hidden = true;
  accountTabs.hidden = false;
  showLoginButton.setAttribute("aria-pressed", String(isLogin));
  showRegisterButton.setAttribute("aria-pressed", String(!isLogin));
  document.querySelector("#registration-title").textContent = isLogin ? "Welcome back" : "Create your account";
  setMessage(formMessage, "");
}

function showSignedIn(user) {
  registrationForm.hidden = true;
  loginForm.hidden = true;
  accountTabs.hidden = true;
  accountPanel.hidden = false;
  accountDetails.textContent = `${user.full_name} · ${user.email}`;
  document.querySelector("#registration-title").textContent = "Your account";
  setMessage(formMessage, "");
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

function addStationOptions(select, stations) {
  select.replaceChildren(new Option("Select a station", ""));
  for (const station of stations) {
    const label = `${station.station_name} (${station.station_code}) — ${station.city}`;
    select.add(new Option(label, String(station.station_id)));
  }
  select.disabled = stations.length === 0;
}

async function loadStations() {
  try {
    const response = await fetch("/api/stations", { headers: { Accept: "application/json" } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "Could not load stations.");
    addStationOptions(sourceStation, result.stations);
    addStationOptions(destinationStation, result.stations);
    searchButton.disabled = result.stations.length === 0;
    if (result.stations.length === 0) {
      setMessage(searchMessage, "No active stations are available yet.", true);
    } else {
      setMessage(searchMessage, "");
    }
  } catch (error) {
    addStationOptions(sourceStation, []);
    addStationOptions(destinationStation, []);
    setMessage(searchMessage, error.message || "Unable to load stations. Please retry later.", true);
  }
}

function formatTime(value) {
  if (!value) return "Time unavailable";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value.replace("T", " ");
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    day: "numeric",
    month: "short",
  }).format(parsed);
}

function renderTrainResults(trains) {
  trainResultsList.replaceChildren();
  if (trains.length === 0) {
    resultsSummary.textContent = "No scheduled trains match this route and date.";
    return;
  }
  resultsSummary.textContent = `${trains.length} train${trains.length === 1 ? "" : "s"} found.`;
  for (const train of trains) {
    const card = document.createElement("article");
    card.className = "train-result";

    const heading = document.createElement("div");
    heading.className = "train-result-heading";
    const name = document.createElement("h3");
    name.textContent = train.train_name;
    const number = document.createElement("span");
    number.className = "train-number";
    number.textContent = train.train_number;
    heading.append(name, number);

    const route = document.createElement("div");
    route.className = "train-route";
    const origin = document.createElement("div");
    const originName = document.createElement("strong");
    originName.textContent = train.source_station_name;
    const originMeta = document.createElement("span");
    originMeta.textContent = `${train.source_station_code} · ${formatTime(train.departure_at)}`;
    origin.append(originName, originMeta);

    const arrow = document.createElement("span");
    arrow.className = "route-arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "→";

    const destination = document.createElement("div");
    const destinationName = document.createElement("strong");
    destinationName.textContent = train.destination_station_name;
    const destinationMeta = document.createElement("span");
    destinationMeta.textContent = `${train.destination_station_code} · ${formatTime(train.arrival_at)}`;
    destination.append(destinationName, destinationMeta);
    route.append(origin, arrow, destination);

    const details = document.createElement("div");
    details.className = "train-result-details";

    const fare = document.createElement("div");
    fare.className = "train-result-detail";
    const fareLabel = document.createElement("span");
    fareLabel.textContent = "Starting fare";
    const fareValue = document.createElement("strong");
    if (train.starting_fare === null || train.starting_fare === undefined) {
      fareValue.textContent = "Fare unavailable";
    } else {
      const currency = train.currency_code || "INR";
      try {
        fareValue.textContent = new Intl.NumberFormat(undefined, {
          style: "currency",
          currency,
          maximumFractionDigits: 2,
        }).format(train.starting_fare);
      } catch (_error) {
        fareValue.textContent = `${currency} ${Number(train.starting_fare).toFixed(2)}`;
      }
    }
    fare.append(fareLabel, fareValue);

    const seats = document.createElement("div");
    seats.className = "train-result-detail";
    const seatsLabel = document.createElement("span");
    seatsLabel.textContent = "Seats available";
    const seatsValue = document.createElement("strong");
    const availableSeats = Number(train.available_seats);
    seatsValue.textContent = Number.isFinite(availableSeats)
      ? `${availableSeats} ${availableSeats === 1 ? "seat" : "seats"}`
      : "Availability unavailable";
    seats.append(seatsLabel, seatsValue);

    details.append(fare, seats);
    card.append(heading, route, details);
    trainResultsList.append(card);
  }
}

trainSearchForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(searchMessage, "");
  searchResults.hidden = true;

  if (sourceStation.value === destinationStation.value) {
    setMessage(searchMessage, "Choose different source and destination stations.", true);
    return;
  }
  if (!journeyDate.value) {
    setMessage(searchMessage, "Choose a journey date.", true);
    journeyDate.focus();
    return;
  }

  const params = new URLSearchParams({
    source_station_id: sourceStation.value,
    destination_station_id: destinationStation.value,
    journey_date: journeyDate.value,
  });
  searchButton.disabled = true;
  searchButton.textContent = "Searching…";
  try {
    const response = await fetch(`/api/trains/search?${params.toString()}`, {
      headers: { Accept: "application/json" },
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "Train search failed.");
    renderTrainResults(result.trains);
    searchResults.hidden = false;
  } catch (error) {
    setMessage(searchMessage, error.message || "Unable to search trains. Please try again.", true);
  } finally {
    searchButton.disabled = false;
    searchButton.textContent = "Search trains";
  }
});

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
    setMessage(formMessage, result.message || "Registration could not be completed.", !response.ok);
    if (response.ok) {
      const registeredEmail = payload.email;
      registrationForm.reset();
      showAuthForm("login");
      document.querySelector("#login-email").value = registeredEmail;
      setMessage(formMessage, "Account created. Please log in.");
    }
  } catch (_error) {
    setMessage(formMessage, "Unable to contact the server. Please try again.", true);
  } finally {
    registerButton.disabled = false;
    registerButton.textContent = "Create account";
  }
});

loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(formMessage, "");
  const payload = Object.fromEntries(new FormData(loginForm).entries());
  loginButton.disabled = true;
  loginButton.querySelector("span").textContent = "Signing in…";
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      setMessage(formMessage, result.message || "Login failed.", true);
      return;
    }
    showSignedIn(result.user);
  } catch (_error) {
    setMessage(formMessage, "Unable to contact the server. Please try again.", true);
  } finally {
    loginButton.disabled = false;
    loginButton.querySelector("span").textContent = "Log in";
  }
});

logoutButton?.addEventListener("click", async () => {
  logoutButton.disabled = true;
  try {
    const response = await fetch("/api/logout", {
      method: "POST",
      headers: { Accept: "application/json" },
    });
    const result = await response.json();
    if (!response.ok) {
      setMessage(formMessage, result.message || "Logout failed.", true);
      return;
    }
    loginForm.reset();
    showAuthForm("login");
    setMessage(formMessage, "You have been logged out.");
  } catch (_error) {
    setMessage(formMessage, "Unable to contact the server. Please try again.", true);
  } finally {
    logoutButton.disabled = false;
  }
});

showLoginButton?.addEventListener("click", () => showAuthForm("login"));
showRegisterButton?.addEventListener("click", () => showAuthForm("register"));

async function restoreSession() {
  try {
    const response = await fetch("/api/session", { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    const result = await response.json();
    if (result.authenticated) showSignedIn(result.user);
  } catch (_error) {
    // The API status indicator reports connection failures separately.
  }
}

function formatLocalDate(value) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

const today = new Date();
journeyDate.min = formatLocalDate(today);
journeyDate.value = formatLocalDate(today);
loadStations();
checkApiStatus();
restoreSession();
