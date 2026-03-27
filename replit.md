# 神盾计划：不死量化 (Shield Plan: Immortal Quant)

## Overview
Shield Plan: Immortal Quant is a fund-grade cryptocurrency quantitative trading intelligence system designed for autonomous fund management. It integrates diverse alpha sources, robust portfolio-level risk management, multi-timeframe analysis, and continuous self-evolution. The system focuses on dynamic risk adjustment, performance attribution, cross-strategy collaborative learning, risk budgeting, and leveraging AI for market analysis and decision-making across a diversified portfolio of trading strategies. Its core purpose is to achieve superior risk-adjusted returns in the cryptocurrency market through intelligent automation and adaptive strategies, positioning it as a leading solution for sophisticated crypto asset management.

## User Preferences
I prefer iterative development with clear communication on major changes. I appreciate detailed explanations of complex functionalities, especially concerning the ML models and trading strategies. Do not make changes to files in the `data/` directory except for model persistence and metrics updates.

## System Architecture

### UI/UX Decisions
The system features a React-based dashboard, built with Vite and Tailwind CSS, utilizing a mobile-first responsive design with Dark/Light glassmorphism and CSS animations. It includes a CEO cockpit, CTO headquarters, signal radar, position management, global market dashboard, intelligence center, and system control. Navigation uses bottom tabs on mobile and top horizontal tabs on desktop. Data visualization is powered by Recharts, and K-line charts use TradingView Lightweight Charts. The system supports paper trading only.

### Technical Implementations
The backend uses Python with FastAPI for API services, asynchronous scanning, and ML model training, managing shared state in `server/titan_state.py`.
- **Core Trading**: Integrates TitanMath and TitanTechAnalyst for technical analysis, with TitanBrain employing a dual-strategy engine (Trend Following/Range Harvester) and ML scores.
- **Data & Workflow**: TitanCommander handles market data scanning, TitanExternalDataManager orchestrates external data with TTL caching, and TitanDB provides PostgreSQL persistence. TitanMemoryBank is a persistent AI learning system.
- **Risk & Money Management**: Features TitanMoneyManager (Kelly Criterion, ATR Risk Parity), TitanRiskMatrix (three-line defense), TitanConstitution (fund-level drawdown breakers), and TitanCapitalSizer (Monte Carlo simulations for position sizing).
- **Machine Learning**: Utilizes a dual-model architecture comprising an Alpha Model (ensemble classifier for market direction) and an MM Model (LightGBM regressor for optimal position size), both trained on Modal. An AdaptiveWeightManager dynamically adjusts ML vs. rule-based strategy weighting.
- **LLM Abstraction Layer**: `TitanLLMClient` provides a unified AI calling interface with dual-engine support (OpenAI GPT-4o-mini / Modal Qwen2.5-7B-Instruct), featuring per-module provider routing, automatic fallback, and call telemetry.
- **Unified Prompt Engineering System**: `titan_prompt_library.py` centralizes prompts for 28 AI modules, including `TITAN_COMPANY_KNOWLEDGE` and `TITAN_JSON_DISCIPLINE`.
- **System Self-Inspection AI**: `TitanSelfInspector` provides autonomous system health auditing with six AI inspectors for analysis and AI-enhanced report generation.
- **Adaptive & Learning Systems**: Includes TitanCritic for ban rules, AdaptiveWeightManager for signal weights, FeedbackEngine for ML prediction accuracy, TitanAICoordinator for strategic directives, and TitanDeepEvolution for deep learning passes with Monte Carlo stress testing.
- **AutoPilot System**: TitanAutoPilot orchestrates autonomous driving in 15-minute cycles, managing cloud training, signal quality, and pause flags.
- **Grid Trading (V23 NeuralGrid)**: Employs a Merton Jump-Diffusion Monte Carlo model for boundary prediction, fee-aware profit calculation, and regime-based dynamic capital allocation.
- **Strategy & Analysis**: TitanScoringEngine provides 6-dimension consensus scoring. Derivatives Panorama integrates CoinGlass v4 API for comprehensive derivatives visualization.

### Feature Specifications
- **ML Features**: 93-dimensional feature set including core technical, advanced, and WorldQuant 101 Alpha factors.
- **Smart Universe Selection**: Core Watchlist (80 assets) complemented by dynamic top 20 by volume, covering 7 sectors.
- **Dual Strategy Engine**: Adapts to market trends.
- **ML Defensive Scoring**: High ML confidence (>85%) penalized -8 points, >70% penalized -5 points on long signals (empirically validated as contrarian indicator). Located in `server/api.py` line ~720.
- **Hold Time Protection (P0-LAST)**: First 2 hours after position open: SL trigger grace period (paper_trader) + guard SL tightening blocked (position_guard). Emergency 5% SL still active.
- **4H Direction Filter**: SignalGate blocks trades against 4H trend direction (long blocked when 4H=down, short blocked when 4H=up). Based on EMA5/EMA12 crossover + recent 4-bar change. Data: 4H=down longs had 0% win rate (14 trades).
- **SL Floor & Ceiling Protection**: Position guard SL tightening limited to max(original_distance×60%, ATR×1.5, entry_price×3%). Paper trader low-volatility SL tightening has 1.5×ATR floor. New positions enforce MIN_SL_DISTANCE=3% (was 1.5%), MAX_SL_DISTANCE=15% (prevents high-volatility coins from creating oversized risk). Based on data: SL<1% had 3% win rate, SL 6-10% had 91% win rate.
- **MIN_TP_SL_RATIO**: 2.0:1 minimum for new positions (33% win rate breakeven).
- **Intelligent Money Management**: Kelly Criterion and ATR Risk Parity.
- **Probability Calibration**: 3-class Isotonic Regression.
- **Triple Barrier Labels**: For ML training with TP/SL simulation.
- **BTC Crash Protection**: Dual-timeframe circuit breaker.
- **Multi-Timeframe Analysis**: Weekly/Daily/4H for opportunities, 1H/15m for entry.
- **3-Line Risk Matrix**: Trade, portfolio, and system-level risk controls.
- **Continuous Self-Evolution**: Mega backtest engine for parameter mutations.
- **Performance Attribution**: Multi-dimensional return analysis.
- **Fund Manager Architecture**: Portfolio-level risk management.
- **Paper Trading**: Virtual environment with auto TP/SL.
- **Dynamic Money Management**: Position sizing adapts to performance.
- **Constitution Circuit Breakers**: Permanent drawdown breakers and daily pauses.
- **Auto Comprehensive Optimize**: Daily system optimization based on AI diagnostics.
- **Auto CTO Briefing**: Daily multi-module strategic analysis with AI-powered recommendations.
- **Weekly Full Pipeline**: Auto-execution of the complete 6-step DeepAll pipeline (Modal Alpha+MM → MegaBacktest → Darwin → MonteCarlo → Simulator).

## External Dependencies
- **Gate.io API**: Market data, historical OHLCV, and derivatives.
- **Pandas, NumPy**: Data manipulation and numerical operations.
- **Scikit-learn, LightGBM, XGBoost, CatBoost**: Machine learning libraries.
- **FastAPI, Uvicorn**: Backend API framework.
- **React, Vite, Tailwind CSS**: Frontend stack.
- **ccxt**: Cryptocurrency exchange library.
- **OpenAI**: Integrated via Replit AI Integrations, accessed through unified TitanLLMClient.
- **Modal**: Self-hosted vLLM + Qwen2.5-7B-Instruct inference service.
- **CoinGlass API v4**: Derivatives data (OI, funding rates, liquidations, long/short ratios, ETF flows).
- **CryptoPanic API**: Real-time crypto news with sentiment scoring.
- **TradingView Lightweight Charts**: For K-line chart visualization.