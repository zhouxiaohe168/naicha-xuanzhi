import { useEffect, useRef, useState, useMemo } from 'react';
import { LineChart, Line, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

export const GaugeRing = ({ value = 0, max = 100, size = 64, strokeWidth = 5, color = '#06b6d4', bgColor = '#1e293b', label, sublabel }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(Math.max(value / max, 0), 1);
  const offset = circumference * (1 - pct);

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={bgColor} strokeWidth={strokeWidth} />
          <circle
            cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={strokeWidth}
            strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
            className="score-ring" style={{ '--ring-circumference': circumference, '--ring-offset': offset }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xs font-black tabular-nums" style={{ color }}>{typeof value === 'number' ? Math.round(value) : value}</span>
          {sublabel && <span className="text-[7px] text-slate-500">{sublabel}</span>}
        </div>
      </div>
      {label && <span className="text-[8px] text-slate-500 font-bold uppercase tracking-wider">{label}</span>}
    </div>
  );
};

export const MiniSparkline = ({ data = [], dataKey = 'value', color = '#06b6d4', height = 32, width = 80 }) => {
  if (!data || data.length < 2) return null;
  return (
    <div style={{ width, height }}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export const AnimatedNumber = ({ value, decimals = 0, prefix = '', suffix = '', className = '' }) => {
  const [display, setDisplay] = useState(value);
  const prevRef = useRef(value);

  useEffect(() => {
    const prev = prevRef.current;
    const target = typeof value === 'number' ? value : parseFloat(value) || 0;
    if (prev === target) return;
    prevRef.current = target;

    const duration = 400;
    const start = performance.now();
    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(prev + (target - prev) * eased);
      if (progress < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }, [value]);

  const formatted = typeof display === 'number' ? display.toFixed(decimals) : display;
  return <span className={`tabular-nums ${className}`}>{prefix}{formatted}{suffix}</span>;
};

export const SkeletonBlock = ({ width = '100%', height = '16px', rounded = '8px', className = '' }) => (
  <div className={`skeleton ${className}`} style={{ width, height, borderRadius: rounded }} />
);

export const SkeletonCard = ({ rows = 3 }) => (
  <div className="shield-glass rounded-2xl p-5 space-y-3">
    <SkeletonBlock width="40%" height="12px" />
    {Array.from({ length: rows }).map((_, i) => (
      <SkeletonBlock key={i} width={`${70 + Math.random() * 30}%`} height="14px" />
    ))}
  </div>
);

export const StrengthBar = ({ value = 0, max = 100, colorStops = ['#ef4444', '#f59e0b', '#10b981'] }) => {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  const colorIdx = pct < 33 ? 0 : pct < 66 ? 1 : 2;
  return (
    <div className="signal-strength-bar">
      <div className="fill" style={{ width: `${pct}%`, backgroundColor: colorStops[colorIdx] }} />
    </div>
  );
};

export const ScoreChip = ({ score, size = 'md' }) => {
  const s = typeof score === 'number' ? score : 0;
  const bg = s >= 80 ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400 glow-emerald'
    : s >= 60 ? 'bg-amber-500/15 border-amber-500/30 text-amber-400 glow-amber'
    : 'bg-red-500/15 border-red-500/30 text-red-400 glow-red';
  const sz = size === 'lg' ? 'text-lg px-3 py-1.5' : size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-sm px-2.5 py-1';
  return (
    <span className={`font-black rounded-xl border ${bg} ${sz} tabular-nums inline-block`}>
      {Math.round(s)}
    </span>
  );
};

export const StatusDot = ({ status = 'healthy', pulse = true }) => {
  const colors = {
    healthy: 'bg-emerald-400',
    warning: 'bg-amber-400',
    danger: 'bg-red-400',
    offline: 'bg-slate-600',
  };
  return (
    <span className="relative flex h-2.5 w-2.5">
      {pulse && status !== 'offline' && (
        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-50 ${colors[status]}`} />
      )}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${colors[status]}`} />
    </span>
  );
};

export const PortfolioDonut = ({ data = [], size = 160, innerRadius = 45, outerRadius = 65 }) => {
  const COLORS = ['#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#ec4899', '#14b8a6'];
  if (!data || data.length === 0) return null;
  return (
    <div style={{ width: size, height: size }}>
      <ResponsiveContainer width="100%" height={size}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%"
            innerRadius={innerRadius} outerRadius={outerRadius} paddingAngle={2} strokeWidth={0}>
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

export const ProgressRing = ({ value = 0, max = 100, size = 24, strokeWidth = 3, color = '#10b981' }) => {
  const r = (size - strokeWidth) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.min(Math.max(value / max, 0), 1);
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1e293b" strokeWidth={strokeWidth} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={strokeWidth}
        strokeDasharray={c} strokeDashoffset={c * (1 - pct)} strokeLinecap="round" className="score-ring" />
    </svg>
  );
};

export const EmptyState = ({ icon: Icon, title, subtitle }) => (
  <div className="flex flex-col items-center justify-center py-12 animate-fadeIn">
    {Icon && <Icon className="w-12 h-12 text-slate-700 mb-4" />}
    <h4 className="text-sm font-bold text-slate-500 mb-1">{title}</h4>
    {subtitle && <p className="text-[10px] text-slate-600">{subtitle}</p>}
  </div>
);
