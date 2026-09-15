import { useEffect, useRef } from "react";

/**
 * RainWebGL — a subtle, state-responsive weather background.
 *
 * Pure visuals (WebGL fragment shader). NEVER a data source — the flood/weather
 * numbers on the dashboard always come from the backend model.
 *
 * Intensity uniforms:
 *   uRain    0..1        rain density/strength
 *   uLightning 0..1      active lightning flash
 *   uWater   0..1        rising water/flow effect at the bottom of the screen
 */

const VERT = `
attribute vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
`;

const FRAG = `
precision highp float;
uniform vec2 uRes;
uniform float uTime;
uniform float uRain;
uniform float uLightning;
uniform float uWater;
uniform float uStorm;   // storminess drives lightning frequency on the JS side

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

vec3 rain(vec2 uv, float t) {
  float density = uRain * 300.0;
  vec3 col = vec3(0.0);
  // screen-aligned rain streaks
  float grid = 60.0;
  vec2 cell = floor(uv * vec2(grid, grid * 0.9));
  float h = hash(cell);
  if (h < uRain) {
    float lane = cell.x / grid;
    float fall = fract(uv.y * grid * 0.9 + t * (4.0 + h * 8.0) - h * 20.0);
    float streak = smoothstep(0.0, 0.06, fall) * smoothstep(0.22, 0.1, fall);
    float mv = abs(uv.x * grid - lane - 0.5);
    streak *= smoothstep(0.45, 0.05, mv);
    col += vec3(0.75, 0.87, 1.0) * streak * 0.55 * (0.4 + 0.6 * h);
  }
  return col;
}

vec3 lake(vec2 uv, float t) {
  // animated water band rising from the bottom with the flood state
  float level = 0.04 + uWater * 0.16;
  vec3 col = vec3(0.0);
  if (uv.y < level) {
    float n = sin(uv.y * 90.0 + uTime * 1.4) * 0.5 + sin(uv.x * 140.0 - uTime * 0.9) * 0.5;
    col = vec3(0.35, 0.62, 0.98) * (0.5 + n * 0.35);
    col += vec3(0.4, 0.7, 1.0) * smoothstep(0.0, 0.01, level - uv.y);
    float spark = smoothstep(0.03, 0.0, abs(fract(uv.x * 33.0 + uTime) - 0.5));
    col += vec3(0.85, 0.95, 1.0) * spark * 0.2 * uWater;
  }
  return col;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uRes.xy;
  // soft sky gradient (light blue theme)
  vec3 sky = mix(vec3(0.86, 0.93, 1.0), vec3(0.94, 0.975, 1.0), uv.y);
  vec3 col = sky;

  col += rain(uv, uTime);
  col += lake(uv, uTime);

  // lightning flash (bounded between 0..1 uniform from JS)
  float flash = uLightning;
  col += vec3(0.92, 0.96, 1.0) * flash * 0.35;
  col += vec3(0.9, 0.95, 1.0) * flash * flash * 0.4;

  col = clamp(col, 0.0, 1.0);
  gl_FragColor = vec4(col, 1.0);
}
`;

interface Props {
  rainLevel: number;    // 0..1
  waterLevel: number;   // 0..1 (flood intensity)
}

function compile(gl: WebGLRenderingContext, type: number, src: string) {
  const sh = gl.createShader(type)!;
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    console.error(gl.getShaderInfoLog(sh));
  }
  return sh;
}

export default function RainWebGL({ rainLevel, waterLevel }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progRef = useRef<WebGLProgram | null>(null);
  const uniRef = useRef<Record<string, WebGLUniformLocation | null>>({});
  const flashRef = useRef(0);
  const nextFlashRef = useRef(2 + Math.random() * 6);
  const rainRef = useRef(rainLevel);
  const waterRef = useRef(waterLevel);
  const stormRef = useRef(rainLevel > 0.5 ? 1 : 0.4);

  useEffect(() => {
    rainRef.current = rainLevel;
    waterRef.current = waterLevel;
    stormRef.current = rainLevel > 0.65 ? 1.3 : rainLevel > 0.35 ? 0.8 : 0.35;
  }, [rainLevel, waterLevel]);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const glCtx = canvas.getContext("webgl", { alpha: true, antialias: true }) as WebGLRenderingContext | null;
    if (!glCtx) {
      canvas.style.display = "none";
      return;
    }
    const gl: WebGLRenderingContext = glCtx;
    const prog = gl.createProgram()!;
    gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    gl.useProgram(prog);
    progRef.current = prog;

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "aPos");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

    uniRef.current = {
      uRes: gl.getUniformLocation(prog, "uRes"),
      uTime: gl.getUniformLocation(prog, "uTime"),
      uRain: gl.getUniformLocation(prog, "uRain"),
      uLightning: gl.getUniformLocation(prog, "uLightning"),
      uWater: gl.getUniformLocation(prog, "uWater"),
      uStorm: gl.getUniformLocation(prog, "uStorm"),
    };

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    function resize() {
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = window.innerWidth + "px";
      canvas.style.height = window.innerHeight + "px";
      gl.viewport(0, 0, canvas.width, canvas.height);
    }
    resize();
    window.addEventListener("resize", resize);

    let raf = 0;
    const t0 = performance.now();
    function frame(now: number) {
      const t = (now - t0) / 1000;

      // lightning scheduling: occasional flashes scaled by storminess
      if (t > nextFlashRef.current) {
        if (Math.random() < (0.28 + stormRef.current * 0.3)) {
          flashRef.current = Math.random();
        }
        nextFlashRef.current = t + 3 + Math.random() * 8;
      }
      flashRef.current *= 0.82;

      gl.useProgram(prog);
      gl.uniform2f(uniRef.current.uRes, canvas.width, canvas.height);
      gl.uniform1f(uniRef.current.uTime, t);
      gl.uniform1f(uniRef.current.uRain, Math.min(1, rainRef.current));
      gl.uniform1f(uniRef.current.uLightning, Math.min(1, flashRef.current));
      gl.uniform1f(uniRef.current.uWater, Math.min(1, waterRef.current));
      gl.uniform1f(uniRef.current.uStorm, stormRef.current);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      gl.deleteProgram(prog);
    };
  }, []);

  return <canvas ref={canvasRef} className="webanim-layer" aria-hidden="true" />;
}