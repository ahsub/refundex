#!/usr/bin/env python3
"""
backtest_2007_2026.py — UIQ Regime-Gate Backtest 2007–2026
===========================================================
Backlog №34 (SWOT W7/O2/Go-Kriterium 2), 07.08.2026

ZWECK:
  Validiert die MSE-Regime-Klassifikation (VIX3M/VIX-Ratio-Schwellen 0.98/1.05
  + VIX>25 für BULL_FRAGILE) historisch gegen einen naiven Benchmark.

FRAGE:
  Hätte die Regime-Gate-Logik eine naive Baseline (Buy-and-Hold SPY) über
  rollende 12M-Fenster geschlagen?

METHODIK:
  1. Tägliche Regime-Klassifikation 2007–2026 aus VIX3M/VIX-Ratio + VIX
  2. Simulierte Strategie: Long SPY nur wenn Regime ≠ STRESS_UNSTABLE
     (= Gate-Logik: STRESS sperrt Momentum, Trendfolge, Breakout)
  3. Vergleich gegen Baseline: Buy-and-Hold SPY (immer investiert)
  4. Metriken: CAGR, Max-Drawdown, Sharpe, Win-Rate Regime-Labels

AUSFÜHRUNG:
  pip install yfinance pandas numpy matplotlib
  python backtest_2007_2026.py

OUTPUT:
  - Konsole: Metriken-Tabelle
  - backtest_results.csv: Tägliche Daten
  - backtest_equity.png: Equity-Kurven (Strategie vs. Baseline)
  - backtest_regime_heatmap.png: Regime-Verteilung über Zeit

ABLAGE: engine/backtest_2007_2026.py
"""

import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
import sys

# ── Konfiguration ─────────────────────────────────────────────

START_DATE  = '2007-01-01'   # VIX3M verfügbar ab ~2007
END_DATE    = '2026-08-06'   # letzter vollständiger Handelstag
STRESS_THR  = 0.98           # ratio_3m_spot < 0.98 → STRESS_UNSTABLE
BULL_THR    = 1.05           # ratio_3m_spot ≥ 1.05 → BULL
VIX_FRAGILE = 25.0           # VIX > 25 bei BULL → BULL_FRAGILE

# Gate-Logik: welche Regime erlauben Investition?
# (identisch zu Strategie-Gates im Aggregator)
INVESTED_REGIMES = {'BULL_QUIET', 'BULL_FRAGILE', 'POST_PANIC_REVERSION'}
# Alternative: nur BULL_QUIET (konservativster Gate)
INVESTED_REGIMES_STRICT = {'BULL_QUIET'}


# ── Hilfsfunktionen ───────────────────────────────────────────

def classify_regime(ratio_3m_spot: float, vix: float) -> str:
    """
    Identisch zur Regime-Klassifikation in market_aggregator.py main().
    ratio_3m_spot = VIX3M/VIX (>1 = Contango = gesund)
    """
    if ratio_3m_spot is None or np.isnan(ratio_3m_spot):
        return 'UNKNOWN'
    if ratio_3m_spot < STRESS_THR:
        return 'STRESS_UNSTABLE'
    elif ratio_3m_spot < BULL_THR:
        return 'POST_PANIC_REVERSION'
    else:
        if vix is not None and not np.isnan(vix) and vix > VIX_FRAGILE:
            return 'BULL_FRAGILE'
        return 'BULL_QUIET'


def calc_metrics(returns: pd.Series, name: str) -> dict:
    """Berechnet Kernmetriken für eine Return-Serie."""
    if returns.empty or returns.isna().all():
        return {'name': name}

    total_return = (1 + returns).prod() - 1
    n_years = len(returns) / 252
    cagr    = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0

    # Max Drawdown
    cum     = (1 + returns).cumprod()
    rolling_max = cum.cummax()
    drawdown    = (cum - rolling_max) / rolling_max
    max_dd  = drawdown.min()

    # Sharpe (annualisiert, rf=0)
    sharpe  = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

    # Tage investiert
    n_invested = (returns != 0).sum()
    pct_invested = n_invested / len(returns) * 100

    # Win-Rate (positive Tage)
    win_rate = (returns > 0).sum() / len(returns[returns != 0]) * 100 if (returns != 0).sum() > 0 else 0

    return {
        'name':           name,
        'total_return':   f'{total_return*100:.1f}%',
        'cagr':           f'{cagr*100:.2f}%',
        'max_drawdown':   f'{max_dd*100:.1f}%',
        'sharpe':         f'{sharpe:.2f}',
        'pct_invested':   f'{pct_invested:.1f}%',
        'win_rate_days':  f'{win_rate:.1f}%',
        'n_years':        f'{n_years:.1f}',
    }


def rolling_cagr(cum_returns: pd.Series, window_days: int = 252) -> pd.Series:
    """Rollierender CAGR über window_days."""
    return cum_returns.pct_change(window_days).apply(
        lambda x: (1 + x) ** (252 / window_days) - 1 if not np.isnan(x) else np.nan
    )


# ── Hauptprogramm ─────────────────────────────────────────────

def main():
    print("UIQ Regime-Gate Backtest 2007–2026")
    print("=" * 50)

    # ── 1. Daten laden ──────────────────────────────────────────
    print(f"\n📥 Lade Daten ({START_DATE} → {END_DATE})...")

    tickers = {
        '^VIX':   'VIX',
        '^VIX3M': 'VIX3M',
        'SPY':    'SPY',
    }

    raw = {}
    for ticker, name in tickers.items():
        print(f"   Lade {ticker}...", end=' ')
        try:
            df = yf.download(ticker, start=START_DATE, end=END_DATE,
                            auto_adjust=True, progress=False)
            raw[name] = df['Close']
            print(f"✅ {len(df)} Tage")
        except Exception as e:
            print(f"❌ {e}")
            sys.exit(1)

    # ── 2. Gemeinsamen Index erstellen ──────────────────────────
    data = pd.DataFrame(raw).dropna()
    print(f"\n✅ Gemeinsame Handelstage: {len(data)} ({data.index[0].date()} → {data.index[-1].date()})")

    # ── 3. Regime-Klassifikation ────────────────────────────────
    data['ratio_3m_spot'] = data['VIX3M'] / data['VIX']
    data['regime'] = data.apply(
        lambda row: classify_regime(row['ratio_3m_spot'], row['VIX']),
        axis=1
    )

    # Regime-Verteilung
    print("\n📊 Regime-Verteilung (2007–2026):")
    regime_counts = data['regime'].value_counts()
    for regime, count in regime_counts.items():
        pct = count / len(data) * 100
        bar = '█' * int(pct / 2)
        print(f"   {regime:<25} {count:5d} Tage ({pct:5.1f}%) {bar}")

    # ── 4. SPY Returns ──────────────────────────────────────────
    data['spy_ret'] = data['SPY'].pct_change().fillna(0)

    # ── 5. Strategien simulieren ─────────────────────────────────
    # Strategie A: investiert wenn nicht STRESS_UNSTABLE (Standard-Gate)
    data['in_market_A'] = data['regime'].isin(INVESTED_REGIMES)
    data['strat_A_ret'] = data['spy_ret'] * data['in_market_A'].astype(int)

    # Strategie B: investiert nur bei BULL_QUIET (konservativ)
    data['in_market_B'] = data['regime'] == 'BULL_QUIET'
    data['strat_B_ret'] = data['spy_ret'] * data['in_market_B'].astype(int)

    # Baseline: Buy-and-Hold SPY
    data['baseline_ret'] = data['spy_ret']

    # ── 6. Metriken berechnen ────────────────────────────────────
    print("\n📈 Performance-Vergleich:")
    print("-" * 75)

    metrics = [
        calc_metrics(data['baseline_ret'], 'Buy-and-Hold SPY (Baseline)'),
        calc_metrics(data['strat_A_ret'],  'Regime-Gate A (kein STRESS)'),
        calc_metrics(data['strat_B_ret'],  'Regime-Gate B (nur BULL_QUIET)'),
    ]

    # Tabelle ausgeben
    cols = ['name', 'total_return', 'cagr', 'max_drawdown', 'sharpe', 'pct_invested']
    headers = ['Strategie', 'Gesamtrendite', 'CAGR', 'Max DD', 'Sharpe', '% investiert']
    widths  = [32, 14, 8, 10, 8, 12]

    header_line = '  '.join(h.ljust(w) for h, w in zip(headers, widths))
    print(f"  {header_line}")
    print("  " + "-" * (sum(widths) + len(widths) * 2))
    for m in metrics:
        row = '  '.join(str(m.get(c, '—')).ljust(w) for c, w in zip(cols, widths))
        print(f"  {row}")

    # ── 7. Regime-spezifische SPY-Returns ───────────────────────
    print("\n📊 SPY-Performance je Regime (durchschn. Tagesrendite × 252):")
    print("-" * 55)
    for regime in ['BULL_QUIET', 'BULL_FRAGILE', 'POST_PANIC_REVERSION', 'STRESS_UNSTABLE']:
        mask = data['regime'] == regime
        if mask.sum() == 0:
            continue
        ret = data.loc[mask, 'spy_ret']
        ann_ret = ret.mean() * 252 * 100
        ann_vol = ret.std() * np.sqrt(252) * 100
        sharpe  = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0
        print(f"  {regime:<25} Ann.Ret: {ann_ret:+6.1f}%  Vol: {ann_vol:5.1f}%  Sharpe: {sharpe:+5.2f}  n={mask.sum()}")

    # ── 8. Krisenperioden-Analyse ────────────────────────────────
    print("\n🔍 Krisenperioden — war Gate aktiv?")
    print("-" * 55)
    crises = [
        ('Finanzkrise',       '2008-09-01', '2009-03-31'),
        ('Euro-Krise',        '2011-07-01', '2011-10-31'),
        ('Vol-Spike 2015',    '2015-08-01', '2015-09-30'),
        ('COVID-Crash',       '2020-02-01', '2020-04-30'),
        ('Zinsschock 2022',   '2022-01-01', '2022-12-31'),
    ]
    for name, start, end in crises:
        mask = (data.index >= start) & (data.index <= end)
        if mask.sum() == 0:
            continue
        period = data.loc[mask]
        stress_pct = (period['regime'] == 'STRESS_UNSTABLE').mean() * 100
        spy_ret_period = (1 + period['spy_ret']).prod() - 1
        gate_ret_period = (1 + period['strat_A_ret']).prod() - 1
        print(f"  {name:<20} STRESS: {stress_pct:5.1f}%  SPY: {spy_ret_period*100:+6.1f}%  Gate-A: {gate_ret_period*100:+6.1f}%")

    # ── 9. Go/No-Go Bewertung ────────────────────────────────────
    baseline_sharpe = float(calc_metrics(data['baseline_ret'], 'X')['sharpe'])
    gate_a_sharpe   = float(calc_metrics(data['strat_A_ret'],  'X')['sharpe'])
    beat_baseline   = gate_a_sharpe > baseline_sharpe

    print(f"\n{'='*50}")
    print(f"✅ Go/No-Go (SWOT Go-Kriterium 2):")
    print(f"   Baseline Sharpe:  {baseline_sharpe:.2f}")
    print(f"   Gate-A Sharpe:    {gate_a_sharpe:.2f}")
    print(f"   Ergebnis: {'✅ Gate schlägt Baseline' if beat_baseline else '❌ Gate schlägt Baseline NICHT'}")
    print(f"   → {'Kommerzialisierung Kriterium 2: ERFÜLLT' if beat_baseline else 'Schwellenwerte überprüfen'}")

    # ── 10. CSV-Export ───────────────────────────────────────────
    out_cols = ['VIX', 'VIX3M', 'ratio_3m_spot', 'regime', 'SPY',
                'spy_ret', 'strat_A_ret', 'strat_B_ret', 'in_market_A']
    data[out_cols].to_csv('engine/backtest_results.csv')
    print(f"\n💾 Daten gespeichert: engine/backtest_results.csv")

    # ── 11. Plot (optional) ──────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        fig, axes = plt.subplots(3, 1, figsize=(14, 12))
        fig.suptitle('UIQ Regime-Gate Backtest 2007–2026', fontsize=14, fontweight='bold')

        # Panel 1: Equity-Kurven
        ax1 = axes[0]
        cum_base   = (1 + data['baseline_ret']).cumprod()
        cum_gate_a = (1 + data['strat_A_ret']).cumprod()
        cum_gate_b = (1 + data['strat_B_ret']).cumprod()
        ax1.plot(cum_base.index,   cum_base,   label='Buy-and-Hold SPY', color='#94a3b8', linewidth=1.5)
        ax1.plot(cum_gate_a.index, cum_gate_a, label='Gate-A (kein STRESS)', color='#3b82f6', linewidth=2)
        ax1.plot(cum_gate_b.index, cum_gate_b, label='Gate-B (nur BULL_QUIET)', color='#22c55e', linewidth=1.5, linestyle='--')
        ax1.set_ylabel('Kumulierte Rendite (1 = Start)')
        ax1.set_title('Equity-Kurven')
        ax1.legend(fontsize=9)
        ax1.grid(alpha=0.3)

        # Panel 2: Regime-Zeitreihe
        ax2 = axes[1]
        regime_colors = {
            'BULL_QUIET': '#22c55e',
            'BULL_FRAGILE': '#f59e0b',
            'POST_PANIC_REVERSION': '#3b82f6',
            'STRESS_UNSTABLE': '#ef4444',
            'UNKNOWN': '#94a3b8',
        }
        regime_num = data['regime'].map({
            'BULL_QUIET': 3, 'BULL_FRAGILE': 2,
            'POST_PANIC_REVERSION': 1, 'STRESS_UNSTABLE': 0, 'UNKNOWN': 0
        })
        for regime, color in regime_colors.items():
            mask = data['regime'] == regime
            ax2.fill_between(data.index, 0, 1,
                           where=mask, alpha=0.7, color=color,
                           transform=ax2.get_xaxis_transform(), label=regime)
        ax2.plot(data.index, data['ratio_3m_spot'], color='white', linewidth=0.5, alpha=0.5)
        ax2.axhline(y=0.98, color='red', linewidth=0.5, linestyle='--', alpha=0.5)
        ax2.axhline(y=1.05, color='green', linewidth=0.5, linestyle='--', alpha=0.5)
        ax2.set_ylabel('VIX3M/VIX Ratio')
        ax2.set_title('Regime-Klassifikation')
        ax2.legend(fontsize=7, loc='upper right', ncol=2)
        ax2.grid(alpha=0.2)

        # Panel 3: Rollierender 1J-CAGR Vergleich
        ax3 = axes[2]
        roll_base   = rolling_cagr(cum_base)
        roll_gate_a = rolling_cagr(cum_gate_a)
        ax3.plot(roll_base.index,   roll_base   * 100, label='Baseline', color='#94a3b8', linewidth=1)
        ax3.plot(roll_gate_a.index, roll_gate_a * 100, label='Gate-A', color='#3b82f6', linewidth=1.5)
        ax3.axhline(y=0, color='white', linewidth=0.5, alpha=0.5)
        ax3.fill_between(roll_gate_a.index,
                        roll_gate_a * 100, roll_base * 100,
                        where=roll_gate_a >= roll_base,
                        alpha=0.2, color='#22c55e', label='Gate-A besser')
        ax3.fill_between(roll_gate_a.index,
                        roll_gate_a * 100, roll_base * 100,
                        where=roll_gate_a < roll_base,
                        alpha=0.2, color='#ef4444', label='Baseline besser')
        ax3.set_ylabel('Rollierender 1J-CAGR (%)')
        ax3.set_title('Rollierender 1J-CAGR Vergleich')
        ax3.legend(fontsize=9)
        ax3.grid(alpha=0.3)

        plt.tight_layout()
        plt.savefig('engine/backtest_equity.png', dpi=150, bbox_inches='tight',
                   facecolor='#0d1117')
        print("📊 Chart gespeichert: engine/backtest_equity.png")
        plt.close()

    except ImportError:
        print("⚠️  matplotlib nicht installiert — kein Chart (pip install matplotlib)")
    except Exception as e:
        print(f"⚠️  Chart-Fehler: {e}")

    print("\n✅ Backtest abgeschlossen.")
    return data


if __name__ == '__main__':
    data = main()
