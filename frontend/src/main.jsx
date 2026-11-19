import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";
import "./react.css";

const API = "/api";

function csrfCookie() {
  return document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith("csrftoken="))?.slice(10) || "";
}

async function refreshCsrfToken() {
  const response = await fetch(`${API}/csrf`, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error("Could not prepare a secure request. Refresh the page and try again.");
  const data = await response.json().catch(() => ({}));
  const token = csrfCookie() || data.csrfToken || "";
  if (!token) throw new Error("The browser did not accept the security cookie. Enable cookies and refresh the page.");
  return token;
}

async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { Accept: "application/json", ...options.headers };
  if (options.body && typeof options.body !== "string") {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const needsCsrf = !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method);
  if (needsCsrf) headers["X-CSRFToken"] = csrfCookie() || await refreshCsrfToken();
  const requestOptions = { ...options, method, headers, credentials: "same-origin" };
  let response = await fetch(`${API}${path}`, requestOptions);
  if (needsCsrf && response.status === 403 && response.headers.get("content-type")?.includes("text/html")) {
    headers["X-CSRFToken"] = await refreshCsrfToken();
    response = await fetch(`${API}${path}`, requestOptions);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || "The request could not be completed.");
  return data;
}

function messageText(error) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function currentPage() {
  const page = window.location.hash.replace(/^#\/?/, "").split("/")[0];
  return ["search", "account", "booking", "payment", "tickets", "admin"].includes(page) ? page : "search";
}

function App() {
  const [page, setPage] = useState(currentPage);
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
  const [paymentBooking, setPaymentBooking] = useState(null);
  const [paymentMessage, setPaymentMessage] = useState("");
  const [paymentError, setPaymentError] = useState(false);
  const [paymentBusy, setPaymentBusy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [passengers, setPassengers] = useState([]);
  const [bookingKey, setBookingKey] = useState("");
  const [pendingTrain, setPendingTrain] = useState(null);
  const [tickets, setTickets] = useState(null);
  const [ticketsMessage, setTicketsMessage] = useState("");
  const [admin, setAdmin] = useState(null);
  const [adminMessage, setAdminMessage] = useState("");
  const [adminBusy, setAdminBusy] = useState(false);
  const [pendingPayments, setPendingPayments] = useState([]);

  function navigate(nextPage) {
    if (currentPage() === nextPage) {
      setPage(nextPage);
      return;
    }
    window.location.hash = `/${nextPage}`;
  }

  useEffect(() => {
    const updatePage = () => setPage(currentPage());
    window.addEventListener("hashchange", updatePage);
    return () => window.removeEventListener("hashchange", updatePage);
  }, []);

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

      const [session, administrator] = await Promise.all([
        api("/session").catch(() => null), api("/admin/session").catch(() => null),
      ]);
      if (isActive() && session?.authenticated) setUser(session.user);
      if (isActive() && administrator?.authenticated) setAdmin(administrator.admin);
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

  useEffect(() => {
    if (page === "tickets" && user) {
      setTicketsMessage("");
      api("/bookings/history").then(setTickets).catch((error) => setTicketsMessage(messageText(error)));
    }
  }, [page, user]);

  useEffect(() => {
    if (page === "admin" && admin) refreshPendingPayments();
  }, [page, admin]);

  async function refreshPendingPayments() {
    try {
      const result = await api("/admin/payments/pending");
      setPendingPayments(result.payments || []);
    } catch (error) {
      setAdminMessage(messageText(error));
    }
  }

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
      navigate("search");
      requestAnimationFrame(() => document.getElementById("search-results")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (error) {
      setSearchError(true);
      setSearchMessage(messageText(error));
      navigate("search");
    }
  }

  function beginBooking(train) {
    if (!user) {
      setPendingTrain(train);
      setAuthMode("login");
      setAuthError(true);
      setAuthMessage("Log in before booking a ticket.");
      navigate("account");
      return;
    }
    setPendingTrain(null);
    setSelectedTrain(train);
    setBookingKey(globalThis.crypto?.randomUUID?.() || "");
    setPassengers(Array.from({ length: passengerCount }, (_, index) => ({
      passenger_name: index === 0 ? user.full_name : "", age: "", gender: "", berth_preference: "NO_PREFERENCE",
    })));
    setBookingMessage("");
    setBookingError(false);
    navigate("booking");
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
      setBookingMessage(`Seats held for 15 minutes. PNR ${result.pnr} · ${assigned}.`);
      setPaymentBooking({ ...result, booking_status: result.status });
      setPaymentMessage("");
      setPaymentError(false);
      setSelectedTrain(null);
      setBookingKey("");
      setTrains((current) => [...current]);
      navigate("payment");
    } catch (error) {
      setBookingError(true);
      setBookingMessage(messageText(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function refreshPaymentStatus() {
    if (!paymentBooking) return;
    setPaymentBusy(true);
    try {
      const history = await api("/bookings/history");
      const booking = [...history.upcoming, ...history.previous].find((item) => item.booking_id === paymentBooking.booking_id);
      if (!booking) throw new Error("Booking could not be found in your account.");
      setPaymentBooking((current) => ({ ...current, ...booking }));
      setPaymentError(booking.payment_status === "FAILED");
      setPaymentMessage(booking.booking_status === "CONFIRMED" ? "Payment approved. Your ticket is confirmed." : booking.payment_status === "FAILED" ? "Payment was rejected. You can submit another request while your seat hold is active." : "Your request is awaiting administrator review.");
    } catch (error) {
      setPaymentError(true);
      setPaymentMessage(messageText(error));
    } finally {
      setPaymentBusy(false);
    }
  }

  async function submitPaymentRequest() {
    if (!paymentBooking || paymentBooking.booking_status === "CONFIRMED") return;
    setPaymentBusy(true);
    setPaymentMessage("");
    try {
      const idempotencyKey = globalThis.crypto?.randomUUID?.();
      if (!idempotencyKey) throw new Error("Secure payment requests are unavailable in this browser.");
      const result = await api(`/bookings/${paymentBooking.booking_id}/payment`, {
        method: "POST",
        body: { idempotency_key: idempotencyKey },
      });
      setPaymentBooking((current) => ({ ...current, booking_status: result.booking_status, payment_status: result.payment_status }));
      setPaymentError(false);
      setPaymentMessage(`Payment request submitted. An administrator must approve booking ${result.pnr}; your seats are held temporarily.`);
    } catch (error) {
      setPaymentError(true);
      setPaymentMessage(messageText(error));
    } finally {
      setPaymentBusy(false);
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
        if (result.role === "ADMIN") {
          setUser(null);
          setAdmin(result.admin);
          setAdminMessage("Administrator signed in.");
          navigate("admin");
          return;
        }
        setAdmin(null);
        setUser(result.user);
        setAuthError(false);
        setAuthMessage("You are signed in.");
        if (pendingTrain) {
          const train = pendingTrain;
          setPendingTrain(null);
          setSelectedTrain(train);
          setBookingKey(globalThis.crypto?.randomUUID?.() || "");
          setPassengers(Array.from({ length: passengerCount }, (_, index) => ({
            passenger_name: index === 0 ? result.user.full_name : "", age: "", gender: "", berth_preference: "NO_PREFERENCE",
          })));
          navigate("booking");
        }
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

  async function reviewPayment(paymentId, decision) {
    setAdminBusy(true);
    setAdminMessage("");
    try {
      const result = await api(`/admin/payments/${paymentId}/review`, { method: "POST", body: { decision } });
      setAdminMessage(`PNR ${result.pnr}: ${decision === "APPROVE" ? "approved" : "rejected"}.`);
      await refreshPendingPayments();
      if (paymentBooking?.booking_id === result.booking_id) {
        setPaymentBooking((current) => ({ ...current, booking_status: result.booking_status, payment_status: result.payment_status }));
      }
    } catch (error) {
      setAdminMessage(messageText(error));
      await refreshPendingPayments();
    } finally {
      setAdminBusy(false);
    }
  }

  async function logoutAdmin() {
    try {
      await api("/admin/logout", { method: "POST" });
      setAdmin(null);
      setPendingPayments([]);
      setAdminMessage("Administrator signed out.");
    } catch (error) {
      setAdminMessage(messageText(error));
    }
  }

  return <>
    <header className="site-header">
      <a className="brand" href="#/search" aria-label="Trackline home"><span className="brand-mark" aria-hidden="true">🚆</span><span className="brand-name">trackline<span>RAILWAY RESERVATIONS</span></span></a>
      <nav className="top-nav page-nav" aria-label="Main navigation"><a href="#/search" aria-current={page === "search" ? "page" : undefined}>Search</a>{user && <a href="#/tickets" aria-current={page === "tickets" ? "page" : undefined}>My tickets</a>}<a href="#/account" aria-current={page === "account" ? "page" : undefined}>{user || admin ? "Account" : "Login"}</a>{admin && <a href="#/admin" aria-current={page === "admin" ? "page" : undefined}>Payment review</a>}<div className="service-status" role="status"><span className={`status-indicator ${apiOnline ? "is-online" : "is-offline"}`} /><span>{apiOnline ? "Backend API is running" : "Backend API is not reachable"}</span></div></nav>
    </header>
    <main id="top" className={`page-shell app-page app-page-${page}`}>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy"><p className="eyebrow"><span className="eyebrow-line" /> YOUR NEXT JOURNEY, MADE SIMPLE</p><h1 id="hero-title">There’s a better<br />way to <em>get there.</em></h1><p className="hero-intro">Find the right train for your plans. Pick your stations, choose a date, and explore the routes ahead.</p><a className="hero-link" href="#plan">Find your train <span aria-hidden="true">↓</span></a></div>
        <div className="hero-visual" aria-hidden="true"><div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" /><div className="visual-caption"><span className="caption-star">✳</span> Every great trip begins with a plan.</div></div><div className="hero-index" aria-hidden="true">01 <span /> EXPLORE</div>
      </section>
      <section id="plan" className="search-panel" aria-labelledby="search-title">
        <div className="section-heading"><div><p className="section-kicker">LET’S GET MOVING</p><h2 id="search-title">Where would you like to go?</h2></div><span className="step-label"><span>01</span> SEARCH TRAINS</span></div>
        <form className="search-form" onSubmit={submitSearch}>
          <div className="field-group"><label htmlFor="source-station">From</label><select id="source-station" required disabled={loadingSearchData} value={sourceId} onChange={(event) => { setSourceId(event.target.value); if (event.target.value === destinationId) setDestinationId(""); }}><option value="">{loadingSearchData ? "Loading stations…" : "Select a station"}</option>{stations.filter((station) => String(station.station_id) !== destinationId).map((station) => <option key={station.station_id} value={station.station_id}>{station.station_name} ({station.station_code}) — {station.city}</option>)}</select></div>
          <div className="field-group"><label htmlFor="destination-station">To</label><select id="destination-station" required disabled={loadingSearchData} value={destinationId} onChange={(event) => { setDestinationId(event.target.value); if (event.target.value === sourceId) setSourceId(""); }}><option value="">{loadingSearchData ? "Loading stations…" : "Select a station"}</option>{stations.filter((station) => String(station.station_id) !== sourceId).map((station) => <option key={station.station_id} value={station.station_id}>{station.station_name} ({station.station_code}) — {station.city}</option>)}</select></div>
          <div className="field-group date-field"><label htmlFor="journey-date">Journey date</label><input id="journey-date" type="date" min={new Date().toLocaleDateString("en-CA")} value={journeyDate} onChange={(event) => setJourneyDate(event.target.value)} required /></div>
          <div className="field-group"><label htmlFor="travel-class">Travel class</label><select id="travel-class" value={classId} onChange={(event) => setClassId(event.target.value)} required disabled={loadingSearchData}><option value="">{loadingSearchData ? "Loading travel classes…" : "Select a travel class"}</option>{classes.map((item) => <option key={item.class_id} value={item.class_id}>{item.class_name} ({item.class_code})</option>)}</select></div>
          <div className="field-group"><label htmlFor="passenger-count">Passengers</label><select id="passenger-count" value={passengerCount} onChange={(event) => setPassengerCount(Number(event.target.value))}>{[1, 2, 3, 4, 5, 6].map((count) => <option key={count} value={count}>{count} passenger{count === 1 ? "" : "s"}</option>)}</select></div>
          <button type="submit" id="search-button" disabled={loadingSearchData || !apiOnline || !stations.length || !classes.length}><span>{loadingSearchData ? "Loading search options…" : "Search trains"}</span><span className="button-arrow" aria-hidden="true">↗</span></button>
        </form>
        {searchDataError && <p className="form-message is-error" role="alert">{searchDataError} <button type="button" className="retry-button" onClick={() => initialize()} disabled={loadingSearchData}>{loadingSearchData ? "Retrying…" : "Retry"}</button></p>}
        <p className={`form-message ${searchError ? "is-error" : ""}`} role="status">{searchMessage}</p>
        {paymentBooking && <section className="payment-panel" aria-labelledby="payment-title"><div className="results-heading"><div><p className="section-kicker">PAYMENT REVIEW</p><h2 id="payment-title">{paymentBooking.booking_status === "CONFIRMED" ? "Ticket confirmed" : "Request payment approval"}</h2></div><span className="step-label">{paymentBooking.booking_status === "CONFIRMED" ? "CONFIRMED" : paymentBooking.payment_status === "INITIATED" ? "AWAITING ADMIN" : "PENDING"}</span></div><p className="payment-reference">Booking reference <strong>{paymentBooking.pnr}</strong></p><p className="payment-amount">Amount to pay <strong>{paymentBooking.currency_code} {Number(paymentBooking.total_fare).toFixed(2)}</strong></p><p className="payment-demo-note">No payment gateway is connected. Submit this request for an administrator to review and approve.</p>{paymentBooking.booking_status !== "CONFIRMED" && paymentBooking.payment_status !== "INITIATED" && <button type="button" className="account-submit" disabled={paymentBusy} onClick={submitPaymentRequest}>{paymentBusy ? "Submitting…" : "Submit for admin approval"}</button>}{paymentBooking.payment_status === "INITIATED" && paymentBooking.booking_status !== "CONFIRMED" && <p className="approval-waiting" role="status">Waiting for the administrator. Seats are held for a limited time.</p>}<p className={`form-message ${paymentError ? "is-error" : "is-success"}`} role="status" aria-live="polite">{paymentMessage}</p><button type="button" className="secondary-button" disabled={paymentBusy} onClick={refreshPaymentStatus}>Check payment status</button><a className="text-button" href="#/tickets">View my tickets</a></section>}
        {(trains.length > 0 || searchMessage) && <section id="search-results" className="search-results" aria-labelledby="results-title"><div className="results-heading"><div><p className="section-kicker">YOUR OPTIONS</p><h2 id="results-title">{trains.length ? "Matching trains" : "No trains found"}</h2></div><p className="results-summary">{trains.length ? `${trains.length} scheduled service${trains.length === 1 ? "" : "s"}` : "Try another date or station pair."}</p></div>
          <div className="train-results-list">{trains.map((train) => <TrainCard key={train.schedule_id} train={train} classId={classId} selectedClass={selectedClass} sourceId={sourceId} destinationId={destinationId} journeyDate={journeyDate} passengerCount={passengerCount} onBook={beginBooking} />)}</div>
          {selectedTrain && <section className="booking-panel" aria-labelledby="booking-title"><div className="results-heading"><div><p className="section-kicker">COMPLETE YOUR JOURNEY</p><h2 id="booking-title">Traveler details</h2></div><span className="step-label">BOOK TICKET</span></div><p className="booking-summary">{selectedTrain.train_name} ({selectedTrain.train_number}) · {selectedTrain.source_station_name} to {selectedTrain.destination_station_name} · {passengerCount} passenger{passengerCount === 1 ? "" : "s"}</p>
            <form className="booking-form" onSubmit={submitBooking}><div className="booking-passenger-fields">{passengers.map((passenger, index) => <fieldset className="booking-passenger-entry" key={index}><legend>Passenger {index + 1}</legend><div className="field-group"><label htmlFor={`passenger-${index}-name`}>Full name</label><input id={`passenger-${index}-name`} maxLength="120" required value={passenger.passenger_name} onChange={(event) => changePassenger(index, "passenger_name", event.target.value)} /></div><div className="field-group"><label htmlFor={`passenger-${index}-age`}>Age</label><input id={`passenger-${index}-age`} type="number" min="0" max="120" required value={passenger.age} onChange={(event) => changePassenger(index, "age", event.target.value)} /></div><div className="field-group"><label htmlFor={`passenger-${index}-gender`}>Gender (optional)</label><input id={`passenger-${index}-gender`} maxLength="30" value={passenger.gender} onChange={(event) => changePassenger(index, "gender", event.target.value)} /></div><div className="field-group"><label htmlFor={`passenger-${index}-berth`}>Berth preference</label><select id={`passenger-${index}-berth`} value={passenger.berth_preference} onChange={(event) => changePassenger(index, "berth_preference", event.target.value)}>{[["NO_PREFERENCE", "No preference"], ["LOWER", "Lower"], ["MIDDLE", "Middle"], ["UPPER", "Upper"], ["SIDE_LOWER", "Side lower"], ["SIDE_UPPER", "Side upper"]].map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></div></fieldset>)}</div><button type="submit" className="account-submit" disabled={submitting}>{submitting ? "Checking seats…" : "Book and reserve seats"}</button></form>
          </section>}
          {bookingMessage && <p className={`form-message ${bookingError ? "is-error" : "is-success"}`} role="status">{bookingMessage}</p>}
        </section>}
      </section>
      <section id="account" className="account-section" aria-labelledby="registration-title"><div className="account-copy"><p className="section-kicker">A LITTLE MORE CONVENIENT</p><h2>Make the next trip<br /><em>yours.</em></h2><p>Create an account to get started with railway reservations. Your details stay yours.</p><div className="account-note"><span className="note-mark" aria-hidden="true">✳</span><span><strong>One less thing to do at the station.</strong><br />Set up your account before your next journey.</span></div><div className="account-decoration" aria-hidden="true"><span /><span /><span /><span /><span /><span /><span /></div></div>
        <div className="account-form-wrap"><div className="form-title-row"><div><p className="section-kicker">GET STARTED</p><h2 id="registration-title">{user ? "Your account" : authMode === "login" ? "Welcome back" : "Create your account"}</h2></div><span className="form-step">02</span></div>
          {admin ? <div className="account-panel"><p className="section-kicker">ADMINISTRATOR SIGNED IN</p><h3>Payment review access</h3><p>{admin.email}</p><button type="button" className="account-submit" onClick={logoutAdmin}>Log out ↗</button></div> : user ? <div className="account-panel"><p className="section-kicker">SIGNED IN</p><h3>Welcome, {user.full_name}</h3><p>{user.email}</p><button type="button" className="account-submit" onClick={logout}>Log out ↗</button></div> : <><div className="account-tabs" role="group" aria-label="Account actions"><button type="button" aria-pressed={authMode === "login"} onClick={() => { setAuthMode("login"); setAuthError(false); setAuthMessage(""); }}>Log in</button><button type="button" aria-pressed={authMode === "register"} onClick={() => { setAuthMode("register"); setAuthError(false); setAuthMessage(""); }}>Create account</button></div>
            <form className="registration-form" onSubmit={submitAuth} key={authMode} noValidate>
              {authMode === "register" && <div className="field-group"><label htmlFor="full-name">Full name</label><input id="full-name" name="full_name" autoComplete="name" maxLength="120" placeholder="e.g. Aditi Rao" required /></div>}
              <div className="field-group"><label htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete={authMode === "login" ? "username" : "email"} maxLength="254" placeholder="you@example.com" required /></div>
              {authMode === "register" && <div className="field-group"><label htmlFor="phone-number">Phone number <span className="optional">OPTIONAL</span></label><input id="phone-number" name="phone_number" type="tel" autoComplete="tel" maxLength="25" placeholder="Your phone number" /></div>}
              <div className="field-group"><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete={authMode === "login" ? "current-password" : "new-password"} minLength={authMode === "register" ? 8 : undefined} title={authMode === "register" ? "Use 8–128 characters with an uppercase letter, a lowercase letter, and a number." : undefined} maxLength="128" placeholder={authMode === "login" ? "Your password" : "Create a strong password"} required /></div>
              {authMode === "register" && <p className="field-help">8–128 characters, with uppercase, lowercase, and a number.</p>}
              <button type="submit" className="account-submit" disabled={authBusy}>{authBusy ? "Please wait…" : authMode === "login" ? "Log in ↗" : "Create account ↗"}</button>
            </form></>}
          <p className={`form-message ${authError ? "is-error" : ""}`} role="status">{authMessage}</p><p className="privacy-note"><span aria-hidden="true">▣</span> Your password is securely protected.</p>
        </div>
      </section>
      {page === "tickets" && <section className="ticket-history-page" aria-labelledby="tickets-title"><div className="page-heading-row"><div><p className="section-kicker">YOUR JOURNEYS</p><h1 id="tickets-title">My tickets</h1><p>Bookings, seat details, and payment status.</p></div><button type="button" className="secondary-button" onClick={() => { setTickets(null); setTicketsMessage(""); api("/bookings/history").then(setTickets).catch((error) => setTicketsMessage(messageText(error))); }}>Refresh</button></div>{!user ? <div className="empty-state"><p>Sign in to see your bookings.</p><a className="primary-link-button" href="#/account">Sign in</a></div> : ticketsMessage ? <p className="form-message is-error" role="alert">{ticketsMessage}</p> : tickets ? <><TicketGroup title="Upcoming journeys" bookings={tickets.upcoming || []} /><TicketGroup title="Past journeys" bookings={tickets.previous || []} /></> : <p className="loading-note">Loading your tickets…</p>}</section>}
      {page === "admin" && <section className="admin-review-page" aria-labelledby="admin-title">{!admin ? <div className="empty-state"><h1 id="admin-title">Administrator access required</h1><p>Use the Log in tab on the Account page with an administrator account.</p><a className="primary-link-button" href="#/account">Go to account login</a></div> : <><div className="page-heading-row"><div><p className="section-kicker">PAYMENT DESK</p><h1 id="admin-title">Approval queue</h1><p>Review pending payment requests before tickets are confirmed.</p></div><div className="admin-toolbar"><button type="button" className="secondary-button" disabled={adminBusy} onClick={refreshPendingPayments}>Refresh queue</button><button type="button" className="text-button" onClick={logoutAdmin}>Sign out</button></div></div>{adminMessage && <p className="form-message" role="status">{adminMessage}</p>}{pendingPayments.length ? <div className="approval-list">{pendingPayments.map((payment) => <article className="approval-card" key={payment.payment_id}><div className="approval-card-heading"><div><span className="approval-label">PENDING REVIEW</span><h2>{payment.train_name_snapshot} <small>#{payment.train_number_snapshot}</small></h2></div><strong className="approval-amount">{payment.currency_code} {Number(payment.amount).toFixed(2)}</strong></div><p className="approval-route">{payment.boarding_station_name_snapshot} → {payment.alighting_station_name_snapshot}</p><dl><div><dt>Passenger</dt><dd>{payment.full_name} · {payment.email}</dd></div><div><dt>Booking</dt><dd>PNR {payment.pnr} · {payment.passenger_count} passenger(s)</dd></div><div><dt>Departure</dt><dd>{new Date(payment.departure_at_snapshot).toLocaleString()}</dd></div><div><dt>Seat hold expires</dt><dd>{payment.hold_expires_at ? new Date(payment.hold_expires_at).toLocaleString() : "Expired"}</dd></div></dl><div className="approval-actions"><button type="button" className="approve-button" disabled={adminBusy || !payment.hold_expires_at || new Date(payment.hold_expires_at) <= new Date()} onClick={() => reviewPayment(payment.payment_id, "APPROVE")}>Approve & confirm ticket</button><button type="button" className="reject-button" disabled={adminBusy} onClick={() => reviewPayment(payment.payment_id, "REJECT")}>Reject</button></div></article>)}</div> : <div className="empty-state"><h2>No pending requests</h2><p>New passenger payment requests will appear here.</p></div>}</>}</section>}
    </main>
    <footer className="site-footer"><a className="footer-brand" href="#top">trackline</a><span>Plan well. Travel happy.</span><a href="#plan">Back to top ↑</a></footer>
  </>;
}

function TicketGroup({ title, bookings }) {
  return <section className="ticket-group"><div className="ticket-group-heading"><h2>{title}</h2><span>{bookings.length}</span></div>{bookings.length ? <div className="ticket-list">{bookings.map((ticket) => <article className="ticket-card" key={ticket.booking_id}><div className="ticket-card-top"><div><span className="section-kicker">PNR {ticket.pnr}</span><h3>{ticket.train_name} <small>#{ticket.train_number}</small></h3></div><span className={`ticket-status ticket-status-${ticket.booking_status.toLowerCase()}`}>{ticket.booking_status.replaceAll("_", " ")}</span></div><p className="ticket-route">{ticket.source_station_name} <span>→</span> {ticket.destination_station_name}</p><div className="ticket-meta"><span>{new Date(ticket.departure_at).toLocaleString()}</span><span>{ticket.class_code} · {ticket.currency_code} {Number(ticket.total_fare).toFixed(2)}</span><span>Payment: {ticket.payment_status || "NOT SUBMITTED"}</span></div><div className="ticket-passengers">{ticket.passengers.map((passenger) => <span key={passenger.passenger_id}>{passenger.passenger_name}{passenger.coach_number && passenger.seat_number ? ` · ${passenger.coach_number}-${passenger.seat_number}` : ""}</span>)}</div></article>)}</div> : <p className="empty-inline">No {title.toLowerCase()} yet.</p>}</section>;
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

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
