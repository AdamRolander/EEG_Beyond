import { CLASSES } from './config.js';

// Update three similarity bars based on a {cat, wrench, house} score map.
// Values are clamped to [0, 1].
export function updateBars(scores) {
  if (!scores) return;
  for (const cls of CLASSES) {
    const v = Number(scores[cls] || 0);
    const fill = document.querySelector(`#feedback-container .bar-${cls} .fill`);
    if (fill) fill.style.width = `${Math.max(0, Math.min(1, v)) * 100}%`;
  }
}

export function resetBars() {
  for (const cls of CLASSES) {
    const fill = document.querySelector(`#feedback-container .bar-${cls} .fill`);
    if (fill) fill.style.width = '0%';
  }
}

// Highlight the cued class so the subject knows which bar to track.
export function highlightCued(cls) {
  for (const c of CLASSES) {
    const bar = document.querySelector(`#feedback-container .bar-${c}`);
    if (bar) bar.classList.toggle('cued', c === cls);
  }
}

export function clearHighlight() {
  for (const c of CLASSES) {
    const bar = document.querySelector(`#feedback-container .bar-${c}`);
    if (bar) bar.classList.remove('cued');
  }
}