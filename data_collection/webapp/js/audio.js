// ─── Audio Cue System ────────────────────────────────────────
// Generates a beep tone or plays a pre-recorded name cue before imagery.
const AudioCues = {
  _ctx: null,
  _ttsCache: {},   // stimulusKey → AudioBuffer

  _getContext() {
    if (!this._ctx) {
      this._ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
    // Resume if suspended (autoplay policy)
    if (this._ctx.state === 'suspended') {
      this._ctx.resume();
    }
    return this._ctx;
  },

  /**
   * Play a short beep tone.
   * @param {number} freq  - Hz (default 880)
   * @param {number} durMs - duration in ms (default 200)
   */
  playBeep(freq = 880, durMs = 200) {
    const ctx  = this._getContext();
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type      = 'sine';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durMs / 1000);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + durMs / 1000 + 0.05);
  },

  /**
   * Preload a TTS mp3 for a stimulus name.
   * Files should be at assets/audio/<name>.mp3  (lowercase).
   * @param {string} stimKey - e.g. 'BANANA'
   */
  async preloadTTS(stimKey) {
    const name = CONFIG.stimuli[stimKey]?.name?.toLowerCase();
    if (!name) return;
    const url = `assets/audio/${name}.mp3`;
    try {
      const resp = await fetch(url);
      if (!resp.ok) {
        console.warn(`[Audio] No TTS file for "${name}" at ${url}`);
        return;
      }
      const buf = await resp.arrayBuffer();
      const ctx = this._getContext();
      this._ttsCache[stimKey] = await ctx.decodeAudioData(buf);
      console.log(`[Audio] Preloaded TTS: ${name}`);
    } catch (e) {
      console.warn(`[Audio] Failed to preload TTS for "${name}":`, e);
    }
  },

  /**
   * Play the TTS cue for a stimulus. Falls back to beep if not available.
   * @param {string} stimKey
   */
  playCue(stimKey) {
    const buffer = this._ttsCache[stimKey];
    if (buffer) {
      const ctx = this._getContext();
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(ctx.destination);
      src.start();
    } else {
      this.playBeep();
    }
  },

  /**
   * Preload all available TTS files.
   */
  async preloadAll() {
    const promises = Object.keys(CONFIG.stimuli).map(k => this.preloadTTS(k));
    await Promise.allSettled(promises);
  }
};