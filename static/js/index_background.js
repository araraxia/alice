const BG_SHADER_KEY     = 'bgShaderParams';
const BG_SHADER_VERSION = 3;

const DEFAULT_SHADER_PARAMS = {
    _version: BG_SHADER_VERSION,
    scale: 2.5,

    sprite_max_vibrant:     ['0xFFFFFF', '0xFFFFFF'],
    sprite_brightest:       ['0xEDFEDF', '0xEDFEDF'],
    sprite_brighter:        ['0xDDDDDD', '0xDDDDDD'],
    sprite_bright:          ['0x7ADB52', '0x7ADB52'],
    sprite_medium:          ['0xB524AD', '0x4ADB52'],
    sprite_dark:            ['0xB52312', '0xB52312'],
    sprite_darker:          ['0x912264', '0x489912'],
    sprite_darkest:         ['0x024480', '0x012240'],
    sprite_darkestest:      ['0x024000', '0x000240'],
    sprite_more_darkestest: ['0x000400', '0x000080'],
    sprite_empty:           ['0x000000', '0x000000'],

    verticalWaveFreq:     .05,
    verticalWaveSpeed:    0.005,
    verticalWaveAmount:   0.005,
    wave1Freq:            1.0,
    wave1Speed:           0.005,
    innerWave1YCoeff:     7.0,
    innerWave1TimeCoeff:  0.3,
    wave2Freq:            3.0,
    wave2Speed:           0.005,
    innerWave2YCoeff:     9.0,
    modTimeMultiplier:    -0.1,
    oscillationFrequency:         0.1,
    oscillationStrength:         0.3,
    modA:                 -5.0,
    finalA:               2.0,

    waveSpeed:     0.01,
    waveScale:     0.005,
    waveAmplitude: 3,
    baseIntensity: -0.5,
    separation:    -0.5,
    color2MixAmount: 0.6,
    color1R: 0.3,  color1G: 0.15, color1B: 0.5,
    color2R:   0.5,  color2G:   0.3, color2B:   0.6,

    eq_innerWave1:      'sin(tileUV.x + tileUV.y * innerWave1YCoeff + time * innerWave1TimeCoeff)',
    eq_wave1:           'sin(tileUV.x * wave1Freq + innerWave1 + time * wave1Speed)',
    eq_innerWave2:      'cos(tileUV.x * tileUV.y * innerWave2YCoeff + time * wave2Speed)',
    eq_wave2:           'cos(tileUV.y * wave2Freq + innerWave2)',
    eq_combinedWaves:   'wave1 * wave2',
    eq_slowOscillation: 'sin(time * oscillationFrequency) * oscillationStrength',
    eq_modulation:      'modA * (modTimeMultiplier * time + slowOscillation)',
    eq_finalPattern:    'sin(combinedWaves * finalA + modulation)',
};

function buildShaderSrc(p) {
    const f = v => {
        const n = Number(v);
        if (isNaN(n)) return '0.0';
        const s = n.toString();
        return (s.includes('.') || s.includes('e')) ? s : s + '.0';
    };
    const sp = arr => `vec2(${arr[0]}, ${arr[1]})`;

    return `#ifdef GL_ES
precision mediump float;
#endif

uniform float time;
uniform vec2 resolution;
float scale = ${f(p.scale)};

vec2 SPR_SIZE = vec2(6.0, 8.0);

vec2 sprite_max_vibrant     = ${sp(p.sprite_max_vibrant)};
vec2 sprite_brightest       = ${sp(p.sprite_brightest)};
vec2 sprite_brighter        = ${sp(p.sprite_brighter)};
vec2 sprite_bright          = ${sp(p.sprite_bright)};
vec2 sprite_medium          = ${sp(p.sprite_medium)};
vec2 sprite_dark            = ${sp(p.sprite_dark)};
vec2 sprite_darker          = ${sp(p.sprite_darker)};
vec2 sprite_darkest         = ${sp(p.sprite_darkest)};
vec2 sprite_darkestest      = ${sp(p.sprite_darkestest)};
vec2 sprite_more_darkestest = ${sp(p.sprite_more_darkestest)};
vec2 sprite_empty           = ${sp(p.sprite_empty)};

const int NUM_TONES = 14;
vec2 tones[14];

float ch(vec2 ch, vec2 uv) {
    uv = floor(uv);
    float bitX = SPR_SIZE.x - uv.x - 1.0;
    float bitY = uv.y * SPR_SIZE.x;
    vec2 bitPosition = vec2(bitX + bitY) - vec2(24.0, 0.0);
    vec2 powerOf2 = exp2(clamp(bitPosition, -1.0, 25.0));
    vec2 extractedBits = mod(floor(ch / powerOf2), 2.0);
    bool inBounds = all(greaterThanEqual(uv, vec2(0.0))) && all(lessThan(uv, SPR_SIZE));
    float pixelValue = dot(extractedBits, vec2(1.0));
    return pixelValue * (inBounds ? 1.0 : 0.0);
}

void init_arrays() {
    tones[0]  = sprite_empty;
    tones[1]  = sprite_more_darkestest;
    tones[2]  = sprite_darkestest;
    tones[3]  = sprite_darkest;
    tones[4]  = sprite_darkest;
    tones[5]  = sprite_darker;
    tones[6]  = sprite_dark;
    tones[7]  = sprite_medium;
    tones[8]  = sprite_medium;
    tones[9]  = sprite_medium;
    tones[10] = sprite_bright;
    tones[11] = sprite_brighter;
    tones[12] = sprite_brightest;
    tones[13] = sprite_max_vibrant;
}

vec2 tone(float b) {
    for (int i = 0; i < NUM_TONES; i++) {
        if (b < float(i) / float(NUM_TONES)) return tones[i];
    }
    return tones[NUM_TONES - 1];
}

void main() {
    init_arrays();

    vec2 spriteGridSize = SPR_SIZE * scale;
    vec2 fitres = floor(resolution / spriteGridSize) * spriteGridSize;
    vec2 res = floor(resolution.xy / SPR_SIZE) / scale;
    vec2 uv = floor(gl_FragCoord.xy / scale);
    vec2 uv2 = uv * 0.357;
    vec2 screenOffset = (resolution - fitres) / (2.0 * scale);
    uv -= screenOffset;

    float minResolution = min(res.x, res.y);
    vec2 tileUV = floor(uv / SPR_SIZE) / minResolution;

    float verticalWaveFreq    = ${f(p.verticalWaveFreq)};
    float verticalWaveSpeed   = ${f(p.verticalWaveSpeed)};
    float verticalWaveAmount  = ${f(p.verticalWaveAmount)};
    tileUV.y += sin(time * verticalWaveSpeed + tileUV.x * verticalWaveFreq) * verticalWaveAmount;

    float wave1Freq           = ${f(p.wave1Freq)};
    float wave1Speed          = ${f(p.wave1Speed)};
    float innerWave1YCoeff    = ${f(p.innerWave1YCoeff)};
    float innerWave1TimeCoeff = ${f(p.innerWave1TimeCoeff)};
    float wave2Freq           = ${f(p.wave2Freq)};
    float wave2Speed          = ${f(p.wave2Speed)};
    float innerWave2YCoeff    = ${f(p.innerWave2YCoeff)};
    float modTimeMultiplier   = ${f(p.modTimeMultiplier)};
    float oscillationFrequency        = ${f(p.oscillationFrequency)};
    float oscillationStrength        = ${f(p.oscillationStrength)};
    float modA                = ${f(p.modA)};
    float finalA              = ${f(p.finalA)};

    float innerWave1      = ${p.eq_innerWave1};
    float wave1           = ${p.eq_wave1};
    float innerWave2      = ${p.eq_innerWave2};
    float wave2           = ${p.eq_wave2};
    float combinedWaves   = ${p.eq_combinedWaves};
    float slowOscillation = ${p.eq_slowOscillation};
    float modulation      = ${p.eq_modulation};
    float finalPattern    = ${p.eq_finalPattern};

    float plm = (finalPattern / 2.0 + 0.4);

    vec2 spriteData     = tone(plm);
    vec2 spritePixelPos = mod(uv, SPR_SIZE);
    float pixelValue    = ch(spriteData, spritePixelPos);

    float baseBrightness = 0.4;
    pixelValue = abs(pixelValue) + baseBrightness;

    vec2 screenBounds = fitres / scale;
    bool inRange = all(greaterThan(uv, vec2(0.0))) && all(lessThan(uv, screenBounds));
    pixelValue *= inRange ? 1.0 : 0.0;

    float waveSpeed     = ${f(p.waveSpeed)};
    float waveScale     = ${f(p.waveScale)};
    float waveAmplitude = ${f(p.waveAmplitude)};
    float baseIntensity = ${f(p.baseIntensity)};
    float separation    = ${f(p.separation)};

    float color1Phase   = uv.y * waveScale + time * waveSpeed;
    float color1Texture = length(uv2 * 0.015);
    float color1WaveRaw = sin(color1Phase + color1Texture);
    float color1Wave    = color1WaveRaw * 0.5 + 0.5;

    float color2Phase   = uv.x * waveScale * 1.3 + time * waveSpeed * 0.7;
    float phaseOffset = 3.14159;
    float color2WaveRaw = cos(color2Phase + phaseOffset);
    float color2Wave    = color2WaveRaw * 0.5 + 0.5;

    float color1Threshold   = smoothstep(separation, 1.0, color1Wave);
    float color2Threshold     = smoothstep(separation, 1.0, color2Wave);
    float color1Base        = baseIntensity + color1Threshold * waveAmplitude;
    float color2Base          = baseIntensity + color2Threshold   * waveAmplitude;
    float color1Suppression = 1.0 - color2Threshold   * 0.7;
    float color2Suppression   = 1.0 - color1Threshold * 0.7;

    float color1Intensity = pixelValue * color1Base * color1Suppression;
    float color2Intensity   = pixelValue * color2Base   * color2Suppression;

    vec3 color1Color = vec3(${f(p.color1R)}, ${f(p.color1G)}, ${f(p.color1B)});
    vec3 color2Color   = vec3(${f(p.color2R)},   ${f(p.color2G)},   ${f(p.color2B)});

    vec3 color1 = color1Color * color1Intensity;
    vec3 color2   = color2Color   * color2Intensity;

    float color2MixAmount = ${f(p.color2MixAmount)};
    vec3 finalColor = color1 + color2 * color2MixAmount;

    gl_FragColor = vec4(finalColor, 1.0);
}`;
}

class BackgroundWave {
    constructor() {
        this.canvas = document.getElementById('background');
        this.body   = document.body;
        this.gl     = this.canvas
            ? (this.canvas.getContext('webgl') || this.canvas.getContext('experimental-webgl'))
            : null;
        this.isEnabled   = true;
        this.animationId = null;

        if (!this.gl) {
            console.warn('[BackgroundWave] WebGL unavailable — background disabled');
            this.body.style.visibility = 'visible';
            return;
        }

        this.vertexShaderSource = `
            attribute vec4 a_position;
            void main() { gl_Position = a_position; }
        `;

        this.currentParams  = this._loadParams();
        this.fragShaderSrc  = buildShaderSrc(this.currentParams);
        this.init();
    }

    _loadParams() {
        try {
            const saved = localStorage.getItem(BG_SHADER_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                if (parsed._version === BG_SHADER_VERSION) {
                    return { ...DEFAULT_SHADER_PARAMS, ...parsed };
                }
                localStorage.removeItem(BG_SHADER_KEY);
            }
        } catch (e) {}
        return { ...DEFAULT_SHADER_PARAMS };
    }

    saveParams(params) {
        try {
            localStorage.setItem(BG_SHADER_KEY, JSON.stringify({ ...params, _version: BG_SHADER_VERSION }));
        } catch (e) {}
    }

    init() {
        this.vertexShader   = this.createShader(this.gl.VERTEX_SHADER,   this.vertexShaderSource);
        this.fragmentShader = this.createShader(this.gl.FRAGMENT_SHADER, this.fragShaderSrc);
        if (!this.vertexShader || !this.fragmentShader) {
            console.error('[BackgroundWave] Shader compilation failed on init');
            this.body.style.visibility = 'visible';
            return;
        }
        this.initProgram();
        this.initBuffer();
        this.body.style.visibility = 'visible';
        this.animationId = requestAnimationFrame(this.render.bind(this));
    }

    createShader(type, source) {
        const shader = this.gl.createShader(type);
        this.gl.shaderSource(shader, source);
        this.gl.compileShader(shader);
        if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
            console.error('[BackgroundWave] Shader compile error:', this.gl.getShaderInfoLog(shader));
            this.gl.deleteShader(shader);
            return null;
        }
        return shader;
    }

    recompile(params) {
        if (!this.gl) return { ok: false, error: 'WebGL not available' };

        const src     = buildShaderSrc(params);
        const newFrag = this.gl.createShader(this.gl.FRAGMENT_SHADER);
        this.gl.shaderSource(newFrag, src);
        this.gl.compileShader(newFrag);
        if (!this.gl.getShaderParameter(newFrag, this.gl.COMPILE_STATUS)) {
            const err = this.gl.getShaderInfoLog(newFrag);
            this.gl.deleteShader(newFrag);
            return { ok: false, error: err };
        }

        const newProg = this.gl.createProgram();
        this.gl.attachShader(newProg, this.vertexShader);
        this.gl.attachShader(newProg, newFrag);
        this.gl.linkProgram(newProg);
        if (!this.gl.getProgramParameter(newProg, this.gl.LINK_STATUS)) {
            const err = this.gl.getProgramInfoLog(newProg);
            this.gl.deleteShader(newFrag);
            this.gl.deleteProgram(newProg);
            return { ok: false, error: err };
        }

        this.gl.detachShader(this.shaderProgram, this.fragmentShader);
        this.gl.deleteShader(this.fragmentShader);
        this.gl.deleteProgram(this.shaderProgram);

        this.fragmentShader = newFrag;
        this.shaderProgram  = newProg;
        this.gl.useProgram(this.shaderProgram);
        this.resolutionUniformLocation = this.gl.getUniformLocation(this.shaderProgram, 'resolution');
        this.timeUniformLocation       = this.gl.getUniformLocation(this.shaderProgram, 'time');

        this.currentParams = params;
        this.fragShaderSrc = src;
        return { ok: true };
    }

    initProgram() {
        this.shaderProgram = this.gl.createProgram();
        this.gl.attachShader(this.shaderProgram, this.vertexShader);
        this.gl.attachShader(this.shaderProgram, this.fragmentShader);
        this.gl.linkProgram(this.shaderProgram);
        this.gl.useProgram(this.shaderProgram);
    }

    initBuffer() {
        const vertices = new Float32Array([-1,-1, 1,-1, -1,1, 1,1]);
        const buf = this.gl.createBuffer();
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, buf);
        this.gl.bufferData(this.gl.ARRAY_BUFFER, vertices, this.gl.STATIC_DRAW);

        const a_pos = this.gl.getAttribLocation(this.shaderProgram, 'a_position');
        this.gl.enableVertexAttribArray(a_pos);
        this.gl.vertexAttribPointer(a_pos, 2, this.gl.FLOAT, false, 0, 0);

        this.resolutionUniformLocation = this.gl.getUniformLocation(this.shaderProgram, 'resolution');
        this.timeUniformLocation       = this.gl.getUniformLocation(this.shaderProgram, 'time');
    }

    render(timestamp) {
        if (!this.isEnabled) return;
        this.canvas.width  = window.innerWidth;
        this.canvas.height = window.innerHeight;
        this.gl.uniform2f(this.resolutionUniformLocation, this.canvas.width, this.canvas.height);
        this.gl.uniform1f(this.timeUniformLocation, timestamp * 0.001);
        this.gl.clearColor(0, 0, 0, 1);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);
        this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
        this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
        this.animationId = requestAnimationFrame(this.render.bind(this));
    }

    toggle() {
        if (!this.gl) return this.isEnabled;
        this.isEnabled = !this.isEnabled;
        if (this.isEnabled) {
            this.canvas.style.display = 'block';
            this.animationId = requestAnimationFrame(this.render.bind(this));
        } else {
            this.canvas.style.display = 'none';
            if (this.animationId) {
                cancelAnimationFrame(this.animationId);
                this.animationId = null;
            }
        }
        return this.isEnabled;
    }

    isBackgroundEnabled() { return this.isEnabled; }
}

let backgroundWave;
document.addEventListener('DOMContentLoaded', () => {
    backgroundWave = new BackgroundWave();
});
