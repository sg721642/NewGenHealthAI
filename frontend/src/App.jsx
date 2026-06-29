/**
 * NewGenHealthAI — WORLD-CLASS REDESIGN
 * Aesthetic: "Neural Clinic" — Editorial luxury medical AI
 * Fonts: Bricolage Grotesque (display) + Figtree (body) + JetBrains Mono (code/meta)
 * ALL CORE LOGIC 100% PRESERVED
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import './index.css';

// ═══════════════════════════════════════════════════════════════
//  WORLD-CLASS CSS DESIGN SYSTEM
// ═══════════════════════════════════════════════════════════════
const AUTH_CSS = `
/* ═══ AUTH PAGE ══════════════════════════════════════════════ */
.auth-root {
  position: fixed; inset: 0; display: flex; align-items: center; justify-content: center;
  background: #020617; z-index: 9999; padding: 16px;
}
.auth-bg { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
.auth-orb {
  position: absolute; border-radius: 50%; filter: blur(120px);
  animation: authFloat 20s ease-in-out infinite;
}
.auth-orb-1 { width: 600px; height: 600px; top: -200px; left: -150px; background: radial-gradient(circle, rgba(0,229,204,0.15) 0%, transparent 70%); }
.auth-orb-2 { width: 400px; height: 400px; bottom: -100px; right: -80px; background: radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 70%); animation-delay: -10s; }
@keyframes authFloat {
  0%,100% { transform: translate(0,0) scale(1); }
  50% { transform: translate(30px, -40px) scale(1.05); }
}
.auth-grid {
  position: absolute; inset: 0;
  background-image: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 50px 50px;
  mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black 30%, transparent 100%);
}
.auth-card {
  position: relative; z-index: 1;
  width: 100%; max-width: 440px;
  background: linear-gradient(145deg, rgba(9,15,30,0.98) 0%, rgba(6,12,24,0.98) 100%);
  border: 1px solid rgba(0,229,204,0.15);
  border-radius: 28px;
  padding: 40px 36px;
  box-shadow: 0 40px 120px rgba(0,0,0,0.8), 0 0 80px rgba(0,229,204,0.05), inset 0 1px 0 rgba(255,255,255,0.06);
  backdrop-filter: blur(30px);
  animation: authCardIn 0.6s cubic-bezier(0.34,1.56,0.64,1) both;
}
@keyframes authCardIn {
  from { opacity:0; transform: translateY(30px) scale(0.95); }
  to   { opacity:1; transform: none; }
}
.auth-card::before {
  content: ''; position: absolute; top: 0; left: 20%; right: 20%; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0,229,204,0.6), transparent);
}
.auth-logo {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  margin-bottom: 28px;
}
.auth-logo-gem {
  width: 52px; height: 52px; border-radius: 16px;
  background: linear-gradient(135deg, #0891b2, #22d3ee, #00f5ff);
  box-shadow: 0 0 40px rgba(0,245,255,0.4), 0 8px 24px rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; color: #020617;
  animation: authGemPulse 3s ease-in-out infinite;
}
@keyframes authGemPulse {
  0%,100% { box-shadow: 0 0 30px rgba(0,245,255,0.3), 0 8px 24px rgba(0,0,0,0.4); }
  50%      { box-shadow: 0 0 60px rgba(0,245,255,0.6), 0 8px 24px rgba(0,0,0,0.4); }
}
.auth-logo-text { display: flex; flex-direction: column; }
.auth-logo-name { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 18px; color: #e6f1ff; letter-spacing: -0.02em; }
.auth-logo-sub  { font-family: 'JetBrains Mono', monospace; font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: #00f5ff; margin-top: 2px; }
.auth-eyebrow {
  text-align: center; margin-bottom: 24px;
}
.auth-eyebrow h2 { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700; font-size: 22px; color: #e6f1ff; letter-spacing: -0.02em; margin-bottom: 6px; }
.auth-eyebrow p  { font-size: 13px; color: #64748b; line-height: 1.5; }
.auth-tabs {
  display: flex; gap: 4px; padding: 4px;
  background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px;
  margin-bottom: 28px;
}
.auth-tab {
  flex: 1; padding: 9px 0; border: none; border-radius: 9px; cursor: pointer;
  font-family: 'Figtree', sans-serif; font-size: 13.5px; font-weight: 600;
  transition: all 0.2s ease;
  background: transparent; color: #64748b;
}
.auth-tab.active {
  background: linear-gradient(135deg, #0891b2, #22d3ee);
  color: #020617;
  box-shadow: 0 4px 16px rgba(0,229,204,0.25);
}
.auth-field { margin-bottom: 16px; }
.auth-label { display: block; font-size: 12px; font-weight: 600; color: #94a3b8; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 8px; }
.auth-input-wrap { position: relative; }
.auth-input {
  width: 100%; padding: 13px 16px; padding-right: 44px;
  background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.10);
  border-radius: 12px; font-family: 'Figtree', sans-serif; font-size: 14px; color: #e6f1ff;
  transition: all 0.2s ease; outline: none; box-sizing: border-box;
}
.auth-input:focus { border-color: rgba(0,229,204,0.4); background: rgba(0,229,204,0.04); box-shadow: 0 0 0 3px rgba(0,229,204,0.08); }
.auth-input::placeholder { color: #334155; }
.auth-eye {
  position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
  background: none; border: none; color: #64748b; cursor: pointer; font-size: 13px;
  transition: color 0.2s; padding: 4px;
}
.auth-eye:hover { color: #00f5ff; }
.auth-submit {
  width: 100%; padding: 14px; border: none; border-radius: 14px;
  background: linear-gradient(135deg, #22d3ee, #00f5ff, #38bdf8);
  color: #020617; font-family: 'Figtree', sans-serif; font-size: 15px; font-weight: 700;
  cursor: pointer; letter-spacing: 0.01em;
  box-shadow: 0 4px 24px rgba(0,229,204,0.3);
  transition: all 0.25s cubic-bezier(0.34,1.56,0.64,1);
  margin-top: 8px; position: relative; overflow: hidden;
}
.auth-submit:hover:not(:disabled) { transform: translateY(-2px) scale(1.01); box-shadow: 0 8px 36px rgba(0,229,204,0.45); }
.auth-submit:active { transform: scale(0.98); }
.auth-submit:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
.auth-submit-shine {
  position: absolute; top: 0; left: -100%; width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25), transparent);
  transform: skewX(-20deg); transition: left 0.6s ease;
}
.auth-submit:hover .auth-submit-shine { left: 150%; }
.auth-err {
  margin-top: 12px; padding: 10px 14px; border-radius: 10px;
  background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2);
  color: #f87171; font-size: 12.5px; display: flex; align-items: center; gap: 8px;
}
.auth-ok {
  margin-top: 12px; padding: 10px 14px; border-radius: 10px;
  background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.2);
  color: #4ade80; font-size: 12.5px; display: flex; align-items: center; gap: 8px;
}
.auth-footer { text-align: center; margin-top: 20px; font-size: 11.5px; color: #334155; }
.auth-footer strong { color: #00f5ff; }
/* ═══ USER CHIP ═══════════════════════════════════════════════ */
.nc-user-chip {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 12px; margin-bottom: 8px;
  background: rgba(0,229,204,0.04); border: 1px solid rgba(0,229,204,0.12);
}
.nc-user-avatar {
  width: 32px; height: 32px; border-radius: 10px; flex-shrink: 0;
  background: linear-gradient(135deg, #0891b2, #00f5ff);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: #020617; font-weight: 700; font-family: 'Bricolage Grotesque';
}
.nc-user-info { flex: 1; min-width: 0; }
.nc-user-name { font-size: 13px; font-weight: 600; color: #e6f1ff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nc-user-role { font-size: 10px; color: #00f5ff; font-family: 'JetBrains Mono'; letter-spacing: 0.08em; }
.nc-logout-btn {
  display: flex; align-items: center; justify-content: center; gap: 7px;
  width: 100%; padding: 9px 12px; border-radius: 10px; border: none; cursor: pointer;
  background: rgba(239,68,68,0.07); border: 1px solid rgba(239,68,68,0.18);
  color: #f87171; font-family: 'Figtree', sans-serif; font-size: 12.5px; font-weight: 600;
  transition: all 0.2s ease; margin-bottom: 8px;
}
.nc-logout-btn:hover { background: rgba(239,68,68,0.14); border-color: rgba(239,68,68,0.35); color: #fca5a5; transform: translateY(-1px); }
`;

const WORLD_CLASS_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,300;12..96,400;12..96,500;12..96,600;12..96,700;12..96,800&family=Figtree:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400&family=JetBrains+Mono:wght@300;400;500&display=swap');

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}

:root {
  /* 🔥 ULTRA PREMIUM DARK THEME */

  --void: #020617;
  --abyss: #030712;
  --depth: #020617;
  --surface: #050a18;
  --elevated: #070f1f;
  --panel: #0b1324;
  --overlay: #0f172a;
  --highlight: #1e293b;

  /* 🚀 PRIMARY ACCENT (NEON CYAN / AI FEEL) */
  --mint: #00f5ff;
  --mint-2: #22d3ee;
  --mint-3: #0891b2;

  --mint-glow: rgba(0,245,255,0.25);
  --mint-glow2: rgba(0,245,255,0.10);
  --mint-glow3: rgba(0,245,255,0.05);

  /* 🔥 SECONDARY ACCENT (MODERN PURPLE) */
  --rose: #8b5cf6;
  --rose-dim: #6d28d9;
  --rose-glow: rgba(139,92,246,0.25);

  /* ⚡ WARNING / HIGHLIGHT */
  --amber: #facc15;
  --amber-glow: rgba(250,204,21,0.2);

  /* ✅ SUCCESS */
  --green: #22c55e;
  --green-glow: rgba(34,197,94,0.2);

  /* 🧊 GLASSMORPHISM */
  --glass-1: rgba(255,255,255,0.04);
  --glass-2: rgba(255,255,255,0.07);
  --glass-3: rgba(255,255,255,0.12);

  --border-1: rgba(255,255,255,0.08);
  --border-2: rgba(255,255,255,0.15);
  --border-mint: rgba(0,245,255,0.3);
  --border-mint2: rgba(0,245,255,0.5);

  /* 🧠 TEXT */
  --t1: #e6f1ff;
  --t2: #94a3b8;
  --t3: #64748b;
  --t4: #334155;

  /* 🔥 SHADOWS (DEPTH) */
  --shadow-sm: 0 2px 6px rgba(0,0,0,0.5);
  --shadow-md: 0 8px 30px rgba(0,0,0,0.6);
  --shadow-lg: 0 20px 60px rgba(0,0,0,0.7);
  --shadow-xl: 0 40px 120px rgba(0,0,0,0.9);

  --shadow-mint: 0 0 40px rgba(0,245,255,0.35);
  --shadow-mint-sm: 0 0 15px rgba(0,245,255,0.4);

  /* 🎯 SAME (KEEP) */
  --f-display: 'Bricolage Grotesque', sans-serif;
  --f-body: 'Figtree', sans-serif;
  --f-mono: 'JetBrains Mono', monospace;

  --r-xs: 6px; --r-sm: 10px; --r-md: 16px;
  --r-lg: 22px; --r-xl: 30px; --r-full: 9999px;

  --ease: cubic-bezier(0.4,0,0.2,1);
  --spring: cubic-bezier(0.34,1.56,0.64,1);
  --t-fast: 0.15s; --t-med: 0.25s; --t-slow: 0.4s;
}

[data-theme="light"] {
  --void: #f4f7fb; --abyss: #edf1f8; --depth: #e6ecf5;
  --surface: #ffffff; --elevated: #f8fafd; --panel: #f1f5fc;
  --overlay: #e8eef8; --highlight: #dde5f4;
  --border-1: rgba(0,0,0,0.07); --border-2: rgba(0,0,0,0.12);
  --glass-1: rgba(255,255,255,0.6); --glass-2: rgba(255,255,255,0.8);
  --t1: #0d1b2e; --t2: #3d5270; --t3: #7a90b0; --t4: #adbacf;
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.05);
  --shadow-lg: 0 12px 40px rgba(0,0,0,0.10), 0 4px 12px rgba(0,0,0,0.06);
}

html,body,#root {
  height:100%; width:100%; overflow:hidden;
  font-family: var(--f-body);
  background: var(--void);
  color: var(--t1);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ═══ BACKGROUND SYSTEM ═══════════════════════════════════════ */
.nc-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

/* DARK MODE */
:root:not([data-theme="light"]) .nc-bg {
  background: linear-gradient(
    -45deg,
    #020617,
    #030712,
    #020617,
    #0a192f
  );
}

/* LIGHT MODE */
[data-theme="light"] .nc-bg {
  background: linear-gradient(
    -45deg,
    #f8fafc,
    #eef2ff,
    #f1f5f9,
    #e0f2fe
  );
}

@keyframes gradientFlow {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
/* Grid */
.nc-bg-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(var(--border-1) 1px, transparent 1px),
    linear-gradient(90deg, var(--border-1) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black 40%, transparent 100%);
}
/* Mesh orbs */
.nc-orb {
  position: absolute; border-radius: 50%; filter: blur(100px);
  animation: ncFloat 25s ease-in-out infinite;
  will-change: transform;
}
.nc-orb-a {
  width: 700px; height: 700px;
  background: radial-gradient(circle at 40% 40%, rgba(0,229,204,0.12) 0%, transparent 70%);
  top: -200px; left: -150px; animation-delay: 0s;
}
.nc-orb-b {
  width: 500px; height: 500px;
  background: radial-gradient(circle at 60% 60%, rgba(255,77,109,0.08) 0%, transparent 70%);
  bottom: -100px; right: -80px; animation-delay: -10s;
}
.nc-orb-c {
  width: 400px; height: 400px;
  background: radial-gradient(circle at 50% 50%, rgba(0,145,255,0.06) 0%, transparent 70%);
  top: 35%; right: 25%; animation-delay: -18s;
}
@keyframes ncFloat {
  0%,100% { transform: translate(0,0); }
  25%      { transform: translate(40px,-30px); }
  50%      { transform: translate(-20px,50px); }
  75%      { transform: translate(60px,20px); }
}
/* Noise texture */
.nc-bg::after {
  content: '';
  position: absolute; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
  opacity: 0.5;
}

/* ═══ APP SHELL ═══════════════════════════════════════════════ */
.nc-app {
animation: appFade 0.8s ease;
  position: relative; z-index: 1;
  display: flex; height: 100vh; width: 100vw; overflow: hidden;
}

/* ═══ SIDEBAR ═════════════════════════════════════════════════ */
.nc-sidebar {
animation: sidebarSlide 0.6s ease;
  width: 288px; flex-shrink: 0;
  display: flex; flex-direction: column;
  position: relative; z-index: 10; overflow: hidden;
  transition: width var(--t-med) var(--ease), opacity var(--t-med) var(--ease);
  background: linear-gradient(180deg,
    rgba(6,12,23,0.97) 0%,
    rgba(9,15,30,0.97) 100%
  );
  border-right: 1px solid var(--border-1);
  backdrop-filter: blur(20px);
box-shadow: 0 0 40px rgba(0,0,0,0.8);
}
.nc-sidebar::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--mint) 50%, transparent 100%);
  opacity: 0.4;
}
.nc-sidebar::after {
  content: '';
  position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(135deg,
    rgba(0,229,204,0.03) 0%,
    transparent 50%,
    rgba(255,77,109,0.02) 100%
  );
}
.nc-sidebar.collapsed { width: 0; border-right-color: transparent; overflow: hidden; }

/* ── Brand ──────────────────────────────────────────── */
.nc-brand {
  padding: 20px 18px 16px;
  border-bottom: 1px solid var(--border-1);
  position: relative; z-index: 1;
  background: linear-gradient(180deg, rgba(0,229,204,0.04) 0%, transparent 100%);
}
.nc-brand-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.nc-brand-gem {
  width: 44px; height: 44px; flex-shrink: 0;
  border-radius: 14px; position: relative; overflow: hidden;
  background: linear-gradient(135deg, var(--mint-3), var(--mint-2), var(--mint));
  box-shadow: var(--shadow-mint), var(--shadow-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 19px; color: var(--void);
  animation: gemPulse 4s ease-in-out infinite;
}
.nc-brand-gem::before {
  content: '';
  position: absolute; top: -40%; left: -40%;
  width: 80%; height: 80%;
  background: rgba(255,255,255,0.3);
  border-radius: 50%; filter: blur(8px);
  animation: gemShine 4s ease-in-out infinite;
}
@keyframes gemPulse {
  0%,100% { box-shadow: var(--shadow-mint), var(--shadow-md); }
  50%      { box-shadow: 0 0 40px rgba(0,229,204,0.35), 0 0 80px rgba(0,229,204,0.12), var(--shadow-md); }
}
  @keyframes sidebarSlide {
  from {
    transform: translateX(-20px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
@keyframes gemShine {
  0%,100% { opacity: 0.6; transform: translate(0,0); }
  50%      { opacity: 1; transform: translate(10%,10%); }
}
  @keyframes appFade {
  from {
    opacity: 0;
    transform: scale(0.995);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
.nc-brand-info { min-width: 0; }
.nc-brand-name {
  font-family: var(--f-display);
  font-weight: 800; font-size: 14.5px; letter-spacing: -0.02em;
  color: var(--t1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  line-height: 1.2;
}
.nc-brand-tag {
  font-family: var(--f-mono); font-size: 9.5px; font-weight: 400;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--mint); opacity: 0.9; margin-top: 2px;
}

/* New Chat Button */
.nc-new-btn {
transition: all 0.3s cubic-bezier(0.34,1.56,0.64,1);
  position: relative; width: 100%; overflow: hidden;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 11px 18px; border: none; border-radius: var(--r-md); cursor: pointer;
  font-family: var(--f-body); font-weight: 600; font-size: 13.5px;
  letter-spacing: 0.01em; color: var(--void);
  background: linear-gradient(135deg, #22d3ee, #00f5ff, #38bdf8);
  box-shadow: 0 4px 24px rgba(0,229,204,0.3), var(--shadow-md);
  transition: all var(--t-med) var(--ease);
}
.nc-new-btn::before {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.2), rgba(255,255,255,0));
  opacity: 0; transition: opacity var(--t-med);
}
.nc-new-btn-shine {
  position: absolute; top: 0; left: -100%; width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25), transparent);
  transform: skewX(-20deg);
  transition: left 0.6s var(--ease);
}
.nc-new-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 36px rgba(0,229,204,0.4), var(--shadow-md); 
transform: translateY(-2px) scale(1.02);}
.nc-new-btn:hover::before { opacity: 1; }
.nc-new-btn:hover .nc-new-btn-shine { left: 150%; }
.nc-new-btn:active { transform: translateY(0) scale(0.99); }

/* ── Chat History ─────────────────────────────────── */
.nc-hist { flex: 1; overflow-y: auto; padding: 14px 12px; position: relative; z-index: 1; }
.nc-hist::-webkit-scrollbar { width: 2px; }
.nc-hist::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 10px; }

.nc-hist-head {
  display: flex; align-items: center; gap: 8px;
  padding: 0 6px 10px;
  font-family: var(--f-mono); font-size: 9px; font-weight: 500;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--t3);
}
.nc-hist-line { flex: 1; height: 1px; background: linear-gradient(90deg, var(--border-1), transparent); }

.nc-session {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 10px; border-radius: var(--r-sm); cursor: pointer;
  margin-bottom: 1px; position: relative; overflow: hidden;
  transition: all var(--t-fast) var(--ease);
  border: 1px solid transparent;
}
.nc-session::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px;
  background: var(--mint); transform: scaleY(0); transform-origin: center;
  transition: transform var(--t-fast) var(--ease); border-radius: 0 2px 2px 0;
}
.nc-session:hover { background: var(--glass-1); border-color: var(--border-1); }
.nc-session:hover::before { transform: scaleY(1); }
.nc-session.active {
  background: rgba(0,229,204,0.06);
  border-color: rgba(0,229,204,0.15);
}
.nc-session.active::before { transform: scaleY(1); }
.nc-session-icon {
  width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
  background: var(--glass-1); border: 1px solid var(--border-1);
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; color: var(--t3); transition: all var(--t-fast);
}
.nc-session:hover .nc-session-icon, .nc-session.active .nc-session-icon {
  background: rgba(0,229,204,0.08); border-color: rgba(0,229,204,0.2); color: var(--mint);
}
.nc-session-body { flex: 1; min-width: 0; }
.nc-session-title {
  font-size: 12.5px; font-weight: 500; color: var(--t1);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.3;
  transition: color var(--t-fast);
}
.nc-session:hover .nc-session-title { color: var(--t1); }
.nc-session-time {
  font-family: var(--f-mono); font-size: 9.5px; color: var(--t3); margin-top: 1px;
}
.nc-session-del {
  width: 24px; height: 24px; border-radius: 7px; border: none;
  background: transparent; color: var(--t4); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 9.5px; opacity: 0; transition: all var(--t-fast); flex-shrink: 0;
}
.nc-session:hover .nc-session-del { opacity: 1; }
.nc-session-del:hover { background: rgba(255,77,109,0.12); color: var(--rose); opacity: 1; }

/* Empty / Loading */
.nc-empty {
  text-align: center; padding: 40px 16px; color: var(--t3);
}
.nc-empty-icon {
  width: 48px; height: 48px; border-radius: 14px; margin: 0 auto 14px;
  background: var(--glass-1); border: 1px solid var(--border-1);
  display: flex; align-items: center; justify-content: center; font-size: 18px;
}
.nc-empty-text { font-size: 12.5px; line-height: 1.6; }

/* Loading spinner */
.nc-spin {
  width: 20px; height: 20px; border-radius: 50%; margin: 0 auto 12px;
  border: 2px solid var(--border-1); border-top-color: var(--mint);
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Sidebar Footer ───────────────────────────────── */
.nc-sb-foot { padding: 14px 14px 16px; border-top: 1px solid var(--border-1); position: relative; z-index: 1; }

.nc-dev-card {
  position: relative;
  overflow: hidden;
  background: var(--glass-1);
  border: 1px solid var(--border-1);
  border-radius: var(--r-md);
  padding: 14px 14px 12px;
  margin-bottom: 10px;

  backdrop-filter: blur(20px);
  transition: all 0.35s ease;
}

.nc-dev-card:hover {
  transform: translateY(-6px) scale(1.01);
  border-color: var(--border-mint);
  box-shadow: var(--shadow-mint);
}
.nc-dev-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--mint), var(--rose));
}
.nc-dev-card::after {
  content: ''; position: absolute; bottom: -60px; right: -40px;
  width: 120px; height: 120px; border-radius: 50%;
  background: radial-gradient(circle, rgba(0,229,204,0.05) 0%, transparent 70%);
  pointer-events: none;
}
.nc-dev-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 9px 3px 7px; border-radius: var(--r-full);
  background: rgba(0,229,204,0.08); border: 1px solid rgba(0,229,204,0.2);
  font-family: var(--f-mono); font-size: 8.5px; font-weight: 500;
  letter-spacing: 0.1em; text-transform: uppercase; color: var(--mint);
  margin-bottom: 10px;
}
.nc-dev-chip i { font-size: 8px; }
.nc-dev-name {
  font-family: var(--f-display); font-weight: 700; font-size: 14px;
  color: var(--t1); letter-spacing: -0.01em; margin-bottom: 3px;
}
.nc-dev-links { display: flex; gap: 6px; margin: 8px 0; }
.nc-dev-link {
  width: 28px; height: 28px; border-radius: 9px; flex-shrink: 0;
  background: var(--glass-2); border: 1px solid var(--border-1);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; color: var(--t2); text-decoration: none;
  transition: all var(--t-fast) var(--ease);
}
.nc-dev-link:hover { background: rgba(0,229,204,0.1); border-color: rgba(0,229,204,0.3); color: var(--mint); transform: translateY(-1px); }
.nc-dev-meta { font-size: 11px; color: var(--t2); line-height: 1.6; }
.nc-mentor-divider {
  display: flex; align-items: center; gap: 8px; margin: 10px 0 8px;
}
.nc-mentor-divider span {
  font-family: var(--f-mono); font-size: 8px; font-weight: 500;
  letter-spacing: 0.14em; text-transform: uppercase;
  padding: 2px 8px; border-radius: var(--r-full);
  background: rgba(255,77,109,0.08); border: 1px solid rgba(255,77,109,0.2); color: var(--rose);
}
.nc-mentor-divider::before, .nc-mentor-divider::after {
  content: ''; flex: 1; height: 1px; background: var(--border-1);
}
.nc-theme-toggle {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  width: 100%; padding: 9px 14px; cursor: pointer;
  background: var(--glass-1); border: 1px solid var(--border-1);
  border-radius: var(--r-sm); color: var(--t2);
  font-family: var(--f-body); font-size: 12.5px; font-weight: 500;
  transition: all var(--t-fast) var(--ease);
}
.nc-theme-toggle:hover { background: var(--glass-2); border-color: var(--border-2); color: var(--t1); }

/* ═══ MAIN PANEL ══════════════════════════════════════════════ */
.nc-main {
  flex: 1; display: flex; flex-direction: column; min-width: 0;
  background: linear-gradient(180deg, var(--void) 0%, var(--abyss) 100%);
  position: relative;
}
  .nc-main::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 120px;

  background: linear-gradient(
    to top,
    rgba(2,6,23,1),
    transparent
  );

  pointer-events: none;
}

/* ═══ HEADER ══════════════════════════════════════════════════ */
.nc-header {
  height: 60px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px;
  background: rgba(4,8,15,0.75);
  border-bottom: 1px solid var(--border-1);
  backdrop-filter: blur(20px) saturate(150%);
  position: relative; z-index: 5;
}
.nc-header::after {
  content: ''; position: absolute; bottom: -1px; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0,229,204,0.15), transparent);
}
.nc-h-left { display: flex; align-items: center; gap: 12px; }
.nc-menu-btn {
  width: 34px; height: 34px; border-radius: var(--r-sm); border: none;
  background: var(--glass-1); border: 1px solid var(--border-1);
  color: var(--t2); cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-size: 13px; transition: all var(--t-fast) var(--ease); flex-shrink: 0;
}
.nc-menu-btn:hover { background: var(--glass-2); border-color: var(--border-2); color: var(--t1); }

.nc-h-title {
  font-family: var(--f-display); font-weight: 700; font-size: 15px;
  letter-spacing: -0.01em;
  background: linear-gradient(135deg, var(--t1) 0%, rgba(0,229,204,0.9) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.nc-ai-badge {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: var(--r-full);
  background: rgba(16,185,129,0.07); border: 1px solid rgba(16,185,129,0.2);
  font-family: var(--f-mono); font-size: 10px; font-weight: 400; color: var(--green);
}
.nc-ai-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--green);
  animation: aiBlink 2.5s ease-in-out infinite;
}
@keyframes aiBlink {
  0%,100% { opacity:1; box-shadow: 0 0 0 0 rgba(16,185,129,0.5); }
  50%      { opacity:0.7; box-shadow: 0 0 0 5px rgba(16,185,129,0); }
}
.nc-h-right { display: flex; align-items: center; gap: 5px; }
.nc-hbtn {
  width: 34px; height: 34px; border-radius: var(--r-sm); border: none;
  background: var(--glass-1); border: 1px solid var(--border-1);
  color: var(--t2); cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-size: 12.5px; transition: all var(--t-fast) var(--ease);
}
.nc-hbtn:hover { background: var(--glass-2); border-color: var(--border-2); color: var(--t1); }
.nc-hbtn.danger:hover { background: rgba(255,77,109,0.07); border-color: rgba(255,77,109,0.25); color: var(--rose); }

/* ═══ CHAT AREA ═══════════════════════════════════════════════ */
.nc-chat {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 32px 0 16px; scroll-behavior: smooth;
  position: relative;
}
.nc-chat::-webkit-scrollbar { width: 3px; }
.nc-chat::-webkit-scrollbar-track { background: transparent; }
.nc-chat::-webkit-scrollbar-thumb { background: var(--border-1); border-radius: 10px; }
.nc-chat::-webkit-scrollbar-thumb:hover { background: var(--border-2); }

/* ═══ WELCOME SCREEN ══════════════════════════════════════════ */
.nc-welcome {
  display: flex; align-items: center; justify-content: center;
  min-height: 100%; padding: 20px;
}
.nc-welcome.hidden { display: none; }

.nc-wl-inner {
  max-width: 680px; width: 100%; text-align: center;
  animation: wlEnter 0.7s var(--ease) both;
}
@keyframes wlEnter {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: none; }
}

/* Hero Icon */
.nc-wl-hero {
  position: relative; display: inline-flex;
  margin-bottom: 32px; cursor: default;
}
.nc-wl-rings {
  position: absolute; inset: -20px;
  animation: ringsSpin 20s linear infinite;
}
@keyframes ringsSpin { to { transform: rotate(360deg); } }
.nc-wl-rings-inner {
  width: 100%; height: 100%; border-radius: 50%;
  border: 1px dashed rgba(0,229,204,0.15);
  position: relative;
}
.nc-wl-rings-inner::before {
  content: ''; position: absolute; inset: 10px;
  border-radius: 50%; border: 1px dashed rgba(0,229,204,0.08);
}
.nc-wl-icon-wrap {
animation: heroFloat 5s ease-in-out infinite, aiPulse 3s ease-in-out infinite;

  width: 88px; height: 88px; border-radius: 26px; position: relative;
  background: linear-gradient(135deg, var(--mint-3) 0%, var(--mint-2) 50%, var(--mint) 100%);
  box-shadow: 0 0 0 1px rgba(0,229,204,0.2), 0 0 60px rgba(0,229,204,0.3), 0 0 120px rgba(0,229,204,0.1), var(--shadow-xl);
  display: flex; align-items: center; justify-content: center;
  font-size: 36px; color: var(--void);
  animation: heroFloat 5s ease-in-out infinite;
}
.nc-wl-icon-wrap::before {
  content: '';
  position: absolute; top: 10%; left: 10%; width: 30%; height: 30%;
  background: rgba(255,255,255,0.35); border-radius: 50%; filter: blur(6px);
}
@keyframes heroFloat {
  0%,100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}
  @keyframes aiPulse {
  0%,100% {
    box-shadow: 0 0 40px rgba(0,245,255,0.25);
  }
  50% {
    box-shadow: 0 0 80px rgba(0,245,255,0.6);
  }
}

/* Eyebrow */
.nc-wl-eyebrow {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 14px; border-radius: var(--r-full); margin-bottom: 16px;
  background: rgba(0,229,204,0.06); border: 1px solid rgba(0,229,204,0.15);
  font-family: var(--f-mono); font-size: 10px; font-weight: 400;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--mint);
}
.nc-wl-eyebrow-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--mint); }

.nc-wl-title {
animation: titleGlow 4s ease-in-out infinite;
text-shadow: 0 0 30px rgba(0,245,255,0.35);
  font-family: var(--f-display); font-weight: 800;
  font-size: clamp(28px, 4vw, 42px); letter-spacing: -0.03em; line-height: 1.1;
  margin-bottom: 14px;
  background: linear-gradient(135deg, var(--t1) 0%, #d0f5f0 40%, var(--mint) 70%, #a0e8e0 100%);
  background-size: 200% 200%; animation: titleShimmer 5s ease-in-out infinite;
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  text-shadow: 0 0 40px rgba(0,245,255,0.4);
}
@keyframes titleShimmer {
  0%,100% { background-position: 0% 50%; }
  50%      { background-position: 100% 50%; }
}
  @keyframes titleGlow {
  0%,100% {
    text-shadow: 0 0 20px rgba(0,245,255,0.2);
  }
  50% {
    text-shadow: 0 0 40px rgba(0,245,255,0.5);
  }
}

.nc-wl-sub {
  font-size: 15px; font-weight: 300; color: var(--t2); line-height: 1.65;
  margin-bottom: 40px; max-width: 480px; margin-left: auto; margin-right: auto;
}

/* Quick Questions */
.nc-qlabel {
  font-family: var(--f-mono); font-size: 9.5px; font-weight: 500;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--t3);
  margin-bottom: 14px; display: flex; align-items: center; gap: 10px;
}
.nc-qlabel::before, .nc-qlabel::after {
  content: ''; flex: 1; height: 1px;
  background: linear-gradient(90deg, transparent, var(--border-2), transparent);
}
.nc-qgrid {
  display: grid; grid-template-columns: repeat(3,1fr); gap: 10px;
  margin-bottom: 32px;
}
@media (max-width: 560px) { .nc-qgrid { grid-template-columns: repeat(2,1fr); } }
.nc-qcard {
transition: all 0.35s ease;
  position: relative; overflow: hidden;
  display: flex; flex-direction: column; align-items: flex-start; gap: 10px;
  padding: 16px 15px; border-radius: var(--r-md); cursor: pointer;
  background: var(--glass-1); border: 1px solid var(--border-1);
  text-align: left; font-family: var(--f-body);
  transition: all var(--t-med) var(--ease);
}
.nc-qcard-glow {
  position: absolute; inset: 0;
  background: radial-gradient(circle at 50% 0%, rgba(0,229,204,0.08), transparent 70%);
  opacity: 0; transition: opacity var(--t-med);
}
.nc-qcard-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: rgba(0,229,204,0.08); border: 1px solid rgba(0,229,204,0.15);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; color: var(--mint); transition: all var(--t-med) var(--ease);
  position: relative; z-index: 1;
}
.nc-qcard-label {
  font-size: 12.5px; font-weight: 500; color: var(--t1); line-height: 1.3;
  position: relative; z-index: 1;
}
.nc-qcard-arrow {
  position: absolute; bottom: 12px; right: 12px; font-size: 9px; color: var(--t3);
  opacity: 0; transform: translate(-4px, 4px); transition: all var(--t-med) var(--ease);
}
.nc-qcard:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow:
    0 20px 60px rgba(0,0,0,0.6),
    0 0 30px rgba(0,245,255,0.2);
}
.nc-qcard:hover .nc-qcard-glow { opacity: 1; }
.nc-qcard:hover .nc-qcard-icon { background: rgba(0,229,204,0.14); transform: scale(1.05); }
.nc-qcard:hover .nc-qcard-arrow { opacity: 1; transform: translate(0,0); }
.nc-qcard:active { transform: translateY(-1px) scale(0.99); }

/* Capability Pills */
.nc-caps { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.nc-cap {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: var(--r-full);
  background: var(--glass-1); border: 1px solid var(--border-1);
  font-size: 11.5px; font-weight: 400; color: var(--t2);
  transition: all var(--t-fast) var(--ease);
  animation: capEnter 0.5s var(--ease) both;
}
.nc-cap:nth-child(1) { animation-delay: 0.2s; }
.nc-cap:nth-child(2) { animation-delay: 0.3s; }
.nc-cap:nth-child(3) { animation-delay: 0.4s; }
@keyframes capEnter {
  from { opacity:0; transform: translateY(8px); }
  to   { opacity:1; transform: none; }
}
.nc-cap i { font-size: 11px; color: var(--mint); }
.nc-cap:hover { border-color: var(--border-mint); background: rgba(0,229,204,0.04); color: var(--t1); }

/* ═══ MESSAGES ════════════════════════════════════════════════ */
.nc-msgs { max-width: 820px; margin: 0 auto; padding: 0 20px; }

.nc-msg {
  display: flex; margin-bottom: 28px;
  animation: msgIn 0.35s var(--ease) both;
}
@keyframes msgIn {
  from { opacity:0; transform: translateY(14px) scale(0.98); }
  to   { opacity:1; transform: none; }
}

/* Avatars */
.nc-avatar {
  width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; position: relative;
}
.nc-msg-u { flex-direction: row-reverse; }
.nc-msg-u .nc-avatar {
  margin-left: 11px; margin-top: 3px;
  background: linear-gradient(135deg, #0d2845, #091e38);
  border: 1px solid rgba(0,229,204,0.18); color: var(--mint);
}
.nc-msg-b { flex-direction: row; }
.nc-msg-b .nc-avatar {
  margin-right: 11px; margin-top: 3px;
  background: linear-gradient(135deg, var(--mint-3), var(--mint));
  color: var(--void);
  box-shadow: var(--shadow-mint-sm), var(--shadow-sm);
}

/* Bubble bodies */
.nc-body { max-width: calc(100% - 55px); min-width: 0; }

/* User bubble */
.nc-bubble-u {
  background: linear-gradient(135deg, #0d2845 0%, #091e38 100%);
  border: 1px solid rgba(0,229,204,0.12);
  border-radius: var(--r-xl) 6px var(--r-xl) var(--r-xl);
  padding: 14px 18px; font-size: 14.5px; line-height: 1.65;
  color: var(--t1); position: relative; overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.nc-bubble-u::before {
  content: '';
  position: absolute; top: 0; right: 0;
  width: 80px; height: 80px;
  background: radial-gradient(circle at 100% 0%, rgba(0,229,204,0.06), transparent 70%);
}

/* Bot bubble */
.nc-bubble-b {
  background: linear-gradient(
    135deg,
    rgba(10,20,40,0.85),
    rgba(15,25,50,0.95)
  );

  border: 1px solid rgba(0,245,255,0.15);
  border-left: 2px solid var(--mint);

  border-radius: 10px var(--r-xl) var(--r-xl) var(--r-xl);

  padding: 16px 20px;
  font-size: 14.5px;
  line-height: 1.75;

  color: var(--t1);

  backdrop-filter: blur(20px);

  box-shadow:
    0 10px 40px rgba(0,0,0,0.6),
    0 0 20px rgba(0,245,255,0.08);

  transition: transform 0.2s ease;
}

.nc-bubble-b:hover {
  transform: translateY(-2px);
}
.nc-bubble-b::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 100%;
  background: linear-gradient(135deg, rgba(0,229,204,0.02) 0%, transparent 50%);
  pointer-events: none; border-radius: inherit;
}
/* Markdown inside bot bubble */
.nc-bubble-b p { margin-bottom: 10px; }
.nc-bubble-b p:last-child { margin-bottom: 0; }
.nc-bubble-b strong { color: var(--mint); font-weight: 600; }
.nc-bubble-b em { color: var(--t2); font-style: italic; }
.nc-bubble-b h1,.nc-bubble-b h2,.nc-bubble-b h3 {
  font-family: var(--f-display); font-weight: 700;
  color: var(--t1); margin: 12px 0 6px; letter-spacing: -0.01em;
}
.nc-bubble-b ul,.nc-bubble-b ol { padding-left: 20px; margin-bottom: 10px; }
.nc-bubble-b li { margin-bottom: 5px; color: var(--t1); }
.nc-bubble-b li::marker { color: var(--mint); }
.nc-bubble-b code {
  font-family: var(--f-mono); font-size: 12.5px;
  background: rgba(0,229,204,0.06); border: 1px solid rgba(0,229,204,0.12);
  padding: 2px 7px; border-radius: 5px; color: var(--mint);
}
.nc-bubble-b blockquote {
  border-left: 3px solid var(--mint-2); padding-left: 12px;
  color: var(--t2); margin: 8px 0; font-style: italic;
}
.nc-bubble-b a { color: var(--mint); text-decoration: underline; text-decoration-color: rgba(0,229,204,0.3); }
.nc-bubble-b hr { border: none; border-top: 1px solid var(--border-1); margin: 12px 0; }

/* Uploaded image */
.nc-img-upload {
  display: block; max-width: 240px; border-radius: var(--r-md);
  margin-bottom: 10px; border: 1px solid var(--border-mint);
  box-shadow: var(--shadow-md);
}

/* Msg footer */
.nc-msg-foot {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 8px; gap: 8px; padding: 0 2px;
}
.nc-msg-u .nc-msg-foot { flex-direction: row-reverse; }
.nc-msg-time {
  font-family: var(--f-mono); font-size: 9.5px; color: var(--t3);
}
.nc-msg-src {
  display: flex; align-items: center; gap: 4px;
  font-family: var(--f-mono); font-size: 9px; color: var(--amber); opacity: 0.8;
}
.nc-msg-acts { display: flex; gap: 4px; }
.nc-msg-act {
  width: 26px; height: 26px; border-radius: 8px; border: none;
  background: var(--glass-1); border: 1px solid var(--border-1);
  color: var(--t3); cursor: pointer; display: flex;
  align-items: center; justify-content: center; font-size: 10px;
  transition: all var(--t-fast) var(--ease);
}
.nc-msg-act:hover { background: rgba(0,229,204,0.08); border-color: rgba(0,229,204,0.2); color: var(--mint); }

/* ═══ TYPING INDICATOR ════════════════════════════════════════ */
.nc-typing-wrap { display: none; }
.nc-typing-wrap.active { display: flex; }
.nc-typing-bubble {
  background: linear-gradient(135deg, rgba(9,15,30,0.95), rgba(12,21,37,0.98));
  border: 1px solid var(--border-1); border-left: 2px solid var(--mint);
  border-radius: 6px var(--r-xl) var(--r-xl) var(--r-xl);
  padding: 14px 18px; display: flex; align-items: center; gap: 10px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.35);
}
.nc-typing-label { font-size: 12.5px; color: var(--t2); font-style: italic; }
.nc-tdots { display: flex; align-items: center; gap: 4px; }
.nc-tdots span {
  display: block; width: 5px; height: 5px; border-radius: 50%; background: var(--mint);
  animation: tdot 1.2s ease-in-out infinite;
}
.nc-tdots span:nth-child(2) { animation-delay: 0.2s; background: rgba(0,229,204,0.7); }
.nc-tdots span:nth-child(3) { animation-delay: 0.4s; background: rgba(0,229,204,0.4); }
@keyframes tdot {
  0%,80%,100% { transform: scale(0.5); opacity: 0.3; }
  40%          { transform: scale(1); opacity: 1; }
}

/* ═══ INPUT AREA ══════════════════════════════════════════════ */
.nc-input-zone {
  flex-shrink: 0; padding: 12px 20px 20px;
  /* DARK MODE */
:root:not([data-theme="light"]) .nc-input-zone {
  background: linear-gradient(
    0deg,
    rgba(2,6,23,0.95),
    rgba(2,6,23,0.7),
    transparent
  );
}

/* LIGHT MODE */
[data-theme="light"] .nc-input-zone {
  background: linear-gradient(
    0deg,
    rgba(255,255,255,0.95),
    rgba(255,255,255,0.7),
    transparent
  );
}
  position: relative;
}
.nc-input-zone::before {
  content: ''; position: absolute; top: 0; left: 20px; right: 20px; height: 1px;
  background: linear-gradient(90deg, transparent, var(--border-1), transparent);
}
.nc-input-frame {
  max-width: 820px; margin: 0 auto; position: relative;
  transform: translateY(-10px);
}
.nc-input-card {
animation: inputBreath 6s ease-in-out infinite;
  display: flex;
  align-items: center;
  gap: 8px;

  padding: 12px 14px;

  background: rgba(10, 20, 40, 0.6);
  backdrop-filter: blur(25px) saturate(180%);

  border: 1px solid rgba(0,245,255,0.25);
  border-radius: 999px;

  box-shadow:
    0 0 0 1px rgba(0,245,255,0.05),
    0 10px 50px rgba(0,0,0,0.7),
    0 0 60px rgba(0,245,255,0.15);

  transition: all 0.3s ease;
}

/* Hover glow */
.nc-input-card:hover {
  box-shadow:
    0 0 0 1px rgba(0,245,255,0.2),
    0 20px 60px rgba(0,0,0,0.8),
    0 0 80px rgba(0,245,255,0.3);
}
  [data-theme="light"] .nc-input-card {
  background: rgba(255,255,255,0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(0,0,0,0.08);
  box-shadow: 0 10px 40px rgba(0,0,0,0.08);
}
  
.nc-input-card:focus-within {
  border-color: var(--mint);
  box-shadow:
    0 0 0 2px rgba(0,245,255,0.2),
    0 0 60px rgba(0,245,255,0.3);
}
.nc-input-card:focus-within {
  border-color: rgba(0,229,204,0.3);
  box-shadow: 0 8px 40px rgba(0,0,0,0.5), 0 0 0 3px rgba(0,229,204,0.07), var(--shadow-mint);
}
.nc-iside {
  width: 34px; height: 34px; border-radius: 10px; border: none; flex-shrink: 0;
  background: transparent; color: var(--t3); cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-size: 14px;
  transition: all var(--t-fast) var(--ease);
}
.nc-iside:hover { background: rgba(0,229,204,0.07); color: var(--mint); }
.nc-textarea {
  flex: 1; background: transparent; border: none; outline: none; resize: none;
  font-family: var(--f-body); font-size: 14.5px; font-weight: 400;
  color: var(--t1); line-height: 1.6; padding: 6px 0; max-height: 120px; overflow-y: auto;
}
.nc-textarea::placeholder { color: var(--t3); font-style: italic; }
.nc-textarea::-webkit-scrollbar { width: 2px; }
.nc-textarea::-webkit-scrollbar-thumb { background: var(--border-2); }

/* Send button — the crown jewel */
.nc-send {
  position: relative;
  overflow: hidden;

  width: 42px;
  height: 42px;
  border-radius: 14px;
  border: none;

  background: linear-gradient(135deg, #00f5ff, #22d3ee, #38bdf8);
  color: var(--void);

  display: flex;
  align-items: center;
  justify-content: center;

  font-size: 15px;
  cursor: pointer;

  box-shadow:
    0 0 20px rgba(0,245,255,0.5),
    0 0 40px rgba(0,245,255,0.2);

  transition: all 0.3s ease;
}

.nc-send:hover {
  transform: scale(1.1);
  box-shadow:
    0 0 40px rgba(0,245,255,0.8),
    0 0 80px rgba(0,245,255,0.3);
}

.nc-send:active {
  transform: scale(0.95);
}
.nc-send::before {
  content: '';
  position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
  background: conic-gradient(from 0deg, transparent 0%, rgba(255,255,255,0.15) 30%, transparent 60%);
  animation: sendSpin 3s linear infinite; opacity: 0;
  transition: opacity var(--t-med);
}
.nc-send:not(:disabled):hover {
  transform: scale(1.06) translateY(-1px);
  box-shadow: 0 8px 30px rgba(0,229,204,0.5), var(--shadow-md);
}
.nc-send:not(:disabled):hover::before { opacity: 1; }
.nc-send:not(:disabled):active { transform: scale(0.97); }
.nc-send:disabled { opacity: 0.35; cursor: not-allowed; }
@keyframes sendSpin { to { transform: rotate(360deg); } }
@keyframes inputBreath {
  0%,100% {
    box-shadow:
      0 0 0 1px rgba(0,245,255,0.05),
      0 10px 50px rgba(0,0,0,0.7),
      0 0 40px rgba(0,245,255,0.15);
  }
  50% {
    box-shadow:
      0 0 0 1px rgba(0,245,255,0.2),
      0 15px 60px rgba(0,0,0,0.8),
      0 0 80px rgba(0,245,255,0.3);
  }
}

/* Input hint */
.nc-hint {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  margin-top: 10px; font-size: 10.5px; color: var(--t3);
  font-family: var(--f-mono);
}
.nc-hint i { color: var(--mint); opacity: 0.6; }

/* ═══ TOAST ═══════════════════════════════════════════════════ */
.nc-toast {
  position: fixed; bottom: 24px; right: 24px; z-index: 99999;
  display: flex; align-items: center; gap: 10px;
  padding: 12px 18px 12px 14px; border-radius: var(--r-md);
  font-family: var(--f-body); font-size: 13px; font-weight: 500; color: #fff;
  box-shadow: var(--shadow-xl);
  transform: translateX(calc(100% + 32px));
  opacity: 0; pointer-events: none;
  transition: all 0.4s var(--spring);
}
.nc-toast.show {
  transform: translateX(0); opacity: 1; pointer-events: auto;
}
.nc-toast i { font-size: 14px; flex-shrink: 0; }
.nc-toast-bar {
  position: absolute; bottom: 0; left: 0; height: 2px; border-radius: 0 0 var(--r-md) var(--r-md);
  background: rgba(255,255,255,0.3);
  animation: toastBar 3s linear forwards;
}
@keyframes toastBar { from { width: 100%; } to { width: 0%; } }

/* ═══ MOBILE BACKDROP ═════════════════════════════════════════ */
.nc-veil {
  position: fixed; inset: 0; z-index: 9;
  background: rgba(0,0,0,0.65); backdrop-filter: blur(4px);
  animation: veilIn 0.2s ease;
}
@keyframes veilIn { from { opacity: 0; } to { opacity: 1; } }

/* ═══ RESPONSIVE ══════════════════════════════════════════════ */
@media (max-width: 768px) {
  .nc-sidebar {
  [data-theme="light"] .nc-sidebar {
  background: linear-gradient(
    180deg,
    #ffffff 0%,
    #f1f5f9 100%
  );
}
    position: fixed; top: 0; left: 0; bottom: 0; z-index: 10;
    width: 288px !important;
  }
  .nc-sidebar.collapsed { width: 0 !important; }
  .nc-wl-title { font-size: 26px; }
  .nc-qgrid { grid-template-columns: repeat(2,1fr); }
  .nc-input-zone { padding: 10px 14px 16px; }
  .nc-header { padding: 0 14px; }
  .nc-chat { padding: 16px 0 8px; }
  .nc-msgs { padding: 0 14px; }
}

/* ═══ STAGGER CHILDREN (welcome screen) ══════════════════════ */
.nc-wl-inner > * {
  animation: wlChild 0.6s var(--ease) both;
}
.nc-wl-inner > *:nth-child(1) { animation-delay: 0.05s; }
.nc-wl-inner > *:nth-child(2) { animation-delay: 0.1s; }
.nc-wl-inner > *:nth-child(3) { animation-delay: 0.15s; }
.nc-wl-inner > *:nth-child(4) { animation-delay: 0.2s; }
.nc-wl-inner > *:nth-child(5) { animation-delay: 0.25s; }
.nc-wl-inner > *:nth-child(6) { animation-delay: 0.3s; }
.nc-wl-inner > *:nth-child(7) { animation-delay: 0.35s; }
@keyframes wlChild {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: none; }
}

/* ═══ FOLLOW-UP QUESTION CHIPS ═══════════════════════════════ */
.nc-followup-section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(0,245,255,0.1);
}
.nc-followup-label {
  display: flex; align-items: center; gap: 6px;
  font-family: var(--f-mono); font-size: 9px; font-weight: 500;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--mint); margin-bottom: 10px; opacity: 0.8;
}
.nc-followup-q {
  margin-bottom: 12px;
  animation: fuQEnter 0.4s var(--ease) both;
}
.nc-followup-q:nth-child(2) { animation-delay: 0.1s; }
.nc-followup-q:nth-child(3) { animation-delay: 0.2s; }
.nc-followup-q:nth-child(4) { animation-delay: 0.3s; }
@keyframes fuQEnter {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: none; }
}
.nc-followup-qtext {
  font-size: 13px; font-weight: 500; color: var(--t1);
  margin-bottom: 8px; line-height: 1.5;
}
.nc-followup-opts {
  display: flex; flex-wrap: wrap; gap: 6px;
}
.nc-followup-chip {
  position: relative; overflow: hidden;
  padding: 7px 14px; border-radius: var(--r-full);
  background: rgba(0,245,255,0.06);
  border: 1px solid rgba(0,245,255,0.2);
  color: var(--mint); cursor: pointer;
  font-family: var(--f-body); font-size: 12.5px; font-weight: 500;
  transition: all 0.25s var(--ease);
  animation: chipIn 0.35s var(--spring) both;
}
.nc-followup-chip:nth-child(1) { animation-delay: 0.15s; }
.nc-followup-chip:nth-child(2) { animation-delay: 0.25s; }
.nc-followup-chip:nth-child(3) { animation-delay: 0.35s; }
.nc-followup-chip:nth-child(4) { animation-delay: 0.45s; }
.nc-followup-chip:nth-child(5) { animation-delay: 0.55s; }
@keyframes chipIn {
  from { opacity: 0; transform: translateY(6px) scale(0.9); }
  to   { opacity: 1; transform: none; }
}
.nc-followup-chip:hover {
  background: rgba(0,245,255,0.15);
  border-color: rgba(0,245,255,0.5);
  transform: translateY(-2px) scale(1.04);
  box-shadow: 0 4px 20px rgba(0,245,255,0.25), 0 0 30px rgba(0,245,255,0.1);
  color: #fff;
}
.nc-followup-chip:active {
  transform: translateY(0) scale(0.97);
}
.nc-followup-chip::before {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(0,245,255,0.1), transparent);
  opacity: 0; transition: opacity 0.25s;
}
.nc-followup-chip:hover::before { opacity: 1; }
.nc-followup-round {
  display: inline-flex; align-items: center; gap: 5px;
  margin-top: 10px; padding: 3px 10px; border-radius: var(--r-full);
  background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.2);
  font-family: var(--f-mono); font-size: 8.5px; font-weight: 500;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--rose);
}

/* ═══ TTS SPEAKER BUTTON ═════════════════════════════════════ */
.nc-msg-act.speaking {
  background: rgba(0,245,255,0.15);
  border-color: rgba(0,245,255,0.4);
  color: var(--mint);
  animation: speakerPulse 1.5s ease-in-out infinite;
}
@keyframes speakerPulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(0,245,255,0.3); }
  50%     { box-shadow: 0 0 0 6px rgba(0,245,255,0); }
}

/* ═══ VOICE RECORDING INDICATOR ══════════════════════════════ */
.nc-rec-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 14px; border-radius: var(--r-full); margin-top: 8px;
  background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2);
  font-family: var(--f-mono); font-size: 11px; color: #ef4444;
  animation: recPulse 2s ease-in-out infinite;
}
@keyframes recPulse {
  0%,100% { border-color: rgba(239,68,68,0.2); }
  50%     { border-color: rgba(239,68,68,0.5); }
}
.nc-rec-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #ef4444;
  animation: aiBlink 1s ease-in-out infinite;
}
`;

// ═══════════════════════════════════════════════════════════════
//  SECTION 2 — UTILITY HELPERS (UNCHANGED)
// ═══════════════════════════════════════════════════════════════
function formatTimeAgo(timestamp) {
  const now = new Date();
  const past = new Date(timestamp);
  const diffMs = now - past;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return past.toLocaleDateString();
}

function buildDownloadText(chatHistory) {
  let content = 'NewGenHealthAI Chat Export\n';
  content += '='.repeat(50) + '\n\n';
  chatHistory.forEach((msg) => {
    content += `[${msg.timestamp}] ${msg.type === 'user' ? 'You' : 'NewGenHealthAI'}:\n`;
    content += msg.content + '\n';
    if (msg.source) content += `Source: ${msg.source}\n`;
    content += '\n';
  });
  return content;
}

// ═══════════════════════════════════════════════════════════════
//  SECTION 3 — SIDEBAR
// ═══════════════════════════════════════════════════════════════
function Sidebar({ sidebarOpen, sessions, currentSessionId, onNewChat, onLoadSession, onDeleteSession, onToggleTheme, theme, user, onLogout }) {
  return (
    <aside className={`nc-sidebar${sidebarOpen ? '' : ' collapsed'}`}>

      {/* Brand */}
      <div className="nc-brand">
        <div className="nc-brand-row">
          <div className="nc-brand-gem">
            <i className="fas fa-heartbeat" />
          </div>
          <div className="nc-brand-info">
            <div className="nc-brand-name">NewGenHealthAI</div>
            <div className="nc-brand-tag">AI Assistant v3.0</div>
          </div>
        </div>
        <button className="nc-new-btn" onClick={onNewChat}>
          <div className="nc-new-btn-shine" />
          <i className="fas fa-plus" />
          New Conversation
        </button>
      </div>

      {/* History */}
      <div className="nc-hist">
        <div className="nc-hist-head">
          <span>History</span>
          <div className="nc-hist-line" />
        </div>

        {sessions === null ? (
          <div className="nc-empty">
            <div className="nc-spin" />
            <div className="nc-empty-text">Loading sessions…</div>
          </div>
        ) : sessions.length === 0 ? (
          <div className="nc-empty">
            <div className="nc-empty-icon"><i className="fas fa-comment-medical" /></div>
            <div className="nc-empty-text">No conversations yet.<br />Start your first chat.</div>
          </div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.session_id}
              className={`nc-session${currentSessionId === session.session_id ? ' active' : ''}`}
              onClick={() => onLoadSession(session.session_id)}
            >
              <div className="nc-session-icon"><i className="fas fa-message" /></div>
              <div className="nc-session-body">
                <div className="nc-session-title">{session.preview || 'New conversation'}</div>
                <div className="nc-session-time">{formatTimeAgo(session.last_active)}</div>
              </div>
              <button
                className="nc-session-del"
                onClick={(e) => { e.stopPropagation(); onDeleteSession(session.session_id); }}
              >
                <i className="fas fa-trash" />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="nc-sb-foot">
        <div className="nc-dev-card">
          <div className="nc-dev-chip"><i className="fas fa-chalkboard-teacher" /> Mentor</div>
          <div className="nc-dev-name">Dr. Susham Biswas</div>
          <div className="nc-dev-meta">
            Associate Professor &amp; Ex-HOD(CSE)<br />
            RGIPT
          </div>
        </div>

        {/* User chip + logout */}
        {user && (
          <>
            <div className="nc-user-chip">
              <div className="nc-user-avatar">{user.username ? user.username[0].toUpperCase() : '?'}</div>
              <div className="nc-user-info">
                <div className="nc-user-name">{user.username}</div>
                <div className="nc-user-role">● Online</div>
              </div>
            </div>
            <button className="nc-logout-btn" onClick={onLogout}>
              <i className="fas fa-right-from-bracket" />
              Sign Out
            </button>
          </>
        )}
        <button className="nc-theme-toggle" onClick={onToggleTheme}>
          <i className={`fas ${theme === 'dark' ? 'fa-sun' : 'fa-moon'}`} />
          {theme === 'dark' ? 'Switch to Light' : 'Switch to Dark'}
        </button>
      </div>
    </aside>
  );
}

// ═══════════════════════════════════════════════════════════════
//  SECTION 4 — CHAT AREA
// ═══════════════════════════════════════════════════════════════
const QUICK_QUESTIONS = [
  { icon: 'fa-thermometer',    label: 'Fever Symptoms',       q: 'What are the symptoms of fever?' },
  { icon: 'fa-head-side-virus',label: 'Headache Treatment',   q: 'How to treat a headache?' },
  { icon: 'fa-heart-pulse',    label: 'High Blood Pressure',  q: 'What causes high blood pressure?' },
  { icon: 'fa-notes-medical',  label: 'Diabetes Management',  q: 'Tell me about diabetes management' },
  { icon: 'fa-virus-covid',    label: 'COVID Prevention',     q: 'COVID-19 prevention tips' },
  { icon: 'fa-pills',          label: 'Cold Remedies',        q: 'Common cold remedies' },
];

function ChatArea({ messages, isTyping, showWelcome, onQuickQuestion, onFollowUpClick, chatAreaRef }) {
  return (
    <div className="nc-chat" ref={chatAreaRef}>

      {/* Welcome Screen */}
      <div className={`nc-welcome${showWelcome ? '' : ' hidden'}`}>
        <div className="nc-wl-inner">

          {/* Hero Icon */}
          <div className="nc-wl-hero">
            <div className="nc-wl-rings"><div className="nc-wl-rings-inner" /></div>
            <div className="nc-wl-icon-wrap">
              <i className="fas fa-stethoscope" />
            </div>
          </div>

          {/* Eyebrow */}
          <div className="nc-wl-eyebrow">
            <div className="nc-wl-eyebrow-dot" />
            AI-Powered Medical Intelligence
          </div>

          {/* Title */}
          <h1 className="nc-wl-title">Welcome to NewGenHealthAI</h1>

          {/* Subtitle */}
          <p className="nc-wl-sub">
            Your intelligent medical companion — ask about symptoms, treatments,
            diagnostics, and wellness guidance with clinical accuracy.
          </p>

          {/* Quick Questions */}
          <div className="nc-qlabel">Quick Start</div>
          <div className="nc-qgrid">
            {QUICK_QUESTIONS.map(({ icon, label, q }) => (
              <button key={q} className="nc-qcard" onClick={() => onQuickQuestion(q)}>
                <div className="nc-qcard-glow" />
                <div className="nc-qcard-icon"><i className={`fas ${icon}`} /></div>
                <span className="nc-qcard-label">{label}</span>
                <span className="nc-qcard-arrow"><i className="fas fa-arrow-up-right" /></span>
              </button>
            ))}
          </div>

          {/* Capability pills */}
          <div className="nc-caps">
            {[
              { icon: 'fa-brain',        label: 'AI-Powered' },
              { icon: 'fa-database',     label: 'Medical Database' },
              { icon: 'fa-shield-heart', label: 'Clinically Aligned' },
            ].map(({ icon, label }) => (
              <div key={label} className="nc-cap">
                <i className={`fas ${icon}`} /> {label}
              </div>
            ))}
          </div>

        </div>
      </div>

      {/* Messages */}
      <div className="nc-msgs">
        {messages.map((msg, idx) => (
          <MessageBubble key={idx} msg={msg} onFollowUpClick={onFollowUpClick} />
        ))}

        {/* Typing Indicator */}
        <div className={`nc-msg nc-msg-b nc-typing-wrap${isTyping ? ' active' : ''}`}>
          <div className="nc-avatar"><i className="fas fa-robot" /></div>
          <div className="nc-body">
            <div className="nc-typing-bubble">
              <span className="nc-typing-label">Analyzing your query</span>
              <div className="nc-tdots"><span /><span /><span /></div>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}

function MessageBubble({ msg, onFollowUpClick }) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const audioRef = useRef(null);

  const copyText = useCallback(() => {
    navigator.clipboard.writeText(msg.content).catch(() => {});
  }, [msg.content]);

  // TTS: Speak this message
  const speakMessage = useCallback(async () => {
    // If already speaking, stop
    if (isSpeaking && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsSpeaking(false);
      return;
    }
    try {
      setIsSpeaking(true);
      // Use fetch+blob for better browser compatibility than new Audio(url)
      const ttsUrl = `/api/v1/voice/tts?text=${encodeURIComponent(msg.content.substring(0, 2000))}`;
      const res = await fetch(ttsUrl);
      if (!res.ok) throw new Error(`TTS failed: ${res.status}`);
      const audioBlob = await res.blob();
      const blobUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(blobUrl);
      audioRef.current = audio;
      audio.onended = () => { setIsSpeaking(false); URL.revokeObjectURL(blobUrl); };
      audio.onerror = () => { setIsSpeaking(false); URL.revokeObjectURL(blobUrl); };
      await audio.play();
    } catch (err) {
      console.error('TTS playback failed:', err);
      setIsSpeaking(false);
    }
  }, [msg.content, isSpeaking]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  if (msg.type === 'user') {
    return (
      <div className="nc-msg nc-msg-u">
        <div className="nc-avatar"><i className="fas fa-user" /></div>
        <div className="nc-body">
          <div className="nc-bubble-u">
            {msg.image && <img src={msg.image} alt="uploaded" className="nc-img-upload" />}
            {msg.content}
          </div>
          <div className="nc-msg-foot">
            <span className="nc-msg-time">{msg.timestamp}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="nc-msg nc-msg-b">
      <div className="nc-avatar"><i className="fas fa-robot" /></div>
      <div className="nc-body">
        <div className="nc-bubble-b">
          <ReactMarkdown>{msg.content}</ReactMarkdown>

          {/* ═══ Follow-Up Question Chips ═══ */}
          {msg.followUp && msg.followUp.questions && msg.followUp.questions.length > 0 && (
            <div className="nc-followup-section">
              <div className="nc-followup-label">
                <i className="fas fa-stethoscope" />
                Doctor is asking follow-up questions
              </div>
              {msg.followUp.questions.map((q, qIdx) => (
                <div key={qIdx} className="nc-followup-q">
                  <div className="nc-followup-qtext">{q.text}</div>
                  <div className="nc-followup-opts">
                    {(q.options || []).map((opt, oIdx) => (
                      <button
                        key={oIdx}
                        className="nc-followup-chip"
                        onClick={() => onFollowUpClick && onFollowUpClick(opt)}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              <div className="nc-followup-round">
                <i className="fas fa-clipboard-question" />
                Round {msg.followUp.triage_round} of {msg.followUp.max_rounds}
              </div>
            </div>
          )}
        </div>
        <div className="nc-msg-foot">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="nc-msg-time">{msg.timestamp}</span>
            {msg.source && (
              <span className="nc-msg-src">
                <i className="fas fa-database" /> {msg.source}
              </span>
            )}
          </div>
          <div className="nc-msg-acts">
            <button
              className={`nc-msg-act${isSpeaking ? ' speaking' : ''}`}
              title={isSpeaking ? 'Stop speaking' : 'Listen to response'}
              onClick={speakMessage}
            >
              <i className={`fas ${isSpeaking ? 'fa-volume-xmark' : 'fa-volume-high'}`} />
            </button>
            <button className="nc-msg-act" title="Copy response" onClick={copyText}>
              <i className="fas fa-copy" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  SECTION 5 — INPUT AREA (with Voice Input via Groq Whisper)
// ═══════════════════════════════════════════════════════════════
function InputArea({ inputValue, setInputValue, onSend, isTyping, inputRef, onImageUpload }) {
  const [voiceState, setVoiceState] = useState('idle'); // idle | recording | transcribing
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const elapsedRef = useRef(0);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); }
  };
  const handleInput = (e) => {
    setInputValue(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  // ── Transcribe audio blob via backend Groq Whisper ───────────
  const transcribeAudio = useCallback(async (audioBlob, ext) => {
    setVoiceState('transcribing');
    try {
      const formData = new FormData();
      formData.append('file', audioBlob, `recording${ext}`);
      console.log('[Voice] Sending to STT:', audioBlob.size, 'bytes, ext:', ext);

      const res = await fetch('/api/v1/voice/stt', { method: 'POST', body: formData });
      const data = await res.json().catch(() => null);
      console.log('[Voice] STT response:', data);

      if (!data) {
        alert('Voice server error. Make sure the backend is running.');
        return;
      }

      if (data.error) {
        console.error('[Voice] Server error:', data.error);
        alert('Transcription error: ' + data.error);
        return;
      }

      if (data.text && data.text.trim()) {
        const transcribed = data.text.trim();
        console.log('[Voice] Got text:', transcribed);
        setInputValue(prev => {
          const sep = prev && prev.trim() ? ' ' : '';
          return prev + sep + transcribed;
        });
      } else {
        alert('No speech detected. Speak clearly for at least 2 seconds.');
      }
    } catch (err) {
      console.error('[Voice] Error:', err);
      alert('Voice failed: ' + err.message);
    } finally {
      setVoiceState('idle');
    }
  }, [setInputValue]);

  // ── Stop recording ───────────────────────────────────────────
  const stopRecording = useCallback(() => {
    console.log('[Voice] Stopping recording...');
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // ── Start recording ──────────────────────────────────────────
  const startRecording = useCallback(async () => {
    console.log('[Voice] Starting recording...');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });
      console.log('[Voice] Got microphone stream');
      streamRef.current = stream;
      audioChunksRef.current = [];

      // Find best MIME type
      let mimeType = '';
      for (const mt of ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4', '']) {
        if (!mt || MediaRecorder.isTypeSupported(mt)) { mimeType = mt; break; }
      }
      console.log('[Voice] Using MIME:', mimeType || '(default)');

      const opts = mimeType ? { mimeType } : {};
      const recorder = new MediaRecorder(stream, opts);

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
          console.log('[Voice] Chunk:', e.data.size, 'bytes');
        }
      };

      recorder.onstop = async () => {
        console.log('[Voice] Recording stopped, chunks:', audioChunksRef.current.length);
        // Stop mic
        stream.getTracks().forEach(t => t.stop());
        streamRef.current = null;
        const duration = elapsedRef.current;
        setRecordingTime(0);

        if (duration < 1) {
          console.warn('[Voice] Too short (' + duration + 's), skipping');
          setVoiceState('idle');
          return;
        }

        const mime = recorder.mimeType || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: mime });
        console.log('[Voice] Blob:', blob.size, 'bytes, type:', mime, 'duration:', duration + 's');

        if (blob.size < 1000) {
          console.warn('[Voice] Blob too small, skipping');
          setVoiceState('idle');
          return;
        }

        // Determine extension
        let ext = '.webm';
        if (mime.includes('ogg')) ext = '.ogg';
        else if (mime.includes('mp4')) ext = '.mp4';
        else if (mime.includes('mpeg') || mime.includes('mp3')) ext = '.mp3';

        await transcribeAudio(blob, ext);
      };

      recorder.onerror = (e) => {
        console.error('[Voice] Recorder error:', e);
        stream.getTracks().forEach(t => t.stop());
        streamRef.current = null;
        setVoiceState('idle');
        setRecordingTime(0);
      };

      mediaRecorderRef.current = recorder;
      recorder.start(1000); // 1s timeslice
      setVoiceState('recording');
      setRecordingTime(0);
      elapsedRef.current = 0;
      console.log('[Voice] Recording started');

      timerRef.current = setInterval(() => {
        elapsedRef.current += 1;
        setRecordingTime(elapsedRef.current);
      }, 1000);

    } catch (err) {
      console.error('[Voice] Mic access error:', err);
      setVoiceState('idle');
      if (err.name === 'NotAllowedError') {
        alert('Microphone access denied. Please allow microphone permission and try again.');
      } else if (err.name === 'NotFoundError') {
        alert('No microphone found. Please connect a microphone.');
      } else {
        alert('Microphone error: ' + err.message);
      }
    }
  }, [transcribeAudio]);

  // ── Toggle handler ───────────────────────────────────────────
  const handleMicClick = useCallback(() => {
    console.log('[Voice] Mic clicked, current state:', voiceState);
    if (voiceState === 'recording') {
      stopRecording();
    } else if (voiceState === 'idle') {
      startRecording();
    }
    // If transcribing, ignore click
  }, [voiceState, stopRecording, startRecording]);

  const formatTime = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  const placeholder = voiceState === 'transcribing'
    ? '⏳ Transcribing your speech...'
    : voiceState === 'recording'
      ? `🎙️ Recording (${formatTime(recordingTime)}) — click 🟥 to stop`
      : 'Describe your symptoms or ask a medical question…';

  const micIcon = voiceState === 'recording'
    ? 'fa-stop-circle'
    : voiceState === 'transcribing'
      ? 'fa-spinner fa-spin'
      : 'fa-microphone';

  const micStyle = voiceState === 'recording'
    ? { color: '#ef4444', animation: 'aiBlink 1s ease-in-out infinite', fontSize: '16px' }
    : voiceState === 'transcribing'
      ? { color: '#00e5cc', animation: 'aiBlink 1s ease-in-out infinite' }
      : {};

  return (
    <div className="nc-input-zone">
      <div className="nc-input-frame">
        <div className="nc-input-card">

          <label className="nc-iside" title="Upload medical image" style={{ cursor: 'pointer' }}>
            <i className="fas fa-paperclip" />
            <input type="file" accept="image/*" hidden onChange={onImageUpload} />
          </label>

          <textarea
            ref={inputRef}
            className="nc-textarea"
            placeholder={placeholder}
            rows={1}
            value={inputValue}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
          />

          {/* ── Recording time indicator ── */}
          {voiceState === 'recording' && (
            <span style={{
              color: '#ef4444', fontFamily: 'JetBrains Mono, monospace',
              fontSize: '12px', fontWeight: 600, minWidth: '36px', textAlign: 'center',
            }}>
              {formatTime(recordingTime)}
            </span>
          )}

          <button
            className="nc-iside"
            title={
              voiceState === 'recording' ? 'Stop recording'
                : voiceState === 'transcribing' ? 'Transcribing...'
                : 'Voice input — click to speak'
            }
            onClick={handleMicClick}
            disabled={voiceState === 'transcribing'}
            style={micStyle}
          >
            <i className={`fas ${micIcon}`} />
          </button>

          <button
            className="nc-send"
            title="Send message"
            aria-label="Send message"
            onClick={onSend}
            disabled={!inputValue.trim() || isTyping}
          >
            <i className="fas fa-paper-plane" style={{ position: 'relative', zIndex: 1 }} />
          </button>

        </div>

        <div className="nc-hint">
          <i className="fas fa-shield-alt" />
          AI responses are informational only — always consult a qualified healthcare professional.
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  LOGIN PAGE COMPONENT
// ═══════════════════════════════════════════════════════════════
function LoginPage({ onAuthSuccess }) {
  const [tab, setTab] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');

  useEffect(() => {
    const id = 'auth-styles';
    if (!document.getElementById(id)) {
      const s = document.createElement('style');
      s.id = id; s.textContent = AUTH_CSS;
      document.head.appendChild(s);
    }
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr(''); setOk('');
    if (!username.trim() || !password) { setErr('Please fill in all fields.'); return; }
    setLoading(true);
    try {
      const endpoint = tab === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/register';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setErr(data.detail || 'Something went wrong. Please try again.');
      } else {
        setOk(tab === 'login' ? `Welcome back, ${data.username}! 👋` : `Account created! Welcome, ${data.username}! 🎉`);
        localStorage.setItem('auth_token', data.token);
        localStorage.setItem('auth_user', JSON.stringify({ username: data.username, user_id: data.user_id }));
        setTimeout(() => onAuthSuccess({ username: data.username, user_id: data.user_id }, data.token), 800);
      }
    } catch {
      setErr('Connection error. Please check your internet and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-root">
      <div className="auth-bg">
        <div className="auth-grid" />
        <div className="auth-orb auth-orb-1" />
        <div className="auth-orb auth-orb-2" />
      </div>
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-gem"><i className="fas fa-heartbeat" /></div>
          <div className="auth-logo-text">
            <div className="auth-logo-name">NewGenHealthAI</div>
            <div className="auth-logo-sub">Personal Medical AI · Free Forever</div>
          </div>
        </div>
        <div className="auth-eyebrow">
          <h2>{tab === 'login' ? 'Welcome Back' : 'Create Account'}</h2>
          <p>{tab === 'login'
            ? 'Sign in to access your personal AI health assistant and full chat history.'
            : 'Register for free — your own private AI health assistant, forever.'
          }</p>
        </div>
        <div className="auth-tabs">
          <button className={`auth-tab${tab === 'login' ? ' active' : ''}`} onClick={() => { setTab('login'); setErr(''); setOk(''); }}>Sign In</button>
          <button className={`auth-tab${tab === 'register' ? ' active' : ''}`} onClick={() => { setTab('register'); setErr(''); setOk(''); }}>Register</button>
        </div>
        <form onSubmit={submit}>
          <div className="auth-field">
            <label className="auth-label">Username</label>
            <div className="auth-input-wrap">
              <input
                id="auth-username"
                className="auth-input"
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
              />
            </div>
          </div>
          <div className="auth-field">
            <label className="auth-label">Password</label>
            <div className="auth-input-wrap">
              <input
                id="auth-password"
                className="auth-input"
                type={showPw ? 'text' : 'password'}
                placeholder={tab === 'register' ? 'Min 6 characters' : 'Enter your password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
              />
              <button type="button" className="auth-eye" onClick={() => setShowPw(v => !v)} tabIndex={-1}>
                <i className={`fas ${showPw ? 'fa-eye-slash' : 'fa-eye'}`} />
              </button>
            </div>
          </div>
          {err && <div className="auth-err"><i className="fas fa-circle-exclamation" />{err}</div>}
          {ok  && <div className="auth-ok"><i className="fas fa-circle-check" />{ok}</div>}
          <button type="submit" id="auth-submit" className="auth-submit" disabled={loading}>
            <div className="auth-submit-shine" />
            {loading ? <><i className="fas fa-spinner fa-spin" /> &nbsp;Please wait…</> :
              tab === 'login' ? <><i className="fas fa-right-to-bracket" /> &nbsp;Sign In</> :
                               <><i className="fas fa-user-plus" /> &nbsp;Create Free Account</>
            }
          </button>
        </form>
        <div className="auth-footer">
          <strong>100% Free</strong> · Your data is private & isolated · No credit card needed
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  SECTION 6 — APP ROOT (ALL CORE LOGIC 100% PRESERVED)
// ═══════════════════════════════════════════════════════════════
const API_BASE = '/api/v1';

function useIsMobile(bp = 768) {
  const [v, setV] = useState(() => window.innerWidth <= bp);
  useEffect(() => {
    const h = () => setV(window.innerWidth <= bp);
    window.addEventListener('resize', h);
    return () => window.removeEventListener('resize', h);
  }, [bp]);
  return v;
}

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (window.innerWidth <= 768) return false;
    return localStorage.getItem('sidebarOpen') !== 'false';
  });

  // ── Auth state ─────────────────────────────────────────────
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('auth_user')); } catch { return null; }
  });
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('auth_token') || null);

  const handleAuthSuccess = useCallback((userData, token) => {
    setUser(userData);
    setAuthToken(token);
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      if (authToken) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${authToken}` },
        });
      }
    } catch { /* silent */ }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    setUser(null);
    setAuthToken(null);
    setMessages([]);
    setChatHistory([]);
    setSessions(null);
    setShowWelcome(true);
  }, [authToken]);

  // Helper: build auth headers
  const authHeaders = useCallback((extra = {}) => {
    const h = { ...extra };
    if (authToken) h['Authorization'] = `Bearer ${authToken}`;
    return h;
  }, [authToken]);
  // ───────────────────────────────────────────────────────────

  const [sessions, setSessions] = useState(null);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);
  const [showWelcome, setShowWelcome] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [toast, setToast] = useState({ show: false, message: '', type: 'success' });

  const chatAreaRef = useRef(null);
  const inputRef = useRef(null);
  const toastTimerRef = useRef(null);

  // Inject CSS
  useEffect(() => {
    const id = 'nc-styles';
    if (!document.getElementById(id)) {
      const s = document.createElement('style');
      s.id = id; s.textContent = WORLD_CLASS_CSS;
      document.head.appendChild(s);
    }
    return () => { const el = document.getElementById(id); if (el) el.remove(); };
  }, []);

  // Theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);
  const toggleTheme = () => setTheme(t => t === 'light' ? 'dark' : 'light');

  // Sidebar
  const toggleSidebar = () => {
    setSidebarOpen(prev => {
      if (!isMobile) localStorage.setItem('sidebarOpen', !prev);
      return !prev;
    });
  };
  const closeSidebar = () => setSidebarOpen(false);

  // Toast
  const showToast = useCallback((message, type = 'success') => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ show: true, message, type });
    toastTimerRef.current = setTimeout(() => setToast(t => ({ ...t, show: false })), 3000);
  }, []);

  // Scroll
  const scrollToBottom = useCallback(() => {
    if (chatAreaRef.current)
      chatAreaRef.current.scrollTo({ top: chatAreaRef.current.scrollHeight, behavior: 'smooth' });
  }, []);
  useEffect(() => { scrollToBottom(); }, [messages, isTyping, scrollToBottom]);

  // Load sessions
  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`, { headers: authHeaders() });
      const data = await res.json();
      if (data.success && data.sessions) setSessions(data.sessions);
    } catch { setSessions([]); }
  }, []);

  // Mount: load history
  useEffect(() => {
    if (!user) return; // Don't load sessions if not logged in
    loadSessions();
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/history`, { headers: authHeaders() });
        const data = await res.json();
        if (data.success && data.messages && data.messages.length > 0) {
          const msgs = data.messages.map(m => ({
            type: m.role === 'user' ? 'user' : 'assistant',
            content: m.content, timestamp: m.timestamp || '', source: m.source || null,
          }));
          setMessages(msgs); setChatHistory(msgs.map(m => ({ ...m }))); setShowWelcome(false);
        }
      } catch { /* silent */ }
    })();
  }, [loadSessions, user]);

  // Load session
  const loadSession = useCallback(async (sessionId) => {
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}`, { headers: authHeaders() });
      const data = await res.json();
      if (data.success) {
        setCurrentSessionId(sessionId);
        const msgs = data.messages.map(m => ({
          type: m.role === 'user' ? 'user' : 'assistant',
          content: m.content, timestamp: m.timestamp || '', source: m.source || null,
        }));
        setMessages(msgs); setChatHistory(msgs.map(m => ({ ...m }))); setShowWelcome(false);
        showToast('Session loaded', 'success');
      }
    } catch { showToast('Failed to load session', 'error'); }
  }, [showToast]);

  // Delete session
  const deleteSession = useCallback(async (sessionId) => {
    if (!window.confirm('Delete this conversation?')) return;
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}`, { method: 'DELETE', headers: authHeaders() });
      if (res.ok) {
        await loadSessions();
        if (currentSessionId === sessionId) createNewChat();
        showToast('Conversation deleted', 'success');
      }
    } catch { showToast('Failed to delete', 'error'); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId, loadSessions, showToast]);

  // New chat
  const createNewChat = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/new-chat`, { method: 'POST', headers: authHeaders() });
      if (res.ok) {
        setMessages([]); setChatHistory([]); setCurrentSessionId(null);
        setShowWelcome(true); await loadSessions();
        showToast('New conversation started', 'success');
      }
    } catch { showToast('Failed to create chat', 'error'); }
  }, [loadSessions, showToast]);

  // Clear chat
  const clearChat = useCallback(async () => {
    if (!window.confirm('Clear this conversation?')) return;
    try {
      const res = await fetch(`${API_BASE}/clear`, { method: 'POST', headers: authHeaders() });
      if (res.ok) {
        setMessages([]); setChatHistory([]); setShowWelcome(true);
        showToast('Conversation cleared', 'success');
      }
    } catch { showToast('Failed to clear', 'error'); }
  }, [showToast]);

  // Download
  const downloadChat = useCallback(() => {
    if (chatHistory.length === 0) { showToast('No messages to download', 'error'); return; }
    const content = buildDownloadText(chatHistory);
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `NewGenHealthAI-chat-${Date.now()}.txt`; a.click();
    URL.revokeObjectURL(url);
    showToast('Chat exported', 'success');
  }, [chatHistory, showToast]);

  // Image upload (MULTI-MODEL CLASSIFICATION + RAG)
  const handleImageUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const imageURL = URL.createObjectURL(file);
    const userMsg = { type: 'user', content: '📷 Uploaded Medical Image for Analysis', image: imageURL, timestamp: time };
    setMessages(prev => [...prev, userMsg]);
    setChatHistory(prev => [...prev, userMsg]);
    setIsTyping(true);
    setShowWelcome(false);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/analyze-image`, { method: 'POST', body: formData, headers: authHeaders() });
      const data = await res.json();
      console.log('Image API Response:', data);

      if (data.type === 'medical_diagnosis') {
        // --- Medical image detected ---
        const categoryLabels = {
          skin: '🧬 Skin Disease',
          xray: '🦴 X-ray / Fracture',
          retina: '👁️ Retinal / Eye Disease',
          general: '🏥 General Medical Condition',
        };
        const domainLabels = {
          skin: '📸 Skin photo detected',
          xray: '📸 X-ray / grayscale scan detected',
          retina: '📸 Retinal fundus scan detected',
          general: '📸 Medical image detected',
        };
        const catLabel = categoryLabels[data.category] || '🩺 Medical';
        const domainLabel = domainLabels[data.domain_hint] || '';
        const conf = (data.confidence * 100).toFixed(1);

        let result = `## 🩺 Medical Image Analysis\n\n`;
        if (domainLabel) result += `*${domainLabel}*\n\n`;
        result += `**Category:** ${catLabel}\n\n`;
        result += `### 🔍 Primary Diagnosis: **${data.disease}**\n`;
        result += `**Confidence:** ${conf}%\n\n`;

        // Top predictions from winning model
        if (data.predictions && data.predictions.length > 0) {
          result += `### 🔬 Differential Predictions\n`;
          data.predictions.forEach((p, i) => {
            const pct = (p.confidence * 100).toFixed(1);
            const filled = Math.round(p.confidence * 20);
            const bar = '█'.repeat(filled) + '░'.repeat(20 - filled);
            result += `${i + 1}. **${p.disease}** — ${pct}% \`${bar}\`\n`;
          });
          result += '\n';
        }

        result += `---\n*⚠️ AI-assisted analysis — always consult a qualified healthcare professional for diagnosis and treatment.*\n`;

        const botMsg = { type: 'assistant', content: result, timestamp: new Date().toLocaleTimeString(), source: `${data.category} model` };
        setMessages(prev => [...prev, botMsg]);

        // Medical details from RAG + LLM
        if (data.medical_details) {
          const detailMsg = {
            type: 'assistant',
            content: `### 📋 Medical Information: ${data.disease}\n\n${data.medical_details}`,
            timestamp: new Date().toLocaleTimeString(),
            source: 'RAG + LLM',
          };
          setMessages(prev => [...prev, detailMsg]);
        }

      } else {
        // --- General (non-medical) image ---
        let result = `## 🖼️ Image Analysis\n\n`;
        if (data.description) {
          result += `**Description:** ${data.description}\n\n`;
        }
        result += `*This image does not appear to be a recognizable medical image.\nUpload a clear skin photo, X-ray, retina scan, or other medical image for AI-powered diagnosis.*`;
        const botMsg = { type: 'assistant', content: result, timestamp: new Date().toLocaleTimeString() };
        setMessages(prev => [...prev, botMsg]);
      }

    } catch (err) {
      console.error('Image analysis error:', err);
      setMessages(prev => [...prev, { type: 'assistant', content: '⚠️ Image analysis failed. Please try again.', timestamp: time }]);
    }
    setIsTyping(false);
    event.target.value = '';
  };

  // Send message (CORE LOGIC FULLY PRESERVED)
  const sendMessage = useCallback(async (overrideText) => {
    const message = (overrideText ?? inputValue).trim();
    if (!message || isTyping) return;
    setShowWelcome(false);
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg = { type: 'user', content: message, timestamp: time, source: null };
    setMessages(prev => [...prev, userMsg]);
    setChatHistory(prev => [...prev, userMsg]);
    setInputValue('');
    if (inputRef.current) inputRef.current.style.height = 'auto';
    setIsTyping(true);
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      if (data.success) {
        const botMsg = {
          type: 'assistant',
          content: data.response,
          timestamp: new Date().toLocaleTimeString(),
          source: data.source || null,
          followUp: data.follow_up || null,
        };
        setMessages(prev => [...prev, botMsg]);
        setChatHistory(prev => [...prev, botMsg]);
        if (data.follow_up) {
          showToast('Doctor needs more information', 'info');
        } else {
          showToast('Response received', 'success');
        }
        await loadSessions();
      } else {
        setMessages(prev => [...prev, { type: 'assistant', content: 'Sorry, I encountered an error. Please try again.', timestamp: new Date().toLocaleTimeString() }]);
        showToast('Error occurred', 'error');
      }
    } catch {
      setMessages(prev => [...prev, { type: 'assistant', content: 'Connection error. Please check your internet and try again.', timestamp: new Date().toLocaleTimeString() }]);
      showToast('Connection error', 'error');
    } finally { setIsTyping(false); }
  }, [inputValue, isTyping, loadSessions, showToast]);

  const handleQuickQuestion = useCallback((q) => { setTimeout(() => sendMessage(q), 200); }, [sendMessage]);

  // Follow-up chip click handler — sends the option as a new message
  const handleFollowUpClick = useCallback((optionText) => {
    setTimeout(() => sendMessage(optionText), 150);
  }, [sendMessage]);

  // Toast config
  const toastBg = { success: 'linear-gradient(135deg,#059669,#10b981)', error: 'linear-gradient(135deg,#be123c,#f43f5e)', info: 'linear-gradient(135deg,#1d4ed8,#3b82f6)' };
  const toastIcon = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle' };

  // ═══ RENDER ════════════════════════════════════════════════
  // Show login page if not authenticated
  if (!user || !authToken) {
    return <LoginPage onAuthSuccess={handleAuthSuccess} />;
  }

  return (
    <>
      {/* Cinematic Background */}
      <div className="nc-bg">
        <div className="nc-bg-grid" />
        <div className="nc-orb nc-orb-a" />
        <div className="nc-orb nc-orb-b" />
        <div className="nc-orb nc-orb-c" />
      </div>

      <div className="nc-app">
        {/* Mobile veil */}
        {isMobile && sidebarOpen && <div className="nc-veil" onClick={closeSidebar} />}

        {/* Sidebar */}
        <Sidebar
          sidebarOpen={sidebarOpen}
          sessions={sessions}
          currentSessionId={currentSessionId}
          onNewChat={createNewChat}
          onLoadSession={loadSession}
          onDeleteSession={deleteSession}
          onToggleTheme={toggleTheme}
          theme={theme}
          user={user}
          onLogout={handleLogout}
        />

        {/* Main */}
        <main className="nc-main">
          {/* Header */}
          <header className="nc-header">
            <div className="nc-h-left">
              <button className="nc-menu-btn" onClick={toggleSidebar} title="Toggle sidebar">
                <i className="fas fa-bars" />
              </button>
              <span className="nc-h-title">Medical AI Assistant</span>
              <div className="nc-ai-badge"><div className="nc-ai-dot" /> AI Ready</div>
            </div>
            <div className="nc-h-right">
              <button 
  className="nc-hbtn"
  onClick={() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  }}
>
  <i className="fas fa-expand"></i>
</button>
              <button className="nc-hbtn danger" title="Clear conversation" onClick={clearChat}>
                <i className="fas fa-trash-can" />
              </button>
              <button className="nc-hbtn" title="Download transcript" onClick={downloadChat}>
                <i className="fas fa-arrow-down-to-line" />
              </button>
              <button className="nc-hbtn" title="Settings">
                <i className="fas fa-sliders" />
              </button>
            </div>
          </header>

          {/* Chat */}
          <ChatArea
            messages={messages}
            isTyping={isTyping}
            showWelcome={showWelcome}
            onQuickQuestion={handleQuickQuestion}
            onFollowUpClick={handleFollowUpClick}
            chatAreaRef={chatAreaRef}
          />

          {/* Input */}
          <InputArea
            inputValue={inputValue}
            setInputValue={setInputValue}
            onSend={() => sendMessage()}
            isTyping={isTyping}
            inputRef={inputRef}
            onImageUpload={handleImageUpload}
          />
        </main>
      </div>

      {/* Toast */}
      <div className={`nc-toast${toast.show ? ' show' : ''}`} style={{ background: toastBg[toast.type] }}>
        <i className={`fas ${toastIcon[toast.type]}`} />
        <span>{toast.message}</span>
        {toast.show && <div className="nc-toast-bar" />}
      </div>
    </>
  );
}
