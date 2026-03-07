// ─── Stimulus Factory ────────────────────────────────────────
// Loads GLB models from assets/ or falls back to procedural geometry.
// Also generates a visual noise mask texture.

const StimulusFactory = {
  _loader: null,
  _modelCache: {},    // key → THREE.Group (cloneable)
  _maskTexture: null,

  /**
   * Try to load all GLB models. Non-fatal if missing — falls back to geometry.
   */
  async preloadModels() {
    // GLTFLoader is not in the core three.js r128 build.
    // We load it dynamically, and if it's not available we skip.
    if (typeof THREE.GLTFLoader === 'undefined') {
      try {
        // Try loading from CDN
        await this._loadScript(
          'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/examples/js/loaders/GLTFLoader.min.js'
        );
      } catch (e) {
        console.warn('[Stimuli] GLTFLoader not available, using procedural fallbacks');
        return;
      }
    }

    this._loader = new THREE.GLTFLoader();

    const promises = Object.entries(CONFIG.stimuli).map(async ([key, cfg]) => {
      try {
        const gltf = await this._loadGLB(`assets/${cfg.file}`);
        // Normalize scale: fit into a bounding sphere of radius ~shapeScale
        const box = new THREE.Box3().setFromObject(gltf.scene);
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = (CONFIG.rendering.shapeScale * 2) / maxDim;
        gltf.scene.scale.setScalar(scale);

        // Center
        const center = box.getCenter(new THREE.Vector3());
        gltf.scene.position.sub(center.multiplyScalar(scale));

        this._modelCache[key] = gltf.scene;
        console.log(`[Stimuli] Loaded GLB: ${cfg.file}`);
      } catch (e) {
        console.warn(`[Stimuli] GLB not found for ${key} (${cfg.file}), will use fallback`);
      }
    });

    await Promise.allSettled(promises);
  },

  _loadGLB(url) {
    return new Promise((resolve, reject) => {
      this._loader.load(url, resolve, undefined, reject);
    });
  },

  _loadScript(url) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = url;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  },

  /**
   * Get a mesh/group for a stimulus key.
   * Returns a clone (safe to add/remove from scene).
   */
  createMesh(key) {
    if (this._modelCache[key]) {
      const clone = this._modelCache[key].clone();
      clone.userData = { stimKey: key, rotationSpeed: 0.3 };
      return clone;
    }
    // Fallback procedural
    return this._createFallback(key);
  },

  _createFallback(key) {
    const s = CONFIG.rendering.shapeScale;
    let geometry;

    switch (key) {
      case 'BANANA':
        // Torus arc as banana approximation
        geometry = new THREE.TorusGeometry(s * 0.8, s * 0.25, 16, 32, Math.PI);
        break;
      case 'STRAWBERRY':
        // Cone (roughly strawberry-shaped)
        geometry = new THREE.ConeGeometry(s * 0.6, s * 1.2, 32);
        break;
      case 'CUBE':
        geometry = new THREE.BoxGeometry(s * 1.4, s * 1.4, s * 1.4);
        break;
      default:
        geometry = new THREE.SphereGeometry(s, 32, 32);
    }

    const colorMap = { BANANA: 0xffe135, STRAWBERRY: 0xdc143c, CUBE: 0xcccccc };
    const material = new THREE.MeshStandardMaterial({
      color: colorMap[key] || 0xaaaaaa,
      roughness: 0.6,
      metalness: 0.1
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData = { stimKey: key, rotationSpeed: 0.3 };
    return mesh;
  },

  /**
   * Create a noise mask texture (visual mask phase).
   * Returns a THREE.Mesh with a noisy plane.
   */
  createMaskPlane(width, height) {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');
    const imageData = ctx.createImageData(256, 256);
    for (let i = 0; i < imageData.data.length; i += 4) {
      const v = Math.random() * 255;
      imageData.data[i]     = v;
      imageData.data[i + 1] = v;
      imageData.data[i + 2] = v;
      imageData.data[i + 3] = 255;
    }
    ctx.putImageData(imageData, 0, 0);

    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;

    const geo = new THREE.PlaneGeometry(width || 4, height || 4);
    const mat = new THREE.MeshBasicMaterial({ map: texture });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { isMask: true };
    return mesh;
  },

  /**
   * Create a 2D noise mask for browser-mode (returns a canvas element).
   */
  create2DMask(w, h) {
    const canvas = document.createElement('canvas');
    canvas.width = w || 512;
    canvas.height = h || 512;
    const ctx = canvas.getContext('2d');
    const imageData = ctx.createImageData(canvas.width, canvas.height);
    for (let i = 0; i < imageData.data.length; i += 4) {
      const v = Math.random() * 255;
      imageData.data[i]     = v;
      imageData.data[i + 1] = v;
      imageData.data[i + 2] = v;
      imageData.data[i + 3] = 255;
    }
    ctx.putImageData(imageData, 0, 0);
    return canvas;
  },

  /**
   * Standard lighting setup.
   */
  createLighting() {
    const ambient = new THREE.AmbientLight(0xffffff, CONFIG.rendering.ambientLight);
    const dir = new THREE.DirectionalLight(0xffffff, CONFIG.rendering.directionalLight);
    dir.position.set(5, 5, 5);
    return [ambient, dir];
  }
};