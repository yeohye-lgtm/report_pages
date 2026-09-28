"""Read-only historical inputs; version-aware counts; never delete daily JSON."""
from __future__ import annotations
import hashlib
import html
import json
import warnings
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HTML_RETENTION_DAYS = 365
WINDOWS = (30,90,180)


def dump_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(content, encoding='utf-8')
    temporary.replace(path)


def archive_path(root, day, suffix):
    return Path(root)/f'{day:%Y}'/f'{day:%m}'/(day.isoformat()+suffix)


def load_daily_reports(root):
    rows = {}
    for path in sorted(Path(root).rglob('*.json')):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data,dict) or data.get('date') != day.isoformat():
                raise ValueError('date mismatch')
        except (OSError,ValueError) as exc:
            warnings.warn(f'Invalid archive {path.name}: {type(exc).__name__}')
            continue
        if day in rows and rows[day] != data:
            raise ValueError('Conflicting duplicate daily JSON: '+day.isoformat())
        rows[day] = data
    return [rows[day] for day in sorted(rows)]


def comparable(report, version='1.0'):
    return (report.get('rules_version')==version and
            report.get('assessment_state') in ('assessed','provisional') and
            report.get('risk_level') in ('GREEN','YELLOW','ORANGE','RED'))


def history_payload(records, current):
    day = date.fromisoformat(current['date'])
    rows = {r['date']:r for r in records if r['date'] <= current['date']}
    # A layout-only rerender must not substitute for the original dated observation.
    if current.get('assessment_state') != 'not_revalidated':
        rows[current['date']] = current
    selected = [r for r in rows.values() if comparable(r)]
    trend = {'same_rules_count':len(selected)}
    for n in WINDOWS:
        cutoff = (day-timedelta(days=n-1)).isoformat()
        window = [r for r in selected if cutoff <= r['date'] <= current['date']]
        trend['days_'+str(n)] = dict(days=n, available_count=len(window),
            level_days=dict(Counter(r['risk_level'] for r in window)),
            first_date=min((r['date'] for r in window),default=None),
            last_date=max((r['date'] for r in window),default=None))
    streak=0; cursor=day
    if comparable(current):
        while True:
            r=rows.get(cursor.isoformat())
            if not r or not comparable(r) or r['risk_level']!=current['risk_level']: break
            streak+=1; cursor-=timedelta(days=1)
    return dict(trend=trend, current_level_streak_days=streak, history_count=len(rows))


def monthly_summary(records, month, as_of):
    rows=[r for r in records if r['date'].startswith(month) and r['date']<=as_of.isoformat()]
    groups={}
    for r in rows:
        version=r.get('rules_version','legacy')
        group=groups.setdefault(version,dict(report_count=0,eligible_count=0,level_days={},limited_count=0))
        group['report_count']+=1
        eligible=comparable(r,version) if version!='legacy' else False
        if eligible:
            group['eligible_count']+=1
            level=r['risk_level'];group['level_days'][level]=group['level_days'].get(level,0)+1
        else:group['limited_count']+=1
    counts=Counter(a['id'] for r in rows if comparable(r) for a in r.get('axes',[]) if a.get('stress'))
    return dict(schema_version=2,month=month,as_of=as_of.isoformat(),
        period_state='in_progress' if month==as_of.strftime('%Y-%m') else 'closed_calendar',
        report_count=len(rows),first_date=min((r['date'] for r in rows),default=None),
        last_date=max((r['date'] for r in rows),default=None),by_rules_version=groups,
        stress_axis_report_counts=dict(counts),
        note='보고서 기록 수입니다. 독립 시장 관측 수가 아닙니다. 기존 소수점 점수는 평균내지 않습니다.')


def monthly_html(summary):
    e=lambda x:html.escape(str(x),quote=True)
    blocks=''
    for version,g in summary['by_rules_version'].items():
        states=' · '.join(f'{e(k)} {v}일' for k,v in g['level_days'].items()) or '새 기준 비교에서 제외'
        blocks+=f'<section><h2>기준 {e(version)}</h2><p>전체 {g["report_count"]}개 · 비교 가능 {g["eligible_count"]}개</p><p>{states}</p><small>확인 제한·이전 기준 {g["limited_count"]}개</small></section>'
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI 월간 요약 '+e(summary['month'])+'</title><style>body{margin:0;background:#0b0e12;color:#edf1f6;font:16px/1.6 system-ui,sans-serif}main{max-width:520px;margin:auto;padding:24px 18px}section{background:#12171e;border:1px solid #27313d;border-radius:18px;padding:18px;margin:15px 0}h1{font-size:24px}h2{font-size:18px}small{color:#a2adbc}a{color:#aacbff}</style><main><h1>'+e(summary['month'])+' 월간 기록</h1><p>'+('월중 집계' if summary['period_state']=='in_progress' else '종료된 월 · 누락 여부 별도 확인')+'</p>'+blocks+'<section><p>'+e(summary['note'])+'</p><small>자료 범위 '+e(summary['first_date'])+' ~ '+e(summary['last_date'])+'</small></section><a href="../../latest.html">오늘 상황판으로 →</a></main></html>'


def write_monthly_summaries(root, records, as_of):
    months=sorted({r['date'][:7] for r in records if r['date']<=as_of.isoformat()})
    for month in months:
        data=monthly_summary(records,month,as_of)
        atomic_write(Path(root)/(month+'.json'),dump_json(data))
        atomic_write(Path(root)/(month+'.html'),monthly_html(data))
    return months


def preserve_revision(path):
    """Retain old bytes when a same-day report is explicitly regenerated."""
    path=Path(path)
    if path.exists():
        digest=hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        dest=path.parent/'revisions'/(path.stem+'-'+digest+path.suffix)
        if not dest.exists():
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(path.read_bytes())


def cleanup_old_html(root, today):
    cutoff=today-timedelta(days=HTML_RETENTION_DAYS-1)
    removed=[]
    for path in Path(root).rglob('*.html'):
        try:day=date.fromisoformat(path.name[:10])
        except ValueError:continue
        if day<cutoff:
            path.unlink();removed.append(str(path))
    return removed
