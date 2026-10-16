"""Closed-position win rates and funded account comparisons (separate from forecasts)."""
from __future__ import annotations

from .controls import identity, MODELS


def pnl_stats(pnls):
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    return {"trades": len(pnls), "wins": len(wins), "losses": len(losses),
            "win_rate": len(wins) / len(pnls) if pnls else None,
            "realized_pnl": sum(pnls),
            "avg_win": sum(wins) / len(wins) if wins else None,
            "avg_loss": sum(losses) / len(losses) if losses else None,
            "profit_factor": sum(wins) / -sum(losses) if losses else None,
            "small_sample": len(pnls) < 30}


def comparison(conn, board, short, curves):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='trade_cycles'").fetchone()
    models = []
    baselines = {r["key"]: r for r in board if r["key"] in ("hold", "position")}
    baselines.update({r["key"]: dict(r, name=r["label"]) for r in short if r["key"] == "short"})
    for model in MODELS:
        rows = []
        all_pnl = []
        for account in board:
            owner, base = identity(account["key"])
            if owner != model:
                continue
            pnls = [r[0] for r in conn.execute("SELECT pnl FROM trade_cycles WHERE strategy=? AND closed_at IS NOT NULL",
                                              (account["key"],))] if exists else []
            all_pnl += pnls
            rows.append({**account, **pnl_stats(pnls), "strategy": base,
                         "win_rate_applicable": base != "dca_smart_ai"})
        for account in short:
            owner, base = identity(account["key"])
            if owner != model or account.get("budget") is None:
                continue
            pnls = [r[0] for r in conn.execute("SELECT realized_cny FROM paper_trades WHERE strategy=? AND status='closed'",
                                              (account["key"],))]
            all_pnl += pnls
            rows.append({**account, **pnl_stats(pnls), "strategy": base, "name": account["label"],
                         "win_rate_applicable": True})
        budget = sum(r.get("budget", 0) for r in rows)
        complete = bool(rows) and all(r.get("value") is not None for r in rows)
        value = sum(r["value"] for r in rows) if complete else None
        for row in rows:
            base = baselines.get("position" if row["strategy"] == "position_ai" else "short")
            row["baseline_return"] = base.get("return") if base else None
            row["excess_return"] = (row["return"] - row["baseline_return"]
                                    if row.get("return") is not None and row["baseline_return"] is not None else None)
        baseline_return = (sum(r["budget"] * r["baseline_return"] for r in rows) / budget
                           if budget and rows and all(r["baseline_return"] is not None for r in rows) else None)
        # Combine account returns with capital weights, carrying each account's
        # last mark forward. Unstarted accounts contribute their original cash.
        owned = [s for s in curves["series"] if identity(s["key"])[0] == model]
        weights = {r["key"]: r.get("budget", 0) for r in rows}
        events = sorted((ts, s["key"], ret) for s in owned for ts, ret in s["points"])
        marks, points, peak, mdd = {}, [], 1.0, 0.0
        for ts, key, ret in events:
            marks[key] = ret
            total = sum(weights.get(k, 0) * v for k, v in marks.items()) / budget if budget else 0
            if points and points[-1][0] == ts:
                points[-1][1] = total
            else:
                points.append([ts, total])
        for _, ret in points + ([["now", value / budget - 1]] if value is not None and budget else []):
            peak = max(peak, 1 + ret)
            mdd = max(mdd, 1 - (1 + ret) / peak)
        starts = [r.get("started_at") for r in rows if r.get("started_at")]
        models.append({"key": model, "name": model.title(), "budget": budget, "value": value,
                       "return": value / budget - 1 if value is not None and budget else None,
                       "baseline_return": baseline_return,
                       "excess_return": value / budget - 1 - baseline_return if value is not None and budget and baseline_return is not None else None,
                       "max_drawdown": mdd, "started_at": min(starts) if starts else None,
                       "accounts": rows, "points": points, **pnl_stats(all_pnl)})
    return {"models": models, "baselines": list(baselines.values()), "version": "independent-v1",
            "rules": "仅比较中长线与短线，胜率按扣费后完整平仓周期计，分批卖出合并。旧账户不参与。"}
