# Shader Editor — Planning Document

## Overview

Add an interactive editor panel for `indexBGShader.glsl` that exposes variables and equations
as editable fields. Pressing **Apply** rebuilds the GLSL source string in JS and recompiles
the WebGL shader in-place (no page reload, no re-fetch).

---

## Implementation Approach

The shader is currently loaded as a raw string (`this.fragShaderSrc`). The plan:

1. Convert `indexBGShader.glsl` into a **JS template** inside `index_background.js` (or a
   companion file), with named slots for every editable value.
2. The editor UI reads its current field values, builds the GLSL string by substitution, and
   calls a new `BackgroundWave.recompile(src)` method.
3. `recompile()` detaches and deletes the old fragment shader and program, creates new ones
   from the supplied source, and re-binds uniforms. The render loop continues uninterrupted.
4. If compilation fails, the WebGL info log is displayed in the editor; the old shader keeps
   running.

No WebGL uniform changes are needed — all values are baked into the GLSL source string at
Apply time. This keeps the shader code simple and makes equation editing straightforward.

---

## Variable Inventory

### Assumed mappings for magic-number variables
*(Please confirm or correct each one before implementation)*

| UI variable | Current shader expression | Assumed value |
| --- | --- | --- |
| `scale` | `float scale = 2.5;` | `2.5` |
| `verticalWaveFreq` | `float verticalWaveFreq = 3.5;` | `3.5` |
| `verticalWaveSpeed` | `float verticalWaveSpeed = 0.05;` | `0.05` |
| `verticalWaveAmount` | `float verticalWaveAmount = 0.2;` | `0.2` |
| `wave1Freq` | `float wave1Freq = 1.0;` | `1.0` |
| `wave1Speed` | `float wave1Speed = 0.005;` | `0.005` |
| `wave1a` | `7.0` in `tileUV.y * 7.0` (inside innerWave1) | `7.0` |
| `wave1b` | `0.3` in `time * 0.3` (inside innerWave1) | `0.3` |
| `wave2Freq` | `float wave2Freq = 3.0;` | `3.0` |
| `wave2Speed` | `float wave2Speed = 0.005;` | `0.005` |
| `wave2a` | `9.0` in `tileUV.y * 9.0` (inside innerWave2) | `9.0` |
| `offsetVar` | `-0.1` in `float timeOffset = -0.1 * time;` | `-0.1` |
| `oscillationA` | `0.25` in `sin(time * 0.25)` | `0.25` |
| `oscillationB` | `2.0` in `sin(time * 0.25) * 2.0` | `2.0` |
| `modA` | `-5.0` in `float modulation = -5.0 * ...` | `-5.0` |
| `finalA` | `2.0` in `sin(combinedWaves * 2.0 + modulation)` | `2.0` |

### Sprite tone values
Each is a `vec2` of two 24-bit hex values (even/odd pixel dither pair).

| UI variable | Current value |
| --- | --- |
| `sprite_max_vibrant` | `vec2(0xFFFFFF, 0xFFFFFF)` |
| `sprite_brightest` | `vec2(0xEDFEDF, 0xEDFEDF)` |
| `sprite_brighter` | `vec2(0xDDDDDD, 0xDDDDDD)` |
| `sprite_bright` | `vec2(0x7ADB52, 0x7ADB52)` |
| `sprite_medium` | `vec2(0xB524AD, 0x4ADB52)` |
| `sprite_dark` | `vec2(0xB52312, 0xB52312)` |
| `sprite_darker` | `vec2(0x912264, 0x489912)` |
| `sprite_darkest` | `vec2(0x024480, 0x012240)` |
| `sprite_darkestest` | `vec2(0x024000, 0x000240)` |
| `sprite_more_darkestest` | `vec2(0x000400, 0x000080)` |
| `sprite_empty` | `vec2(0x000000, 0x000000)` |

---

## Editable Equations

These are GLSL expression strings injected verbatim into the shader at Apply time.
Available bindings at the point of injection: `tileUV`, `time`, all scalar variables above.

| Name | Current expression |
| --- | --- |
| `innerWave1` | `sin(tileUV.x + tileUV.y * wave1a + time * wave1b)` |
| `wave1` | `sin(tileUV.x * wave1Freq + innerWave1 + time * wave1Speed)` |
| `innerWave2` | `cos(tileUV.x - tileUV.y * wave2a + time * wave2Speed)` |
| `wave2` | `cos(tileUV.y * wave2Freq + innerWave2)` |
| `combinedWaves` | `wave1 + wave2` |
| `slowOscillation` | `sin(time * oscillationA) * oscillationB` |
| `modulation` | `modA * (offsetVar * time + slowOscillation)` |
| `finalPattern` | `sin(combinedWaves * finalA + modulation)` |

*(These replace the current hardcoded expressions. The `wave1a`, `wave1b`, `wave2a` variables
are introduced as named substitutions for the previously-unnamed magic numbers.)*

---

## Questions for the User

**Q1 — Variable mappings**
Do the assumed mappings in the table above match your intent? In particular:

- Is `wave1a = 7.0` (the Y-coefficient of `tileUV` in `innerWave1`)? — Yes. Rename `wave1a` to `innerWave1YCoeff`
- Is `wave1b = 0.3` (the time-coefficient in `innerWave1`)? — Yes. Rename `wave1b` to `innerWave1TimeCoeff`
- Is `wave2a = 9.0` (the Y-coefficient of `tileUV` in `innerWave2`)? — Yes. Rename `wave2a` to `innerWave2YCoeff`
- Is `offsetVar = -0.1` (the time multiplier before `modulation`)? — Yes. Rename `offsetVar` to `modTimeMultiplier`

**Q2 — Sprite hex inputs**
Each sprite level is two separate 24-bit hex values that dither between even/odd pixels.
How should these be presented in the UI?
- Option A: Two text inputs per level (each showing e.g. `0x7ADB52`)
- Option B: Two HTML color pickers per level (only uses RGB, maps directly to `#7ADB52`)
- Option C: Single combined text input per level showing `0x7ADB52, 0x7ADB52`
Use Option A.

**Q3 — UI location**
Where should this editor live?
- Option A: A new draggable W98 window (like the graph modal or item search)
- Option B: A fixed panel (e.g. right side of screen, always visible when open)
- Option C: Appended to an existing page/window
Integrate it into the current `BG` window. There is a button in the index window's title bar that opens a window for background controls.

**Q4 — Colour wave controls**
The shader also has a second set of parameters (`waveSpeed`, `waveScale`, `waveAmplitude`,
`baseIntensity`, `separation`, `purpleColor`, `goldColor`) that control the purple/gold colour
waves. Should these be included in the editor too, or out of scope for now?
Include these in the editor too.

**Q5 — Compile errors**
If the Apply'd GLSL fails to compile (e.g. a typo in an equation field), what should happen?
- Option A: Show the raw WebGL error log in a read-only text area in the editor
- Option B: Show a simple modal/alert with the error
- Option C: Silently keep the last working shader
Use option B with a simple modal error.

**Q6 — Persistence**
Should edited values persist across page reloads (e.g. saved to `localStorage`), or is
this a live-session-only tool?
Save to localStorage.

**Q7 — Trigger / button**
How is the editor opened? Is there already a button on the page for this, or does one need
to be added?
See the answer to Q3.