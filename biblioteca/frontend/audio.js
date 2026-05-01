import { CLASSES, ASSETS } from './config.js';

// Preloaded cache: {class_name: HTMLAudioElement | null}
const cache = new Map();

// Preload all audio. Resolves even if some files are missing
// (those classes will fall back to a silent timer in `play`).
export async function preloadAudio() {
  await Promise.all(CLASSES.map(cls => loadOne(cls)));
}

function loadOne(cls) {
  const url = ASSETS.audioPath(cls);
  return new Promise(resolve => {
    const a = new Audio(url);
    a.preload = 'auto';
    let resolved = false;
    const done = (ok) => {
      if (resolved) return;
      resolved = true;
      cache.set(cls, ok ? a : null);
      if (!ok) console.warn(`[audio] failed to load ${url}; will use silent timer`);
      resolve();
    };
    a.addEventListener('canplaythrough', () => done(true), { once: true });
    a.addEventListener('error', () => done(false), { once: true });
    // Safety timeout — some browsers don't fire canplaythrough reliably
    setTimeout(() => done(a.readyState >= 2), 4000);
    a.load();
  });
}

// Play the cue for `cls`. Resolves when audio ENDS (or after fallbackMs
// if the file is unavailable). Cloning lets concurrent plays not stomp
// each other (rare in our timing but harmless).
export async function play(cls, fallbackMs = 800) {
  const a = cache.get(cls);
  if (!a) {
    await sleep(fallbackMs);
    return;
  }
  return new Promise(resolve => {
    const node = a.cloneNode();
    node.addEventListener('ended', () => resolve(), { once: true });
    node.addEventListener('error', () => resolve(), { once: true });
    node.play().catch(() => resolve());
  });
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));