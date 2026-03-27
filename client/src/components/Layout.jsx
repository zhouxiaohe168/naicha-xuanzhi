import React from 'react';
import { LayoutDashboard, Radar, Briefcase, Globe, Settings, Sun, Moon, Cpu, Coins } from 'lucide-react';
import { useShield } from '../hooks/useShieldData';

const tabs = [
  { id: '总览', Icon: LayoutDashboard, label: 'CEO驾驶舱', short: '总览' },
  { id: 'CTO', Icon: Cpu, label: 'CTO总部', short: 'CTO' },
  { id: '信号', Icon: Radar, label: '信号雷达', short: '信号' },
  { id: '持仓', Icon: Briefcase, label: '持仓管理', short: '持仓' },
  { id: '市场', Icon: Coins, label: '全局看板', short: '市场' },
  { id: '情报', Icon: Globe, label: '情报中心', short: '情报' },
  { id: '系统', Icon: Settings, label: '系统控制', short: '系统' },
];

const Layout = ({ children }) => {
  const { activeTab, setActiveTab, alphaSignals, paperPositions, theme, toggleTheme, notifications } = useShield();

  const getBadge = (id) => {
    if (id === '信号') return alphaSignals?.length > 0 ? alphaSignals.length : null;
    if (id === '持仓') return paperPositions?.length > 0 ? paperPositions.length : null;
    if (id === '系统') {
      const unread = notifications?.filter(n => !n.read)?.length || 0;
      return unread > 0 ? unread : null;
    }
    return null;
  };

  return (
    <div className="flex flex-col h-full">
      <nav className="hidden md:flex shield-glass-elevated rounded-2xl p-1.5 mb-4 items-center gap-1 overflow-x-auto scrollbar-hide">
        {tabs.map(tab => {
          const isActive = activeTab === tab.id;
          const badge = getBadge(tab.id);
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-xs transition-all duration-300 min-w-fit btn-glow ${
                isActive
                  ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-black shadow-lg shadow-amber-500/20'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              }`}
            >
              <tab.Icon className="w-4 h-4" />
              <span>{tab.label}</span>
              {badge && (
                <span className={`absolute -top-1 -right-1 min-w-[16px] h-4 flex items-center justify-center text-[9px] font-black rounded-full px-1 ${
                  isActive ? 'bg-black text-amber-400' : 'bg-amber-500 text-black animate-pulse'
                }`}>
                  {badge}
                </span>
              )}
            </button>
          );
        })}
        <button
          onClick={toggleTheme}
          className="ml-auto p-2 rounded-xl text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 transition-all min-w-fit"
          title={theme === 'dark' ? '切换亮色' : '切换暗色'}
        >
          {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>
      </nav>

      <div key={activeTab} className="flex-1 animate-fadeIn pb-20 md:pb-0">
        {children}
      </div>

      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 shield-glass-elevated border-t border-slate-700/50 safe-area-bottom">
        <div className="flex items-center justify-around px-0.5 py-1">
          {tabs.map(tab => {
            const isActive = activeTab === tab.id;
            const badge = getBadge(tab.id);
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative flex flex-col items-center gap-0.5 px-1 py-1.5 rounded-lg transition-all duration-200 min-w-0 flex-1 ${
                  isActive
                    ? 'text-amber-400'
                    : 'text-slate-500 active:text-slate-300'
                }`}
              >
                <tab.Icon className={`w-4.5 h-4.5 ${isActive ? 'drop-shadow-[0_0_6px_rgba(245,158,11,0.4)]' : ''}`} />
                <span className={`text-[8px] font-bold leading-tight ${isActive ? 'text-amber-400' : 'text-slate-600'}`}>{tab.short}</span>
                {badge && (
                  <span className="absolute -top-0.5 right-1/4 min-w-[14px] h-3.5 flex items-center justify-center text-[8px] font-black rounded-full px-0.5 bg-amber-500 text-black">
                    {badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
};

export default Layout;
