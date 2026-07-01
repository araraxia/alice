class ShaderEditor {
    constructor() {
        this.applyBtn     = document.getElementById('shader-apply-button');
        this.resetBtn     = document.getElementById('shader-reset-button');
        this._hintUpdaters = null;

        if (this.applyBtn) this.applyBtn.addEventListener('click', () => this.apply());
        if (this.resetBtn) this.resetBtn.addEventListener('click', () => this.reset());

        this._waitForBg();
    }

    _waitForBg() {
        if (typeof backgroundWave !== 'undefined' && backgroundWave && backgroundWave.currentParams) {
            this.populate(backgroundWave.currentParams);
            this._attachDefaultHints();
        } else {
            setTimeout(() => this._waitForBg(), 100);
        }
    }

    _num(id) {
        const el = document.getElementById(id);
        return el ? parseFloat(el.value) : 0;
    }

    _hex(id) {
        const el = document.getElementById(id);
        return el ? el.value.trim() || '0x000000' : '0x000000';
    }

    _eq(id) {
        const el = document.getElementById(id);
        return el ? el.value.trim() : '';
    }

    collectParams() {
        const hex = (base, idx) => this._hex(`sed-spr-${base}-${idx}`);
        const sp  = name => [hex(name, 0), hex(name, 1)];

        return {
            scale: this._num('sed-scale'),

            sprite_max_vibrant:     sp('max_vibrant'),
            sprite_brightest:       sp('brightest'),
            sprite_brighter:        sp('brighter'),
            sprite_bright:          sp('bright'),
            sprite_medium:          sp('medium'),
            sprite_dark:            sp('dark'),
            sprite_darker:          sp('darker'),
            sprite_darkest:         sp('darkest'),
            sprite_darkestest:      sp('darkestest'),
            sprite_more_darkestest: sp('more_darkestest'),
            sprite_empty:           sp('empty'),

            verticalWaveFreq:     this._num('sed-verticalWaveFreq'),
            verticalWaveSpeed:    this._num('sed-verticalWaveSpeed'),
            verticalWaveAmount:   this._num('sed-verticalWaveAmount'),
            wave1Freq:            this._num('sed-wave1Freq'),
            wave1Speed:           this._num('sed-wave1Speed'),
            innerWave1YCoeff:     this._num('sed-innerWave1YCoeff'),
            innerWave1TimeCoeff:  this._num('sed-innerWave1TimeCoeff'),
            wave2Freq:            this._num('sed-wave2Freq'),
            wave2Speed:           this._num('sed-wave2Speed'),
            innerWave2YCoeff:     this._num('sed-innerWave2YCoeff'),
            modTimeMultiplier:    this._num('sed-modTimeMultiplier'),
            oscillationFrequency:         this._num('sed-oscillationFrequency'),
            oscillationStrength:         this._num('sed-oscillationStrength'),
            modA:                 this._num('sed-modA'),
            finalA:               this._num('sed-finalA'),

            waveSpeed:     this._num('sed-waveSpeed'),
            waveScale:     this._num('sed-waveScale'),
            waveAmplitude: this._num('sed-waveAmplitude'),
            baseIntensity: this._num('sed-baseIntensity'),
            separation:    this._num('sed-separation'),
            color2MixAmount: this._num('sed-color2MixAmount'),
            color1R:       this._num('sed-color1R'),
            color1G:       this._num('sed-color1G'),
            color1B:       this._num('sed-color1B'),
            color2R:         this._num('sed-color2R'),
            color2G:         this._num('sed-color2G'),
            color2B:         this._num('sed-color2B'),

            eq_innerWave1:      this._eq('sed-eq-innerWave1'),
            eq_wave1:           this._eq('sed-eq-wave1'),
            eq_innerWave2:      this._eq('sed-eq-innerWave2'),
            eq_wave2:           this._eq('sed-eq-wave2'),
            eq_combinedWaves:   this._eq('sed-eq-combinedWaves'),
            eq_slowOscillation: this._eq('sed-eq-slowOscillation'),
            eq_modulation:      this._eq('sed-eq-modulation'),
            eq_finalPattern:    this._eq('sed-eq-finalPattern'),
        };
    }

    populate(params) {
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };

        set('sed-scale', params.scale);

        ['max_vibrant','brightest','brighter','bright','medium','dark','darker',
         'darkest','darkestest','more_darkestest','empty'].forEach(name => {
            const arr = params[`sprite_${name}`] || ['0x000000', '0x000000'];
            set(`sed-spr-${name}-0`, arr[0]);
            set(`sed-spr-${name}-1`, arr[1]);
        });

        ['verticalWaveFreq','verticalWaveSpeed','verticalWaveAmount',
         'wave1Freq','wave1Speed','innerWave1YCoeff','innerWave1TimeCoeff',
         'wave2Freq','wave2Speed','innerWave2YCoeff','modTimeMultiplier',
         'oscillationFrequency','oscillationStrength','modA','finalA',
         'waveSpeed','waveScale','waveAmplitude','baseIntensity','separation','color2MixAmount',
         'color1R','color1G','color1B','color2R','color2G','color2B'].forEach(name => {
            set(`sed-${name}`, params[name]);
        });

        ['innerWave1','wave1','innerWave2','wave2','combinedWaves',
         'slowOscillation','modulation','finalPattern'].forEach(name => {
            set(`sed-eq-${name}`, params[`eq_${name}`]);
        });

        if (this._hintUpdaters) this._refreshHints();
    }

    _buildDefaultMap() {
        const d   = typeof DEFAULT_SHADER_PARAMS !== 'undefined' ? DEFAULT_SHADER_PARAMS : {};
        const map = {};

        map['sed-scale'] = d.scale;

        ['max_vibrant','brightest','brighter','bright','medium','dark','darker',
         'darkest','darkestest','more_darkestest','empty'].forEach(name => {
            const arr = d[`sprite_${name}`] || ['0x000000','0x000000'];
            map[`sed-spr-${name}-0`] = arr[0];
            map[`sed-spr-${name}-1`] = arr[1];
        });

        ['verticalWaveFreq','verticalWaveSpeed','verticalWaveAmount',
         'wave1Freq','wave1Speed','innerWave1YCoeff','innerWave1TimeCoeff',
         'wave2Freq','wave2Speed','innerWave2YCoeff','modTimeMultiplier',
         'oscillationFrequency','oscillationStrength','modA','finalA',
         'waveSpeed','waveScale','waveAmplitude','baseIntensity','separation','color2MixAmount',
         'color1R','color1G','color1B','color2R','color2G','color2B'].forEach(name => {
            map[`sed-${name}`] = d[name];
        });

        ['innerWave1','wave1','innerWave2','wave2','combinedWaves',
         'slowOscillation','modulation','finalPattern'].forEach(name => {
            map[`sed-eq-${name}`] = d[`eq_${name}`];
        });

        return map;
    }

    _attachDefaultHints() {
        const defaultMap   = this._buildDefaultMap();
        this._hintUpdaters = [];

        Object.entries(defaultMap).forEach(([id, defaultVal]) => {
            const el = document.getElementById(id);
            if (!el) return;

            const hint = document.createElement('span');
            hint.className = 'sed-default-hint';
            el.insertAdjacentElement('afterend', hint);

            const isNum = el.type === 'number';
            const defaultStr = String(defaultVal);

            const update = () => {
                const raw = el.value.trim();
                const changed = isNum
                    ? parseFloat(raw) !== parseFloat(defaultStr)
                    : raw !== defaultStr;
                hint.textContent = changed ? `↩ ${defaultVal}` : '';
            };

            el.addEventListener('input', update);
            update();
            this._hintUpdaters.push(update);
        });
    }

    _refreshHints() {
        this._hintUpdaters.forEach(fn => fn());
    }

    apply() {
        if (typeof backgroundWave === 'undefined' || !backgroundWave || !backgroundWave.gl) {
            alert('Background shader is not available.');
            return;
        }
        const params = this.collectParams();
        const result = backgroundWave.recompile(params);
        if (!result.ok) {
            alert('Shader compile error:\n\n' + result.error);
            return;
        }
        backgroundWave.saveParams(params);
    }

    reset() {
        if (typeof DEFAULT_SHADER_PARAMS !== 'undefined') {
            this.populate(DEFAULT_SHADER_PARAMS);
        }
    }
}

window.ShaderEditor = ShaderEditor;
