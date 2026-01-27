/**
 * EEG Stimulus Platform - Configuration Module
 * 
 * Central configuration for all experiment parameters.
 * Modify this file to customize stimulus properties.
 */

export const Config = {
    // ============================================================
    // COLOR STIMULI
    // Pure sRGB primaries for baseline measurements
    // ============================================================
    colors: {
        RED:    { hex: 0xff0000, name: 'RED',   code: 'COL_R' },
        GREEN:  { hex: 0x00ff00, name: 'GREEN', code: 'COL_G' },
        BLUE:   { hex: 0x0000ff, name: 'BLUE',  code: 'COL_B' },
        BLACK:  { hex: 0x000000, name: 'BLACK', code: 'COL_K' },
        WHITE:  { hex: 0xffffff, name: 'WHITE', code: 'COL_W' }
    },
    
    // ============================================================
    // SHAPE STIMULI
    // 3D primitive solids
    // ============================================================
    shapes: {
        SPHERE:      { name: 'SPHERE',      code: 'SHP_SPH' },
        CUBE:        { name: 'CUBE',        code: 'SHP_CUB' },
        PYRAMID:     { name: 'PYRAMID',     code: 'SHP_PYR' },
        ICOSAHEDRON: { name: 'ICOSAHEDRON', code: 'SHP_ICO' }
    },
    
    // ============================================================
    // VISUAL PARAMETERS
    // ============================================================
    neutralGray: 0x808080,  // ISI background
    
    scene: {
        cameraFOV: 50,
        cameraNear: 0.1,
        cameraFar: 1000,
        cameraZ: 5,
        shapeScale: 1.5,
        shapeColor: 0xe0e0e0,
        ambientIntensity: 0.4,
        directionalIntensity: 0.6
    },
    
    // ============================================================
    // DEFAULT TIMING (ms)
    // ============================================================
    defaults: {
        stimulusDuration: 3000,
        isiDuration: 1000,
        repetitions: 3,
        rotationSpeed: 0.5  // rad/s
    },
    
    // ============================================================
    // EVENT CODES
    // Used for EEG marker encoding
    // ============================================================
    eventCodes: {
        EXPERIMENT_START: 100,
        EXPERIMENT_END: 101,
        STIM_ONSET: 1,
        STIM_OFFSET: 2,
        PAUSE: 50,
        RESUME: 51,
        ABORT: 99,
        
        // Color-specific (10-19)
        COL_R: 10,
        COL_G: 11,
        COL_B: 12,
        COL_K: 13,
        COL_W: 14,
        
        // Shape-specific (20-29)
        SHP_SPH: 20,
        SHP_CUB: 21,
        SHP_PYR: 22,
        SHP_ICO: 23
    }
};

/**
 * Add a custom color stimulus
 */
export function addColor(name, hex, code) {
    Config.colors[name] = { hex, name, code };
}

/**
 * Add a custom shape stimulus
 */
export function addShape(name, code, geometryFactory = null) {
    Config.shapes[name] = { name, code, geometryFactory };
}

export default Config;