# Covenant Hedge Fund — Compliance Rules (enforced in code)

These 25 rules are enforced by `covenant_risk.check_compliance` and related
modules. They are **not** suggestions to an LLM.

| # | Rule | Enforcement |
|---|------|-------------|
| 1 | Max single position 25% of equity | `MAX_POSITION_PCT` + vol scaling |
| 2 | Max gross exposure 100% (no leverage) | cash accounting in paper book |
| 3 | Min cash reserve 5% | buy size clipped |
| 4 | Max crypto sleeve 40% | asset_class check |
| 5 | Max 8 names per strategy | open-position gate |
| 6 | Min diversification (≥2 when possible) | asset picker |
| 7 | Correlation cap — halve size if crowded beta | `spy_corr_63` |
| 8 | Volatility-scaled position sizing | `vol_scaled_weight` |
| 9 | Minimum 20 daily bars of history | feature gate |
| 10 | Minimum trade notional $25 | size floor |
| 11 | Max single fill 20% of equity | fill cap |
| 12 | Buy confidence floor 35 | synthesis gate |
| 13 | Sell confidence floor 30 | synthesis gate |
| 14 | Long-only (no shorting) | SELL reduces longs only |
| 15 | User TP/SL honored over signals | `evaluate_strategy` |
| 16 | Horizon-matched lookback for asset pick | `covenant_picker` |
| 17 | Shared market snapshot per symbol | `hf_market_snapshots` |
| 18 | Strategy-isolated positions | `(portfolio, strategy, symbol)` |
| 19 | Auditable decision graph | analyst signals on `hf_decisions` |
| 20 | Deterministic synthesis | confidence-weighted scoring |
| 21 | Paper trading only | no live brokerage |
| 22 | Fee model 1/10 on reported PnL | `calculate_fees` |
| 23 | SPY benchmark on backtests | metrics module |
| 24 | Sharpe / Sortino / max drawdown | metrics module |
| 25 | LLM optional — never required for trades | quant-only path |

Optional LLM augmentation (macro commentary) must not change trade actions.
