#ifdef GL_ES
precision mediump float;
#endif

uniform float time; // Animation Clock
uniform vec2 resolution; // Canvas resolution
float scale = 2.5; // Scale factor for the background

vec2 SPR_SIZE = vec2(6.0, 8.0);

// Grayscale tones - Fixed hex values
vec2 c_a = vec2(0.25, 0.25);  // 0x404040 normalized
vec2 c_b = vec2(0.5, 0.5);    // 0x808080 normalized
vec2 c_c = vec2(0.69, 0.69);  // 0xB0B0B0 normalized
vec2 c_d = vec2(0.94, 0.94);  // 0xF0F0F0 normalized
vec2 c_spc = vec2(0.0, 0.0);  // Fixed invalid hex value

const int NUM_TONES = 12;
vec2 tones[12];

float ch(vec2 ch, vec2 uv)
{
    uv = floor(uv);
    vec2 b = vec2((SPR_SIZE.x - uv.x - 1.0) + uv.y * SPR_SIZE.x) - vec2(24.0, 0.0);
    vec2 p = mod(floor(ch / exp2(clamp(b, -1.0, 25.0))), 2.0);
    
    // Fixed boolean logic
    bool inBounds = all(greaterThanEqual(uv, vec2(0.0))) && all(lessThan(uv, SPR_SIZE));
    float o = dot(p, vec2(1.0)) * (inBounds ? 1.0 : 0.0);
    return o;
}

void init_arrays()
{
    tones[0] = c_spc;
    tones[1] = c_spc;
    tones[2] = c_spc;
    tones[3] = c_spc;
    tones[4] = c_d;
    tones[5] = c_d;
    tones[6] = c_c;
    tones[7] = c_c;
    tones[8] = c_b;
    tones[9] = c_b;
    tones[10] = c_a;
    tones[11] = c_a;
}

vec2 tone(float b)
{
    for(int i = 0; i < NUM_TONES; i++)
    {
        if(b < float(i) / float(NUM_TONES))
        {
            return tones[i];
        }
    }
    
    return tones[NUM_TONES - 1];
}

void main() 
{
    init_arrays();
    vec2 fitres = floor(resolution / (SPR_SIZE * scale)) * (SPR_SIZE * scale);    
    vec2 res = floor(resolution.xy / SPR_SIZE) / scale;    
    vec2 uv = floor(gl_FragCoord.xy / scale);
    vec2 uv2 = uv * 0.357;
    uv -= (resolution - fitres) / (2.0 * scale);
    
    vec2 tasp = res / min(res.x, res.y);
    vec2 tuv = floor(uv / SPR_SIZE) / min(res.x, res.y);
    tuv.y += sin(time * 0.4 + tuv.x * 7.0) * 0.15;
    
    float plm = sin(tuv.x * 6.0 + sin(tuv.x + tuv.y * 5.0 + time * 0.3) + time * 0.4) + cos(tuv.y * 13.0 + cos(tuv.x - tuv.y * 9.0 + time * 0.1));
    plm = sin(plm * 2.0 - 5.0 * (-0.1 * time + sin(time * 0.25) * 2.0));
    plm = (plm / 2.0 + 0.4);
    
    vec2 c = tone(plm);
    
    float pix = ch(c, mod(uv, SPR_SIZE));
    pix = abs(pix) + 0.4;
    
    // Fixed boolean logic
    bool inRange = all(greaterThan(uv, vec2(0.0))) && all(lessThan(uv, fitres / scale));
    pix *= inRange ? 1.0 : 0.0;
    
    gl_FragColor = vec4(vec3(pix * 0.5 * sin(uv.y * 0.005 + time + length(uv2 * 0.015)), pix * 0.1, pix * 0.5), 1.0);
}