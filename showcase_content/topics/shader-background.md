# GLSL Shader Background

## Overview

The animated background on the main page is powered by a custom GLSL (OpenGL Shading Language) shader that creates a dynamic, wave-based pattern with purple and gold colors.

## Technical Implementation

### Canvas Setup

The background uses an HTML5 canvas with WebGL context:

```javascript
const canvas = document.getElementById('background');
const gl = canvas.getContext('webgl');
```

### Shader Pipeline

The system consists of two shaders:

1. **Vertex Shader** - Positions vertices for screen-space rendering
2. **Fragment Shader** - Calculates color for each pixel

### Wave Pattern Generation

The shader creates complex patterns using multiple sine/cosine waves:

```glsl
float wave1 = sin(tileUV.x * wave1Freq + innerWave1 + time * wave1Speed);
float wave2 = cos(tileUV.y * wave2Freq + innerWave2);
float combinedWaves = wave1 + wave2;
```

### Procedural Textures

The pattern is generated procedurally using:

- **Tiled sprites** - 6×8 pixel patterns
- **Bit encoding** - Patterns stored as hex values
- **Dynamic selection** - Pattern chosen based on wave intensity

## Sprite System

### Tone Definitions

Different "tones" represent different brightness levels:

```glsl
vec2 sprite_max_vibrant = vec2(0xFFFFFF, 0xFFFFFF);
vec2 sprite_brightest = vec2(0xEDFEDF, 0xEDFEDF);
vec2 sprite_brighter = vec2(0xDDDDDD, 0xDDDDDD);
vec2 sprite_bright = vec2(0x7ADB52, 0x7ADB52);
vec2 sprite_medium = vec2(0xB524AD, 0x4ADB52);
vec2 sprite_dark = vec2(0xB52312, 0xB52312);
vec2 sprite_darker = vec2(0x912264, 0x489912);
vec2 sprite_darkest = vec2(0x024480, 0x012240);
vec2 sprite_darkestest = vec2(0x024000, 0x000240);
vec2 sprite_more_darkestest = vec2(0x000400, 0x000080);
vec2 sprite_empty = vec2(0x000000, 0x000000);
```

Each vec2 stores a complete 6×8 pixel pattern in 48 bit. Ideally these would be generated algorithmically, but the dither patterns are currently designed manually. I'm not very knowledgable about different dither pattern algorithms, so combining that with my first attempt at utilizing GLSL was a bit too much for one project.

If you want to learn more about dither patterns, here are some good resources that I would recommend:

- [https://surma.dev/things/ditherpunk/](https://surma.dev/things/ditherpunk/)
- [https://forums.tigsource.com/index.php?topic=40832.msg1363742#msg1363742](https://forums.tigsource.com/index.php?topic=40832.msg1363742#msg1363742) (more about mapping a dither pattern but still a neat read anyway)
- [https://blog.kaetemi.be/2015/04/01/practical-bayer-dithering/](https://blog.kaetemi.be/2015/04/01/practical-bayer-dithering/)

### Bit Extraction

The shader extracts individual pixels from the packed data:

```glsl
float bitX = SPR_SIZE.x - uv.x - 1.0;
float bitY = uv.y * SPR_SIZE.x;
vec2 bitPosition = vec2(bitX + bitY) - vec2(24.0, 0.0);

vec2 powerOf2 = exp2(clamp(bitPosition, -1.0, 25.0));
vec2 extractedBits = mod(floor(ch / powerOf2), 2.0);
```

## Color System

### Dual Wave Colors

Two independent color waves create the purple/gold effect:

```glsl
// Purple wave - vertical bias
float purpleWave = sin(uv.y * waveScale + time * waveSpeed);

// Gold wave - horizontal bias with 180° phase shift
float goldWave = cos(uv.x * waveScale * 1.3 + time * waveSpeed * 0.7 + π);
```

### Color Mixing

Colors are applied with mutual suppression to reduce overlap:

```glsl
vec3 purpleColor = vec3(0.5, 0.15, 0.5);
vec3 goldColor = vec3(1.0, 0.87, 0.11);

float purpleSuppression = 1.0 - goldThreshold * 0.7;
float goldSuppression = 1.0 - purpleThreshold * 0.7;

vec3 finalColor = purple * purpleSuppression + gold * goldSuppression;
```

## Performance Optimizations

### Efficient Rendering

- **Single draw call** - Entire background in one pass
- **Procedural generation** - No texture uploads
- **Bit operations** - Fast pixel extraction
- **GPU acceleration** - All calculations on GPU

### Adaptive Quality

The shader scales with screen resolution automatically:

```glsl
vec2 fitres = floor(resolution / spriteGridSize) * spriteGridSize;
vec2 res = floor(resolution.xy / SPR_SIZE) / scale;
```

## Customization

### Adjustable Parameters

Easy to modify values:

```glsl
float waveSpeed = 0.5;        // Animation speed
float waveScale = 0.005;      // Wave frequency
float waveAmplitude = 0.8;    // Wave intensity
float separation = 0.2;       // Color separation
```

## Browser Compatibility

Requires WebGL support (available in all modern browsers):

- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support (iOS 8+)
- Opera: Full support

Fallback: Plain color background if WebGL unavailable.

## Toggle Control

Users can disable the background animation:

```javascript
backgroundWave.toggle();
```

This improves performance on lower-end devices.

## Source Files

- [indexBGShader.glsl](/files/showcase/indexBGShader.glsl) - Main shader code
- [index_background.js](/files/showcase/index_background.js) - JavaScript wrapper
- [sprite_pattern_generator.py](/files/showcase/sprite_pattern_generator.py) - Pattern creation tool

## Future Enhancements

Ideas for the shader:

- [ ] User-customizable colors
- [ ] Algorithmic pattern generation
- [ ] Particle effects
- [ ] Interactive elements (mouse influence)
- [ ] Seasonal themes
- [ ] Performance auto-adjust
