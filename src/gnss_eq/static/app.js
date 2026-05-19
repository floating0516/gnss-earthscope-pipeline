const state = {
  config: null,
  map: null,
  mapReady: false,
  events: [],
  selectedEvent: null,
  selectedJobId: null,
};

const $ = (id) => document.getElementById(id);

async function apiGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  });
  const response = await fetch(url);
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

async function apiPost(path, body = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

async function apiText(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value));
  const response = await fetch(url);
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.text();
}

async function errorMessage(response) {
  try {
    const payload = await response.json();
    return payload.detail || response.statusText;
  } catch {
    return response.statusText;
  }
}

function initMap() {
  state.map = new maplibregl.Map({
    container: "map",
    style: "https://tiles.openfreemap.org/styles/bright",
    center: [-160, 5],
    zoom: 2.05,
    minZoom: 1,
    maxZoom: 12,
    bearing: 0,
    pitch: 0,
    attributionControl: false,
  });
  state.map.addControl(new maplibregl.NavigationControl({ visualizePitch: false, showCompass: true }), "bottom-right");
  state.map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");
  state.map.on("load", () => {
    state.mapReady = true;
    addMapSourcesAndLayers();
    renderEvents();
  });
  state.map.on("click", "earthquake-points", (event) => {
    const feature = event.features?.[0];
    if (feature?.properties?.event_id) selectEvent(feature.properties.event_id).catch(showError);
  });
  state.map.on("mouseenter", "earthquake-points", () => state.map.getCanvas().style.cursor = "pointer");
  state.map.on("mouseleave", "earthquake-points", () => state.map.getCanvas().style.cursor = "");
}

function addMapSourcesAndLayers() {
  state.map.addSource("earthquakes", { type: "geojson", data: emptyFeatureCollection() });
  state.map.addSource("stations", { type: "geojson", data: emptyFeatureCollection() });
  state.map.addSource("radius-ring", { type: "geojson", data: emptyFeatureCollection() });

  state.map.addLayer({
    id: "radius-fill",
    type: "fill",
    source: "radius-ring",
    paint: {
      "fill-color": "#ffbe5c",
      "fill-opacity": 0.06,
    },
  });
  state.map.addLayer({
    id: "radius-line",
    type: "line",
    source: "radius-ring",
    paint: {
      "line-color": "#ffbe5c",
      "line-width": 2,
      "line-opacity": 0.8,
      "line-dasharray": [2, 2],
    },
  });
  state.map.addLayer({
    id: "station-points-glow",
    type: "circle",
    source: "stations",
    paint: {
      "circle-radius": 9,
      "circle-color": "#63f7c4",
      "circle-opacity": 0.16,
      "circle-blur": 0.8,
    },
  });
  state.map.addLayer({
    id: "station-points",
    type: "circle",
    source: "stations",
    paint: {
      "circle-radius": 4,
      "circle-color": "#63f7c4",
      "circle-stroke-color": "#e5fff6",
      "circle-stroke-width": 1,
      "circle-opacity": 0.96,
    },
  });
  state.map.addLayer({
    id: "earthquake-points-glow",
    type: "circle",
    source: "earthquakes",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["get", "magnitude"], 5, 14, 7, 26, 9, 42],
      "circle-color": "#ff6b5c",
      "circle-opacity": 0.22,
      "circle-blur": 0.65,
    },
  });
  state.map.addLayer({
    id: "earthquake-points",
    type: "circle",
    source: "earthquakes",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["get", "magnitude"], 5, 5, 7, 10, 9, 18],
      "circle-color": ["interpolate", ["linear"], ["get", "magnitude"], 5, "#ffbe5c", 7, "#ff8a5c", 9, "#ff4d5c"],
      "circle-stroke-color": "#fff7df",
      "circle-stroke-width": 1.5,
      "circle-opacity": 0.96,
    },
  });
}

function emptyFeatureCollection() {
  return { type: "FeatureCollection", features: [] };
}

function setSourceData(sourceId, data) {
  if (!state.mapReady) return;
  const source = state.map.getSource(sourceId);
  if (source) source.setData(data);
}

function eventFeatureCollection(events) {
  return {
    type: "FeatureCollection",
    features: events
      .filter((event) => event.latitude != null && event.longitude != null)
      .map((event) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [Number(event.longitude), Number(event.latitude)] },
        properties: {
          event_id: event.event_id,
          magnitude: Number(event.magnitude || 0),
          place: event.place || "",
          time_utc: event.time_utc || event.event_date || "",
        },
      })),
  };
}

function stationFeatureCollection(stations) {
  return {
    type: "FeatureCollection",
    features: stations
      .filter((station) => station.latitude != null && station.longitude != null)
      .map((station) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [Number(station.longitude), Number(station.latitude)] },
        properties: {
          station: station.station,
          distance_km: Number(station.distance_km || 0),
        },
      })),
  };
}

function circleFeature(longitude, latitude, radiusKm, steps = 128) {
  const coords = [];
  const lat = Number(latitude);
  const lon = Number(longitude);
  const angularDistance = Number(radiusKm) / 6371;
  const latRad = toRadians(lat);
  const lonRad = toRadians(lon);
  for (let i = 0; i <= steps; i += 1) {
    const bearing = (i / steps) * Math.PI * 2;
    const pointLat = Math.asin(
      Math.sin(latRad) * Math.cos(angularDistance) +
      Math.cos(latRad) * Math.sin(angularDistance) * Math.cos(bearing)
    );
    const pointLon = lonRad + Math.atan2(
      Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latRad),
      Math.cos(angularDistance) - Math.sin(latRad) * Math.sin(pointLat)
    );
    coords.push([normalizeLongitude(toDegrees(pointLon)), toDegrees(pointLat)]);
  }
  return {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [coords] },
      properties: {},
    }],
  };
}

function toRadians(value) { return value * Math.PI / 180; }
function toDegrees(value) { return value * 180 / Math.PI; }
function normalizeLongitude(value) { return ((value + 540) % 360) - 180; }
function nearestWrappedLongitude(longitude, referenceLongitude) {
  let wrapped = longitude;
  while (wrapped - referenceLongitude > 180) wrapped -= 360;
  while (referenceLongitude - wrapped > 180) wrapped += 360;
  return wrapped;
}

function renderEvents() {
  setSourceData("earthquakes", eventFeatureCollection(state.events));
  renderEventList();
  if (state.events.length && state.mapReady) {
    const bounds = coordinateBounds(state.events);
    if (bounds) state.map.fitBounds(bounds, { padding: 54, maxZoom: 5, duration: 850 });
  }
}

function coordinateBounds(items) {
  const coords = items
    .filter((item) => item.latitude != null && item.longitude != null)
    .map((item) => [Number(item.longitude), Number(item.latitude)]);
  if (!coords.length) return null;
  const bounds = new maplibregl.LngLatBounds(coords[0], coords[0]);
  coords.slice(1).forEach((coord) => bounds.extend(coord));
  return bounds;
}

function renderEventList() {
  $("result-count").textContent = state.events.length;
  $("event-list").innerHTML = state.events.map((event) => `
    <article class="event-item ${state.selectedEvent?.event_id === event.event_id ? "active" : ""}" data-event-id="${escapeHtml(event.event_id)}">
      <strong>${escapeHtml(event.event_id)} · M${escapeHtml(event.magnitude ?? "?")}</strong>
      <span>${escapeHtml(event.place || "未知地点")}</span>
      <span>${escapeHtml(event.time_utc || event.event_date || "")}</span>
      <span>已有数据：${escapeHtml(event.existing_data_status || "无记录")}</span>
    </article>
  `).join("");
  document.querySelectorAll(".event-item").forEach((node) => {
    node.addEventListener("click", () => selectEvent(node.dataset.eventId));
  });
}

function renderStations(stations) {
  setSourceData("stations", stationFeatureCollection(stations));
  if (state.selectedEvent?.latitude != null && state.selectedEvent?.longitude != null) {
    setSourceData(
      "radius-ring",
      circleFeature(state.selectedEvent.longitude, state.selectedEvent.latitude, Number($("radius-km").value || 200))
    );
  } else {
    setSourceData("radius-ring", emptyFeatureCollection());
  }
}

async function loadHealth() {
  const health = await apiGet("/api/health");
  const pill = $("health-pill");
  pill.textContent = health.db_exists ? (health.workflow_enabled ? "DB OK · 可运行" : "DB OK · 只读") : "DB 缺失";
  pill.className = `pill ${health.db_exists ? "ok" : "warn"}`;
  $("run-btn").disabled = !state.selectedEvent || !health.workflow_enabled;
}

async function searchEvents() {
  setConsole("preview-box", "正在查询本地 SQLite 数据库……");
  const hasExisting = $("has-existing").checked ? true : undefined;
  const payload = await apiGet("/api/events", {
    q: $("search-q").value,
    min_magnitude: $("min-mag").value,
    start_date: $("start-date").value,
    end_date: $("end-date").value,
    has_existing_data: hasExisting,
    limit: $("limit").value,
  });
  state.events = payload.items;
  state.selectedEvent = null;
  renderEvents();
  clearSelection();
  setConsole("preview-box", `找到 ${payload.total} 个事件，地图上显示 ${payload.items.length} 个。`);
}

async function selectEvent(eventId) {
  const detail = await apiGet(`/api/events/${encodeURIComponent(eventId)}`);
  state.selectedEvent = detail.event;
  renderEventList();
  $("selected-title").textContent = `${detail.event.event_id} · ${detail.event.place || "未知地点"}`;
  $("selected-meta").innerHTML = metaHtml(detail);
  const badge = $("existing-badge");
  const existing = detail.existing_data?.status || "无本地归档记录";
  badge.textContent = `本地数据：${existing}`;
  badge.className = `status-badge ${detail.existing_data?.status ? "ok" : "muted"}`;
  $("preview-btn").disabled = false;
  $("run-btn").disabled = !(state.config?.workflow_enabled);
  const stations = await apiGet(`/api/events/${encodeURIComponent(eventId)}/stations`, {
    radius_km: $("radius-km").value,
    limit: $("max-stations").value,
  });
  renderStations(stations.items);
  if (detail.event.latitude != null && detail.event.longitude != null && state.mapReady) {
    const longitude = nearestWrappedLongitude(Number(detail.event.longitude), state.map.getCenter().lng);
    state.map.easeTo({
      center: [longitude, Number(detail.event.latitude)],
      zoom: 6,
      bearing: 0,
      pitch: 0,
      duration: 700,
    });
  }
}

function metaHtml(detail) {
  const event = detail.event;
  const candidates = Object.entries(detail.candidate_counts || {}).map(([radius, count]) => `${radius}km: ${count}`).join(" · ") || "0";
  return [
    ["时间", event.time_utc || event.event_date || ""],
    ["震级", event.magnitude ?? ""],
    ["坐标", `${event.latitude ?? "?"}, ${event.longitude ?? "?"}`],
    ["深度", `${event.depth_km ?? "?"} km`],
    ["候选站", candidates],
    ["验证文件", `${detail.verified_station_count || 0} 站 / ${detail.verified_file_count || 0} 文件`],
  ].map(([label, value]) => `<div class="meta"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
}

function clearSelection() {
  $("selected-title").textContent = "尚未选择事件";
  $("selected-meta").innerHTML = "";
  $("existing-badge").textContent = "等待查询";
  $("existing-badge").className = "status-badge muted";
  $("preview-btn").disabled = true;
  $("run-btn").disabled = true;
  setSourceData("stations", emptyFeatureCollection());
  setSourceData("radius-ring", emptyFeatureCollection());
}

function workflowPayload() {
  if (!state.selectedEvent) throw new Error("请先选择一个事件");
  return {
    event_id: state.selectedEvent.event_id,
    radius_km: Number($("radius-km").value),
    max_stations: Number($("max-stations").value),
    include_existing: $("include-existing").checked,
  };
}

async function previewWorkflow() {
  const payload = await apiPost("/api/workflows/preview", workflowPayload());
  setConsole("preview-box", JSON.stringify(payload, null, 2));
}

async function runWorkflow() {
  const payload = {
    ...workflowPayload(),
    timeout: Number($("timeout").value),
    base_url: $("base-url").value,
    api_key: $("api-key").value,
  };
  const response = await apiPost("/api/workflows/run", payload);
  state.selectedJobId = response.job_id;
  setConsole("preview-box", `工作流已启动：${response.job_id}`);
  await loadJobs();
}

async function loadJobs() {
  const payload = await apiGet("/api/jobs");
  $("jobs-list").innerHTML = payload.items.map((job) => `
    <div class="job-item" data-job-id="${escapeHtml(job.job_id)}">
      <strong>${escapeHtml(job.status)} · ${escapeHtml(job.event_id)}</strong>
      <span>${escapeHtml(job.started_at)} · ${escapeHtml(job.job_id)}</span>
    </div>
  `).join("") || '<div class="job-item"><span>暂无网页端启动的 job。</span></div>';
  document.querySelectorAll(".job-item[data-job-id]").forEach((node) => {
    node.addEventListener("click", () => {
      state.selectedJobId = node.dataset.jobId;
      loadLogs();
    });
  });
  if (!state.selectedJobId && payload.items.length) state.selectedJobId = payload.items[0].job_id;
  if (state.selectedJobId) await loadLogs();
}

async function loadLogs() {
  if (!state.selectedJobId) return;
  const text = await apiText(`/api/jobs/${encodeURIComponent(state.selectedJobId)}/logs`, { tail: 240 });
  $("log-box").textContent = text || "日志尚未写入。";
}

function setConsole(id, text) {
  $(id).textContent = text;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function wireEvents() {
  $("search-btn").addEventListener("click", () => searchEvents().catch(showError));
  $("preview-btn").addEventListener("click", () => previewWorkflow().catch(showError));
  $("run-btn").addEventListener("click", () => runWorkflow().catch(showError));
  $("radius-km").addEventListener("change", () => {
    if (state.selectedEvent) selectEvent(state.selectedEvent.event_id).catch(showError);
  });
  $("base-url").addEventListener("change", () => localStorage.setItem("gnss-eq-base-url", $("base-url").value));
}

function showError(error) {
  setConsole("preview-box", `错误：${error.message}`);
}

async function boot() {
  state.config = await apiGet("/api/config");
  $("base-url").value = localStorage.getItem("gnss-eq-base-url") || state.config.default_base_url || "";
  initMap();
  wireEvents();
  await loadHealth();
  await loadJobs();
  setInterval(() => loadJobs().catch(() => {}), 5000);
}

boot().catch(showError);
