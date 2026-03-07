// ─── Three.js / WebXR Renderer ───────────────────────────────
// Supports two modes:
//   'browser' — fullscreen canvas overlay, no VR
//   'vr'      — WebXR immersive-vr session
class VRRenderer {
  constructor() {
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.vrGroup = null;      // group attached to camera for VR
    this.sceneGroup = null;   // group in world space for browser mode
    this.currentObject = null;
    this.isPresenting = false;
    this.mode = 'browser';    // 'browser' | 'vr'
    this.container = null;
    this._resizeHandler = null;
  }

  init(container, mode) {
    this.mode = mode || 'browser';
    this.container = container;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.outputEncoding = THREE.sRGBEncoding;

    if (this.mode === 'vr') {
      this.renderer.xr.enabled = true;
    }

    container.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(CONFIG.rendering.neutralGray);

    this.camera = new THREE.PerspectiveCamera(
      CONFIG.rendering.cameraFOV,
      window.innerWidth / window.innerHeight,
      0.1, 1000
    );
    this.camera.position.set(0, 0, 5);

    // VR group (child of camera, positioned in front)
    this.vrGroup = new THREE.Group();
    this.vrGroup.position.set(0, 0, -CONFIG.rendering.vrDistance);

    // Scene group (world space, for browser mode)
    this.sceneGroup = new THREE.Group();
    this.scene.add(this.sceneGroup);

    // Lighting
    StimulusFactory.createLighting().forEach(l => this.scene.add(l));

    this._resizeHandler = () => this._onResize();
    window.addEventListener('resize', this._resizeHandler);

    console.log(`[Renderer] Initialized (mode=${this.mode})`);
  }

  async enterVR() {
    if (this.mode !== 'vr') throw new Error('Not in VR mode');
    if (!navigator.xr) throw new Error('WebXR not supported');

    const supported = await navigator.xr.isSessionSupported('immersive-vr');
    if (!supported) throw new Error('VR not supported on this device');

    const session = await navigator.xr.requestSession('immersive-vr', {
      optionalFeatures: ['local-floor'],
      requiredFeatures: ['local']
    });

    await this.renderer.xr.setSession(session);
    this.scene.add(this.camera);
    this.camera.add(this.vrGroup);
    session.addEventListener('end', () => this._onVREnd());
    this.isPresenting = true;
    console.log('[Renderer] Entered VR');
  }

  exitVR() {
    if (this.mode === 'vr') {
      const session = this.renderer?.xr?.getSession();
      if (session) session.end();
    }
  }

  _onVREnd() {
    this.camera.remove(this.vrGroup);
    this.isPresenting = false;
    console.log('[Renderer] Exited VR');
  }

  // ── Phase display methods ──────────────────────────────────

  /**
   * Show fixation cross (white + on gray).
   */
  showFixation() {
    this._clear();
    this.scene.background = new THREE.Color(CONFIG.rendering.neutralGray);

    const mat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const armLen = 0.15, armW = 0.012;
    const hBar = new THREE.Mesh(new THREE.BoxGeometry(armLen * 2, armW, armW), mat);
    const vBar = new THREE.Mesh(new THREE.BoxGeometry(armW, armLen * 2, armW), mat);
    const cross = new THREE.Group();
    cross.add(hBar, vBar);
    cross.userData = { isPhaseObject: true };

    this._addToView(cross);
  }

  /**
   * Show a 3D stimulus for perception phase.
   */
  showStimulus(stimKey) {
    this._clear();
    this.scene.background = new THREE.Color(0x000000);

    const mesh = StimulusFactory.createMesh(stimKey);
    mesh.userData.isPhaseObject = true;
    this._addToView(mesh);
    this.currentObject = mesh;
  }

  /**
   * Show visual noise mask.
   */
  showMask() {
    this._clear();
    this.scene.background = new THREE.Color(CONFIG.rendering.neutralGray);

    const mask = StimulusFactory.createMaskPlane(5, 5);
    mask.userData.isPhaseObject = true;
    this._addToView(mask);
  }

  /**
   * Imagery phase — black screen (eyes closed).
   */
  showImagery() {
    this._clear();
    this.scene.background = new THREE.Color(CONFIG.rendering.imageryColor);
  }

  /**
   * Rest phase — gray with "Rest" text (in 2D overlay; 3D just gray).
   */
  showRest() {
    this._clear();
    this.scene.background = new THREE.Color(CONFIG.rendering.neutralGray);

    // In browser mode the 2D overlay will show "Rest" text.
    // In VR we could add a text sprite, but keeping it simple for now.
  }

  /**
   * ISI / neutral screen.
   */
  showNeutral() {
    this._clear();
    this.scene.background = new THREE.Color(CONFIG.rendering.neutralGray);
  }

  // ── Internal helpers ───────────────────────────────────────

  _addToView(obj) {
    if (this.mode === 'vr' && this.isPresenting) {
      this.vrGroup.add(obj);
    } else {
      // Position in front of camera for browser mode
      obj.position.set(0, 0, -CONFIG.rendering.vrDistance);
      this.sceneGroup.add(obj);
    }
  }

  _clear() {
    this.currentObject = null;

    // Clear sceneGroup children
    while (this.sceneGroup.children.length) {
      const c = this.sceneGroup.children[0];
      this.sceneGroup.remove(c);
      this._dispose(c);
    }
    // Clear vrGroup children
    while (this.vrGroup.children.length) {
      const c = this.vrGroup.children[0];
      this.vrGroup.remove(c);
      this._dispose(c);
    }
  }

  _dispose(obj) {
    obj.traverse?.(child => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach(m => m.dispose());
        } else {
          child.material.dispose();
        }
      }
    });
  }

  // ── Render loop ────────────────────────────────────────────

  startRenderLoop() {
    this.renderer.setAnimationLoop((time) => {
      // Rotate current stimulus object
      if (this.currentObject) {
        const speed = this.currentObject.userData?.rotationSpeed || 0;
        if (speed) this.currentObject.rotation.y += speed * 0.016;
      }
      this.renderer.render(this.scene, this.camera);
    });
  }

  stopRenderLoop() {
    if (this.renderer) this.renderer.setAnimationLoop(null);
  }

  _onResize() {
    if (this.renderer?.xr?.isPresenting) return;
    if (!this.renderer) return;
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
  }

  dispose() {
    this.stopRenderLoop();
    this._clear();
    this.exitVR();
    if (this._resizeHandler) {
      window.removeEventListener('resize', this._resizeHandler);
    }
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.domElement?.remove();
    }
    this.renderer = null;
    this.scene = null;
    this.camera = null;
  }
}

// Global instance
const vrRenderer = new VRRenderer();