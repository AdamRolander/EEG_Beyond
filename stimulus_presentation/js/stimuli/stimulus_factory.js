/**
 * EEG Stimulus Platform - Stimulus Factory Module
 * 
 * Creates and manages visual stimuli (colors and 3D shapes).
 * Designed for easy extension with new stimulus types.
 */

import * as THREE from 'three';
import { Config } from '../config.js';

export const StimulusFactory = {
    
    // ============================================================
    // COLOR STIMULI
    // ============================================================
    
    /**
     * Create a full-screen color stimulus
     * Uses scene background color for maximum fill
     * 
     * @param {object} colorConfig - Color configuration from Config.colors
     * @returns {THREE.Color} Three.js color object
     */
    createColorStimulus(colorConfig) {
        // Disable color management for accurate sRGB
        THREE.ColorManagement.enabled = false;
        return new THREE.Color(colorConfig.hex);
    },
    
    /**
     * Apply color stimulus to scene
     * 
     * @param {THREE.Scene} scene - Target scene
     * @param {object} colorConfig - Color configuration
     */
    applyColorToScene(scene, colorConfig) {
        scene.background = this.createColorStimulus(colorConfig);
    },
    
    // ============================================================
    // SHAPE STIMULI
    // ============================================================
    
    /**
     * Create a 3D primitive shape
     * 
     * @param {string} shapeType - Shape type from Config.shapes
     * @param {object} options - Optional customization
     * @returns {THREE.Mesh} Three.js mesh
     */
    createShapeStimulus(shapeType, options = {}) {
        const scale = options.scale || Config.scene.shapeScale;
        const color = options.color || Config.scene.shapeColor;
        
        let geometry = this.createGeometry(shapeType, scale);
        
        // Use MeshStandardMaterial for proper lighting response
        const material = new THREE.MeshStandardMaterial({
            color: color,
            roughness: options.roughness || 0.7,
            metalness: options.metalness || 0.1,
            flatShading: options.flatShading || false
        });
        
        const mesh = new THREE.Mesh(geometry, material);
        
        // Store metadata
        mesh.userData = {
            type: 'shape',
            config: Config.shapes[shapeType],
            rotationAxis: options.rotationAxis || 'y',
            rotationSpeed: options.rotationSpeed || 0
        };
        
        return mesh;
    },
    
    /**
     * Create geometry for a shape type
     * 
     * @param {string} shapeType - Shape identifier
     * @param {number} scale - Base scale factor
     * @returns {THREE.BufferGeometry}
     */
    createGeometry(shapeType, scale) {
        // Check for custom geometry factory
        const shapeConfig = Config.shapes[shapeType];
        if (shapeConfig && shapeConfig.geometryFactory) {
            return shapeConfig.geometryFactory(scale);
        }
        
        // Built-in geometries
        switch (shapeType) {
            case 'SPHERE':
                return new THREE.SphereGeometry(scale, 32, 32);
                
            case 'CUBE':
                return new THREE.BoxGeometry(
                    scale * 1.6,
                    scale * 1.6,
                    scale * 1.6
                );
                
            case 'PYRAMID':
                // Tetrahedron as pyramid
                return new THREE.TetrahedronGeometry(scale * 1.4);
                
            case 'ICOSAHEDRON':
                return new THREE.IcosahedronGeometry(scale * 1.2);
                
            case 'OCTAHEDRON':
                return new THREE.OctahedronGeometry(scale * 1.3);
                
            case 'DODECAHEDRON':
                return new THREE.DodecahedronGeometry(scale * 1.1);
                
            case 'TORUS':
                return new THREE.TorusGeometry(scale, scale * 0.3, 16, 48);
                
            case 'CYLINDER':
                return new THREE.CylinderGeometry(
                    scale * 0.8, 
                    scale * 0.8, 
                    scale * 2, 
                    32
                );
                
            case 'CONE':
                return new THREE.ConeGeometry(scale, scale * 2, 32);
                
            default:
                console.warn(`Unknown shape: ${shapeType}, using sphere`);
                return new THREE.SphereGeometry(scale, 32, 32);
        }
    },
    
    // ============================================================
    // LIGHTING
    // ============================================================
    
    /**
     * Create standard lighting setup
     * Minimal complexity for research purposes
     * 
     * @returns {THREE.Light[]} Array of lights
     */
    createLighting() {
        const lights = [];
        
        // Ambient light for base illumination
        const ambient = new THREE.AmbientLight(
            0xffffff,
            Config.scene.ambientIntensity
        );
        lights.push(ambient);
        
        // Single directional light
        const directional = new THREE.DirectionalLight(
            0xffffff,
            Config.scene.directionalIntensity
        );
        directional.position.set(5, 5, 5);
        lights.push(directional);
        
        return lights;
    },
    
    /**
     * Create alternative lighting setups
     */
    createFlatLighting() {
        // High ambient, no directional - minimizes 3D depth cues
        return [new THREE.AmbientLight(0xffffff, 1.0)];
    },
    
    createDramaticLighting() {
        // Strong directional with low ambient - emphasizes 3D form
        const lights = [];
        lights.push(new THREE.AmbientLight(0xffffff, 0.2));
        
        const key = new THREE.DirectionalLight(0xffffff, 0.8);
        key.position.set(5, 5, 5);
        lights.push(key);
        
        const fill = new THREE.DirectionalLight(0x4444ff, 0.3);
        fill.position.set(-5, 0, 5);
        lights.push(fill);
        
        return lights;
    },
    
    // ============================================================
    // UTILITY FUNCTIONS
    // ============================================================
    
    /**
     * Create neutral gray background color
     */
    createNeutralBackground() {
        return new THREE.Color(Config.neutralGray);
    },
    
    /**
     * Update shape rotation
     * 
     * @param {THREE.Mesh} shape - Shape mesh
     * @param {number} deltaTime - Time since last frame (seconds)
     */
    updateRotation(shape, deltaTime) {
        if (!shape.userData || shape.userData.type !== 'shape') return;
        
        const speed = shape.userData.rotationSpeed;
        const axis = shape.userData.rotationAxis;
        
        switch (axis) {
            case 'x':
                shape.rotation.x += speed * deltaTime;
                break;
            case 'y':
                shape.rotation.y += speed * deltaTime;
                break;
            case 'z':
                shape.rotation.z += speed * deltaTime;
                break;
            case 'xy':
                shape.rotation.x += speed * deltaTime;
                shape.rotation.y += speed * deltaTime * 0.7;
                break;
        }
    },
    
    /**
     * Reset shape rotation to initial state
     */
    resetRotation(shape) {
        shape.rotation.set(0, 0, 0);
    }
};

// ============================================================
// EXTENSION API
// Add custom stimuli programmatically
// ============================================================

/**
 * Register a custom shape with a geometry factory
 * 
 * @param {string} name - Unique shape identifier
 * @param {function} geometryFactory - Function(scale) => THREE.BufferGeometry
 * @param {string} code - Event code for logging
 * 
 * @example
 * registerCustomShape('STAR', (scale) => {
 *     return new THREE.ExtrudeGeometry(starShape, { depth: 0.5 });
 * }, 'SHP_STR');
 */
export function registerCustomShape(name, geometryFactory, code) {
    Config.shapes[name] = {
        name,
        code,
        geometryFactory
    };
    console.log(`[StimulusFactory] Registered custom shape: ${name}`);
}

/**
 * Register a custom color
 */
export function registerCustomColor(name, hex, code) {
    Config.colors[name] = { hex, name, code };
    console.log(`[StimulusFactory] Registered custom color: ${name}`);
}

export default StimulusFactory;