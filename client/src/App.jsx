import React from 'react';
import { Radar, AlertTriangle } from 'lucide-react';
import { ShieldProvider, useShield } from './hooks/useShieldData';
import CommandBar from './components/CommandBar';
import Layout from './components/Layout';
import CEODashboard from './pages/CEODashboard';
import CTOHeadquarters from './pages/CTOHeadquarters';
import SignalRadar from './pages/SignalRadar';
import PositionManager from './pages/PositionManager';
import MarketDashboard from './pages/MarketDashboard';
import IntelCenter from './pages/IntelCenter';
import SystemControl from './pages/SystemControl';

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error('App crash:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#020617] text-slate-100 flex flex-col items-center justify-center">
          <AlertTriangle className="w-16 h-16 text-red-500 mb-4" />
          <h2 className="text-xl font-black text-white mb-2">系统异常</h2>
          <p className="text-slate-400 text-xs mb-4 max-w-md text-center">{this.state.error?.message || '未知错误'}</p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            className="bg-amber-500 text-black font-bold text-xs px-6 py-2 rounded-xl hover:bg-amber-400 transition-all"
          >
            重启系统
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

class PageErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error('Page crash:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="shield-glass rounded-2xl p-8 text-center animate-fadeIn">
          <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto mb-4" />
          <h3 className="text-lg font-black text-white mb-2">模块渲染异常</h3>
          <p className="text-slate-400 text-xs mb-4">{this.state.error?.message || '未知错误'}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="bg-amber-500 text-black font-bold text-xs px-6 py-2 rounded-xl hover:bg-amber-400 transition-all"
          >
            重新加载模块
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const ShieldApp = () => {
  const { isLoading, activeTab } = useShield();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#020617] text-slate-100 flex flex-col items-center justify-center">
        <div className="relative">
          <div className="absolute inset-0 bg-amber-500/20 rounded-full blur-3xl animate-pulse" />
          <Radar className="w-16 h-16 text-amber-500 animate-spin relative z-10" />
        </div>
        <p className="text-slate-400 text-lg mt-6 font-bold">神盾计划：不死量化 启动中...</p>
        <p className="text-slate-600 text-xs mt-2">加载系统模块...</p>
      </div>
    );
  }

  const pages = {
    '总览': <CEODashboard />,
    'CTO': <CTOHeadquarters />,
    '信号': <SignalRadar />,
    '持仓': <PositionManager />,
    '市场': <MarketDashboard />,
    '情报': <IntelCenter />,
    '系统': <SystemControl />,
  };

  return (
    <div className="min-h-screen bg-[#020617] text-slate-100 p-2 md:p-5 font-sans selection:bg-amber-500/30">
      <CommandBar />
      <Layout>
        <PageErrorBoundary key={activeTab}>
          {pages[activeTab] || <CEODashboard />}
        </PageErrorBoundary>
      </Layout>
    </div>
  );
};

const App = () => (
  <AppErrorBoundary>
    <ShieldProvider>
      <ShieldApp />
    </ShieldProvider>
  </AppErrorBoundary>
);

export default App;
