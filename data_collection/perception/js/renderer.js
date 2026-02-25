// Three.js + WebXR renderer
class VRRenderer {
  constructor() {
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.vrContainer = null;
    this.currentStimulus = null;
    this.isPresenting = false;
    this.animationId = null;
  }

  init(container) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.xr.enabled = true;
    container.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(CONFIG.rendering.neutralGray);

    this.camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 1000);
    this.camera.position.z = 5;

    this.vrContainer = new THREE.Group();
    this.vrContainer.position.set(0, 0, -CONFIG.rendering.vrDistance);

    StimulusFactory.createLighting().forEach(light => this.scene.add(light.clone()));
    StimulusFactory.createLighting().forEach(light => this.vrContainer.add(light.clone()));

    window.addEventListener('resize', () => this.onResize());
    console.log('[Renderer] Initialized');
  }

  async enterVR() {
    if (!navigator.xr) throw new Error('WebXR not supported');

    const supported = await navigator.xr.isSessionSupported('immersive-vr');
    if (!supported) throw new Error('VR not supported on this device');

    const session = await navigator.xr.requestSession('immersive-vr', {
      optionalFeatures: ['local-floor'],
      requiredFeatures: ['local']
    });

    await this.renderer.xr.setSession(session);
    this.scene.add(this.camera);
    this.camera.add(this.vrContainer);
    session.addEventListener('end', () => this.onVREnd());
    this.isPresenting = true;
    console.log('[Renderer] Entered VR');
  }

  exitVR() {
    const session = this.renderer.xr.getSession();
    if (session) session.end();
  }

  onVREnd() {
    this.camera.remove(this.vrContainer);
    this.isPresenting = false;
    console.log('[Renderer] Exited VR');
  }

  showStimulus(stimulus) {
    this.clearStimulus();

    if (stimulus.type === 'color') {
      this.scene.background = new THREE.Color(stimulus.hex);
      this.currentStimulus = { type: 'color', hex: stimulus.hex };
    } else {
      this.scene.background = new THREE.Color(0x000000);
      const mesh = StimulusFactory.createShapeMesh(stimulus.key, {
        rotationSpeed: stimulus.rotationSpeed || CONFIG.defaults.rotationSpeed
      });

      if (this.isPresenting) {
        this.vrContainer.add(mesh);
      } else {
        this.scene.add(mesh);
      }
      this.currentStimulus = mesh;
    }
  }

  showISI() {
    this.clearStimulus();
    this.scene.background = new THREE.Color(CONFIG.rendering.neutralGray);
  }

  clearStimulus() {
    if (this.currentStimulus) {
      if (this.currentStimulus.isMesh) {
        this.scene.remove(this.currentStimulus);
        this.vrContainer.remove(this.currentStimulus);
        this.currentStimulus.geometry?.dispose();
        this.currentStimulus.material?.dispose();
      }
      this.currentStimulus = null;
    }
  }

  startRenderLoop(onFrame) {
    this.renderer.setAnimationLoop((time, frame) => {
      if (this.currentStimulus?.isMesh && this.currentStimulus.userData.rotationSpeed) {
        this.currentStimulus.rotation.y += this.currentStimulus.userData.rotationSpeed * 0.016;
      }
      if (onFrame) onFrame(time, frame);
      this.renderer.render(this.scene, this.camera);
    });
  }

  stopRenderLoop() {
    this.renderer.setAnimationLoop(null);
  }

  onResize() {
    if (!this.renderer.xr.isPresenting) {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
    }
  }

  dispose() {
    this.stopRenderLoop();
    this.clearStimulus();
    this.exitVR();
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.domElement.remove();
    }
    this.renderer = null;
    this.scene = null;
    this.camera = null;
  }
}

// Global instance
const vrRenderer = new VRRenderer();
