

(() => {
  // Snow must boot after <body> exists; also support pages that don't set data-user-id.
  function getUserId() {
    const body = document.body;
    const html = document.documentElement;
    const v = (body && body.dataset && body.dataset.userId) || (html && html.dataset && html.dataset.userId) || "anon";
    // Avoid weird keys like "undefined" / "null"
    return (v === "undefined" || v === "null" || v === "") ? "anon" : v;
  }

  function getKeys() {
    const uid = getUserId();
    return {
      userKey: `snow_enabled_user_${uid}`,
      globalKey: "snow_enabled"
    };
  }

  let canvas = null;
  let ctx = null;
  let rafId = null;
  let running = false;
  let enabled = true;

  // Mild snow: bigger flakes, fewer, slower
const FLAKE_COUNT = 70;
const SIZE_MIN = 0.9;
const SIZE_MAX = 2.4;
const SPEED_MIN = 0.35;
const SPEED_MAX = 1.05;

  const flakes = [];

  function ensureCanvas() {
    if (canvas) return;

    canvas = document.createElement("canvas");
    canvas.id = "snowCanvas";
    canvas.style.position = "fixed";
    canvas.style.left = "0";
    canvas.style.top = "0";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.pointerEvents = "none";

    // Behind glass panels, above wallpaper
    // wallpaper is z-index -1, content panels are default/auto -> keep snow at 0
    canvas.style.zIndex = "0";

    // Smooth fade on/off
    canvas.style.opacity = "1";
    canvas.style.transition = "opacity 260ms ease";

    document.body.appendChild(canvas);
    ctx = canvas.getContext("2d");

    resize();
    initFlakes();
    window.addEventListener("resize", resize);
  }

  function resize() {
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function rand(min, max) {
    return Math.random() * (max - min) + min;
  }

  function initFlakes() {
    flakes.length = 0;
    for (let i = 0; i < FLAKE_COUNT; i++) {
      flakes.push(makeFlake(true));
    }
  }

  function makeFlake(randomY = false) {
    const w = window.innerWidth;
    const h = window.innerHeight;
    return {
      x: rand(0, w),
      y: randomY ? rand(0, h) : rand(-h * 0.15, -10),
      r: rand(SIZE_MIN, SIZE_MAX),
      vy: rand(SPEED_MIN, SPEED_MAX),
      vx: rand(-0.12, 0.12),
      drift: rand(0.6, 1.35),
      phase: rand(0, Math.PI * 2)
    };
  }

  function step() {
    if (!running) return;

    const w = window.innerWidth;
    const h = window.innerHeight;

    ctx.clearRect(0, 0, w, h);

    // soft flake color that suits glass
    ctx.fillStyle = "rgba(255,255,255,0.62)";

    for (let i = 0; i < flakes.length; i++) {
      const f = flakes[i];

      f.phase += 0.008 * f.drift;
      f.x += f.vx + Math.sin(f.phase) * 0.18 * f.drift;
      f.y += f.vy;

      // draw
      ctx.beginPath();
      ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
      ctx.fill();

      // recycle
      if (f.y > h + 12 || f.x < -20 || f.x > w + 20) {
        flakes[i] = makeFlake(false);
      }
    }

    rafId = requestAnimationFrame(step);
  }

  function start() {
    ensureCanvas();
    if (running) return;
    running = true;
    rafId = requestAnimationFrame(step);
  }

  function stop() {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    if (ctx) ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
  }

  function setCanvasVisible(v) {
    ensureCanvas();
    canvas.style.opacity = v ? "1" : "0";
  }

  function store(v) {
    const { userKey, globalKey } = getKeys();
    const val = v ? "1" : "0";
    // Store both: per-user (preferred) + global fallback (useful on unauth pages)
    localStorage.setItem(userKey, val);
    localStorage.setItem(globalKey, val);
  }

  function readStored() {
    const { userKey, globalKey } = getKeys();
    // Prefer user-specific value; if missing (e.g., unauth page), fall back to global.
    let v = localStorage.getItem(userKey);
    if (v === null) v = localStorage.getItem(globalKey);
    return v === null ? true : v === "1";
  }

  function enable() {
    enabled = true;
    store(true);
    setCanvasVisible(true);
    start();
    return true;
  }

  function disable() {
    enabled = false;
    store(false);
    setCanvasVisible(false);
    // pause after fade to avoid “pop”
    setTimeout(() => {
      if (!enabled) stop();
    }, 280);
    return false;
  }

  function toggle() {
    return enabled ? disable() : enable();
  }

  function setEnabled(v) {
    return v ? enable() : disable();
  }

  function isEnabled() {
    return !!enabled;
  }

  // Expose API
  window.Snow = { enable, disable, toggle, setEnabled, isEnabled };

  function boot() {
    // Boot (read stored state BEFORE starting)
    enabled = readStored();
    if (enabled) {
      start();
    } else {
      ensureCanvas();
      setCanvasVisible(false);
      stop();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();