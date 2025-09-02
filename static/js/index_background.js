

class BackgroundWave {
    constructor () {
        this.canvas = document.getElementById("background");
        this.body = document.body;
        this.gl = this.canvas.getContext('webgl') || this.canvas.getContext('experimental-webgl');
        this.vertexShaderSource = `
            attribute vec4 a_position;
            void main() {
                gl_Position = a_position;
            }
        `
        this.fetchShader();
    }

    init() {
        console.log("Initializing shaders");
        this.vertexShader = this.createShader(this.gl.VERTEX_SHADER, this.vertexShaderSource);
        this.fragmentShader = this.createShader(this.gl.FRAGMENT_SHADER, this.fragShaderSrc);
        this.initProgram();
        this.initBuffer();

        console.log("Initialization complete, starting render loop");
        this.body.style.visibility = "visible";
        requestAnimationFrame(this.render.bind(this));
    }

    async fetchShader() {
        console.log("Fetching fragment shader from ", SHADERURL);
        const response = await fetch(SHADERURL);
        if (!response.ok) {
            console.error("Error fetching shader:", response.statusText);
            throw new Error("Failed to fetch shader");
        }

        this.fragShaderSrc = await response.text();
        if (!this.fragShaderSrc) {
            throw new Error("Failed to load fragment shader");
        }

        console.log("Fragment shader fetched successfully");
        this.init();
    }

    createShader(type, source) {
        console.log("Creating shader:", type);
        const shader = this.gl.createShader(type);
        this.gl.shaderSource(shader, source);
        this.gl.compileShader(shader);
        if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
            console.error("Error compiling shader:", this.gl.getShaderInfoLog(shader));
            this.gl.deleteShader(shader);
        }
        console.log("Shader compiled successfully");
        return shader;
    }

    initProgram() {
        console.log("Initializing shader program");
        this.shaderProgram = this.gl.createProgram();
        this.gl.attachShader(this.shaderProgram, this.vertexShader);
        this.gl.attachShader(this.shaderProgram, this.fragmentShader);
        this.gl.linkProgram(this.shaderProgram);
        this.gl.useProgram(this.shaderProgram);
        console.log("Shader program initialized");
    }

    initBuffer() {
        console.log("Initializing buffer");
        const vertices = new Float32Array([
            -1, -1,
            1, -1,
            -1, 1,
            1, 1
        ]);

        const vertexBuffer = this.gl.createBuffer();
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, vertexBuffer);
        this.gl.bufferData(this.gl.ARRAY_BUFFER, vertices, this.gl.STATIC_DRAW);

        const a_position = this.gl.getAttribLocation(this.shaderProgram, 'a_position');
        this.gl.enableVertexAttribArray(a_position);
        this.gl.vertexAttribPointer(a_position, 2, this.gl.FLOAT, false, 0, 0);

        this.resolutionUniformLocation = this.gl.getUniformLocation(this.shaderProgram, 'resolution');
        this.timeUniformLocation = this.gl.getUniformLocation(this.shaderProgram, 'time');

        console.log("Buffer initialized");
    }

    render(timestamp) {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;

        this.gl.uniform2f(this.resolutionUniformLocation, this.canvas.width, this.canvas.height);
        this.gl.uniform1f(this.timeUniformLocation, timestamp * 0.001);

        this.gl.clearColor(0, 0, 0, 1);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);
        this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
        this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
        requestAnimationFrame(this.render.bind(this));
    }
}

document.addEventListener("DOMContentLoaded", () => {
    new BackgroundWave();
});
