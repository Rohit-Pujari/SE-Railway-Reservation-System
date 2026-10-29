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
const travelClass = document.querySelector("#travel-class");
const passengerCount = document.querySelector("#passenger-count");
let currentTrainResults = [];
let stationsLoaded = false;
let classesLoaded = false;
let signedInPassenger = null;
let activeBooking = null;
const bookingRequestKeys = new Map();
const bookingPanel = document.querySelector("#booking-panel");
const bookingSummary = document.querySelector("#booking-summary");
const bookingForm = document.querySelector("#booking-form");
const bookingPassengerFields = document.querySelector("#booking-passenger-fields");
const bookingMessage = document.querySelector("#booking-message");
const bookingSubmitButton = document.querySelector("#booking-submit-button");

function updateSearchButton() {
  searchButton.disabled = !(stationsLoaded && classesLoaded);
}
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
  signedInPassenger = user;
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

async function loadTravelClasses() {
  try {
    const response = await fetch("/api/travel-classes", { headers: { Accept: "application/json" } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "Could not load travel classes.");
    travelClass.replaceChildren(new Option("Select a travel class", ""));
    for (const item of result.travel_classes) {
      travelClass.add(new Option(`${item.class_name} (${item.class_code})`, String(item.class_id)));
    }
    classesLoaded = result.travel_classes.length > 0;
    travelClass.disabled = !classesLoaded;
    updateSearchButton();
    if (!classesLoaded) setMessage(searchMessage, "No active travel classes are available yet.", true);
  } catch (error) {
    travelClass.replaceChildren(new Option("Travel classes unavailable", ""));
    travelClass.disabled = true;
    classesLoaded = false;
    updateSearchButton();
    setMessage(searchMessage, error.message || "Unable to load travel classes. Please retry later.", true);
  }
}

async function loadStations() {
  try {
    const response = await fetch("/api/stations", { headers: { Accept: "application/json" } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "Could not load stations.");
    addStationOptions(sourceStation, result.stations);
    addStationOptions(destinationStation, result.stations);
    stationsLoaded = result.stations.length > 0;
    updateSearchButton();
    if (result.stations.length === 0) {
      setMessage(searchMessage, "No active stations are available yet.", true);
    } else {
      setMessage(searchMessage, "");
    }
  } catch (error) {
    addStationOptions(sourceStation, []);
    addStationOptions(destinationStation, []);
    stationsLoaded = false;
    updateSearchButton();
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
  currentTrainResults = trains;
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
    const selectedClassLabel = travelClass.selectedOptions[0]?.textContent || "selected class";
    fareLabel.textContent = `Fare per passenger · ${selectedClassLabel}`;
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

    const totalFare = document.createElement("div");
    totalFare.className = "train-result-detail";
    const totalFareLabel = document.createElement("span");
    totalFareLabel.textContent = `Estimated total · ${passengerCount.value} passenger${Number(passengerCount.value) === 1 ? "" : "s"}`;
    const totalFareValue = document.createElement("strong");
    if (train.starting_fare === null || train.starting_fare === undefined) {
      totalFareValue.textContent = "Total unavailable";
    } else {
      const estimatedTotal = Number(train.starting_fare) * Number(passengerCount.value);
      const currency = train.currency_code || "INR";
      try {
        totalFareValue.textContent = new Intl.NumberFormat(undefined, {
          style: "currency",
          currency,
          maximumFractionDigits: 2,
        }).format(estimatedTotal);
      } catch (_error) {
        totalFareValue.textContent = `${currency} ${estimatedTotal.toFixed(2)}`;
      }
    }
    totalFare.append(totalFareLabel, totalFareValue);

    const seats = document.createElement("div");
    seats.className = "train-result-detail";
    const seatsLabel = document.createElement("span");
    seatsLabel.textContent = "Seats available";
    const seatsValue = document.createElement("strong");
    seatsValue.textContent = "Checking…";
    seats.append(seatsLabel, seatsValue);
    const availabilityParams = new URLSearchParams({
      schedule_id: String(train.schedule_id),
      source_station_id: sourceStation.value,
      destination_station_id: destinationStation.value,
      journey_date: journeyDate.value,
      class_id: travelClass.value,
    });
    fetch(`/api/seats/availability?${availabilityParams.toString()}`, {
      headers: { Accept: "application/json" },
    }).then(async (response) => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.message || "Availability unavailable");
      const count = Number(result.available_seats);
      seatsValue.textContent = Number.isFinite(count)
        ? `${count} ${count === 1 ? "seat" : "seats"} · ${result.class_code || travelClass.selectedOptions[0].textContent}`
        : "Availability unavailable";
    }).catch(() => {
      seatsValue.textContent = "Availability unavailable";
    });

    details.append(fare, totalFare, seats);
    const bookButton = document.createElement("button");
    bookButton.type = "button";
    bookButton.className = "book-train-button";
    bookButton.textContent = "Book ticket";
    bookButton.addEventListener("click", () => startBooking(train));
    card.append(heading, route, details, bookButton);
    trainResultsList.append(card);
  }
}

function createBookingRequestKey(train) {
  const key = `${train.schedule_id}:${sourceStation.value}:${destinationStation.value}:${journeyDate.value}:${travelClass.value}:${passengerCount.value}`;
  if (!bookingRequestKeys.has(key)) {
    if (!globalThis.crypto?.getRandomValues) throw new Error("Secure booking requests are unavailable in this browser.");
    const token = globalThis.crypto.randomUUID?.()
      || Array.from(globalThis.crypto.getRandomValues(new Uint8Array(16)), (value) => value.toString(16).padStart(2, "0")).join("");
    bookingRequestKeys.set(key, token);
  }
  return key;
}

function formatCurrency(amount, currency) {
  const code = currency || "INR";
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: code }).format(amount);
  } catch (_error) {
    return `${code} ${Number(amount).toFixed(2)}`;
  }
}

function appendBookingField(container, labelText, control) {
  const wrapper = document.createElement("div");
  wrapper.className = "field-group";
  const label = document.createElement("label");
  label.textContent = labelText;
  label.htmlFor = control.id;
  wrapper.append(label, control);
  container.append(wrapper);
}

function showBookingForm(train) {
  const requestKey = createBookingRequestKey(train);
  activeBooking = {
    requestKey,
    idempotencyKey: bookingRequestKeys.get(requestKey),
    train,
    sourceStationId: sourceStation.value,
    destinationStationId: destinationStation.value,
    journeyDate: journeyDate.value,
    classId: travelClass.value,
    passengerCount: Number(passengerCount.value),
  };
  bookingSummary.textContent = `${train.train_name} (${train.train_number}) · ${train.source_station_name} to ${train.destination_station_name} · ${activeBooking.passengerCount} passenger${activeBooking.passengerCount === 1 ? "" : "s"}. Seats will be rechecked and reserved when you submit.`;
  bookingPassengerFields.replaceChildren();

  for (let index = 0; index < activeBooking.passengerCount; index += 1) {
    const section = document.createElement("fieldset");
    section.className = "booking-passenger-entry";
    const legend = document.createElement("legend");
    legend.textContent = `Passenger ${index + 1}`;
    section.append(legend);

    const name = document.createElement("input");
    name.id = `booking-passenger-${index}-name`;
    name.name = "passenger_name";
    name.autocomplete = index === 0 ? "name" : "off";
    name.maxLength = 120;
    name.required = true;
    if (index === 0 && signedInPassenger?.full_name) name.value = signedInPassenger.full_name;
    appendBookingField(section, "Full name", name);

    const age = document.createElement("input");
    age.id = `booking-passenger-${index}-age`;
    age.name = "age";
    age.type = "number";
    age.min = "0";
    age.max = "120";
    age.step = "1";
    age.required = true;
    appendBookingField(section, "Age", age);

    const gender = document.createElement("input");
    gender.id = `booking-passenger-${index}-gender`;
    gender.name = "gender";
    gender.maxLength = 30;
    gender.placeholder = "Optional";
    appendBookingField(section, "Gender (optional)", gender);

    const berth = document.createElement("select");
    berth.id = `booking-passenger-${index}-berth`;
    berth.name = "berth_preference";
    for (const [value, labelText] of [
      ["NO_PREFERENCE", "No preference"], ["LOWER", "Lower"], ["MIDDLE", "Middle"],
      ["UPPER", "Upper"], ["SIDE_LOWER", "Side lower"], ["SIDE_UPPER", "Side upper"],
    ]) berth.add(new Option(labelText, value));
    appendBookingField(section, "Berth preference", berth);
    bookingPassengerFields.append(section);
  }

  bookingForm.hidden = false;
  bookingPanel.hidden = false;
  setMessage(bookingMessage, "Enter traveler details. Availability, fare, booking, and seat reservation are handled together when submitted.");
  bookingPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function startBooking(train) {
  if (activeBooking) {
    bookingPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    setMessage(bookingMessage, "Finish or retry the booking already in progress.", true);
    return;
  }
  if (!signedInPassenger) {
    setMessage(searchMessage, "Log in before booking a ticket.", true);
    showAuthForm("login");
    document.querySelector("#account").scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  try {
    showBookingForm(train);
    setMessage(searchMessage, "");
  } catch (error) {
    setMessage(searchMessage, error.message || "Could not start this booking.", true);
  }
}

bookingForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!activeBooking) return;
  bookingSubmitButton.disabled = true;
  bookingSubmitButton.textContent = "Checking seats…";
  setMessage(bookingMessage, "");

  try {
    const passengers = Array.from(bookingPassengerFields.querySelectorAll(".booking-passenger-entry"), (entry) => ({
      passenger_name: entry.querySelector('[name="passenger_name"]').value,
      age: entry.querySelector('[name="age"]').value,
      gender: entry.querySelector('[name="gender"]').value,
      berth_preference: entry.querySelector('[name="berth_preference"]').value,
    }));
    const response = await fetch("/api/bookings", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        schedule_id: activeBooking.train.schedule_id,
        source_station_id: activeBooking.sourceStationId,
        destination_station_id: activeBooking.destinationStationId,
        journey_date: activeBooking.journeyDate,
        class_id: activeBooking.classId,
        passengers,
        idempotency_key: activeBooking.idempotencyKey,
      }),
    });
    const booking = await response.json();
    if (!response.ok) throw new Error(booking.message || "Booking could not be completed.");

    const assignedSeats = (booking.assigned_seats || [])
      .map((seat) => `${seat.coach_number}-${seat.seat_number}`)
      .join(", ");
    const expiry = booking.hold_expires_at
      ? new Date(booking.hold_expires_at.replace(" ", "T")).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "soon";
    bookingForm.hidden = true;
    setMessage(
      bookingMessage,
      `Seats reserved pending payment. PNR ${booking.pnr} · ${assignedSeats} · ${formatCurrency(booking.total_fare, booking.currency_code)} total. Seat hold expires at ${expiry}.`,
    );
    bookingRequestKeys.delete(activeBooking.requestKey);
    activeBooking = null;
    renderTrainResults(currentTrainResults);
  } catch (error) {
    setMessage(bookingMessage, error.message || "Booking could not be completed. Please try again.", true);
  } finally {
    bookingSubmitButton.disabled = false;
    bookingSubmitButton.textContent = "Book and reserve seats";
  }
});

passengerCount?.addEventListener("change", () => {
  if (currentTrainResults.length) renderTrainResults(currentTrainResults);
});

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
  if (!travelClass.value) {
    setMessage(searchMessage, "Choose a travel class.", true);
    travelClass.focus();
    return;
  }

  const params = new URLSearchParams({
    source_station_id: sourceStation.value,
    destination_station_id: destinationStation.value,
    journey_date: journeyDate.value,
    class_id: travelClass.value,
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
    signedInPassenger = null;
    activeBooking = null;
    bookingPanel.hidden = true;
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
loadTravelClasses();
checkApiStatus();
restoreSession();
