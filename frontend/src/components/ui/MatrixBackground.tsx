import { useEffect, useRef } from 'react';

interface Orb {
  x: number; y: number;
  vx: number; vy: number;
  r: number;
  color: string;
  opacity: number;
}

const ORBS: Orb[] = [
  { x: 0.15, y: 0.2,  vx: 0.00008, vy: 0.00005, r: 0.5,  color: '79,126,247',  opacity: 0.18 },
  { x: 0.75, y: 0.75, vx: -0.00006, vy: -0.00004, r: 0.45, color: '45,212,191',  opacity: 0.13 },
  { x: 0.55, y: 0.15, vx: 0.00005, vy: 0.00009,  r: 0.35, color: '99,102,241',  opacity: 0.09 },
  { x: 0.85, y: 0.35, vx: -0.00007, vy: 0.00006, r: 0.3,  color: '79,126,247',  opacity: 0.08 },
  { x: 0.2,  y: 0.8,  vx: 0.00006, vy: -0.00005, r: 0.4,  color: '45,212,191',  opacity: 0.07 },
];

export function MatrixBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = window.innerWidth;
    let h = window.innerHeight;
    let frameId: number;

    const state = ORBS.map(o => ({ ...o }));

    const resize = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w;
      canvas.height = h;
    };
    resize();
    window.addEventListener('resize', resize);

    const draw = () => {
      frameId = requestAnimationFrame(draw);

      ctx.clearRect(0, 0, w, h);

      for (const orb of state) {
        orb.x += orb.vx;
        orb.y += orb.vy;
        if (orb.x < -0.1 || orb.x > 1.1) orb.vx *= -1;
        if (orb.y < -0.1 || orb.y > 1.1) orb.vy *= -1;

        const cx = orb.x * w;
        const cy = orb.y * h;
        const r = orb.r * Math.min(w, h);

        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        grad.addColorStop(0,   `rgba(${orb.color}, ${orb.opacity})`);
        grad.addColorStop(0.5, `rgba(${orb.color}, ${orb.opacity * 0.4})`);
        grad.addColorStop(1,   `rgba(${orb.color}, 0)`);

        ctx.fillStyle = grad;
        ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
      }
    };

    frameId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        style={{
          position: 'fixed',
          inset: 0,
          width: '100%',
          height: '100%',
          zIndex: 0,
          pointerEvents: 'none',
        }}
        aria-hidden="true"
      />
      {/* Grain texture overlay */}
      <div
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,
          pointerEvents: 'none',
          opacity: 0.035,
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'repeat',
          backgroundSize: '256px 256px',
        }}
      />
    </>
  );
}
