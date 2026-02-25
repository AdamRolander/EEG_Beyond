// Stimulus factory for creating visual stimuli
const StimulusFactory = {

  createColorStimulus(colorKey) {
    const colorConfig = CONFIG.stimuli.colors[colorKey];
    return {
      type: 'color',
      key: colorKey,
      config: colorConfig,
      hex: colorConfig.hex
    };
  },

  createShapeMesh(shapeKey, options = {}) {
    const scale = options.scale || CONFIG.rendering.shapeScale;

    let geometry;
    switch (shapeKey) {
      case 'SPHERE':
        geometry = new THREE.SphereGeometry(scale, 32, 32);
        break;
      case 'CUBE':
        geometry = new THREE.BoxGeometry(scale * 1.6, scale * 1.6, scale * 1.6);
        break;
      case 'PYRAMID':
        geometry = new THREE.TetrahedronGeometry(scale * 1.4);
        break;
      case 'ICOSAHEDRON':
        geometry = new THREE.IcosahedronGeometry(scale * 1.2);
        break;
      default:
        // For complex shapes, fallback to sphere
        geometry = new THREE.SphereGeometry(scale, 32, 32);
    }

    const material = new THREE.MeshStandardMaterial({
      color: CONFIG.rendering.shapeColor,
      roughness: 0.7,
      metalness: 0.1
    });

    const mesh = new THREE.Mesh(geometry, material);
    const shapeConfig = CONFIG.stimuli.primitives[shapeKey] || CONFIG.stimuli.complex[shapeKey];
    mesh.userData = {
      type: 'shape',
      key: shapeKey,
      config: shapeConfig,
      rotationSpeed: options.rotationSpeed || 0
    };

    return mesh;
  },

  createLighting() {
    return [
      new THREE.AmbientLight(0xffffff, CONFIG.rendering.ambientLight),
      (() => {
        const light = new THREE.DirectionalLight(0xffffff, CONFIG.rendering.directionalLight);
        light.position.set(5, 5, 5);
        return light;
      })()
    ];
  }
};
