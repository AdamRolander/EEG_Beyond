// Stimulus presentation. The subject sees exactly one of:
//   - fixation cross (during pre-cue and imagery)
//   - stimulus image (during anchor / perception)
//   - blank screen (during rest)
//   - feedback bars (during rest in FEEDBACK phase)

const $ = (id) => document.getElementById(id);

function hideAll() {
  $('fixation-cross').hidden = true;
  $('stimulus-image').hidden = true;
  $('blank-screen').hidden = true;
  $('feedback-container').hidden = true;
  $('instruction-text').hidden = true;
}

export function showFixation() { hideAll(); $('fixation-cross').hidden = false; }
export function showImage(src) {
  hideAll();
  const img = $('stimulus-image');
  img.src = src;
  img.hidden = false;
}
export function showBlank() { hideAll(); $('blank-screen').hidden = false; }
export function showFeedback() { hideAll(); $('feedback-container').hidden = false; }
export function showInstruction(text) {
  hideAll();
  const el = $('instruction-text');
  el.textContent = text;
  el.hidden = false;
}
export function clearScreen() { hideAll(); }

// Image preloading
const imageCache = new Set();

export function preloadImage(src) {
  if (imageCache.has(src)) return Promise.resolve();
  return new Promise(resolve => {
    const img = new Image();
    img.onload = () => { imageCache.add(src); resolve(); };
    img.onerror = () => {
      console.warn(`[render] missing image: ${src}`);
      resolve();
    };
    img.src = src;
  });
}