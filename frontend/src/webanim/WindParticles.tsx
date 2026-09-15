import { useEffect, useRef } from "react";
import type { GridCell } from "../types";
import { CHENNAI } from "../stores/appStore";

interface Props {
  grid: GridCell[];
  active: boolean;
}

/**
 * WindParticles — a Canvas 2D overlay rendered inside the map container.
 * Drops drift along the u/v wind field from the backend /api/wind/grid.
 */
export default function WindParticles({ grid, active }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    let raf = 0;
    const N = 90;
    const parts = Array.from({ length: N }, () => ({
      x: Math.random(),
      y: Math.random(),
      hue: 195 + Math.random() * 25,
    }));

    function resize() {
      canvas.width = canvas.clientWidth || 400;
      canvas.height = canvas.clientHeight || 400;
    }
    resize();
    window.addEventListener("resize", resize);

    function uv(x: number, y: number): [number, number] {
      let best = 0, bd = Infinity;
      for (let i = 0; i < grid.length; i++) {
        const c = grid[i];
        const dl = ((c.lon - (CHENNAI.lon + (x - 0.5) * 0.12)) ** 2 +
          (c.lat - (CHENNAI.lat - (y - 0.5) * 0.12)) ** 2) ** 0.5;
        if (dl < bd) { bd = dl; best = i; }
      }
      const c = grid[best];
      return [c.u_ms ?? 0, c.v_ms ?? 0];
    }

    function frame() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const p of parts) {
        const [u, v] = uv(p.x, p.y);
        const sp = Math.hypot(u, v);
        if (sp < 0.4) { p.x += (Math.random() - 0.5) * 0.002; p.y += (Math.random() - 0.5) * 0.002; }
        else {
          p.x += (u / sp) * 0.012 * Math.min(1.6, sp);
          p.y += (v / sp) * 0.012 * Math.min(1.6, sp);
        }
        if (p.x < 0) p.x = 1; if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1; if (p.y > 1) p.y = 0;

        const alpha = Math.min(0.75, 0.12 + sp * 0.25);
        ctx.strokeStyle = `hsla(${p.hue}, 85%, 62%, ${alpha})`;
        ctx.lineWidth = sp > 4 ? 1.6 : 1.1;
        ctx.beginPath();
        ctx.moveTo(p.x * canvas.width, p.y * canvas.height);
        ctx.lineTo((p.x - (u / (sp || 1)) * 0.018) * canvas.width, (p.y - (v / (sp || 1)) * 0.018) * canvas.height);
        ctx.stroke();
      }
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, [active, grid]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute", inset: 0, width: "100%", height: "100%",
        pointerEvents: "none", display: active ? "block" : "none", zIndex: 3,
      }}
    />
  );
}