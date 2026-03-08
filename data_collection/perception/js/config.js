// Configuration constants
const CONFIG = {
  // Stimulus definitions
  stimuli: {
    colors: {
      RED:   { hex: 0xff0000, name: 'Red',   code: 'COL_RED'   },
      GREEN: { hex: 0x00ff00, name: 'Green', code: 'COL_GREEN' },
      BLUE:  { hex: 0x0000ff, name: 'Blue',  code: 'COL_BLUE'  },
      BLACK: { hex: 0x000000, name: 'Black', code: 'COL_BLACK' },
      WHITE: { hex: 0xffffff, name: 'White', code: 'COL_WHITE' }
    },
    primitives: {
      SPHERE:      { name: 'Sphere',      code: 'SHP_SPHERE'      },
      CUBE:        { name: 'Cube',        code: 'SHP_CUBE'        },
      PYRAMID:     { name: 'Pyramid',     code: 'SHP_PYRAMID'     },
      ICOSAHEDRON: { name: 'Icosahedron', code: 'SHP_ICOSAHEDRON' }
    },
    complex: {
      FACE:      { name: 'Face',      code: 'CPX_FACE'      },
      BUILDING:  { name: 'Building',  code: 'CPX_BUILDING'  },
      LANDSCAPE: { name: 'Landscape', code: 'CPX_LANDSCAPE' }
    }
  },

  // Marker codes for LSL
  markerCodes: {
    EXP_START:   90,
    EXP_END:     91,
    TRIAL_START: 1,
    STIM_ONSET:  10,
    STIM_OFFSET: 11,
    BREAK_START: 40,
    BREAK_END:   41,
    LIKERT_BASE: 50, // 50-55 for ratings 1-5
    PAUSE:       60,
    RESUME:      61,
    // Color codes: 100-104
    COL_RED:   100,
    COL_GREEN: 101,
    COL_BLUE:  102,
    COL_BLACK: 103,
    COL_WHITE: 104,
    // Shape codes: 200-203
    SHP_SPHERE:      200,
    SHP_CUBE:        201,
    SHP_PYRAMID:     202,
    SHP_ICOSAHEDRON: 203,
    // Complex codes: 300+
    CPX_FACE:      300,
    CPX_BUILDING:  301,
    CPX_LANDSCAPE: 302
  },

  // Rendering settings
  rendering: {
    neutralGray:      0x808080,
    shapeColor:       0xe0e0e0,
    shapeScale:       1.5,
    vrDistance:       2.5,
    ambientLight:     0.4,
    directionalLight: 0.6
  },

  // Default timing
  defaults: {
    stimulusDuration:  3000,
    isiDuration:       1000,
    repetitions:       3,
    trialsUntilBreak:  8,
    rotationSpeed:     0.5
  }
};
