from __future__ import annotations

import html
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HTML_RETENTION_DAYS = 365
WINDOWS = (30, 90, 180)


def parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def archive_path(archive_dir, report_date, suffix):
    return archive_dir / f"{report_date:%Y}" / f"{report_date:%m}" / f"{report_date:%Y-%m-%d}{suffix}"


def migrate_legacy_archive(archive_dir):
    archive_dir.mkdir(parents=True, exist_ok=True)
    for path in list(archive_dir.glob("*.json")) + list(archive_dir.glob("*.html")):
        report_date = parse_date(path.stem)
        if report_date is None:
            continue
        destination = archive_path(archive_dir, report_date, path.suffix)
        destination.parent.mkdir(parents=True, exist_ok=True)
        path.replace(destination)


def load_daily_reports(archive_dir):
    migrate_legacy_archive(archive_dir)
    reports = []
    for path in archive_dir.rglob("*.json"):
        report_date = parse_date(path.stem)
        if report_date is None:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            score = float(data["risk_score"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        data = dict(data)
        data["_report_date"] = report_date.isoformat()
        data["_risk_score"] = score
        reports.append(data)
    return sorted(reports, key=lambda item: item["_report_date"])


def calculate_trend(reports, end_date, days):
    cutoff = end_date - timedelta(days=days - 1)
    selected = [item for item in reports if cutoff <= parse_date(item["_report_date"]) <= end_date]
    selected.sort(key=lambda item: item["_report_date"])
    scores = [item["_risk_score"] for item in selected]
    if not scores:
        return {"days": days, "available_count": 0, "avg": None, "max": None, "min": None, "change": None}
    return {"days": days, "available_count": len(scores), "avg": round(sum(scores) / len(scores), 2), "max": round(max(scores), 2), "min": round(min(scores), 2), "change": round(scores[-1] - scores[0], 2)}


def calculate_level_streak(reports, current_level):
    expected = str(current_level or "UNKNOWN").upper()
    streak = 0
    for item in sorted(reports, key=lambda x: x["_report_date"], reverse=True):
        if str(item.get("risk_level", "UNKNOWN")).upper() != expected:
            break
        streak += 1
    return streak


def monthly_summary(reports, month):
    selected = sorted([x for x in reports if x["_report_date"].startswith(month)], key=lambda x: x["_report_date"])
    scores = [x["_risk_score"] for x in selected]
    levels = Counter(str(x.get("risk_level", "UNKNOWN")).upper() for x in selected)
    return {"month": month, "available_count": len(selected), "avg_risk_score": round(sum(scores)/len(scores), 2) if scores else None, "max_risk_score": round(max(scores), 2) if scores else None, "min_risk_score": round(min(scores), 2) if scores else None, "change": round(scores[-1]-scores[0], 2) if scores else None, "first_date": selected[0]["_report_date"] if selected else None, "last_date": selected[-1]["_report_date"] if selected else None, "risk_level_days": dict(sorted(levels.items()))}


def monthly_html(summary):
    def v(key):
        return "확인 제한" if summary.get(key) is None else str(summary[key])
    levels = " · ".join(f"{html.escape(k)} {n}일" for k, n in summary.get("risk_level_days", {}).items()) or "데이터 없음"
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI 투자리스크 월간 요약 · {html.escape(summary["month"])}</title><style>body{{margin:0;background:#090b0e;color:#eef2f5;font-family:system-ui,sans-serif}}main{{max-width:520px;margin:auto;padding:24px 16px}}.card{{margin-top:16px;padding:16px;border:1px solid #2a313a;border-radius:18px;background:#15191f}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.metric{{padding:13px;background:#11151a;border:1px solid #2a313a;border-radius:14px}}.k{{color:#97a2ad;font-size:11px}}.v{{margin-top:8px;font-size:21px;font-weight:800}}a{{color:#9db8ee}}</style></head><body><main><div class="k">AI CREDIT RISK MONITOR · MONTHLY SUMMARY</div><h1>{html.escape(summary["month"])} 월간 요약</h1><div class="k">{summary.get("first_date") or ""} ~ {summary.get("last_date") or ""}</div><section class="card"><div class="grid"><div class="metric"><div class="k">평균</div><div class="v">{v("avg_risk_score")}</div></div><div class="metric"><div class="k">최고</div><div class="v">{v("max_risk_score")}</div></div><div class="metric"><div class="k">최저</div><div class="v">{v("min_risk_score")}</div></div><div class="metric"><div class="k">변화폭</div><div class="v">{v("change")}</div></div></div></section><section class="card"><div class="k">위험단계 누적일수</div><p>{levels}</p></section><section class="card"><a href="../../latest.html">최신 리포트로 돌아가기</a></section></main></body></html>'''


def write_monthly_summaries(summary_dir, reports):
    summary_dir.mkdir(parents=True, exist_ok=True)
    links = []
    for month in sorted({x["_report_date"][:7] for x in reports}):
        summary = monthly_summary(reports, month)
        (summary_dir / f"{month}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (summary_dir / f"{month}.html").write_text(monthly_html(summary), encoding="utf-8")
        links.append({"month": month, "json": f"./summary/monthly/{month}.json", "html": f"./summary/monthly/{month}.html"})
    return links


def build_history_payload(archive_dir, summary_dir, current_date, current_level):
    reports = load_daily_reports(archive_dir)
    return {"trend": {f"days_{days}": calculate_trend(reports, current_date, days) for days in WINDOWS}, "current_level_streak_days": calculate_level_streak(reports, current_level), "history_count": len(reports), "monthly_summary": {"current_month": current_date.strftime("%Y-%m"), "json": f"./summary/monthly/{current_date:%Y-%m}.json", "html": f"./summary/monthly/{current_date:%Y-%m}.html", "available": sorted(path.stem for path in summary_dir.glob("*.json"))}}


def cleanup_old_html(archive_dir, today):
    cutoff = today - timedelta(days=HTML_RETENTION_DAYS - 1)
    removed = []
    for path in archive_dir.rglob("*.html"):
        report_date = parse_date(path.stem)
        if report_date and report_date < cutoff:
            removed.append(str(path))
            path.unlink()
    return removed
