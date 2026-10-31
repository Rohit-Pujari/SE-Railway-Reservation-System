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
  const [stationForm, setStationForm] = useState({ station_code: "", station_name: "", city: "", state: "" });
  const [editingStationId, setEditingStationId] = useState(null);
  const [stationSaving, setStationSaving] = useState(false);
  const [routeForm, setRouteForm] = useState({ route_name: "", route_status: "ACTIVE", stop_ids: "", distances: "" });
  const [editingRouteId, setEditingRouteId] = useState(null);
  const [routeSaving, setRouteSaving] = useState(false);
  const [assignmentForm, setAssignmentForm] = useState({ train_id: "", route_id: "" });
  const [assignmentSaving, setAssignmentSaving] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    train_id: "", route_id: "", departure_at: "", arrival_at: "", schedule_status: "SCHEDULED",
  });
  const [editingScheduleId, setEditingScheduleId] = useState(null);
  const [scheduleSaving, setScheduleSaving] = useState(false);

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

  async function saveStation(event) {
    event.preventDefault(); setStationSaving(true); setError(""); setNotice("");
    try {
      const result = await request(editingStationId ? `/admin/stations/${editingStationId}` : "/admin/stations", {
        method: editingStationId ? "PATCH" : "POST", body: stationForm,
      });
      setNotice(result.message || "Station saved successfully.");
      setStationForm({ station_code: "", station_name: "", city: "", state: "" });
      setEditingStationId(null); await loadDashboard(); setTab("routes");
    } catch (err) { setError(err.message); }
    finally { setStationSaving(false); }
  }

  function startEditStation(station) {
    setEditingStationId(station.station_id);
    setStationForm({ station_code: station.station_code, station_name: station.station_name, city: station.city, state: station.state || "" });
  }

  async function saveRoute(event) {
    event.preventDefault(); setRouteSaving(true); setError(""); setNotice("");
    try {
      const ids = routeForm.stop_ids.split(",").map(value => value.trim()).filter(Boolean);
      const distances = routeForm.distances.trim() ? routeForm.distances.split(",").map(value => value.trim()) : [];
      if (ids.length < 2) throw new Error("Enter at least two station IDs in route order.");
      if (distances.length !== ids.length) throw new Error("Enter one cumulative distance for every station.");
      const stops = ids.map((id, index) => ({
        station_id: Number(id), sequence: index + 1,
        distance_from_origin_km: Number(distances[index]),
      }));
      if (stops.some(stop => !Number.isInteger(stop.station_id) || stop.station_id <= 0 || !Number.isFinite(stop.distance_from_origin_km))) {
        throw new Error("Station IDs and distances must be valid numbers.");
      }
      const body = { route_name: routeForm.route_name, route_status: routeForm.route_status, stops };
      const result = await request(editingRouteId ? `/admin/routes/${editingRouteId}` : "/admin/routes", {
        method: editingRouteId ? "PATCH" : "POST", body,
      });
      setNotice(result.message || "Route saved successfully.");
      setRouteForm({ route_name: "", route_status: "ACTIVE", stop_ids: "", distances: "" });
      setEditingRouteId(null); await loadDashboard(); setTab("routes");
    } catch (err) { setError(err.message); }
    finally { setRouteSaving(false); }
  }

  function startEditRoute(route) {
    setEditingRouteId(route.route_id);
    setRouteForm({
      route_name: route.route_name, route_status: route.route_status,
      stop_ids: (route.stops || []).map(stop => stop.station_id).join(", "),
      distances: (route.stops || []).map(stop => stop.distance_km).join(", "),
    });
  }

  async function saveAssignment(event) {
    event.preventDefault(); setAssignmentSaving(true); setError(""); setNotice("");
    try {
      const result = await request("/admin/train-routes", { method: "POST", body: {
        train_id: Number(assignmentForm.train_id), route_id: Number(assignmentForm.route_id),
      }});
      setNotice(result.message || "Route assigned successfully.");
      await loadDashboard(); setTab("routes");
    } catch (err) { setError(err.message); }
    finally { setAssignmentSaving(false); }
  }

  async function removeAssignment(assignment) {
    if (!window.confirm(`Remove route ${assignment.route_name} from train ${assignment.train_number}?`)) return;
    setError(""); setNotice("");
    try {
      const result = await request("/admin/train-routes", { method: "DELETE", body: {
        train_id: assignment.train_id, route_id: assignment.route_id,
      }});
      setNotice(result.message || "Assignment removed."); await loadDashboard();
    } catch (err) { setError(err.message); }
  }

  async function saveSchedule(event) {
    event.preventDefault(); setScheduleSaving(true); setError(""); setNotice("");
    try {
      const result = await request(
        editingScheduleId ? "/admin/schedules/" + editingScheduleId : "/admin/schedules",
        { method: editingScheduleId ? "PATCH" : "POST", body: {
          train_id: Number(scheduleForm.train_id), route_id: Number(scheduleForm.route_id),
          departure_at: scheduleForm.departure_at, arrival_at: scheduleForm.arrival_at,
          schedule_status: scheduleForm.schedule_status,
        }}
      );
      setNotice(result.message || "Train schedule saved successfully.");
      setScheduleForm({ train_id: "", route_id: "", departure_at: "", arrival_at: "", schedule_status: "SCHEDULED" });
      setEditingScheduleId(null); await loadDashboard(); setTab("schedules");
    } catch (err) { setError(err.message); }
    finally { setScheduleSaving(false); }
  }

  function startEditSchedule(schedule) {
    const localValue = value => value ? String(value).replace(" ", "T").slice(0, 16) : "";
    setEditingScheduleId(schedule.schedule_id);
    setScheduleForm({
      train_id: String(schedule.train_id), route_id: String(schedule.route_id),
      departure_at: localValue(schedule.departure_at), arrival_at: localValue(schedule.arrival_at),
      schedule_status: schedule.schedule_status,
    });
    setError(""); setNotice("");
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
      {tab==="routes" && <>
        <p className="section-kicker">NETWORK MANAGEMENT</p><h2>Stations and routes</h2>
        <h3>Station directory</h3>
        <form className="admin-management-form" onSubmit={saveStation}>
          <div><label htmlFor="station-code">Station code</label><input id="station-code" value={stationForm.station_code} onChange={e=>setStationForm({...stationForm,station_code:e.target.value})} maxLength="10" pattern="[A-Za-z0-9-]{1,10}" required /></div>
          <div><label htmlFor="station-name">Station name</label><input id="station-name" value={stationForm.station_name} onChange={e=>setStationForm({...stationForm,station_name:e.target.value})} maxLength="120" required /></div>
          <div><label htmlFor="station-city">City</label><input id="station-city" value={stationForm.city} onChange={e=>setStationForm({...stationForm,city:e.target.value})} maxLength="100" required /></div>
          <div><label htmlFor="station-state">State (optional)</label><input id="station-state" value={stationForm.state} onChange={e=>setStationForm({...stationForm,state:e.target.value})} maxLength="100" /></div>
          <button type="submit" disabled={stationSaving}>{stationSaving?"Saving…":editingStationId?"Update station":"Add station +"}</button>
          {editingStationId && <button type="button" className="admin-small-button" onClick={()=>{setEditingStationId(null);setStationForm({station_code:"",station_name:"",city:"",state:""});}}>Cancel</button>}
        </form>
        <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>ID</th><th>Code</th><th>Station</th><th>City</th><th>State</th><th>Status</th><th>Action</th></tr></thead><tbody>{(data?.stations||[]).map(station=><tr key={station.station_id}><td>{station.station_id}</td><td>{station.station_code}</td><td>{station.station_name}</td><td>{station.city}</td><td>{station.state||"—"}</td><td>{station.station_status}</td><td><button className="admin-small-button" onClick={()=>startEditStation(station)}>Edit</button></td></tr>)}</tbody></table>{!data?.stations?.length&&<p className="admin-empty">No stations found.</p>}</div>
        <h3>Route builder</h3>
        <p>Enter station IDs in travel order. Find each ID in the station directory above. Distances are cumulative kilometres from the first station.</p>
        <form className="admin-management-form" onSubmit={saveRoute}>
          <div><label htmlFor="route-name">Route name</label><input id="route-name" value={routeForm.route_name} onChange={e=>setRouteForm({...routeForm,route_name:e.target.value})} maxLength="150" required /></div>
          <div><label htmlFor="route-status">Status</label><select id="route-status" value={routeForm.route_status} onChange={e=>setRouteForm({...routeForm,route_status:e.target.value})}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select></div>
          <div className="admin-management-wide"><label htmlFor="route-stop-ids">Station IDs in order (comma-separated)</label><input id="route-stop-ids" value={routeForm.stop_ids} onChange={e=>setRouteForm({...routeForm,stop_ids:e.target.value})} placeholder="e.g. 1, 4, 7" required /></div>
          <div className="admin-management-wide"><label htmlFor="route-distances">Cumulative distances in km (comma-separated)</label><input id="route-distances" value={routeForm.distances} onChange={e=>setRouteForm({...routeForm,distances:e.target.value})} placeholder="e.g. 0, 42.5, 118" required /></div>
          <button type="submit" disabled={routeSaving}>{routeSaving?"Saving…":editingRouteId?"Update route":"Create route +"}</button>
          {editingRouteId && <button type="button" className="admin-small-button" onClick={()=>{setEditingRouteId(null);setRouteForm({route_name:"",route_status:"ACTIVE",stop_ids:"",distances:""});}}>Cancel</button>}
        </form>
        <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>ID</th><th>Route</th><th>Status</th><th>Stops</th><th>Action</th></tr></thead><tbody>{(data?.routes||[]).map(route=><tr key={route.route_id}><td>{route.route_id}</td><td>{route.route_name}</td><td>{route.route_status}</td><td>{(route.stops||[]).map(stop=>stop.station_code).join(" → ")}</td><td><button className="admin-small-button" onClick={()=>startEditRoute(route)}>Edit</button></td></tr>)}</tbody></table>{!data?.routes?.length&&<p className="admin-empty">No routes found.</p>}</div>
        <h3>Assign routes to trains</h3>
        <form className="admin-management-form" onSubmit={saveAssignment}>
          <div><label htmlFor="assignment-train">Active train</label><select id="assignment-train" value={assignmentForm.train_id} onChange={e=>setAssignmentForm({...assignmentForm,train_id:e.target.value})} required><option value="">Select train</option>{(data?.trains||[]).filter(train=>train.train_status==="ACTIVE").map(train=><option key={train.train_id} value={train.train_id}>{train.train_number} — {train.train_name}</option>)}</select></div>
          <div><label htmlFor="assignment-route">Active route</label><select id="assignment-route" value={assignmentForm.route_id} onChange={e=>setAssignmentForm({...assignmentForm,route_id:e.target.value})} required><option value="">Select route</option>{(data?.routes||[]).filter(route=>route.route_status==="ACTIVE").map(route=><option key={route.route_id} value={route.route_id}>{route.route_name}</option>)}</select></div>
          <button type="submit" disabled={assignmentSaving}>{assignmentSaving?"Assigning…":"Assign route +"}</button>
        </form>
        <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Train</th><th>Assigned route</th><th>Action</th></tr></thead><tbody>{(data?.train_routes||[]).map(item=><tr key={item.train_id+"-"+item.route_id}><td>{item.train_number} — {item.train_name}</td><td>{item.route_name}</td><td><button className="admin-danger-button" onClick={()=>removeAssignment(item)}>Remove assignment</button></td></tr>)}</tbody></table>{!data?.train_routes?.length&&<p className="admin-empty">No train-route assignments yet.</p>}</div>
      </>}
      {tab==="schedules" && <>
        <div className="admin-title-row"><div><p className="section-kicker">TIMETABLE & INVENTORY</p><h2>Train schedule management</h2><p>Create schedules for assigned train and route pairs, or update an existing timetable.</p></div><button onClick={loadDashboard} disabled={busy}>Refresh ↻</button></div>
        <form className="admin-schedule-form" onSubmit={saveSchedule}>
          <div><label htmlFor="schedule-train">Train</label><select id="schedule-train" value={scheduleForm.train_id} onChange={e=>setScheduleForm({...scheduleForm,train_id:e.target.value})} required><option value="">Select train</option>{(data?.trains||[]).map(train=><option key={train.train_id} value={train.train_id}>{train.train_number} — {train.train_name} ({train.train_status.toLowerCase()})</option>)}</select></div>
          <div><label htmlFor="schedule-route">Assigned route</label><select id="schedule-route" value={scheduleForm.route_id} onChange={e=>setScheduleForm({...scheduleForm,route_id:e.target.value})} required><option value="">Select route</option>{(data?.routes||[]).map(route=><option key={route.route_id} value={route.route_id}>{route.route_name} ({route.route_status.toLowerCase()})</option>)}</select></div>
          <div><label htmlFor="schedule-departure">Departure date & time</label><input id="schedule-departure" type="datetime-local" value={scheduleForm.departure_at} onChange={e=>setScheduleForm({...scheduleForm,departure_at:e.target.value})} required /></div>
          <div><label htmlFor="schedule-arrival">Arrival date & time</label><input id="schedule-arrival" type="datetime-local" value={scheduleForm.arrival_at} onChange={e=>setScheduleForm({...scheduleForm,arrival_at:e.target.value})} required /></div>
          <div><label htmlFor="schedule-status">Schedule status</label><select id="schedule-status" value={scheduleForm.schedule_status} onChange={e=>setScheduleForm({...scheduleForm,schedule_status:e.target.value})}><option value="SCHEDULED">Scheduled</option><option value="CANCELLED">Cancelled</option><option value="COMPLETED">Completed</option></select></div>
          <button type="submit" disabled={scheduleSaving}>{scheduleSaving?"Saving…":editingScheduleId?"Update schedule":"Create schedule +"}</button>
          {editingScheduleId && <button type="button" className="admin-small-button" onClick={()=>{setEditingScheduleId(null);setScheduleForm({train_id:"",route_id:"",departure_at:"",arrival_at:"",schedule_status:"SCHEDULED"});}}>Cancel edit</button>}
        </form>
        <p className="admin-form-note">Intermediate station times are estimated from route distances. Schedules with bookings can have their status updated, but their train, route and timetable are locked to protect existing tickets.</p>
        <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>ID</th><th>Train</th><th>Route</th><th>Departure</th><th>Arrival</th><th>Status</th><th>Seats</th><th>Action</th></tr></thead><tbody>{(data?.schedules||[]).map(schedule=><tr key={schedule.schedule_id}><td>{schedule.schedule_id}</td><td>{schedule.train_number} — {schedule.train_name}</td><td>{schedule.route_name}</td><td>{date(schedule.departure_at)}</td><td>{date(schedule.arrival_at)}</td><td>{schedule.schedule_status}</td><td>{schedule.available_seats}/{schedule.total_seats}</td><td><button className="admin-small-button" onClick={()=>startEditSchedule(schedule)}>Edit</button></td></tr>)}</tbody></table>{!data?.schedules?.length&&<p className="admin-empty">No train schedules found.</p>}</div>
      </>}
      {tab==="bookings" && <><p className="section-kicker">RESERVATIONS</p><h2>Bookings</h2>{rows(data?.bookings,[["pnr","PNR"],["train_name_snapshot","Train"],["full_name","Passenger"],["email","Email"],["booking_status","Status"],["passenger_count","Passengers"],["total_fare","Fare"],["created_at","Created"]])}</>}
      {tab==="cancellations" && <><p className="section-kicker">SERVICE RECORDS</p><h2>Cancellation records</h2>{rows(data?.cancellations,[["pnr","PNR"],["train_name_snapshot","Train"],["full_name","Requested by"],["cancellation_status","Status"],["passenger_items","Passengers"],["cancellation_charge","Charge"],["refund_amount","Refund"],["requested_at","Requested"]])}</>}
    </div>
    <footer className="admin-footer">Trackline Railway Reservations · Administrator workspace</footer>
  </main>;
}
