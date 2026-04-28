(() => {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReducedMotion) return;

  const canvas = document.createElement('canvas');
  canvas.id = 'hacker-grid-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  document.body.prepend(canvas);

  const gl = canvas.getContext('webgl', {
    alpha: true,
    antialias: false,
    depth: false,
    stencil: false,
    premultipliedAlpha: false
  });

  if (!gl) {
    canvas.remove();
    return;
  }

  const vertexSource = `
    attribute vec2 aPosition;
    varying vec2 vUv;
    void main() {
      vUv = (aPosition + 1.0) * 0.5;
      gl_Position = vec4(aPosition, 0.0, 1.0);
    }
  `;

  const fragmentSource = `
    precision mediump float;
    varying vec2 vUv;
    uniform vec2 uResolution;
    uniform float uTime;
    uniform vec2 uMouse;

    float hash(vec2 p) {
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
    }

    float grid(vec2 uv, float size, float thickness) {
      vec2 g = abs(fract(uv * size - 0.5) - 0.5) / fwidth(uv * size);
      float line = min(g.x, g.y);
      return 1.0 - smoothstep(0.0, thickness, line);
    }

    void main() {
      vec2 uv = vUv;
      float aspect = uResolution.x / max(uResolution.y, 1.0);
      vec2 centered = (uv - 0.5) * vec2(aspect, 1.0);

      float t = uTime * 0.35;
      float coarseGrid = grid(uv + vec2(t * 0.04, -t * 0.12), 14.0, 1.2);
      float fineGrid = grid(uv + vec2(-t * 0.11, t * 0.07), 55.0, 1.0) * 0.35;

      float scan = 0.15 + 0.85 * exp(-fract(uv.y * 2.0 + t * 1.35) * 8.5);
      float noise = (hash(floor(uv * uResolution.xy * 0.2 + t * 90.0)) - 0.5) * 0.07;

      vec2 mouse = (uMouse - 0.5) * vec2(aspect, 1.0);
      float dist = length(centered - mouse);
      float pulse = exp(-dist * 7.5) * (0.35 + 0.65 * sin(uTime * 5.0));

      vec3 base = vec3(0.01, 0.03, 0.02);
      vec3 neon = vec3(0.12, 0.95, 0.42);
      float intensity = coarseGrid * 0.55 + fineGrid + scan * 0.18 + pulse * 0.3 + noise;
      vec3 color = base + neon * intensity;

      float vignette = smoothstep(1.1, 0.2, length(centered));
      color *= vignette;

      float alpha = clamp(intensity * 0.28 + 0.08, 0.08, 0.42);
      gl_FragColor = vec4(color, alpha);
    }
  `;

  const createShader = (type, source) => {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.warn(gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  };

  const vShader = createShader(gl.VERTEX_SHADER, vertexSource);
  const fShader = createShader(gl.FRAGMENT_SHADER, fragmentSource);
  if (!vShader || !fShader) {
    canvas.remove();
    return;
  }

  const program = gl.createProgram();
  gl.attachShader(program, vShader);
  gl.attachShader(program, fShader);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.warn(gl.getProgramInfoLog(program));
    canvas.remove();
    return;
  }

  gl.useProgram(program);

  const quad = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
    gl.STATIC_DRAW
  );

  const aPosition = gl.getAttribLocation(program, 'aPosition');
  gl.enableVertexAttribArray(aPosition);
  gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);

  const uResolution = gl.getUniformLocation(program, 'uResolution');
  const uTime = gl.getUniformLocation(program, 'uTime');
  const uMouse = gl.getUniformLocation(program, 'uMouse');

  let mouseX = 0.5;
  let mouseY = 0.5;
  const handlePointer = (x, y) => {
    mouseX = Math.min(Math.max(x / window.innerWidth, 0), 1);
    mouseY = 1 - Math.min(Math.max(y / window.innerHeight, 0), 1);
  };

  window.addEventListener('pointermove', (event) => {
    handlePointer(event.clientX, event.clientY);
  }, { passive: true });

  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.floor(window.innerWidth * dpr);
    const height = Math.floor(window.innerHeight * dpr);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(uResolution, canvas.width, canvas.height);
  };

  window.addEventListener('resize', resize, { passive: true });
  resize();

  const start = performance.now();
  const loop = () => {
    const now = (performance.now() - start) / 1000;
    gl.uniform1f(uTime, now);
    gl.uniform2f(uMouse, mouseX, mouseY);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    requestAnimationFrame(loop);
  };

  requestAnimationFrame(loop);
})();
