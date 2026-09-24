#!/usr/bin/env node
/*
 * record-demos.mjs — graba los GIF de la galería "Demos en vivo" del README
 * (assets/demos/*.gif, 480x300, en bucle).
 *
 * Cómo funciona: abre cada demo publicada en GitHub Pages con Chromium
 * (Playwright), CONGELA el reloj de la página (requestAnimationFrame,
 * performance.now, animaciones/transiciones CSS vía Web Animations y SMIL) y lo
 * avanza a mano fotograma a fotograma, con una captura PNG por paso. El
 * resultado es fluido y reproducible aunque la máquina no llegue a 60 fps
 * (WebGL por software incluido). Después ffmpeg monta cada GIF: escala a
 * 480x300, paleta propia por GIF y, en las demos que no tienen principio ni
 * fin, un fundido entre el final y el principio para que el bucle no dé salto.
 *
 * Requisitos:
 *   - Node 18+ y conexión a internet (graba las demos en vivo).
 *   - ffmpeg con palettegen/paletteuse/xfade en el PATH (o FFMPEG=/ruta/ffmpeg).
 *   - Playwright con su Chromium. El repo no tiene package.json: instálalo
 *     fuera, por ejemplo junto al repo, y pásale la ruta:
 *       npm i --prefix ../.record-demos playwright
 *       node ../.record-demos/node_modules/playwright/cli.js install chromium
 *     (vale cualquier versión; si ya tienes uno instalado, usa esa ruta).
 *
 * Uso (desde la raíz del repo):
 *   node scripts/record-demos.mjs --playwright=../.record-demos/node_modules/playwright
 *     graba los 6 GIF (en vez de --playwright= vale la variable PLAYWRIGHT_MODULE,
 *     o nada si `playwright` se resuelve desde scripts/).
 *   Opciones: nombres de demo para grabar solo esas (p. ej. `aurora easing`),
 *   --frames-dir=carpeta para conservar los PNG intermedios, --no-gpu para
 *   forzar WebGL por software.
 *
 * Para cambiar encuadre, duración o guion de una demo, edita su entrada en DEMOS.
 */

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT_DIR = path.join(ROOT, 'assets', 'demos');
const BASE = 'https://alebrito124356.github.io';
const FFMPEG = process.env.FFMPEG || 'ffmpeg';

// El GIF guarda los retardos en centésimas: 70 ms (7 cs) por fotograma da
// 14,29 fps exactos, sin el redondeo que tendrían 15 fps (6,67 cs).
const FRAME_MS = 70;
const OUT_W = 480;
const OUT_H = 300;

/* ------------------------------------------------------------------------ */
/* Reloj virtual: se inyecta antes que cualquier script de la página.        */
/* ------------------------------------------------------------------------ */
function virtualTimeShim() {
  if (window.__vt) return;
  const vt = {
    now: 0,
    nextId: 1,
    raf: new Map(),
    anims: new WeakMap(),
    smil: new WeakMap(),
  };
  Object.defineProperty(window, '__vt', { value: vt });

  // rAF y performance.now solo avanzan cuando el grabador llama a tick().
  window.requestAnimationFrame = (cb) => {
    const id = vt.nextId++;
    vt.raf.set(id, cb);
    return id;
  };
  window.cancelAnimationFrame = (id) => { vt.raf.delete(id); };
  const now = () => vt.now;
  try { Performance.prototype.now = now; } catch { /* sigue con la instancia */ }
  try { performance.now = now; } catch { /* sin override */ }

  // Una ronda de rAF en el nuevo instante virtual.
  vt.tick = (ms) => {
    vt.now += ms;
    const callbacks = [...vt.raf.values()];
    vt.raf.clear();
    for (const cb of callbacks) {
      try { cb(vt.now); } catch (err) { console.error(err); }
    }
  };

  // Animaciones y transiciones CSS (y WAAPI): cada una arranca en el instante
  // virtual en que aparece y se coloca a mano en su tiempo local.
  // SMIL: cada <svg> raíz se pausa y se lleva al mismo reloj.
  vt.sync = () => {
    for (const a of document.getAnimations()) {
      let start = vt.anims.get(a);
      if (start === undefined) {
        start = vt.now;
        vt.anims.set(a, start);
      }
      try {
        if (a.playState !== 'paused') a.pause();
        a.currentTime = vt.now - start;
      } catch { /* animación sin efecto o ya cancelada */ }
    }
    for (const svg of document.querySelectorAll('svg')) {
      if (svg.ownerSVGElement || typeof svg.setCurrentTime !== 'function') continue;
      if (!vt.smil.has(svg)) {
        vt.smil.set(svg, vt.now);
        svg.pauseAnimations();
      }
      svg.setCurrentTime((vt.now - vt.smil.get(svg)) / 1000);
    }
  };
}

/* ------------------------------------------------------------------------ */
/* Utilidades de guion                                                       */
/* ------------------------------------------------------------------------ */
const easeInOut = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

// Interpola una lista de [ms, valor] con ease-in-out entre puntos.
function keyframes(points, t) {
  if (t <= points[0][0]) return points[0][1];
  for (let i = 1; i < points.length; i++) {
    const [t1, v1] = points[i];
    const [t0, v0] = points[i - 1];
    if (t <= t1) return v0 + (v1 - v0) * easeInOut((t - t0) / (t1 - t0));
  }
  return points[points.length - 1][1];
}

async function centerOf(page, selector) {
  const box = await page.evaluate((sel) => {
    const r = document.querySelector(sel).getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  }, selector);
  return box;
}

const heroReady = () => !!document.querySelector('#scene') && window.__vt.raf.size > 0;

/* ------------------------------------------------------------------------ */
/* Las 6 demos                                                               */
/*   viewport/clip: en píxeles CSS; el clip debe ser 16:10 (sale a 480x300).  */
/*   seconds: duración del GIF. crossfade: segundos extra que se funden con   */
/*   el principio para cerrar el bucle (0 = el guion ya cierra solo);        */
/*   transition: tipo de xfade de ese cierre (por defecto 'fade').           */
/*   speed: velocidad del reloj virtual respecto al real.                    */
/*   maxTick: paso máximo de rAF (los heros de three.js recortan delta a    */
/*   100 ms, así que se avanza en subpasos).                                 */
/*   setup(ctx): antes del primer fotograma. frame(ctx): antes de cada uno.  */
/*   gif: opciones de ffmpeg (scale, dither, statsMode, maxColors).          */
/* ------------------------------------------------------------------------ */
const DEMOS = [
  {
    name: 'aurora',
    url: `${BASE}/threejs-hero-collection/aurora.html`,
    shows: 'hero con aurora en GLSL (fbm) moviéndose detrás del texto',
    viewport: { width: 960, height: 600 },
    clip: { x: 0, y: 0, width: 960, height: 600 },
    seconds: 3.3,
    crossfade: 0.6,
    speed: 2, // a 1x la aurora apenas se mueve en 4 s
    maxTick: 70,
    ready: heroReady,
    // Entre t = 56 s y 64 s las cortinas cubren izquierda y centro (barrido de
    // 0 a 110 s con capturas de prueba, en GPU). Ojo: el hash con sin() del
    // shader no es portable, así que con --no-gpu (SwiftShader) el dibujo de
    // la aurora sale distinto y más tenue, aunque igual de fluido.
    setup: async ({ vt }) => { await vt.advance(56_000); },
    // Todo el fondo cambia en cada fotograma: 64 colores bastan (degradados
    // azules oscuros) y dejan el GIF por debajo de 1,2 MB.
    gif: { scale: 'area', dither: 'bayer:bayer_scale=5', statsMode: 'full', maxColors: 64 },
  },
  {
    name: 'particles',
    url: `${BASE}/threejs-hero-collection/particles.html`,
    shows: 'campo de 2.000 partículas con parallax: el puntero describe una elipse',
    viewport: { width: 960, height: 600 },
    clip: { x: 0, y: 0, width: 960, height: 600 },
    seconds: (57 * FRAME_MS) / 1000, // 3,99 s: un número entero de fotogramas
    crossfade: 0.5,
    speed: 1.5,
    maxTick: 50,
    ready: heroReady,
    // Una vuelta de puntero por bucle (periodo = duración exacta del GIF); se
    // da una vuelta completa antes de grabar para que la cámara, que persigue
    // al puntero con suavizado, ya esté en régimen periódico.
    pointer(t) {
      const a = (2 * Math.PI * t) / (this.seconds * 1000);
      return { x: 480 + 330 * Math.cos(a), y: 300 + 190 * Math.sin(a) };
    },
    async setup({ page, vt, demo }) {
      for (let t = 0; t < demo.seconds * 1000; t += FRAME_MS) {
        const p = demo.pointer(t);
        await page.mouse.move(p.x, p.y);
        await vt.advance(FRAME_MS * demo.speed);
      }
    },
    async frame({ page, t, demo }) {
      const p = demo.pointer(t);
      await page.mouse.move(p.x, p.y);
    },
    // 'area' y no lanczos: el anillo de lanczos alrededor de cada punto
    // triplicaba el peso del GIF (1,35 MB -> 0,4 MB) sin ganar nitidez.
    gif: { scale: 'area', dither: 'bayer:bayer_scale=4', statsMode: 'diff', maxColors: 128 },
  },
  {
    name: 'easing',
    url: `${BASE}/easing-playground/`,
    shows: 'se eligen tres curvas (ease-out-expo, ease-in-out-expo, back-in-out) y cada clic lanza la bola sobre la curva y las transiciones CSS reales',
    viewport: { width: 1280, height: 960 },
    clip: { x: 32, y: 158, width: 1216, height: 760 },
    // 3 ciclos idénticos de 19 fotogramas (clic + 900 ms de vuelo + pausa):
    // el último acaba donde empieza el primero, así que el bucle cierra solo.
    seconds: (3 * 19 * FRAME_MS) / 1000,
    crossfade: 0,
    speed: 1,
    maxTick: 1000 / 60,
    cycle: ['ease-out-expo', 'ease-in-out-expo', 'back-in-out'],
    async setup({ page, vt, demo }) {
      await page.evaluate(() => {
        const s = document.getElementById('durationSlider');
        s.value = '900';
        s.dispatchEvent(new Event('input', { bubbles: true }));
      });
      // Deja la última curva del ciclo reproducida (estado final = inicial).
      const last = demo.cycle[demo.cycle.length - 1];
      const p = await centerOf(page, `.easing-item[data-id="${last}"]`);
      await page.mouse.click(p.x, p.y);
      await vt.advance(1500);
    },
    async frame({ page, i, demo }) {
      if (i % 19 !== 0) return;
      const id = demo.cycle[i / 19];
      const p = await centerOf(page, `.easing-item[data-id="${id}"]`);
      await page.mouse.click(p.x, p.y);
    },
    gif: { dither: 'bayer:bayer_scale=4', statsMode: 'diff' },
  },
  {
    // Primer plano de un solo efecto: los loaders (unos 12 px a 248 px) y la
    // cuadrícula completa de texto (24 px -> 8 px) no se leían en la galería.
    // El brillo se mueve todo el ciclo (el revelado por palabras se queda quieto
    // el 75 % del tiempo). Ciclo de 3 s: 43 fotogramas x 70 ms cierran el bucle.
    name: 'css-text',
    url: `${BASE}/css-animation-cookbook/text.html`,
    shows: 'brillo en degradado que recorre el titular (background-clip: text)',
    viewport: { width: 1280, height: 1040 },
    clip: { x: 121, y: 406, width: 304, height: 190 },
    seconds: 3.01,
    crossfade: 0,
    speed: 1,
    maxTick: 1000 / 60,
    gif: { dither: 'bayer:bayer_scale=4', statsMode: 'diff' },
  },
  {
    // Se graba charts.html y no line-art.html: a ~250 px los trazos finos de
    // line-art casi desaparecen, y las barras, el anillo y la línea de charts
    // se leen de un vistazo. (Para volver a line-art.html: clip { x: 40, y: 234,
    // width: 1200, height: 750 } y mover el ratón a '.hovercard' en t = 1050 ms.)
    name: 'svg-charts',
    url: `${BASE}/svg-animation-lab/charts.html`,
    shows: 'charts que se dibujan al cargar: barras SMIL escalonadas, línea que se traza con su área, anillo al 72 % y sparkline con pulso',
    viewport: { width: 1280, height: 1000 },
    clip: { x: 100, y: 222, width: 1080, height: 675 },
    seconds: 4.2,
    crossfade: 0.6,
    speed: 1,
    maxTick: 1000 / 60,
    gif: { dither: 'bayer:bayer_scale=4', statsMode: 'diff' },
  },
  {
    name: 'scroll-story',
    url: `${BASE}/scroll-story-lab/pinned-scenes.html`,
    shows: 'scroll a tirones por la escena fijada: el escenario sticky se queda quieto mientras la barra avanza y los tres pasos se funden',
    viewport: { width: 960, height: 600 },
    clip: { x: 0, y: 0, width: 960, height: 600 },
    seconds: 4.1,
    // El final (paso 3) y el principio no se parecen: en vez de superponerlos,
    // el bucle cierra con un fundido rápido a negro.
    crossfade: 0.42,
    transition: 'fadeblack',
    speed: 1,
    maxTick: 1000 / 60,
    async setup({ page, demo }) {
      demo.geo = await page.evaluate(() => {
        const r = document.getElementById('scene').getBoundingClientRect();
        return { top: r.top + scrollY, runway: r.height - innerHeight, vh: innerHeight };
      });
    },
    scrollAt(t) {
      const { top, runway, vh } = this.geo;
      const y = (progress) => top + progress * runway;
      return keyframes([
        [0, top - 0.45 * vh], // el escenario entra desde abajo
        [600, top - 0.45 * vh],
        [1300, y(0.15)], // fijado, paso 1
        [1700, y(0.15)],
        [2400, y(0.5)], // paso 2
        [2800, y(0.5)],
        [3500, y(0.86)], // paso 3
      ], t);
    },
    async frame({ page, t, demo }) {
      await page.evaluate((top) => {
        window.scrollTo({ top, behavior: 'instant' });
        window.dispatchEvent(new Event('scroll'));
        window.__vt.tick(0); // el rAF de la página lee el scroll en este mismo instante
      }, Math.round(demo.scrollAt(t)));
    },
    gif: { dither: 'bayer:bayer_scale=4', statsMode: 'diff' },
  },
];

/* ------------------------------------------------------------------------ */
/* Grabación                                                                  */
/* ------------------------------------------------------------------------ */
function loadPlaywright(explicit) {
  const custom = explicit || process.env.PLAYWRIGHT_MODULE;
  const candidates = custom ? [path.resolve(custom)] : ['playwright', 'playwright-core'];
  for (const id of candidates) {
    try { return require(id); } catch { /* siguiente */ }
  }
  console.error(`No encuentro Playwright${custom ? ` en ${path.resolve(custom)}` : ''}.\n` +
    'Mira la cabecera de scripts/record-demos.mjs para instalarlo sin tocar el repo.');
  process.exit(1);
}

function controller(page, maxTick) {
  return {
    sync: () => page.evaluate(() => window.__vt.sync()),
    // Avanza `ms` de reloj virtual en subpasos de como mucho `maxTick`.
    advance: (ms) => page.evaluate(([total, max]) => {
      const n = Math.max(1, Math.ceil(total / max - 1e-6));
      for (let k = 0; k < n; k++) {
        window.__vt.tick(total / n);
        window.__vt.sync();
      }
    }, [ms, maxTick]),
  };
}

async function record(browser, demo, framesDir) {
  const context = await browser.newContext({
    viewport: demo.viewport,
    deviceScaleFactor: 1,
    reducedMotion: 'no-preference',
    colorScheme: 'dark',
  });
  await context.addInitScript(virtualTimeShim);
  const page = await context.newPage();
  page.on('pageerror', (err) => console.warn(`  [${demo.name}] error en la página: ${err.message}`));

  await page.goto(demo.url, { waitUntil: 'load', timeout: 60_000 });
  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
  await page.evaluate(async () => { await document.fonts.ready; });
  // polling por intervalo: el rAF de la página está congelado a propósito.
  if (demo.ready) await page.waitForFunction(demo.ready, null, { polling: 100, timeout: 30_000 });

  const vt = controller(page, demo.maxTick);
  await vt.sync(); // congela ya las animaciones CSS en t = 0
  if (demo.setup) await demo.setup({ page, vt, demo });

  const total = Math.round(((demo.seconds + demo.crossfade) * 1000) / FRAME_MS);
  for (let i = 0; i < total; i++) {
    const t = i * FRAME_MS;
    if (demo.frame) await demo.frame({ page, vt, demo, i, t });
    await vt.sync();
    await page.screenshot({
      path: path.join(framesDir, `f_${String(i).padStart(4, '0')}.png`),
      clip: demo.clip,
    });
    await vt.advance(FRAME_MS * demo.speed);
  }
  await context.close();
  return total;
}

/* ------------------------------------------------------------------------ */
/* Montaje del GIF                                                           */
/* ------------------------------------------------------------------------ */
function encodeGif(demo, framesDir, captured, outFile) {
  const fade = Math.round((demo.crossfade * 1000) / FRAME_MS);
  const frames = captured - fade;
  const sec = (n) => ((n * FRAME_MS) / 1000).toFixed(3);
  const { dither = 'bayer:bayer_scale=4', statsMode = 'diff', maxColors = 256, scale = 'lanczos' } = demo.gif || {};

  // Bucle sin salto: se reproduce [fade, captured) y los últimos `fade`
  // fotogramas se funden con los `fade` primeros.
  const head = fade > 0
    ? `[0:v]format=gbrp,split=2[a][b];` +
      `[a]trim=start_frame=${fade},setpts=PTS-STARTPTS[a1];` +
      `[b]trim=end_frame=${fade},setpts=PTS-STARTPTS[b1];` +
      `[a1][b1]xfade=transition=${demo.transition || 'fade'}:duration=${sec(fade)}:offset=${sec(frames - fade)}[v];[v]`
    : '[0:v]format=gbrp,';
  const graph = head +
    `scale=${OUT_W}:${OUT_H}:flags=${scale},split[s0][s1];` +
    `[s0]palettegen=max_colors=${maxColors}:stats_mode=${statsMode}[p];` +
    `[s1][p]paletteuse=dither=${dither}:diff_mode=rectangle`;

  const args = ['-y', '-v', 'error', '-framerate', '100/7', '-i', path.join(framesDir, 'f_%04d.png'),
    '-filter_complex', graph, '-loop', '0', outFile];
  const res = spawnSync(FFMPEG, args, { stdio: ['ignore', 'inherit', 'inherit'] });
  if (res.error || res.status !== 0) {
    throw new Error(`ffmpeg falló para ${demo.name} (${res.error?.message || `código ${res.status}`})`);
  }
  return frames;
}

/* ------------------------------------------------------------------------ */
async function main() {
  const argv = process.argv.slice(2);
  const flags = new Map(argv.filter((a) => a.startsWith('--')).map((a) => {
    const eq = a.indexOf('=');
    return eq < 0 ? [a.slice(2), true] : [a.slice(2, eq), a.slice(eq + 1)];
  }));
  const only = argv.filter((a) => !a.startsWith('--'));
  const selected = only.length ? DEMOS.filter((d) => only.includes(d.name)) : DEMOS;
  if (!selected.length) {
    console.error(`Demos disponibles: ${DEMOS.map((d) => d.name).join(', ')}`);
    process.exit(1);
  }
  for (const d of selected) {
    if (Math.abs(d.clip.width / d.clip.height - OUT_W / OUT_H) > 1e-3) throw new Error(`${d.name}: el clip no es 16:10`);
  }

  const keepRoot = typeof flags.get('frames-dir') === 'string' ? path.resolve(flags.get('frames-dir')) : null;
  const tmpRoot = keepRoot || fs.mkdtempSync(path.join(os.tmpdir(), 'record-demos-'));
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const gpuArgs = flags.has('no-gpu')
    ? []
    : ['--ignore-gpu-blocklist', '--enable-gpu', ...(process.platform === 'win32' ? ['--use-angle=d3d11'] : [])];
  const { chromium } = loadPlaywright(typeof flags.get('playwright') === 'string' ? flags.get('playwright') : null);
  const browser = await chromium.launch({ args: gpuArgs });
  try {
    for (const demo of selected) {
      const framesDir = path.join(tmpRoot, demo.name);
      fs.rmSync(framesDir, { recursive: true, force: true });
      fs.mkdirSync(framesDir, { recursive: true });
      const t0 = Date.now();
      process.stdout.write(`${demo.name}: grabando... `);
      const captured = await record(browser, demo, framesDir);
      const outFile = path.join(OUT_DIR, `${demo.name}.gif`);
      const frames = encodeGif(demo, framesDir, captured, outFile);
      const kb = fs.statSync(outFile).size / 1024;
      console.log(`${frames} fotogramas, ${((frames * FRAME_MS) / 1000).toFixed(2)} s, ` +
        `${OUT_W}x${OUT_H}, ${(1000 / FRAME_MS).toFixed(2)} fps, ${kb.toFixed(0)} KB ` +
        `(${((Date.now() - t0) / 1000).toFixed(0)} s)`);
    }
  } finally {
    await browser.close();
    if (!keepRoot) fs.rmSync(tmpRoot, { recursive: true, force: true });
  }
  if (keepRoot) console.log(`PNG intermedios en ${keepRoot}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
