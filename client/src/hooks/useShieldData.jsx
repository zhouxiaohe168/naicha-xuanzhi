import { useState, useEffect, useMemo, createContext, useContext, useCallback, useRef } from 'react';

const ShieldContext = createContext(null);

export const ShieldProvider = ({ children }) => {
  const [activeTab, setActiveTab] = useState('总览');
  const [dataAge, setDataAge] = useState(0);
  const [data, setData] = useState(null);
  const [positions, setPositions] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [newOrder, setNewOrder] = useState({ sym: '', entry: '', tp: '', sl: '', amount: '' });
  const [mlStatus, setMlStatus] = useState(null);
  const [sortField, setSortField] = useState('score');
  const [sortDir, setSortDir] = useState('desc');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterMode, setFilterMode] = useState('ALL');
  const [backtestData, setBacktestData] = useState(null);
  const [mmStatus, setMmStatus] = useState(null);
  const [adaptiveWeights, setAdaptiveWeights] = useState(null);
  const [criticStatus, setCriticStatus] = useState(null);
  const [agentMemory, setAgentMemory] = useState(null);
  const [governorStatus, setGovernorStatus] = useState(null);
  const [feedbackStatus, setFeedbackStatus] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [simRunning, setSimRunning] = useState(false);
  const [externalData, setExternalData] = useState(null);
  const [darwinLab, setDarwinLab] = useState(null);
  const [agiData, setAgiData] = useState(null);
  const [v19Data, setV19Data] = useState(null);
  const [mtfData, setMtfData] = useState(null);
  const [mtfSymbol, setMtfSymbol] = useState('BTC');
  const [mtfLoading, setMtfLoading] = useState(false);
  const [pipelineData, setPipelineData] = useState(null);
  const [pipelinePolling, setPipelinePolling] = useState(false);
  const [paperPositions, setPaperPositions] = useState([]);
  const [paperPortfolio, setPaperPortfolio] = useState(null);
  const [paperTrades, setPaperTrades] = useState([]);
  const [tradeModal, setTradeModal] = useState(null);
  const [tradePreview, setTradePreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [constitutionStatus, setConstitutionStatus] = useState(null);
  const [coordinatorData, setCoordinatorData] = useState(null);
  const [capitalSizerData, setCapitalSizerData] = useState(null);
  const [unifiedDecisionData, setUnifiedDecisionData] = useState(null);
  const [returnTargetData, setReturnTargetData] = useState(null);
  const [signalQualityData, setSignalQualityData] = useState(null);
  const [riskBudgetData, setRiskBudgetData] = useState(null);
  const [synapseData, setSynapseData] = useState(null);
  const [aiDiagnostic, setAiDiagnostic] = useState(null);
  const [diagnosticRunning, setDiagnosticRunning] = useState(false);
  const [equityHistory, setEquityHistory] = useState([]);
  const [strategyPerf, setStrategyPerf] = useState(null);
  const [mlFeatures, setMlFeatures] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [theme, setTheme] = useState(() => localStorage.getItem('shield-theme') || 'dark');
  const [memoryStats, setMemoryStats] = useState(null);
  const [memoryAnalysis, setMemoryAnalysis] = useState(null);
  const [memoryAnalyzing, setMemoryAnalyzing] = useState(false);
  const [attributionChartData, setAttributionChartData] = useState(null);
  const [wallStreetMetrics, setWallStreetMetrics] = useState(null);
  const [autopilotStatus, setAutopilotStatus] = useState(null);
  const [gridData, setGridData] = useState(null);
  const [coinglassData, setCoinglassData] = useState(null);
  const [protectionLayers, setProtectionLayers] = useState(null);

  useEffect(() => {
    const timer = setInterval(() => setDataAge(prev => prev + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      if (isLoading) setIsLoading(false);
    }, 800);
    return () => clearTimeout(timeout);
  }, []);

  const activeTabRef = useRef(activeTab);
  useEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);
  const lastCtoFetchRef = useRef(0);

  const fetchCoreData = useCallback(async () => {
    try {
      const response = await fetch('/api/dashboard');
      if (!response.ok) throw new Error('API error ' + response.status);
      const text = await response.text();
      let result;
      try {
        result = JSON.parse(text);
      } catch (parseErr) {
        console.error('JSON parse error, response length:', text.length, parseErr);
        return;
      }
      const marketData = result.market || {};
      marketData.dispatcher = result.dispatcher || null;
      marketData.grid = result.grid || null;
      marketData.ai_reviewer = result.ai_reviewer || null;
      marketData.watchdog = result.watchdog || null;
      marketData.signal_quality = result.signal_quality || null;
      marketData.synapse = result.synapse || null;
      marketData.risk_budget = result.risk_budget || null;
      marketData.unified_decision = result.unified_decision || null;
      marketData.return_target = result.return_target || null;
      setData(marketData);
      setPositions(result.positions || []);
      setMlStatus(result.ml_status || null);
      setMmStatus(result.mm_status || null);
      setAdaptiveWeights(result.adaptive_weights || null);
      setCriticStatus(result.critic_status || null);
      setAgentMemory(result.agent_memory || null);
      setGovernorStatus(result.governor || null);
      setFeedbackStatus(result.feedback || null);
      setSimStatus(result.simulator || null);
      setExternalData(result.external_data || null);
      setDarwinLab(result.darwin_lab || null);
      setPaperPortfolio(result.paper_trader || null);
      setPaperPositions(result.paper_positions || []);
      setConstitutionStatus(result.constitution || null);
      if (result.signal_quality) setSignalQualityData(result.signal_quality);
      if (result.risk_budget) setRiskBudgetData(result.risk_budget);
      if (result.synapse) setSynapseData(result.synapse);
      if (result.ai_coordinator) setCoordinatorData(result.ai_coordinator);
      if (result.capital_sizer) setCapitalSizerData(result.capital_sizer);
      if (result.unified_decision) setUnifiedDecisionData(result.unified_decision);
      if (result.return_target) setReturnTargetData(result.return_target);
      setIsConnected(true);
      setIsLoading(false);
      setDataAge(0);
    } catch (err) {
      console.error('Failed to fetch:', err);
      setIsConnected(false);
      setIsLoading(false);
    }
  }, []);

  const fetchTabData = useCallback(async (tab) => {
    const fetchers = [];
    if (tab === '总览') {
      fetchers.push(
        fetch('/api/paper/trades').then(r => r.ok ? r.json() : null).then(d => { if (d) setPaperTrades(d.trades || d || []); }).catch(() => {}),
        fetch('/api/equity-history').then(r => r.ok ? r.json() : null).then(d => { if (d) setEquityHistory(d.equity_curve || []); }).catch(() => {}),
        fetch('/api/wall-street-metrics').then(r => r.ok ? r.json() : null).then(d => { if (d) setWallStreetMetrics(d); }).catch(() => {}),
        fetch('/api/strategy-performance').then(r => r.ok ? r.json() : null).then(d => { if (d) setStrategyPerf(d); }).catch(() => {}),
        fetch('/api/protection-layers').then(r => r.ok ? r.json() : null).then(d => { if (d) setProtectionLayers(d); }).catch(() => {}),
        fetch('/api/notifications').then(r => r.ok ? r.json() : null).then(d => { if (d) setNotifications(d.notifications || []); }).catch(() => {}),
      );
    } else if (tab === '信号') {
      fetchers.push(
        fetch('/api/v19/dashboard').then(r => r.ok ? r.json() : null).then(d => {
          if (d) { setV19Data(d); if (d.ai_coordinator) setCoordinatorData(d.ai_coordinator); if (d.capital_sizer) setCapitalSizerData(d.capital_sizer); }
        }).catch(() => {}),
        fetch('/api/ml-features').then(r => r.ok ? r.json() : null).then(d => { if (d) setMlFeatures(d); }).catch(() => {}),
        fetch('/api/notifications').then(r => r.ok ? r.json() : null).then(d => { if (d) setNotifications(d.notifications || []); }).catch(() => {}),
      );
    } else if (tab === '持仓') {
      fetchers.push(
        fetch('/api/paper/trades').then(r => r.ok ? r.json() : null).then(d => { if (d) setPaperTrades(d.trades || d || []); }).catch(() => {}),
        fetch('/api/equity-history').then(r => r.ok ? r.json() : null).then(d => { if (d) setEquityHistory(d.equity_curve || []); }).catch(() => {}),
        fetch('/api/grid').then(r => r.ok ? r.json() : null).then(d => { if (d) setGridData(d); }).catch(() => {}),
        fetch('/api/notifications').then(r => r.ok ? r.json() : null).then(d => { if (d) setNotifications(d.notifications || []); }).catch(() => {}),
      );
    } else if (tab === '市场') {
      fetchers.push(
        fetch('/api/external-data/coinglass').then(r => r.ok ? r.json() : null).then(d => { if (d) setCoinglassData(d); }).catch(() => {}),
        fetch('/api/v19/dashboard').then(r => r.ok ? r.json() : null).then(d => {
          if (d) { setV19Data(d); if (d.ai_coordinator) setCoordinatorData(d.ai_coordinator); }
        }).catch(() => {}),
      );
    } else if (tab === '情报') {
      fetchers.push(
        fetch('/api/external-data/coinglass').then(r => r.ok ? r.json() : null).then(d => { if (d) setCoinglassData(d); }).catch(() => {}),
        fetch('/api/wall-street-metrics').then(r => r.ok ? r.json() : null).then(d => { if (d) setWallStreetMetrics(d); }).catch(() => {}),
        fetch('/api/notifications').then(r => r.ok ? r.json() : null).then(d => { if (d) setNotifications(d.notifications || []); }).catch(() => {}),
      );
    } else if (tab === '系统') {
      fetchers.push(
        fetch('/api/autopilot/status').then(r => r.ok ? r.json() : null).then(d => { if (d) setAutopilotStatus(d); }).catch(() => {}),
        fetch('/api/grid').then(r => r.ok ? r.json() : null).then(d => { if (d) setGridData(d); }).catch(() => {}),
        fetch('/api/backtest').then(r => r.ok ? r.json() : null).then(d => { if (d) setBacktestData(d); }).catch(() => {}),
        fetch('/api/notifications').then(r => r.ok ? r.json() : null).then(d => { if (d) setNotifications(d.notifications || []); }).catch(() => {}),
      );
    }
    if (fetchers.length > 0) await Promise.all(fetchers);
  }, []);

  const fetchCtoData = useCallback(async () => {
    const now = Date.now();
    if (now - lastCtoFetchRef.current < 3600000 && lastCtoFetchRef.current > 0) return;
    lastCtoFetchRef.current = now;
    const fetchers = [
      fetch('/api/ai-diagnostic').then(r => r.ok ? r.json() : null).then(d => { if (d) setAiDiagnostic(d); }).catch(() => {}),
      fetch('/api/agi').then(r => r.ok ? r.json() : null).then(d => { if (d) setAgiData(d); }).catch(() => {}),
      fetch('/api/v19/dashboard').then(r => r.ok ? r.json() : null).then(d => {
        if (d) { setV19Data(d); if (d.ai_coordinator) setCoordinatorData(d.ai_coordinator); if (d.capital_sizer) setCapitalSizerData(d.capital_sizer); }
      }).catch(() => {}),
      fetch('/api/autopilot/status').then(r => r.ok ? r.json() : null).then(d => { if (d) setAutopilotStatus(d); }).catch(() => {}),
      fetch('/api/equity-history').then(r => r.ok ? r.json() : null).then(d => { if (d) setEquityHistory(d.equity_curve || []); }).catch(() => {}),
      fetch('/api/strategy-performance').then(r => r.ok ? r.json() : null).then(d => { if (d) setStrategyPerf(d); }).catch(() => {}),
      fetch('/api/ml-features').then(r => r.ok ? r.json() : null).then(d => { if (d) setMlFeatures(d); }).catch(() => {}),
      fetch('/api/notifications').then(r => r.ok ? r.json() : null).then(d => { if (d) setNotifications(d.notifications || []); }).catch(() => {}),
    ];
    await Promise.all(fetchers);
  }, []);

  const fetchAll = useCallback(async () => {
    await fetchCoreData();
    const tab = activeTabRef.current;
    if (tab === 'CTO') {
      await fetchCtoData();
    } else {
      await fetchTabData(tab);
    }
  }, [fetchCoreData, fetchTabData, fetchCtoData]);

  const scanProgressRef = useRef({ scanning: false });
  useEffect(() => {
    scanProgressRef.current = data?.scan_progress || { scanning: false };
  }, [data]);

  useEffect(() => {
    let cancelled = false;
    let timer;
    fetchAll();
    const smartPoll = () => {
      if (cancelled) return;
      const interval = scanProgressRef.current.scanning ? 5000 : 15000;
      timer = setTimeout(async () => {
        if (cancelled) return;
        await fetchAll();
        smartPoll();
      }, interval);
    };
    smartPoll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [fetchAll]);

  useEffect(() => {
    if (activeTab === 'CTO') {
      fetchCtoData();
    } else {
      fetchTabData(activeTab);
    }
  }, [activeTab, fetchCtoData, fetchTabData]);

  useEffect(() => {
    if (!pipelinePolling) return;
    const pollPipeline = async () => {
      try {
        const r = await fetch('/api/pipeline/status');
        if (r.ok) {
          const d = await r.json();
          setPipelineData(d);
          if (!d.running && d.stage !== '' && d.stage !== 'data') {
            setPipelinePolling(false);
          }
        }
      } catch {}
    };
    pollPipeline();
    const t = setInterval(pollPipeline, 2000);
    return () => clearInterval(t);
  }, [pipelinePolling]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('shield-theme', theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  }, []);

  const runSignalQualityAI = useCallback(async () => {
    try {
      const res = await fetch('/api/signal-quality/ai-evaluate', { method: 'POST' });
      if (res.ok) return await res.json();
    } catch (err) { console.error('Signal quality AI failed:', err); }
    return null;
  }, []);

  const runSynapseAI = useCallback(async () => {
    try {
      const res = await fetch('/api/synapse/ai-insights', { method: 'POST' });
      if (res.ok) return await res.json();
    } catch (err) { console.error('Synapse AI failed:', err); }
    return null;
  }, []);

  const handleAddOrder = useCallback(async (e) => {
    e.preventDefault();
    if (!newOrder.sym || !newOrder.entry || !newOrder.amount) return;
    try {
      await fetch('/api/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newOrder),
      });
      setNewOrder({ sym: '', entry: '', tp: '', sl: '', amount: '' });
      fetchAll();
    } catch (err) {
      console.error("Order failed:", err);
    }
  }, [newOrder, fetchAll]);

  const removePosition = useCallback(async (id) => {
    try {
      await fetch(`/api/order/${id}`, { method: 'DELETE' });
      fetchAll();
    } catch (err) {
      console.error(err);
    }
  }, [fetchAll]);

  const openTradeModal = useCallback(async (symbol, direction = 'long') => {
    setTradeModal({ symbol, direction });
    setPreviewLoading(true);
    setTradePreview(null);
    try {
      const res = await fetch('/api/trade/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, direction }),
      });
      const d = await res.json();
      setTradePreview(d);
    } catch (err) {
      console.error('Preview failed:', err);
    }
    setPreviewLoading(false);
  }, []);

  const confirmTrade = useCallback(async (overrides = {}) => {
    if (!tradePreview) return;
    try {
      const res = await fetch('/api/trade/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: tradePreview.symbol,
          direction: tradePreview.direction,
          amount: overrides.amount != null ? overrides.amount : tradePreview.recommended_amount,
          tp_price: overrides.tp_price != null ? overrides.tp_price : tradePreview.tp_price,
          sl_price: overrides.sl_price != null ? overrides.sl_price : tradePreview.sl_price,
          entry_price: overrides.entry_price != null ? overrides.entry_price : tradePreview.price,
        }),
      });
      const d = await res.json();
      if (d.status === 'ok') {
        setTradeModal(null);
        setTradePreview(null);
        fetchAll();
      } else {
        alert(d.message || '下单失败');
      }
    } catch (err) {
      alert('下单失败: ' + err.message);
    }
  }, [tradePreview, fetchAll]);

  const closePaperPosition = useCallback(async (posId) => {
    try {
      const res = await fetch(`/api/trade/close/${posId}`, { method: 'POST' });
      const d = await res.json();
      if (d.status === 'ok') fetchAll();
    } catch (err) {
      console.error('Close failed:', err);
    }
  }, [fetchAll]);

  const fetchPaperTrades = useCallback(async () => {
    try {
      const res = await fetch('/api/paper/trades');
      const d = await res.json();
      setPaperTrades(d.trades || []);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const runDiagnostic = useCallback(async () => {
    setDiagnosticRunning(true);
    try {
      const res = await fetch('/api/ai-diagnostic/run', { method: 'POST' });
      const d = await res.json();
      if (d.error) {
        setAiDiagnostic(prev => ({ ...prev, latest_report: { diagnosis: { health_score: 0, summary: `诊断失败: ${d.error}`, severity: 'critical' } } }));
      } else {
        setAiDiagnostic(prev => ({ ...prev, latest_report: d, stats: { ...prev?.stats, total_diagnostics: (prev?.stats?.total_diagnostics || 0) + 1 } }));
      }
    } catch (err) {
      console.error('Diagnostic failed:', err);
      setAiDiagnostic(prev => ({ ...prev, latest_report: { diagnosis: { health_score: 0, summary: `诊断连接失败: ${err.message}`, severity: 'critical' } } }));
    }
    setDiagnosticRunning(false);
  }, []);

  const executeDiagnosticAction = useCallback(async (actionType, params = {}) => {
    try {
      if (actionType === 'freeze_assets') {
        const assets = params.assets || [];
        if (assets.length === 0) return { error: '未找到需要冻结的资产名称' };
        const res = await fetch('/api/asset/freeze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ assets, reason: params.reason || 'P1诊断建议' }),
        });
        if (!res.ok) return { error: `请求失败 (${res.status})` };
        return await res.json();
      }
      if (actionType === 'enable_risk_limits') {
        const res = await fetch('/api/ai-diagnostic/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: 'enable_risk_limits', daily_limit: params.daily || 0.02, total_limit: params.total || 0.05 }),
        });
        if (!res.ok) return { error: `请求失败 (${res.status})` };
        return await res.json();
      }
      if (actionType === 'calibrate_signals') {
        const res = await fetch('/api/ai-diagnostic/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: 'calibrate_signals' }),
        });
        if (!res.ok) return { error: `请求失败 (${res.status})` };
        return await res.json();
      }
      return { error: '未知操作' };
    } catch (err) {
      console.error('Execute diagnostic action failed:', err);
      return { error: err.message };
    }
  }, []);

  const getFrozenAssets = useCallback(async () => {
    try {
      const res = await fetch('/api/asset/frozen');
      if (res.ok) return await res.json();
    } catch (err) {
      console.error('Get frozen assets failed:', err);
    }
    return { frozen_assets: [], count: 0 };
  }, []);

  const runAutoExecute = useCallback(async () => {
    setDiagnosticRunning(true);
    try {
      const res = await fetch('/api/ai-diagnostic/auto-execute', { method: 'POST' });
      if (!res.ok) {
        const errResult = { error: `请求失败 (${res.status})`, actions_executed: [{ step: 'request', status: 'error' }] };
        setDiagnosticRunning(false);
        return errResult;
      }
      const d = await res.json();
      if (d.error && !d.diagnostic) {
        setAiDiagnostic(prev => ({ ...prev, latest_report: { health_score: 0, summary: `自动诊断失败: ${d.error}`, severity: 'critical' } }));
        setDiagnosticRunning(false);
        return d;
      }
      const diagData = d.diagnostic || {};
      if (diagData.health_score != null) {
        setAiDiagnostic(prev => ({ ...prev, latest_report: diagData, stats: { ...prev?.stats, total_diagnostics: (prev?.stats?.total_diagnostics || 0) + 1 } }));
      }
      setDiagnosticRunning(false);
      return d;
    } catch (err) {
      console.error('Auto execute failed:', err);
      setDiagnosticRunning(false);
      return { error: err.message, actions_executed: [{ step: 'connection', status: 'error' }] };
    }
  }, []);

  const runCriticAI = useCallback(async () => {
    try {
      const res = await fetch('/api/critic/ai-review', { method: 'POST' });
      if (res.ok) return await res.json();
    } catch (err) {
      console.error('Critic AI review failed:', err);
    }
    return null;
  }, []);

  const runDispatcherAI = useCallback(async () => {
    try {
      const res = await fetch('/api/dispatcher/ai-analysis', { method: 'POST' });
      if (res.ok) return await res.json();
    } catch (err) {
      console.error('Dispatcher AI analysis failed:', err);
    }
    return null;
  }, []);

  const analyzeMTF = useCallback(async (symbol) => {
    if (!symbol) return;
    setMtfLoading(true);
    setMtfData(null);
    try {
      const res = await fetch(`/api/mtf/${symbol}`);
      if (res.ok) setMtfData(await res.json());
    } catch (err) {
      setMtfData({ error: err.message });
    }
    setMtfLoading(false);
  }, []);

  const fetchMemoryStats = useCallback(async (days = 30) => {
    try {
      const res = await fetch(`/api/memory-bank/stats?days=${days}`);
      if (res.ok) setMemoryStats(await res.json());
    } catch (err) {
      console.error('Memory stats fetch failed:', err);
    }
  }, []);

  const runMemoryAnalysis = useCallback(async () => {
    setMemoryAnalyzing(true);
    try {
      const res = await fetch('/api/memory-bank/analyze', { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        setMemoryAnalysis(result);
        setMemoryAnalyzing(false);
        return result;
      }
    } catch (err) {
      console.error('Memory analysis failed:', err);
    }
    setMemoryAnalyzing(false);
    return null;
  }, []);

  const generateAutoRules = useCallback(async () => {
    try {
      const res = await fetch('/api/memory-bank/auto-rules', { method: 'POST' });
      if (res.ok) return await res.json();
    } catch (err) {
      console.error('Auto rules generation failed:', err);
    }
    return null;
  }, []);

  const fetchAttributionCharts = useCallback(async () => {
    try {
      const res = await fetch('/api/attribution/chart-data');
      if (res.ok) setAttributionChartData(await res.json());
    } catch (err) {
      console.error('Attribution chart data failed:', err);
    }
  }, []);

  const cruise = data?.cruise || [];
  const btcPulse = data?.btc_pulse || {};
  const logs = data?.logs || [];
  const scanProgress = data?.scan_progress || { current: 0, total: 0, scanning: false };
  const scanModeRaw = data?.scan_mode || '待机';
  const scanModeMap = { 'dynamic_hunter': '动态猎场', 'dynamic_discovery': '动态发现', 'full_scan': '全面扫描', 'quick_scan': '快速扫描', 'idle': '待机', 'scanning': '扫描中' };
  const scanMode = scanModeMap[scanModeRaw] || scanModeRaw;
  const totalScanned = data?.total_scanned || 0;
  const aiSummary = data?.ai_summary || {};
  const fngVal = btcPulse.fng || 0;
  const fngDetail = btcPulse.fng_detail || { value: 0, label: 'Neutral', change: 0, avg_7d: 0, source: 'default', timestamp: 0 };
  const totalPnL = positions.reduce((acc, pos) => acc + (parseFloat(pos.profit_amt) || 0), 0);
  const alphaSignals = cruise.filter(c => c.score >= 70);
  const highAlpha = cruise.filter(c => c.score >= 80);

  const toggleSort = useCallback((field) => {
    if (sortField === field) {
      setSortDir(prev => prev === 'desc' ? 'asc' : 'desc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  }, [sortField]);

  const filteredCruise = useMemo(() => {
    let result = cruise;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(item => item.symbol?.toLowerCase().includes(term) || item.sym?.toLowerCase().includes(term));
    }
    if (filterMode === 'ALPHA') {
      result = result.filter(item => item.score >= 80);
    } else if (filterMode === 'ML_BULL') {
      result = result.filter(item => item.ml?.label === '看涨');
    } else if (filterMode === 'BEARISH') {
      result = result.filter(item => {
        const dir = item.daily?.direction || '';
        const mlLabel = item.ml?.label || '';
        return dir.includes('下跌') || dir.includes('崩') || dir === '强势下跌' || dir === '下跌反弹' || mlLabel === '看跌';
      });
    }
    return result;
  }, [cruise, searchTerm, filterMode]);

  const sortedCruise = useMemo(() => {
    return [...filteredCruise].sort((a, b) => {
      let va, vb;
      if (sortField === 'score') {
        va = a.score; vb = b.score;
      } else if (sortField === 'ml') {
        va = a.ml?.confidence || 0; vb = b.ml?.confidence || 0;
      } else {
        va = a.score; vb = b.score;
      }
      return sortDir === 'desc' ? vb - va : va - vb;
    });
  }, [filteredCruise, sortField, sortDir]);

  const value = {
    activeTab, setActiveTab,
    dataAge, data, isLoading, isConnected,
    positions, paperPositions, paperPortfolio, paperTrades,
    mlStatus, mmStatus, backtestData,
    adaptiveWeights, criticStatus, agentMemory,
    governorStatus, feedbackStatus,
    simStatus, simRunning, setSimRunning,
    externalData, darwinLab, agiData,
    v19Data, coordinatorData, capitalSizerData,
    unifiedDecisionData, returnTargetData,
    constitutionStatus, signalQualityData, riskBudgetData, synapseData,
    pipelineData, pipelinePolling, setPipelinePolling,
    cruise, btcPulse, logs, scanMode, totalScanned, scanProgress, aiSummary,
    fngVal, fngDetail, totalPnL, alphaSignals, highAlpha,
    searchTerm, setSearchTerm,
    filterMode, setFilterMode,
    sortField, sortDir, toggleSort,
    filteredCruise, sortedCruise,
    mtfSymbol, setMtfSymbol, mtfData, mtfLoading, analyzeMTF,
    newOrder, setNewOrder,
    tradeModal, setTradeModal,
    tradePreview, setTradePreview,
    previewLoading,
    aiDiagnostic, diagnosticRunning, runDiagnostic, runAutoExecute,
    executeDiagnosticAction, getFrozenAssets,
    runCriticAI, runDispatcherAI, equityHistory,
    strategyPerf, mlFeatures, notifications, theme, toggleTheme, runSignalQualityAI, runSynapseAI,
    fetchData: fetchAll, handleAddOrder, removePosition,
    openTradeModal, confirmTrade,
    closePaperPosition, fetchPaperTrades,
    memoryStats, memoryAnalysis, memoryAnalyzing,
    fetchMemoryStats, runMemoryAnalysis, generateAutoRules,
    attributionChartData, fetchAttributionCharts,
    wallStreetMetrics, autopilotStatus, gridData, coinglassData, protectionLayers,
  };

  return <ShieldContext.Provider value={value}>{children}</ShieldContext.Provider>;
};

export const useShield = () => {
  const ctx = useContext(ShieldContext);
  if (!ctx) throw new Error('useShield must be used within ShieldProvider');
  return ctx;
};
