// StructOptima 3D viewer / walkthrough. Built to dist/viewer.js (npm run build).
// Input: the scene dict from src/viewer_model.build_scene (metres, Z up).
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const TYPE_COLOURS = { column: 0x2563eb, beam: 0xf59e0b, slab: 0xcbd5e1, wall: 0xd6b48c, footing: 0x78716c };
const STATUS_COLOURS = { PASS: 0x16a34a, WARN: 0xf59e0b, FAIL: 0xdc2626 };
const OTHER = 0x94a3b8;
const OPACITY = { slab: 0.55, wall: 0.35 };
const EYE = 1.6;

function el(tag, style, text) {
  const e = document.createElement(tag);
  if (style) e.style.cssText = style;
  if (text !== undefined) e.textContent = text;
  return e;
}

export function mount(root, scene) {
  root.innerHTML = "";
  const W = () => root.clientWidth || 800;
  const H = () => root.clientHeight || 600;

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(W(), H());
  renderer.localClippingEnabled = true;
  renderer.domElement.style.display = "block";
  renderer.domElement.style.touchAction = "none";
  root.appendChild(renderer.domElement);

  const s3 = new THREE.Scene();
  s3.background = new THREE.Color(0xf1f5f9);
  s3.add(new THREE.HemisphereLight(0xffffff, 0x94a3b8, 1.1));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(-30, -50, 80);
  s3.add(sun);

  const [x0, y0, x1, y1, ztop] = scene.bbox;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const span = Math.max(x1 - x0, y1 - y0, ztop, 5);

  const grid = new THREE.GridHelper(span * 2, Math.round(span * 2), 0xcbd5e1, 0xe2e8f0);
  grid.rotation.x = Math.PI / 2;
  grid.position.set(cx, cy, -0.002);
  s3.add(grid);

  const camera = new THREE.PerspectiveCamera(55, W() / H(), 0.05, span * 20);
  camera.up.set(0, 0, 1);
  const home = () => {
    camera.position.set(cx - span * 1.1, cy - span * 1.3, span * 0.9);
    orbit.target.set(cx, cy, ztop / 3);
    orbit.update();
  };
  const orbit = new OrbitControls(camera, renderer.domElement);
  orbit.enableDamping = true;

  // clipping plane: keeps everything below the cut height
  const clip = new THREE.Plane(new THREE.Vector3(0, 0, -1), ztop + 1);

  const edgeMat = new THREE.LineBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.6, clippingPlanes: [clip] });
  const unitBox = new THREE.BoxGeometry(1, 1, 1);
  const unitEdges = new THREE.EdgesGeometry(unitBox);
  const meshes = [];
  for (const it of scene.items) {
    const mat = new THREE.MeshStandardMaterial({
      roughness: 0.8, metalness: 0, clippingPlanes: [clip], side: THREE.DoubleSide,
      transparent: OPACITY[it.kind] !== undefined, opacity: OPACITY[it.kind] ?? 1, depthWrite: OPACITY[it.kind] === undefined,
    });
    const m = new THREE.Mesh(unitBox, mat);
    m.position.set(it.c[0], it.c[1], it.c[2]);
    m.scale.set(Math.max(it.s[0], 0.01), Math.max(it.s[1], 0.01), Math.max(it.s[2], 0.01));
    m.rotation.z = it.yaw;
    m.add(new THREE.LineSegments(unitEdges, edgeMat));
    m.userData = it;
    s3.add(m);
    meshes.push(m);
  }

  // ---------------------------------------------------------------- UI --
  const panelCss = "position:absolute;background:rgba(255,255,255,.95);border:1px solid #cbd5e1;border-radius:6px;" +
    "padding:8px;box-shadow:0 1px 4px rgba(0,0,0,.12);color:#0f172a";
  const bar = el("div", panelCss + ";left:8px;top:8px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;max-width:calc(100% - 40px)");
  root.style.position = "relative";
  root.appendChild(bar);

  const mkSelect = (label, opts) => {
    const w = el("label", "display:flex;gap:4px;align-items:center", label);
    const s = el("select");
    for (const [v, t] of opts) { const o = el("option", null, t); o.value = v; s.appendChild(o); }
    w.appendChild(s); bar.appendChild(w); return s;
  };
  const mkBtn = (t, title) => { const b = el("button", "cursor:pointer", t); if (title) b.title = title; bar.appendChild(b); return b; };

  const modeSel = mkSelect("View", [["orbit", "Orbit"], ["walk", "Walk-through"]]);
  const colourSel = mkSelect("Colour", [["type", "By member type"], ["status", "By design status"]]);
  const storeySel = mkSelect("Storey", [["all", "All"], ...scene.storeys.map((s, i) => [String(i), s.name])]);
  const kinds = ["column", "beam", "slab", "wall", "footing"];
  const shown = Object.fromEntries(kinds.map((k) => [k, true]));
  for (const k of kinds) {
    const w = el("label", "display:flex;gap:2px;align-items:center");
    const c = el("input"); c.type = "checkbox"; c.checked = true;
    c.onchange = () => { shown[k] = c.checked; applyVisibility(); };
    w.appendChild(c); w.appendChild(document.createTextNode(k[0].toUpperCase() + k.slice(1) + "s"));
    bar.appendChild(w);
  }
  const cutW = el("label", "display:flex;gap:4px;align-items:center", "Section cut");
  const cut = el("input"); cut.type = "range"; cut.min = "0"; cut.max = String(ztop + 1); cut.step = "0.05"; cut.value = cut.max;
  cut.style.width = "90px";
  cutW.appendChild(cut); bar.appendChild(cutW);
  const find = el("input"); find.placeholder = "Find mark (e.g. C1)"; find.size = 14; bar.appendChild(find);
  const homeBtn = mkBtn("Reset view");

  const info = el("div", panelCss + ";right:8px;bottom:8px;max-width:320px;max-height:60%;overflow:auto;display:none");
  root.appendChild(info);
  const legend = el("div", panelCss + ";left:8px;bottom:8px;font-size:12px");
  root.appendChild(legend);
  const help = el("div", panelCss + ";right:8px;top:8px;font-size:12px;display:none;margin-top:44px");
  help.innerHTML = "<b>Walk-through</b><br>W/A/S/D or arrows: move<br>Drag (mouse or finger): look around<br>" +
    "Q / E: down / up a storey<br>Shift: walk faster<br>Or use the on-screen buttons";
  root.appendChild(help);

  // on-screen walk pad (touch screens on site)
  const pad = el("div", panelCss + ";right:8px;bottom:8px;display:none;grid-template-columns:repeat(3,44px);gap:4px;user-select:none");
  const padKeys = [["", null], ["▲", "w"], ["", null], ["◀", "arrowleft"], ["▼", "s"], ["▶", "arrowright"],
                   ["Floor −", "q"], ["", null], ["Floor +", "e"]];
  for (const [label, key] of padKeys) {
    const b = el("button", "height:40px;font-size:13px;padding:0;" + (key ? "" : "visibility:hidden"), label);
    if (key === "q" || key === "e") {
      b.onclick = () => changeStorey(key === "e" ? 1 : -1);
    } else if (key) {
      b.addEventListener("pointerdown", (e) => { e.preventDefault(); keys.add(key); });
      for (const ev of ["pointerup", "pointerleave", "pointercancel"]) b.addEventListener(ev, () => keys.delete(key));
    }
    pad.appendChild(b);
  }
  root.appendChild(pad);

  // ----------------------------------------------------------- colours --
  let selected = null;
  const found = new Set();
  function colourOf(it) {
    if (colourSel.value === "status") return STATUS_COLOURS[it.status] ?? OTHER;
    return TYPE_COLOURS[it.kind] ?? OTHER;
  }
  function recolour() {
    for (const m of meshes) {
      const it = m.userData;
      m.material.color.setHex(colourOf(it));
      m.material.emissive.setHex(m === selected ? 0x7c3aed : found.has(m) ? 0x0ea5e9 : 0x000000);
      m.material.emissiveIntensity = m === selected || found.has(m) ? 0.6 : 0;
    }
    const entries = colourSel.value === "status"
      ? [["PASS", STATUS_COLOURS.PASS], ["WARN", STATUS_COLOURS.WARN], ["FAIL", STATUS_COLOURS.FAIL], ["No status", OTHER]]
      : kinds.map((k) => [k[0].toUpperCase() + k.slice(1), TYPE_COLOURS[k]]);
    legend.innerHTML = entries.map(([t, c]) =>
      `<span style="display:inline-block;width:10px;height:10px;background:#${c.toString(16).padStart(6, "0")};` +
      `margin:0 4px 0 8px;border:1px solid #475569"></span>${t}`).join("");
  }

  function applyVisibility() {
    const s = storeySel.value;
    for (const m of meshes) {
      const it = m.userData;
      // footings are below ground: hidden while walking through the storeys
      m.visible = shown[it.kind] && (s === "all" || String(it.storey) === s) &&
        !(it.kind === "footing" && modeSel.value === "walk");
    }
  }

  function showInfo(m) {
    selected = m;
    recolour();
    if (!m) { info.style.display = "none"; return; }
    const it = m.userData;
    const st = scene.storeys[it.storey]?.name ?? "";
    const statusCol = STATUS_COLOURS[it.status] ? "#" + STATUS_COLOURS[it.status].toString(16).padStart(6, "0") : "#475569";
    let h = `<div style="font-weight:600;font-size:14px">${it.props.Mark ?? it.kind} <span style="color:#64748b;font-weight:400">${it.id}</span></div>`;
    h += `<div style="color:#64748b;margin-bottom:4px">${it.kind} · ${st}</div>`;
    if (it.status) h += `<div style="color:${statusCol};font-weight:600">${it.status}</div>`;
    h += "<table style='border-collapse:collapse;margin-top:4px'>";
    for (const [k, v] of Object.entries(it.props)) {
      if (k === "Mark") continue;
      h += `<tr><td style="color:#475569;padding:1px 8px 1px 0;vertical-align:top">${k}</td><td>${v}</td></tr>`;
    }
    info.innerHTML = h + "</table>";
    info.style.display = "block";
  }

  // ------------------------------------------------------------ picking --
  const ray = new THREE.Raycaster();
  let down = null;
  renderer.domElement.addEventListener("pointerdown", (e) => { down = [e.clientX, e.clientY]; });
  renderer.domElement.addEventListener("pointerup", (e) => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
    const r = renderer.domElement.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    const cutZ = parseFloat(cut.value);
    const hit = ray.intersectObjects(meshes.filter((m) => m.visible), false).find((h) => h.point.z <= cutZ + 1e-6);
    showInfo(hit ? hit.object : null);
  });

  find.addEventListener("input", () => {
    const q = find.value.trim().toUpperCase();
    found.clear();
    if (q) for (const m of meshes) if (String(m.userData.props.Mark ?? "").toUpperCase() === q) found.add(m);
    recolour();
  });

  // --------------------------------------------------------- walk mode --
  let yaw = 0, pitch = 0, walkStorey = 0, dragging = false, last = null;
  const keys = new Set();
  function changeStorey(step) {
    walkStorey = Math.max(0, Math.min(scene.storeys.length - 1, walkStorey + step));
    camera.position.z = scene.storeys[walkStorey].z0 + EYE;
  }
  function startWalk() {
    orbit.enabled = false;
    help.style.display = "block";
    pad.style.display = "grid";
    info.style.bottom = "150px";
    walkStorey = storeySel.value === "all" ? 0 : parseInt(storeySel.value, 10);
    camera.position.set(x0 - 2, cy, scene.storeys[walkStorey].z0 + EYE);
    yaw = 0; pitch = 0;
    applyLook();
    renderer.domElement.tabIndex = 0;
    renderer.domElement.focus();
  }
  function stopWalk() { help.style.display = "none"; pad.style.display = "none"; info.style.bottom = "8px"; orbit.enabled = true; home(); }
  function applyLook() {
    const d = new THREE.Vector3(Math.cos(pitch) * Math.cos(yaw), Math.cos(pitch) * Math.sin(yaw), Math.sin(pitch));
    camera.lookAt(camera.position.clone().add(d));
  }
  renderer.domElement.addEventListener("pointerdown", (e) => { if (modeSel.value === "walk") { dragging = true; last = [e.clientX, e.clientY]; } });
  window.addEventListener("pointerup", () => { dragging = false; });
  window.addEventListener("pointermove", (e) => {
    if (!dragging || modeSel.value !== "walk") return;
    yaw -= (e.clientX - last[0]) * 0.004;
    pitch = Math.max(-1.4, Math.min(1.4, pitch - (e.clientY - last[1]) * 0.004));
    last = [e.clientX, e.clientY];
    applyLook();
  });
  const keyTarget = renderer.domElement;
  keyTarget.addEventListener("keydown", (e) => {
    if (modeSel.value !== "walk") return;
    const k = e.key.toLowerCase();
    if (k === "q" || k === "e") changeStorey(k === "e" ? 1 : -1);
    else keys.add(k);
    if (k.startsWith("arrow") || k === " ") e.preventDefault();
  });
  keyTarget.addEventListener("keyup", (e) => keys.delete(e.key.toLowerCase()));
  keyTarget.addEventListener("blur", () => keys.clear());

  modeSel.onchange = () => { (modeSel.value === "walk" ? startWalk() : stopWalk()); applyVisibility(); };
  colourSel.onchange = recolour;
  storeySel.onchange = applyVisibility;
  cut.oninput = () => { clip.constant = parseFloat(cut.value); };
  homeBtn.onclick = () => { if (modeSel.value === "walk") startWalk(); else home(); };

  // --------------------------------------------------------------- loop --
  const clock = new THREE.Clock();
  function tick() {
    const dt = Math.min(clock.getDelta(), 0.1);
    if (modeSel.value === "walk" && keys.size) {
      const v = (keys.has("shift") ? 6 : 2.5) * dt;
      const f = new THREE.Vector3(Math.cos(yaw), Math.sin(yaw), 0), r = new THREE.Vector3(Math.sin(yaw), -Math.cos(yaw), 0);
      if (keys.has("w") || keys.has("arrowup")) camera.position.addScaledVector(f, v);
      if (keys.has("s") || keys.has("arrowdown")) camera.position.addScaledVector(f, -v);
      if (keys.has("d")) camera.position.addScaledVector(r, v);
      if (keys.has("a")) camera.position.addScaledVector(r, -v);
      if (keys.has("arrowleft")) yaw += 1.5 * dt;
      if (keys.has("arrowright")) yaw -= 1.5 * dt;
      applyLook();
    }
    if (orbit.enabled) orbit.update();
    renderer.render(s3, camera);
    requestAnimationFrame(tick);
  }
  window.addEventListener("resize", () => {
    renderer.setSize(W(), H());
    camera.aspect = W() / H();
    camera.updateProjectionMatrix();
  });

  home();
  recolour();
  applyVisibility();
  tick();
  return { meshes, camera };
}
