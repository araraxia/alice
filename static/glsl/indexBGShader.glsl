#ifdef GL_ES
precision mediump float;
#endif

uniform float time; // Animation Clock
uniform vec2 resolution; // Canvas resolution
float scale = 2.5; // Scale factor for the background

vec2 SPR_SIZE = vec2(6.0, 8.0);

// Dither Patterns for different brightness levels (using 24-bit color values)
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

const int NUM_TONES = 14;
vec2 tones[14];

float ch(vec2 ch, vec2 uv) {
    uv = floor(uv);

    // Calculate bit position within sprite
    float bitX = SPR_SIZE.x - uv.x - 1.0;
    float bitY = uv.y * SPR_SIZE.x;
    vec2 bitPosition = vec2(bitX + bitY) - vec2(24.0, 0.0);

    // Extract bits from sprite data
    vec2 powerOf2 = exp2(clamp(bitPosition, -1.0, 25.0));
    vec2 extractedBits = mod(floor(ch / powerOf2), 2.0);

    // Check if pixel is within sprite bounds
    bool inBounds = all(greaterThanEqual(uv, vec2(0.0))) && all(lessThan(uv, SPR_SIZE));

    // Combine bits and apply bounds check
    float pixelValue = dot(extractedBits, vec2(1.0));
    float result = pixelValue * (inBounds ? 1.0 : 0.0);

    return result;
}

void init_arrays() {
    tones[0] = sprite_empty;
    tones[1] = sprite_more_darkestest;
    tones[2] = sprite_darkestest;
    tones[3] = sprite_darkest;
    tones[4] = sprite_darkest;
    tones[5] = sprite_darker;
    tones[6] = sprite_dark;
    tones[7] = sprite_medium;
    tones[8] = sprite_medium;
    tones[9] = sprite_medium;
    tones[10] = sprite_bright;
    tones[11] = sprite_brighter;
    tones[12] = sprite_brightest;
    tones[13] = sprite_max_vibrant;
}

vec2 tone(float b) {
    for(int i = 0; i < NUM_TONES; i++) {
        if(b < float(i) / float(NUM_TONES)) {
            return tones[i];
        }
    }

    return tones[NUM_TONES - 1];
}

void main() {
    init_arrays();

    // === COORDINATE SETUP ===
    // Calculate fitted resolution that aligns with sprite grid
    vec2 spriteGridSize = SPR_SIZE * scale;
    vec2 fitres = floor(resolution / spriteGridSize) * spriteGridSize;

    // Calculate resolution in sprite units
    vec2 res = floor(resolution.xy / SPR_SIZE) / scale;

    // Get pixel coordinates and secondary UV for effects
    vec2 uv = floor(gl_FragCoord.xy / scale);
    vec2 uv2 = uv * 0.357;  // Secondary UV for additional texture effects

    // Center the pattern on screen
    vec2 screenOffset = (resolution - fitres) / (2.0 * scale);
    uv -= screenOffset;

    // === WAVE PATTERN GENERATION ===
    // Calculate aspect-corrected coordinates
    float minResolution = min(res.x, res.y);
    vec2 aspectRatio = res / minResolution;
    vec2 tileUV = floor(uv / SPR_SIZE) / minResolution;

    // Add vertical wave motion
    float verticalWaveFreq = 3.5;
    float verticalWaveSpeed = 0.05;
    float verticalWaveAmount = 0.2;
    tileUV.y += sin(time * verticalWaveSpeed + tileUV.x * verticalWaveFreq) * verticalWaveAmount;

    // === COMPLEX PATTERN CALCULATION ===
    // Primary wave components
    float wave1Freq = 1.0;
    float wave1Speed = 0.005;
    float innerWave1 = sin(tileUV.x + tileUV.y * 7.0 + time * 0.3);
    float wave1 = sin(tileUV.x * wave1Freq + innerWave1 + time * wave1Speed);

    float wave2Freq = 3.0;
    float wave2Speed = 0.005;
    float innerWave2 = cos(tileUV.x - tileUV.y * 9.0 + time * wave2Speed);
    float wave2 = cos(tileUV.y * wave2Freq + innerWave2);

    // Combine primary waves
    float combinedWaves = wave1 + wave2;

    // Apply secondary modulation
    float timeOffset = -0.1 * time;
    float slowOscillation = sin(time * 0.25) * 2.0;
    float modulation = -5.0 * (timeOffset + slowOscillation);
    float finalPattern = sin(combinedWaves * 2.0 + modulation);

    // Normalize pattern to [0, 1] range
    float plm = (finalPattern / 2.0 + 0.4);

    // === SPRITE RENDERING ===
    // Get sprite data based on pattern intensity
    vec2 spriteData = tone(plm);

    // Render sprite pixel at current position
    vec2 spritePixelPos = mod(uv, SPR_SIZE);
    float pixelValue = ch(spriteData, spritePixelPos);

    // Ensure pixel value is positive and add base brightness
    float baseBrightness = 0.4;
    pixelValue = abs(pixelValue) + baseBrightness;

    // === BOUNDARY MASKING ===
    // Only render pixels within the fitted screen area
    vec2 screenBounds = fitres / scale;
    bool inRange = all(greaterThan(uv, vec2(0.0))) && all(lessThan(uv, screenBounds));
    pixelValue *= inRange ? 1.0 : 0.0;

    // === COLOR WAVE CONTROLS ===
    float waveSpeed = 0.5;        // Controls animation speed
    float waveScale = 0.005;      // Controls wave frequency/size
    float waveAmplitude = 0.8;    // Controls wave intensity (0.0-1.0)
    float baseIntensity = 0.15;    // Minimum brightness to prevent black
    float separation = 0.2;       // Controls color separation (higher = less overlap)

    // === WAVE PATTERN GENERATION ===
    // Purple wave - vertical bias with texture influence
    float purplePhase = uv.y * waveScale + time * waveSpeed;
    float purpleTexture = length(uv2 * 0.015);
    float purpleWaveRaw = sin(purplePhase + purpleTexture);
    float purpleWave = (purpleWaveRaw * 0.5 + 0.5);  // Convert to [0,1]

    // Gold wave - horizontal bias with phase offset
    float goldPhase = uv.x * waveScale * 1.3 + time * waveSpeed * 0.7;
    float phaseOffset = 3.14159;  // π radians = 180° phase shift
    float goldWaveRaw = cos(goldPhase + phaseOffset);
    float goldWave = (goldWaveRaw * 0.5 + 0.5);  // Convert to [0,1]

    // === COLOR SEPARATION LOGIC ===
    // Create thresholds to reduce color overlap
    float purpleThreshold = smoothstep(separation, 1.0, purpleWave);
    float goldThreshold = smoothstep(separation, 1.0, goldWave);

    // Calculate base intensities
    float purpleBase = baseIntensity + purpleThreshold * waveAmplitude;
    float goldBase = baseIntensity + goldThreshold * waveAmplitude;

    // Apply mutual suppression to reduce overlap
    float purpleSuppression = 1.0 - goldThreshold * 0.7;
    float goldSuppression = 1.0 - purpleThreshold * 0.7;

    // Final intensity calculations
    float purpleIntensity = pixelValue * purpleBase * purpleSuppression;
    float goldIntensity = pixelValue * goldBase * goldSuppression;

    // === FINAL COLOR MIXING ===
    // Define color palettes
    vec3 purpleColor = vec3(0.5, 0.15, 0.5);  // RGB purple
    vec3 goldColor = vec3(1.0, 0.87, 0.11);    // More saturated gold (reduced green, removed blue)

    // Apply intensities to colors
    vec3 purple = purpleColor * purpleIntensity;
    vec3 gold = goldColor * goldIntensity;

    // Combine colors with gold slightly dimmed
    float goldMixAmount = 0.5;
    vec3 finalColor = purple + gold * goldMixAmount;

    gl_FragColor = vec4(finalColor, 1.0);
}