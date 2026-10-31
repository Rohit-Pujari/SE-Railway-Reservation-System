import React, { useEffect, useMemo, useState } from "react";
import AdminApp from "./admin.jsx";
import { createRoot } from "react-dom/client";
import "../styles.css";
import "./react.css";

const API = "/api";

function csrfCookie() {
  return document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith("csrftoken="))?.slice(10) || "";
}

async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { Accept: "application/json", ...options.headers };
  if (options.body && typeof options.body !== "string") {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) headers["X-CSRFToken"] = csrfCookie();
  const response = await fetch(`${API}${path}`, { ...options, method, headers, credentials: "same-origin" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || "The request could not be completed.");
  return data;
}

function messageText(error) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function App() {
  const [apiOnline, setApiOnline] = useState(false);
  const [loadingSearchData, setLoadingSearchData] = useState(true);
  const [searchDataError, setSearchDataError] = useState("");
  const [stations, setStations] = useState([]);
  const [classes, setClasses] = useState([]);
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState("register");
  const [authMessage, setAuthMessage] = useState("");
  const [authError, setAuthError] = useState(false);
  const [searchMessage, setSearchMessage] = useState("");
  const [searchError, setSearchError] = useState(false);
  const [sourceId, setSourceId] = useState("");
  const [destinationId, setDestinationId] = useState("");
  const [journeyDate, setJourneyDate] = useState(new Date().toLocaleDateString("en-CA"));
  const [classId, setClassId] = useState("");
  const [passengerCount, setPassengerCount] = useState(1);
  const [trains, setTrains] = useState([]);
  const [selectedTrain, setSelectedTrain] = useState(null);
  const [bookingMessage, setBookingMessage] = useState("");
  const [bookingError, setBookingError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [passengers, setPassengers] = useState([]);
  const [bookingKey, setBookingKey] = useState("");
  const [bookingConfirmation, setBookingConfirmation] = useState(null);

  async function initialize(isActive = () => true) {
    setLoadingSearchData(true);
    setSearchDataError("");
    try {
      await api("/csrf");
      const [healthResult, stationResult, classResult] = await Promise.allSettled([
        api("/health"), api("/stations"), api("/travel-classes"),
      ]);
      if (!isActive()) return;

      const health = healthResult.status === "fulfilled" && healthResult.value.status === "ok";
      setApiOnline(health);
      if (stationResult.status === "fulfilled") setStations(stationResult.value.stations || []);
      else setStations([]);
      if (classResult.status === "fulfilled") {
        const availableClasses = classResult.value.travel_classes || [];
        setClasses(availableClasses);
        if (availableClasses.length) setClassId(String(availableClasses[0].class_id));
      } else setClasses([]);

      const dataErrors = [stationResult, classResult]
        .filter((result) => result.status === "rejected")
        .map((result) => messageText(result.reason));
      if (dataErrors.length) {
        setSearchDataError(`Train search data could not be loaded. Check that MySQL is running and the database settings in .env are correct. ${dataErrors.join(" ")}`);
      } else if (!(stationResult.value.stations || []).length || !(classResult.value.travel_classes || []).length) {
        setSearchDataError("Train search needs at least one active station and one active travel class in the database.");
      } else if (!health) {
        setSearchDataError("The Django API health check failed. Restart the app with ./run-dev.sh and try again.");
      }

      const session = await api("/session").catch(() => null);
      if (isActive() && session?.authenticated) setUser(session.user);
    } catch (_error) {
      if (isActive()) {
        setApiOnline(false);
        setStations([]);
        setClasses([]);
        setSearchDataError("Could not reach the Django API. Check that ./run-dev.sh is running, then retry.");
      }
    } finally {
      if (isActive()) setLoadingSearchData(false);
    }
  }

  useEffect(() => {
    let active = true;
    initialize(() => active);
    return () => { active = false; };
  }, []);

  const selectedClass = useMemo(() => classes.find((item) => String(item.class_id) === classId), [classes, classId]);

  async function submitSearch(event) {
    event.preventDefault();
    setSearchMessage("");
    setTrains([]);
    setSelectedTrain(null);
    if (sourceId === destinationId) {
      setSearchError(true);
      setSearchMessage("Choose different source and destination stations.");
      return;
    }
    const params = new URLSearchParams({ source_station_id: sourceId, destination_station_id: destinationId, journey_date: journeyDate, class_id: classId });
    try {
      const result = await api(`/trains/search?${params}`);
      setTrains(result.trains || []);
      setSearchError(false);
      setSearchMessage(result.trains?.length ? `${result.trains.length} train${result.trains.length === 1 ? "" : "s"} found.` : "No scheduled trains match this route and date.");
    } catch (error) {
      setSearchError(true);
      setSearchMessage(messageText(error));
    }
  }

  function beginBooking(train) {
    if (!user) {
      setAuthMode("login");
      setAuthError(true);
      setAuthMessage("Log in before booking a ticket.");
      document.querySelector("#account")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    setSelectedTrain(train);
    setBookingKey(globalThis.crypto?.randomUUID?.() || "");
    setPassengers(Array.from({ length: passengerCount }, (_, index) => ({
      passenger_name: index === 0 ? user.full_name : "", age: "", gender: "", berth_preference: "NO_PREFERENCE",
    })));
    setBookingMessage("");
    setBookingError(false);
    setBookingConfirmation(null);
  }

  function changePassenger(index, field, value) {
    setPassengers((current) => current.map((passenger, i) => i === index ? { ...passenger, [field]: value } : passenger));
  }

  async function submitBooking(event) {
    event.preventDefault();
    if (!selectedTrain) return;
    setSubmitting(true);
    setBookingMessage("");
    try {
      if (!bookingKey) throw new Error("Secure booking requests are unavailable in this browser.");
      const result = await api("/bookings", { method: "POST", body: {
        schedule_id: selectedTrain.schedule_id,
        source_station_id: sourceId,
        destination_station_id: destinationId,
        journey_date: journeyDate,
        class_id: classId,
        passengers,
        idempotency_key: bookingKey,
      } });
      const assigned = (result.assigned_seats || []).map((seat) => `${seat.coach_number}-${seat.seat_number}`).join(", ");
      setBookingError(false);
      setBookingMessage("");
      setBookingConfirmation({ booking: result, train: selectedTrain, passengers: passengers.map((passenger) => ({ ...passenger })), journeyDate, className: selectedClass?.class_name || "Selected class", classCode: selectedClass?.class_code || "", passengerCount });
      setSelectedTrain(null);
      setBookingKey("");
      setTrains((current) => [...current]);
    } catch (error) {
      setBookingError(true);
      setBookingMessage(messageText(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitAuth(event) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthMessage("");
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      if (authMode === "register") {
        await api("/register", { method: "POST", body: values });
        setAuthMode("login");
        setAuthError(false);
        setAuthMessage("Account created. Please log in.");
      } else {
        const result = await api("/login", { method: "POST", body: values });
        setUser(result.user);
        setAuthError(false);
        setAuthMessage("You are signed in.");
      }
    } catch (error) {
      setAuthError(true);
      setAuthMessage(messageText(error));
    } finally {
      setAuthBusy(false);
    }
  }

  async function logout() {
    try {
      await api("/logout", { method: "POST" });
      setUser(null);
      setSelectedTrain(null);
      setAuthMode("login");
      setAuthError(false);
      setAuthMessage("You have been logged out.");
    } catch (error) {
      setAuthError(true);
      setAuthMessage(messageText(error));
    }
  }

  return <>
    <header className="site-header">
      <a className="brand" href="#top" aria-label="Trackline home"><span className="brand-mark" aria-hidden="true">🚆</span><span className="brand-name">trackline<span>RAILWAY RESERVATIONS</span></span></a>
      <nav className="top-nav" aria-label="Main navigation"><a href="/?admin=1">Admin</a><a href="#plan">Plan a journey</a>{user && <><a href="#booking-history">My bookings</a><a href="#booking-status">Check status</a></>}<a href="#account">{user ? "Your account" : "Create account"}</a><div className="service-status" role="status"><span className={`status-indicator ${apiOnline ? "is-online" : "is-offline"}`} /><span>{apiOnline ? "Backend API is running" : "Backend API is not reachable"}</span></div></nav>
    </header>
    <main id="top" className="page-shell">
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy"><p className="eyebrow"><span className="eyebrow-line" /> YOUR NEXT JOURNEY, MADE SIMPLE</p><h1 id="hero-title">There’s a better<br />way to <em>get there.</em></h1><p className="hero-intro">Find the right train for your plans. Pick your stations, choose a date, and explore the routes ahead.</p><a className="hero-link" href="#plan">Find your train <span aria-hidden="true">↓</span></a></div>
        <div className="hero-visual" aria-hidden="true"><div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" /><div className="visual-caption"><span className="caption-star">✳</span> Every great trip begins with a plan.</div></div><div className="hero-index" aria-hidden="true">01 <span /> EXPLORE</div>
      </section>
      {user && <><BookingHistory user={user} /><BookingStatusLookup /></>}
      <section id="plan" className="search-panel" aria-labelledby="search-title">
        <div className="section-heading"><div><p className="section-kicker">LET’S GET MOVING</p><h2 id="search-title">Where would you like to go?</h2></div><span className="step-label"><span>01</span> SEARCH TRAINS</span></div>
        <form className="search-form" onSubmit={submitSearch}>
          <div className="field-group"><label htmlFor="source-station">From</label><select id="source-station" required disabled={loadingSearchData} value={sourceId} onChange={(event) => setSourceId(event.target.value)}><option value="">{loadingSearchData ? "Loading stations…" : "Select a station"}</option>{stations.map((station) => <option key={station.station_id} value={station.station_id}>{station.station_name} ({station.station_code}) — {station.city}</option>)}</select></div>
          <div className="field-group"><label htmlFor="destination-station">To</label><select id="destination-station" required disabled={loadingSearchData} value={destinationId} onChange={(event) => setDestinationId(event.target.value)}><option value="">{loadingSearchData ? "Loading stations…" : "Select a station"}</option>{stations.map((station) => <option key={station.station_id} value={station.station_id}>{station.station_name} ({station.station_code}) — {station.city}</option>)}</select></div>
          <div className="field-group date-field"><label htmlFor="journey-date">Journey date</label><input id="journey-date" type="date" min={new Date().toLocaleDateString("en-CA")} value={journeyDate} onChange={(event) => setJourneyDate(event.target.value)} required /></div>
          <div className="field-group"><label htmlFor="travel-class">Travel class</label><select id="travel-class" value={classId} onChange={(event) => setClassId(event.target.value)} required disabled={loadingSearchData}><option value="">{loadingSearchData ? "Loading travel classes…" : "Select a travel class"}</option>{classes.map((item) => <option key={item.class_id} value={item.class_id}>{item.class_name} ({item.class_code})</option>)}</select></div>
          <div className="field-group"><label htmlFor="passenger-count">Passengers</label><select id="passenger-count" value={passengerCount} onChange={(event) => setPassengerCount(Number(event.target.value))}>{[1, 2, 3, 4, 5, 6].map((count) => <option key={count} value={count}>{count} passenger{count === 1 ? "" : "s"}</option>)}</select></div>
          <button type="submit" id="search-button" disabled={loadingSearchData || !apiOnline || !stations.length || !classes.length}><span>{loadingSearchData ? "Loading search options…" : "Search trains"}</span><span className="button-arrow" aria-hidden="true">↗</span></button>
        </form>
        {searchDataError && <p className="form-message is-error" role="alert">{searchDataError} <button type="button" className="retry-button" onClick={() => initialize()} disabled={loadingSearchData}>{loadingSearchData ? "Retrying…" : "Retry"}</button></p>}
        <p className={`form-message ${searchError ? "is-error" : ""}`} role="status">{searchMessage}</p>
        {trains.length > 0 && <section className="search-results" aria-labelledby="results-title"><div className="results-heading"><div><p className="section-kicker">YOUR OPTIONS</p><h2 id="results-title">Matching trains</h2></div><p className="results-summary">{trains.length} scheduled service{trains.length === 1 ? "" : "s"}</p></div>
          <div className="train-results-list">{trains.map((train) => <TrainCard key={train.schedule_id} train={train} classId={classId} selectedClass={selectedClass} sourceId={sourceId} destinationId={destinationId} journeyDate={journeyDate} passengerCount={passengerCount} onBook={beginBooking} />)}</div>
          {selectedTrain && <section className="booking-panel" aria-labelledby="booking-title"><div className="results-heading"><div><p className="section-kicker">COMPLETE YOUR JOURNEY</p><h2 id="booking-title">Traveler details</h2></div><span className="step-label">BOOK TICKET</span></div><p className="booking-summary">{selectedTrain.train_name} ({selectedTrain.train_number}) · {selectedTrain.source_station_name} to {selectedTrain.destination_station_name} · {passengerCount} passenger{passengerCount === 1 ? "" : "s"}</p>
            <form className="booking-form" onSubmit={submitBooking}><div className="booking-passenger-fields">{passengers.map((passenger, index) => <fieldset className="booking-passenger-entry" key={index}><legend>Passenger {index + 1}</legend><div className="field-group"><label htmlFor={`passenger-${index}-name`}>Full name</label><input id={`passenger-${index}-name`} maxLength="120" required value={passenger.passenger_name} onChange={(event) => changePassenger(index, "passenger_name", event.target.value)} /></div><div className="field-group"><label htmlFor={`passenger-${index}-age`}>Age</label><input id={`passenger-${index}-age`} type="number" min="0" max="120" required value={passenger.age} onChange={(event) => changePassenger(index, "age", event.target.value)} /></div><div className="field-group"><label htmlFor={`passenger-${index}-gender`}>Gender (optional)</label><input id={`passenger-${index}-gender`} maxLength="30" value={passenger.gender} onChange={(event) => changePassenger(index, "gender", event.target.value)} /></div><div className="field-group"><label htmlFor={`passenger-${index}-berth`}>Berth preference</label><select id={`passenger-${index}-berth`} value={passenger.berth_preference} onChange={(event) => changePassenger(index, "berth_preference", event.target.value)}>{[["NO_PREFERENCE", "No preference"], ["LOWER", "Lower"], ["MIDDLE", "Middle"], ["UPPER", "Upper"], ["SIDE_LOWER", "Side lower"], ["SIDE_UPPER", "Side upper"]].map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></div></fieldset>)}</div><button type="submit" className="account-submit" disabled={submitting}>{submitting ? "Checking seats…" : "Book and reserve seats"}</button></form>
          </section>}
          {bookingMessage && <p className={`form-message ${bookingError ? "is-error" : "is-success"}`} role="status">{bookingMessage}</p>}
          {bookingConfirmation && <TicketConfirmation confirmation={bookingConfirmation} />}
        </section>}
      </section>
      <section id="account" className="account-section" aria-labelledby="registration-title"><div className="account-copy"><p className="section-kicker">A LITTLE MORE CONVENIENT</p><h2>Make the next trip<br /><em>yours.</em></h2><p>Create an account to get started with railway reservations. Your details stay yours.</p><div className="account-note"><span className="note-mark" aria-hidden="true">✳</span><span><strong>One less thing to do at the station.</strong><br />Set up your account before your next journey.</span></div><div className="account-decoration" aria-hidden="true"><span /><span /><span /><span /><span /><span /><span /></div></div>
        <div className="account-form-wrap"><div className="form-title-row"><div><p className="section-kicker">GET STARTED</p><h2 id="registration-title">{user ? "Your account" : authMode === "login" ? "Welcome back" : "Create your account"}</h2></div><span className="form-step">02</span></div>
          {user ? <div className="account-panel"><p className="section-kicker">SIGNED IN</p><h3>Welcome, {user.full_name}</h3><p>{user.email}</p><button type="button" className="account-submit" onClick={logout}>Log out ↗</button></div> : <><div className="account-tabs" role="group" aria-label="Account actions"><button type="button" aria-pressed={authMode === "login"} onClick={() => { setAuthMode("login"); setAuthMessage(""); }}>Log in</button><button type="button" aria-pressed={authMode === "register"} onClick={() => { setAuthMode("register"); setAuthMessage(""); }}>Create account</button></div>
            <form className="registration-form" onSubmit={submitAuth} key={authMode}>
              {authMode === "register" && <div className="field-group"><label htmlFor="full-name">Full name</label><input id="full-name" name="full_name" autoComplete="name" maxLength="120" placeholder="e.g. Aditi Rao" required /></div>}
              <div className="field-group"><label htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete={authMode === "login" ? "username" : "email"} maxLength="254" placeholder="you@example.com" required /></div>
              {authMode === "register" && <div className="field-group"><label htmlFor="phone-number">Phone number <span className="optional">OPTIONAL</span></label><input id="phone-number" name="phone_number" type="tel" autoComplete="tel" maxLength="25" placeholder="Your phone number" /></div>}
              <div className="field-group"><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete={authMode === "login" ? "current-password" : "new-password"} minLength={authMode === "register" ? 8 : undefined} maxLength="128" placeholder={authMode === "login" ? "Your password" : "Create a strong password"} required /></div>
              {authMode === "register" && <p className="field-help">8–128 characters, with uppercase, lowercase, and a number.</p>}
              <button type="submit" className="account-submit" disabled={authBusy}>{authBusy ? "Please wait…" : authMode === "login" ? "Log in ↗" : "Create account ↗"}</button>
            </form></>}
          <p className={`form-message ${authError ? "is-error" : ""}`} role="status">{authMessage}</p><p className="privacy-note"><span aria-hidden="true">▣</span> Your password is securely protected.</p>
        </div>
      </section>
    </main>
    <footer className="site-footer"><a className="footer-brand" href="#top">trackline</a><span>Plan well. Travel happy.</span><a href="#plan">Back to top ↑</a></footer>
  </>;
}



function BookingHistory({ user }) {
  const [history, setHistory] = useState({ upcoming: [], previous: [], count: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("upcoming");
  const [cancelConfirmId, setCancelConfirmId] = useState(null);
  const [cancelingId, setCancelingId] = useState(null);
  const [cancelMessage, setCancelMessage] = useState("");
  const [cancelError, setCancelError] = useState(false);

  async function cancelTicket(booking) {
    setCancelingId(booking.booking_id);
    setCancelMessage("");
    setCancelError(false);
    try {
      const result = await api("/bookings/" + booking.booking_id + "/cancel", {
        method: "POST", body: { reason: "Cancelled by passenger" },
      });
      setCancelMessage(result.message || "Your booking has been cancelled.");
      setCancelConfirmId(null);
      await loadHistory();
    } catch (requestError) {
      setCancelError(true);
      setCancelMessage(messageText(requestError));
    } finally {
      setCancelingId(null);
    }
  }

  async function loadHistory() {
    setLoading(true);
    setError("");
    try {
      const result = await api("/bookings/history");
      setHistory({ upcoming: result.upcoming || [], previous: result.previous || [], count: result.count || 0 });
    } catch (requestError) {
      setError(messageText(requestError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    api("/bookings/history").then((result) => {
      if (active) setHistory({ upcoming: result.upcoming || [], previous: result.previous || [], count: result.count || 0 });
    }).catch((requestError) => {
      if (active) setError(messageText(requestError));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [user.user_id]);

  const bookings = history[activeTab] || [];
  const formatDate = (value) => value ? new Date(value).toLocaleString(undefined, {
    weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  }) : "Not available";

  return <section id="booking-history" className="booking-history" aria-labelledby="booking-history-title">
    <div className="section-heading">
      <div><p className="section-kicker">YOUR TRAVEL RECORD</p><h2 id="booking-history-title">My bookings</h2><p className="booking-history-intro">{history.count} booking{history.count === 1 ? "" : "s"} linked to your account</p></div>
      <button type="button" className="history-refresh" onClick={loadHistory} disabled={loading}>{loading ? "Loading…" : "Refresh ↻"}</button>
    </div>
    {cancelMessage && <p className={cancelError ? "form-message is-error" : "form-message is-success"} role="status">{cancelMessage}</p>}
    <div className="history-tabs" role="tablist" aria-label="Booking history">
      <button type="button" role="tab" aria-selected={activeTab === "upcoming"} className={activeTab === "upcoming" ? "is-active" : ""} onClick={() => setActiveTab("upcoming")}>Upcoming ({history.upcoming.length})</button>
      <button type="button" role="tab" aria-selected={activeTab === "previous"} className={activeTab === "previous" ? "is-active" : ""} onClick={() => setActiveTab("previous")}>Previous ({history.previous.length})</button>
    </div>
    {error && <p className="form-message is-error" role="alert">{error}</p>}
    {loading ? <p className="history-empty">Loading your bookings…</p> : bookings.length === 0 ? <div className="history-empty"><strong>No {activeTab} bookings yet.</strong><span>{activeTab === "upcoming" ? "Your next journey will appear here after you reserve a ticket." : "Completed journeys will appear here."}</span></div> :
      <div className="history-list">{bookings.map((booking) => <article className="history-card" key={booking.booking_id}>
        <div className="history-card-top"><div><span className="history-pnr-label">PNR</span><strong className="history-pnr">{booking.pnr}</strong></div><span className="history-status">{String(booking.booking_status).replaceAll("_", " ")}</span></div>
        <div className="history-train"><strong>{booking.train_name}</strong><span>Train {booking.train_number} · Class {booking.class_code}</span></div>
        <div className="history-route"><div><strong>{booking.source_station_name}</strong><span>{booking.source_station_code}</span></div><span className="history-route-arrow">→</span><div><strong>{booking.destination_station_name}</strong><span>{booking.destination_station_code}</span></div></div>
        <div className="history-meta"><div><span>Departure</span><strong>{formatDate(booking.departure_at)}</strong></div><div><span>Arrival</span><strong>{formatDate(booking.arrival_at)}</strong></div><div><span>Total fare</span><strong>{booking.currency_code} {Number(booking.total_fare).toFixed(2)}</strong></div></div>
        <div className="history-passengers"><strong>Passengers and seats</strong>{booking.passengers.map((passenger) => <span key={passenger.passenger_id}>{passenger.passenger_name} · {passenger.coach_number && passenger.seat_number ? `${passenger.coach_number} / ${passenger.seat_number}` : passenger.allocation_status || "Seat details unavailable"}</span>)}</div>
        {["PENDING_PAYMENT", "CONFIRMED", "PARTIALLY_CANCELLED"].includes(booking.booking_status) && booking.trip_type === "UPCOMING" && <div className="history-cancel-actions">
          {cancelConfirmId === booking.booking_id ? <><span>Cancel this entire booking and release its seats?</span><button type="button" className="cancel-confirm-button" onClick={() => cancelTicket(booking)} disabled={cancelingId === booking.booking_id}>{cancelingId === booking.booking_id ? "Cancelling…" : "Confirm cancellation"}</button><button type="button" className="cancel-dismiss-button" onClick={() => setCancelConfirmId(null)} disabled={cancelingId === booking.booking_id}>Keep booking</button></> : <button type="button" className="cancel-ticket-button" onClick={() => { setCancelMessage(""); setCancelConfirmId(booking.booking_id); }}>Cancel ticket</button>}
        </div>}
      </article>)}</div>}
  </section>;
}



function BookingStatusLookup() {
  const [pnr, setPnr] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function checkStatus(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api(`/bookings/status?pnr=${encodeURIComponent(pnr.trim())}`);
      setResult(data);
    } catch (requestError) {
      setError(messageText(requestError));
    } finally {
      setLoading(false);
    }
  }

  const booking = result?.booking;
  return <section id="booking-status" className="booking-status" aria-labelledby="booking-status-title">
    <div className="section-heading"><div><p className="section-kicker">TRACK YOUR RESERVATION</p><h2 id="booking-status-title">Check booking status</h2><p className="booking-history-intro">Enter the PNR from a booking in your account.</p></div></div>
    <form className="status-lookup-form" onSubmit={checkStatus}>
      <label htmlFor="status-pnr">PNR number</label>
      <div><input id="status-pnr" value={pnr} onChange={(event) => setPnr(event.target.value.toUpperCase())} maxLength="20" autoComplete="off" placeholder="Enter your PNR" required /><button type="submit" disabled={loading}>{loading ? "Checking…" : "Check status ↗"}</button></div>
    </form>
    {error && <p className="form-message is-error" role="alert">{error}</p>}
    {booking && <article className="status-result" aria-live="polite">
      <div className="history-card-top"><div><span className="history-pnr-label">PNR</span><strong className="history-pnr">{booking.pnr}</strong></div><span className="history-status">{booking.booking_status.replaceAll("_", " ")}</span></div>
      <div className="history-train"><strong>{booking.train_name_snapshot}</strong><span>Train {booking.train_number_snapshot} · Class {booking.class_code_snapshot}</span></div>
      <div className="history-route"><div><strong>{booking.boarding_station_name_snapshot}</strong><span>{booking.boarding_station_code_snapshot}</span></div><span className="history-route-arrow">→</span><div><strong>{booking.alighting_station_name_snapshot}</strong><span>{booking.alighting_station_code_snapshot}</span></div></div>
      <div className="status-lifecycle">
        <div><span>Booking status</span><strong>{booking.booking_status.replaceAll("_", " ")}</strong></div>
        <div><span>Payment status</span><strong>{result.payment_status.replaceAll("_", " ")}</strong></div>
        <div><span>Total fare</span><strong>{booking.currency_code} {Number(booking.total_fare).toFixed(2)}</strong></div>
      </div>
      {result.payments.length > 0 && <div className="status-section"><h3>Payment details</h3>{result.payments.map((payment, index) => <p key={index}><strong>{payment.payment_status.replaceAll("_", " ")}</strong> · {payment.payment_method} · {payment.currency_code} {Number(payment.amount).toFixed(2)}{payment.failure_code ? ` · ${payment.failure_code}` : ""}</p>)}</div>}
      {result.cancellations.length > 0 && <div className="status-section"><h3>Cancellation and refund</h3>{result.cancellations.map((item, index) => <p key={index}><strong>Cancellation: {item.cancellation_status.replaceAll("_", " ")}</strong>{item.item_status ? ` · Passenger item: ${item.item_status}` : ""}{item.refund_status ? ` · Refund: ${item.refund_status}` : " · Refund not recorded"}{item.refund_amount != null ? ` · Refund due: ${booking.currency_code} ${Number(item.refund_amount).toFixed(2)}` : ""}{item.refunded_amount != null ? ` · Refunded: ${item.refund_currency} ${Number(item.refunded_amount).toFixed(2)}` : ""}</p>)}</div>}
    </article>}
  </section>;
}

function TicketConfirmation({ confirmation }) {
  const { booking, train, passengers, journeyDate, className, classCode, passengerCount } = confirmation;
  const currency = booking.currency_code || train.currency_code || "INR";
  const farePerPassenger = Number(booking.fare_per_passenger ?? train.starting_fare ?? 0);
  const totalFare = Number(booking.total_fare ?? farePerPassenger * passengerCount);
  const journeyLabel = new Date(`${journeyDate}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });
  const seats = booking.assigned_seats || [];

  return <section className="ticket-confirmation" aria-labelledby="confirmation-title" aria-live="polite">
    <div className="confirmation-heading">
      <div><p className="section-kicker">BOOKING SUCCESSFUL</p><h2 id="confirmation-title">Your ticket details</h2></div>
      <span className="confirmation-status">{String(booking.status || "PENDING_PAYMENT").replaceAll("_", " ")}</span>
    </div>
    <div className="confirmation-pnr"><span>YOUR PNR</span><strong>{booking.pnr}</strong><small>Keep this number for your journey.</small></div>
    <div className="confirmation-grid">
      <div><span>Train</span><strong>{train.train_name} ({train.train_number})</strong></div>
      <div><span>Journey date</span><strong>{journeyLabel}</strong></div>
      <div><span>From</span><strong>{train.source_station_name} ({train.source_station_code})</strong></div>
      <div><span>To</span><strong>{train.destination_station_name} ({train.destination_station_code})</strong></div>
      <div><span>Departure</span><strong>{train.departure_at}</strong></div>
      <div><span>Arrival</span><strong>{train.arrival_at}</strong></div>
      <div><span>Travel class</span><strong>{className}{classCode ? ` (${classCode})` : ""}</strong></div>
      <div><span>Passengers</span><strong>{passengerCount}</strong></div>
    </div>
    <div className="confirmation-passengers">
      <h3>Passenger and seat details</h3>
      {passengers.map((passenger, index) => <div className="confirmation-passenger" key={index}>
        <span><strong>{index + 1}. {passenger.passenger_name}</strong><small>Age {passenger.age}{passenger.gender ? ` · ${passenger.gender}` : ""}</small></span>
        <strong>{seats[index] ? `${seats[index].coach_number} · Seat ${seats[index].seat_number}` : "Seat assigned"}</strong>
      </div>)}
    </div>
    <div className="confirmation-fare">
      <div><span>Fare per passenger</span><strong>{currency} {farePerPassenger.toFixed(2)}</strong></div>
      <div><span>Total fare</span><strong>{currency} {totalFare.toFixed(2)}</strong></div>
    </div>
    {booking.hold_expires_at && <p className="confirmation-note">Seat hold expires: {new Date(booking.hold_expires_at).toLocaleString()}. Complete payment before expiry to retain these seats.</p>}
    <p className="confirmation-note">Booking status: {String(booking.status || "PENDING_PAYMENT").replaceAll("_", " ")}. Your seats are reserved; payment is not yet confirmed.</p>
  </section>;
}

function TrainCard({ train, classId, selectedClass, sourceId, destinationId, journeyDate, passengerCount, onBook }) {
  const [availability, setAvailability] = useState("Checking…");
  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({ schedule_id: train.schedule_id, source_station_id: sourceId, destination_station_id: destinationId, journey_date: journeyDate, class_id: classId });
    api(`/seats/availability?${params}`).then((data) => {
      if (active) setAvailability(`${data.available_seats} seat${Number(data.available_seats) === 1 ? "" : "s"} · ${data.class_code || selectedClass?.class_code || "class"}`);
    }).catch(() => { if (active) setAvailability("Availability unavailable"); });
    return () => { active = false; };
  }, [train.schedule_id, classId, sourceId, destinationId, journeyDate, selectedClass?.class_code]);
  const total = Number(train.starting_fare || 0) * passengerCount;
  return <article className="train-result"><div className="train-result-heading"><h3>{train.train_name}</h3><span className="train-number">{train.train_number}</span></div><div className="train-route"><div><strong>{train.source_station_name}</strong><span>{train.source_station_code} · {train.departure_at}</span></div><span className="route-arrow" aria-hidden="true">→</span><div><strong>{train.destination_station_name}</strong><span>{train.destination_station_code} · {train.arrival_at}</span></div></div><div className="train-result-details"><div className="train-result-detail"><span>Fare per passenger · {selectedClass?.class_name || "selected class"}</span><strong>{train.currency_code || "INR"} {Number(train.starting_fare || 0).toFixed(2)}</strong></div><div className="train-result-detail"><span>Estimated total · {passengerCount} passenger{passengerCount === 1 ? "" : "s"}</span><strong>{train.currency_code || "INR"} {total.toFixed(2)}</strong></div><div className="train-result-detail"><span>Seats available</span><strong>{availability}</strong></div></div><button className="book-train-button" type="button" onClick={() => onBook(train)}>Book ticket</button></article>;
}

const RootApp = new URLSearchParams(window.location.search).get("admin") === "1" ? AdminApp : App;
createRoot(document.getElementById("root")).render(<React.StrictMode><RootApp /></React.StrictMode>);
