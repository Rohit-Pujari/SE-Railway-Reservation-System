import React, { useEffect, useState } from "react";

const API = "/api";
const csrf = () => document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("csrftoken="))?.slice(10) || "";

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { Accept: "application/json", ...options.headers };
  if (options.body) { headers["Content-Type"] = "application/json"; options.body = JSON.stringify(options.body); }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) headers["X-CSRFToken"] = csrf();
  const response = await fetch(API + path, { ...options, method, headers, credentials: "same-origin" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || "Request failed.");
  return data;
}
const date = (value) => value ? new Date(value).toLocaleString() : "—";
const money = (value, currency = "INR") => `${currency} ${Number(value || 0).toFixed(2)}`;

export default function AdminApp() {
  const [admin, setAdmin] = useState(null);
  const [form, setForm] = useState({ email: "", password: "" });
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [newTrain, setNewTrain] = useState({ train_number: "", train_name: "", train_status: "ACTIVE" });
  const [creatingTrain, setCreatingTrain] = useState(false);
  const [editingTrainId, setEditingTrainId] = useState(null);
  const [editTrain, setEditTrain] = useState({ train_number: "", train_name: "", train_status: "ACTIVE" });
  const [savingTrain, setSavingTrain] = useState(false);
  const [removingTrainId, setRemovingTrainId] = useState(null);

  async function loadDashboard() {
    setBusy(true); setError("");
    try { const result = await request("/admin/dashboard"); setData(result); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { request("/csrf").catch(() => {}); }, []);

  async function login(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await request("/csrf");
      const result = await request("/admin/login", { method: "POST", body: form });
      setAdmin(result.admin); setNotice("Administrator session started.");
      await loadDashboard();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  async function logout() {
    try { await request("/admin/logout", { method: "POST" }); setAdmin(null); setData(null); setNotice("You have been logged out."); }
    catch (err) { setError(err.message); }
  }
  async function addTrain(event) {
    event.preventDefault();
    setCreatingTrain(true); setError(""); setNotice("");
    try {
      const result = await request("/admin/trains", { method: "POST", body: newTrain });
      setNotice(result.message || "Train added successfully.");
      setNewTrain({ train_number: "", train_name: "", train_status: "ACTIVE" });
      await loadDashboard();
      setTab("trains");
    } catch (err) { setError(err.message); }
    finally { setCreatingTrain(false); }
  }

  async function changeTrainStatus(train) {
    const next = train.train_status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    setError(""); setNotice("");
    try {
      await request(`/admin/trains/${train.train_id}`, { method: "PATCH", body: { train_status: next } });
      setNotice(`${train.train_name} is now ${next.toLowerCase()}.`);
      await loadDashboard();
    } catch (err) { setError(err.message); }
  }

  async function removeTrain(train) {
    const confirmed = window.confirm(
      "Remove train " + train.train_number + " — " + train.train_name +
      "? Trains with schedules or booking history will be deactivated to preserve existing records."
    );
    if (!confirmed) return;
    setRemovingTrainId(train.train_id);
    setError(""); setNotice("");
    try {
      const result = await request("/admin/trains/" + train.train_id, { method: "DELETE" });
      setNotice(result.message || "Train removed successfully.");
      await loadDashboard();
      setTab("trains");
    } catch (err) { setError(err.message); }
    finally { setRemovingTrainId(null); }
  }
  function startEditTrain(train) {
    setEditingTrainId(train.train_id);
    setEditTrain({
      train_number: train.train_number,
      train_name: train.train_name,
      train_status: train.train_status,
    });
    setError(""); setNotice("");
  }

  async function saveTrainEdits(event) {
    event.preventDefault();
    if (editingTrainId === null) return;
    setSavingTrain(true); setError(""); setNotice("");
    try {
      const result = await request(`/admin/trains/${editingTrainId}`, {
        method: "PATCH",
        body: editTrain,
      });
      setNotice(result.message || "Train details updated successfully.");
      setEditingTrainId(null);
      await loadDashboard();
      setTab("trains");
    } catch (err) { setError(err.message); }
    finally { setSavingTrain(false); }
  }

  const nav = [["overview","Overview"],["trains","Trains"],["routes","Routes"],["schedules","Schedules & seats"],["bookings","Bookings"],["cancellations","Cancellations"]];
  if (!admin) return <main className="admin-shell"><a className="admin-back" href="/">← Back to Trackline</a><section className="admin-login-card"><p className="section-kicker">TRACKLINE · ADMINISTRATION</p><h1>Administrator sign in</h1><p>Use an active administrator account to access railway operations.</p><form onSubmit={login}><label htmlFor="admin-email">Email</label><input id="admin-email" type="email" autoComplete="username" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/><label htmlFor="admin-password">Password</label><input id="admin-password" type="password" autoComplete="current-password" required value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/><button disabled={busy}>{busy ? "Signing in…" : "Sign in to dashboard ↗"}</button></form>{error && <p className="admin-error" role="alert">{error}</p>}{notice && <p className="admin-notice">{notice}</p>}</section></main>;

  const summary = data?.summary || {};
  const rows = (items, columns) => <div className="admin-table-wrap"><table className="admin-table"><thead><tr>{columns.map(([key,label])=><th key={key}>{label}</th>)}</tr></thead><tbody>{(items||[]).map((item,i)=><tr key={item.booking_id || item.schedule_id || item.route_id || item.train_id || item.cancellation_id || i}>{columns.map(([key])=><td key={key}>{key==="departure_at"||key==="arrival_at"||key==="requested_at"||key==="created_at" ? date(item[key]) : key==="total_fare" ? money(item[key],item.currency_code) : key==="stops" ? (item.stops||[]).map(s=>s.station_code).join(" → ") : String(item[key] ?? "—")}</td>)}</tr>)}</tbody></table>{!items?.length && <p className="admin-empty">No records found.</p>}</div>;
  return <main className="admin-shell">
    <header className="admin-header"><div><a className="admin-back" href="/">← Trackline</a><p className="section-kicker">OPERATIONS CONTROL</p><h1>Admin dashboard</h1><span>Signed in as {admin.email}</span></div><button className="admin-logout" onClick={logout}>Log out</button></header>
    <nav className="admin-tabs" aria-label="Admin sections">{nav.map(([id,label])=><button key={id} className={tab===id?"active":""} onClick={()=>setTab(id)}>{label}</button>)}</nav>
    {error && <p className="admin-error" role="alert">{error}</p>}{notice && <p className="admin-notice" role="status">{notice}</p>}
    <div className="admin-content">
      {tab==="overview" && <><div className="admin-title-row"><div><p className="section-kicker">AT A GLANCE</p><h2>Railway operations</h2></div><button onClick={loadDashboard} disabled={busy}>{busy?"Refreshing…":"Refresh data ↻"}</button></div><div className="admin-metrics">{[["Trains",summary.total_trains],["Routes",summary.total_routes],["Schedules",summary.total_schedules],["Bookings",summary.total_bookings],["Active bookings",summary.active_bookings],["Cancellations",summary.total_cancellations]].map(([label,value])=><article key={label}><span>{label}</span><strong>{Number(value||0).toLocaleString()}</strong></article>)}</div><h3>Recent bookings</h3>{rows((data?.bookings||[]).slice(0,8),[["pnr","PNR"],["train_name_snapshot","Train"],["full_name","Passenger"],["booking_status","Status"],["total_fare","Fare"]])}</>}
      {tab==="trains" && <><div className="admin-title-row"><div><p className="section-kicker">FLEET</p><h2>Train management</h2><p>Add a train or activate/deactivate an existing service.</p></div><button onClick={loadDashboard} disabled={busy}>Refresh ↻</button></div><form className="admin-add-train-form" onSubmit={addTrain}><div><label htmlFor="new-train-number">Train number</label><input id="new-train-number" value={newTrain.train_number} onChange={e=>setNewTrain({...newTrain,train_number:e.target.value})} maxLength="20" pattern="[A-Za-z0-9-]{1,20}" title="Use 1–20 letters, numbers, or hyphens." placeholder="e.g. 12627" required /></div><div><label htmlFor="new-train-name">Train name</label><input id="new-train-name" value={newTrain.train_name} onChange={e=>setNewTrain({...newTrain,train_name:e.target.value})} maxLength="150" placeholder="e.g. Karnataka Express" required /></div><div><label htmlFor="new-train-status">Initial status</label><select id="new-train-status" value={newTrain.train_status} onChange={e=>setNewTrain({...newTrain,train_status:e.target.value})}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select></div><button type="submit" disabled={creatingTrain}>{creatingTrain?"Adding…":"Add train +"}</button></form>{editingTrainId !== null && <form className="admin-edit-train-form" onSubmit={saveTrainEdits}>
          <div className="admin-edit-train-heading"><div><p className="section-kicker">EDIT TRAIN</p><h3>Update train details</h3></div><button type="button" className="admin-small-button" onClick={()=>setEditingTrainId(null)}>Cancel</button></div>
          <div className="admin-edit-train-fields">
            <div><label htmlFor="edit-train-number">Train number</label><input id="edit-train-number" value={editTrain.train_number} onChange={e=>setEditTrain({...editTrain,train_number:e.target.value})} maxLength="20" pattern="[A-Za-z0-9-]{1,20}" title="Use 1–20 letters, numbers, or hyphens." required /></div>
            <div><label htmlFor="edit-train-name">Train name</label><input id="edit-train-name" value={editTrain.train_name} onChange={e=>setEditTrain({...editTrain,train_name:e.target.value})} maxLength="150" required /></div>
            <div><label htmlFor="edit-train-status">Status</label><select id="edit-train-status" value={editTrain.train_status} onChange={e=>setEditTrain({...editTrain,train_status:e.target.value})}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select></div>
            <button type="submit" disabled={savingTrain}>{savingTrain?"Saving…":"Save changes"}</button>
          </div>
        </form>}<div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Train no.</th><th>Train name</th><th>Status</th><th>Action</th></tr></thead><tbody>{(data?.trains||[]).map(train=><tr key={train.train_id}><td>{train.train_number}</td><td>{train.train_name}</td><td><span className={`admin-status ${train.train_status.toLowerCase()}`}>{train.train_status}</span></td><td><button className="admin-small-button" onClick={()=>startEditTrain(train)}>Edit</button> <button className="admin-small-button" onClick={()=>changeTrainStatus(train)}>{train.train_status==="ACTIVE"?"Deactivate":"Activate"}</button> <button className="admin-danger-button" onClick={()=>removeTrain(train)} disabled={removingTrainId===train.train_id}>{removingTrainId===train.train_id?"Removing…":"Remove"}</button></td></tr>)}</tbody></table>{!data?.trains?.length&&<p className="admin-empty">No trains found.</p>}</div></>}
      {tab==="routes" && <><p className="section-kicker">NETWORK</p><h2>Routes and stops</h2>{rows(data?.routes,[["route_name","Route"],["route_status","Status"],["stops","Station sequence"]])}</>}
      {tab==="schedules" && <><p className="section-kicker">TIMETABLE & INVENTORY</p><h2>Schedules and seat availability</h2>{rows(data?.schedules,[["train_number","Train no."],["train_name","Train"],["route_name","Route"],["departure_at","Departure"],["arrival_at","Arrival"],["schedule_status","Status"],["available_seats","Available seats"],["total_seats","Total seats"]])}</>}
      {tab==="bookings" && <><p className="section-kicker">RESERVATIONS</p><h2>Bookings</h2>{rows(data?.bookings,[["pnr","PNR"],["train_name_snapshot","Train"],["full_name","Passenger"],["email","Email"],["booking_status","Status"],["passenger_count","Passengers"],["total_fare","Fare"],["created_at","Created"]])}</>}
      {tab==="cancellations" && <><p className="section-kicker">SERVICE RECORDS</p><h2>Cancellation records</h2>{rows(data?.cancellations,[["pnr","PNR"],["train_name_snapshot","Train"],["full_name","Requested by"],["cancellation_status","Status"],["passenger_items","Passengers"],["cancellation_charge","Charge"],["refund_amount","Refund"],["requested_at","Requested"]])}</>}
    </div>
    <footer className="admin-footer">Trackline Railway Reservations · Administrator workspace</footer>
  </main>;
}
