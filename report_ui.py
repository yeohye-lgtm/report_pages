"""Data-only reports rendered into the pinned, user-approved mobile shell."""
from __future__ import annotations
import copy
import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
UI_VERSION = '2.0.0'
RULES_VERSION = '1.0'
AXES = {'funding':'자금조달','demand':'투자수요','borrower':'사업자 안정성','gpu':'GPU 경제성','contagion':'손실 전염'}
LEVELS = {'GREEN':('안정','green'),'YELLOW':('주의','yellow'),'ORANGE':('경계','orange'),'RED':('위기','red'),'UNKNOWN':('판정 보류','gray')}
CHANGE = {'worse':'↑ 악화','better':'↓ 완화','unchanged':'→ 유지','unavailable':'— 비교 불가'}


def text(value):
    s = '' if value is None else str(value)
    s = re.sub(r'\[([^\]]+)\]\(https?://[^\s)]+\)', r'\1', s)
    return re.sub(r'\s+', ' ', s).strip()


def esc(value):
    return html.escape(text(value), quote=True)


def short(value, limit=44):
    s = text(value)
    return s if len(s) <= limit else s[:limit-1].rstrip() + '…'


def safe_url(value):
    try:
        p = urlsplit(str(value or ''))
        return str(value) if p.scheme == 'https' and p.hostname and not p.username and not p.password else ''
    except ValueError:
        return ''


def legacy_view(raw):
    """Migrate presentation only; do not claim to have revalidated historical facts."""
    d = copy.deepcopy(raw)
    level = str(raw.get('risk_level','UNKNOWN')).replace('+','').upper()
    d.update(schema_version=2, ui_version=UI_VERSION, rules_version='legacy',
             assessment_state='not_revalidated', legacy_risk_level=raw.get('risk_level'),
             risk_level=level if level in LEVELS else 'UNKNOWN', risk_score=None,
             watch='', change='unavailable')
    d['headline'] = '기존 보고서를 승인 양식으로 전환했습니다.'
    d['reason'] = '표시된 등급은 원본 참고값 · 시장 재평가 아님'
    d['summary'] = text(raw.get('summary'))
    d['changes'] = []
    d['changes_note'] = '양식 교체 · 시장 변화 비교 안 함'
    d['next_check'] = '다음 일일 실행의 원문 재검증 결과'
    d['assessment_reasons'] = [text(raw.get('summary')) or '원본 상세 설명 없음']
    d['counter_evidence'] = ['원본 기록을 이번 배포에서 재검증하지 않았습니다.']
    d['data_gaps'] = ['기존 기록은 새 판정체계의 관측 표본에 포함하지 않습니다.']
    d['investor_view'] = '이번 배포는 화면 교체입니다. 새 시장판정이나 매매 신호로 해석하지 마세요.'
    d['sources'] = [dict(s, id='S'+str(i)) for i,s in enumerate(raw.get('sources',[]),1) if safe_url(s.get('url'))]
    d['axes'] = []
    match = {'funding':['10y','30y','국채','cds','스프레드','금융'], 'demand':['capex','수요'],
             'borrower':['jupiter','neocloud','차환'], 'gpu':['gpu'], 'contagion':['보증','rvg','backstop']}
    for key in AXES:
        rows = [m for m in raw.get('metrics',[]) if any(w in str(m.get('label','')).lower() for w in match[key])]
        d['axes'].append(dict(id=key, status='UNKNOWN', coverage='partial' if rows else 'limited',
            meaning='원본 기록 참고 · 재검증 전' if rows else '확인 가능한 원본 지표 부족',
            change='unavailable', explanation='저장된 원본 기록입니다. 현재 판정에 반영하지 않습니다.',
            stress=False, cashflow_impact=False, event_ids=[], items=[dict(
                label=m.get('label',''), value=m.get('value','확인 제한'), note=m.get('note',''),
                observed_at=None, comparison='원본 참고', source_ids=[], included=False) for m in rows]))
    return d


def validate(d):
    if not isinstance(d,dict):
        raise ValueError('Report must be an object')
    day = date.fromisoformat(d['date'])
    for key, limit in [('headline',44),('reason',64),('next_check',60),('investor_view',320)]:
        if not isinstance(d.get(key),str) or not 0 < len(d[key]) <= limit:
            raise ValueError('Invalid text length: '+key)
    if len(d.get('axes',[])) != 5 or {a.get('id') for a in d['axes']} != set(AXES):
        raise ValueError('Five distinct axes required')
    if d.get('change') not in CHANGE:
        raise ValueError('Invalid overall change')
    for key in ('assessment_reasons','counter_evidence','data_gaps','changes'):
        if not isinstance(d.get(key),list) or not all(isinstance(x,str) for x in d[key]):
            raise ValueError('String list required: '+key)
    if len(d['changes']) > 3:
        raise ValueError('At most three changes')
    ids = set()
    for s in d.get('sources',[]):
        if not re.fullmatch(r'S\d+',str(s.get('id',''))) or s['id'] in ids or not safe_url(s.get('url')):
            raise ValueError('Invalid source')
        if s.get('published_at') and date.fromisoformat(s['published_at']) > day:
            raise ValueError('Future publication')
        ids.add(s['id'])
    for a in d['axes']:
        if a.get('status') not in LEVELS or a.get('coverage') not in ('sufficient','partial','limited') or a.get('change') not in CHANGE:
            raise ValueError('Invalid axis state')
        if not isinstance(a.get('meaning'),str) or not 0 < len(a['meaning']) <= 32:
            raise ValueError('Axis meaning too long')
        if not isinstance(a.get('explanation'),str):
            raise ValueError('Axis explanation required')
        if any(type(a.get(k)) is not bool for k in ('stress','cashflow_impact')):
            raise ValueError('Boolean flags required')
        if not isinstance(a.get('event_ids'),list) or not all(isinstance(e,str) and e for e in a['event_ids']):
            raise ValueError('Invalid event IDs')
        if not isinstance(a.get('items'),list):
            raise ValueError('items must be a list')
        evidence = False
        for m in a['items']:
            refs = m.get('source_ids',[])
            if not isinstance(refs,list) or any(x not in ids for x in refs):
                raise ValueError('Unresolved citation')
            if type(m.get('included')) is not bool:
                raise ValueError('included must be boolean')
            if m.get('observed_at') and date.fromisoformat(m['observed_at']) > day:
                raise ValueError('Future observation')
            if m['included']:
                if not refs or not m.get('observed_at'):
                    raise ValueError('Used evidence requires sources and observation date')
                evidence = True
        if a['stress'] and (not evidence or not a['event_ids'] or a['coverage']=='limited'):
            raise ValueError('Unsupported stress')
        if a['cashflow_impact'] and not a['stress']:
            raise ValueError('Cashflow impact must have supported stress')
        if a['status'] == 'GREEN' and not evidence:
            raise ValueError('GREEN requires positive evidence, not absence of news')
    ce = d.get('credit_events',{})
    for key in ('critical_confirmed','systemic_confirmed'):
        if type(ce.get(key,False)) is not bool:
            raise ValueError('Invalid credit event')
    if ce.get('critical_confirmed') or ce.get('systemic_confirmed'):
        if not ce.get('source_ids') or not set(ce['source_ids']) <= ids or not ce.get('description'):
            raise ValueError('Credit event lacks evidence')
        if ce.get('systemic_confirmed') and (not ce.get('critical_confirmed') or len(set(ce.get('affected_entities',[]))) < 2):
            raise ValueError('Systemic event lacks transmission')


def classify(d):
    """Stable gates; underlying evidence assessment is qualitative, not a probability."""
    stress = [a for a in d['axes'] if a['stress']]
    independent = any(set(a['event_ids']).isdisjoint(b['event_ids'])
                      for i,a in enumerate(stress) for b in stress[i+1:])
    ce = d.get('credit_events',{})
    if ce.get('systemic_confirmed'):
        level, rule = 'RED','R1'
    elif ce.get('critical_confirmed') or (independent and any(a['cashflow_impact'] for a in stress)):
        level, rule = 'ORANGE','O1'
    elif stress or any(a['status'] in ('YELLOW','ORANGE','RED') for a in d['axes']):
        level, rule = 'YELLOW','Y1'
    elif all(a['coverage']=='sufficient' and a['status']=='GREEN' for a in d['axes']):
        level, rule = 'GREEN','G1'
    else:
        level, rule = 'UNKNOWN','D0'
    state = 'deferred' if level=='UNKNOWN' else ('provisional' if any(a['coverage']!='sufficient' for a in d['axes']) else 'assessed')
    d.update(schema_version=2,ui_version=UI_VERSION,rules_version=RULES_VERSION,risk_level=level,
             risk_score=None,watch='',rule_code=rule,assessment_state=state)
    return d


def ledger(label,value):
    return '<div class="text-ledger"><b>'+esc(label)+'</b><p>'+esc(value)+'</p></div>'


def refs(ids):
    return '<div class="refchips">'+''.join('<button class="refchip" data-ref="'+esc(x)+'" type="button">'+esc(x)+' 출처</button>' for x in ids)+'</div>'


def build_html(data, base='./'):
    d = data if data.get('schema_version')==2 and 'axes' in data else legacy_view(data)
    day = date.fromisoformat(d['date'])
    level = d.get('risk_level','UNKNOWN')
    ko,tone = LEVELS[level]
    legacy = d.get('assessment_state')=='not_revalidated'
    meta = '원본 판정 참고' if legacy else {'assessed':'일일 판정','provisional':'잠정 판정',
        'deferred':'자료 확인 제한','failed':'수집 실패'}.get(d.get('assessment_state'),'확인 제한')
    kv = {'DATE':day.isoformat(),'SHORT_DATE':day.strftime('%m.%d'),'YEAR':str(day.year),
        'BUILD_SHA':str(d.get('build_sha') or 'local'),'CONTENT_MODE':'layout-only' if legacy else 'daily-report','STRIP_NOTE':'UI '+UI_VERSION+' · '+meta,
        'KICKER':meta,'DELTA':CHANGE[d.get('change','unavailable')],'LEVEL_KO':ko,
        'LEVEL':level if level!='UNKNOWN' else 'DATA LIMITED','TONE':tone,
        'HEADLINE':short(d['headline']),'REASON':short(d['reason'],64),
        'CHANGES':short(d.get('changes_note') or ' / '.join(d.get('changes',[])) or '신규 중요 변화 없음',150),
        'NEXT':short(d['next_check'],60),'INVESTOR':d['investor_view'],
        'FOOTER':meta+' · 자료 기준 '+day.isoformat()+' · 생성 '+str(d.get('generated_at') or '원본 시각 미상')}
    kv = {k:esc(v) for k,v in kv.items()}
    panels = {}
    kv['SPECTRUM'] = ''.join('<li class="stage" style="--stage:var(--'+c+')"'+
        (' data-active="true" aria-current="step"' if l==level else '')+
        '><div class="stage-track"></div><span class="stage-name">'+n+(' ●' if l==level else '')+'</span></li>'
        for l,(n,c) in LEVELS.items() if l!='UNKNOWN')
    for a in d['axes']:
        key = a['id']; name = AXES[key]; state, color = LEVELS[a['status']]
        if a['coverage']!='sufficient':
            state,color = ('일부 확인','gray') if a['coverage']=='partial' else ('확인 제한','gray')
        detail = '<p class="sheet-lead">'+esc(a['explanation'])+'</p>'
        for m in a['items']:
            detail += '<section class="data-box"><div class="box-heading"><h3>'+esc(m.get('label'))+'</h3><span>'+esc(m.get('observed_at') or '관측일 확인 제한')+'</span></div><div class="value-row"><span>확인값</span><strong>'+esc(m.get('value') or '확인 제한')+'</strong></div>'
            detail += ledger('비교 기준·변화',m.get('comparison') or '동일 조건 비교값 없음')+ledger('해석·범위',m.get('note') or '추가 설명 없음')
            detail += '<p class="caption">'+('판정 반영' if m['included'] and not legacy else '현재 판정 미반영 · 참고 기록')+'</p>'+refs(m['source_ids'])+'</section>'
        if not a['items']:
            detail += ledger('확인 제한','판정에 쓸 수 있는 검증된 최신 수치가 부족합니다.')
        panels[key] = dict(title=name,subtitle=a['meaning'],status=state+' · '+meta,tone=color,body=detail)
        k=key.upper()
        kv.update({k+'_ARIA':esc(name+' '+CHANGE[a['change']]+' 상세 근거 보기'),
            k+'_CHANGE':esc(a['change']),k+'_TONE':color,k+'_MEANING':esc(short(a['meaning'],32)),
            k+'_STATUS':esc(state+' '+{'worse':'↑','better':'↓','unchanged':'→','unavailable':'—'}[a['change']])})
    method = ledger('적용 기준','기존 판정 참고값입니다. 이번 양식 배포에서 재검증하지 않았습니다.' if legacy else '규칙 v1.0 / '+d.get('rule_code','D0')+' · 운영용 경계 분류이며 검증된 부도예측·매매점수가 아닙니다.')
    method += ''.join(ledger(label,x) for label,key in [('판정 근거','assessment_reasons'),('반대 근거','counter_evidence'),('확인 한계','data_gaps')] for x in d.get(key,[]))
    panels['method'] = dict(title='판정 근거',subtitle='동일 사건을 중복 경보로 계산하지 않습니다.',status=ko+' · '+meta,tone=tone,body=method)
    panels['next'] = dict(title='다음 확인사항',subtitle=d['next_check'],status='조건부 관찰',tone='gray',body=ledger('확인할 변화',d['next_check'])+ledger('투자자 관점',d['investor_view']))
    panels['about'] = dict(title='내용·화면 버전',subtitle='승인한 화면 구조를 재사용합니다.',status='UI '+UI_VERSION,tone='gray',body=ledger('자료 기준일',d['date'])+ledger('생성시각',d.get('generated_at') or '원본 시각 미상')+ledger('이번 렌더링',d.get('rendered_at') or '시각 미기록')+ledger('범위','기존 자료의 양식 교체이며 시장 재평가가 아닙니다.' if legacy else '원자료 확인과 정성적 위험 판단의 한계를 근거에서 확인하세요.'))
    source_rows = []
    for s in d.get('sources',[]):
        if not safe_url(s.get('url')): continue
        source_rows.append('<div class="source-row" id="source-'+esc(s['id'])+'"><span class="ref-id">'+esc(s['id'])+'</span><div><a href="'+esc(s['url'])+'" target="_blank" rel="noopener noreferrer">'+esc(s.get('name'))+' ↗</a><p>발행 '+esc(s.get('published_at') or s.get('date') or '확인 제한')+'</p></div></div>')
    evidence = '<div class="page-title"><p class="kicker">근거</p><h2>왜 이 단계인가?</h2><p>'+esc(meta)+'</p></div><section class="surface">'+method+'</section><section class="surface"><h3>4단계 운영 규칙 v1.0</h3>'
    for l,desc in [('GREEN','주요 축을 충분히 확인했고 유의미한 스트레스가 없음.'),('YELLOW','국지적 경고 또는 제한적인 실제 조달·현금흐름 훼손.'),('ORANGE','독립적인 두 축의 스트레스와 실제 조달·현금흐름 악화, 또는 중요한 차주의 중대한 차환·지급 문제.'),('RED','중요 신용사건이 복수 차주·대주단으로 전염되거나 광범위한 자금조달 경색.')]:
        n,c=LEVELS[l]
        evidence += '<div class="rule"><b class="rule-key '+c+'">'+n+'</b><p>'+desc+'</p></div>'
    evidence += '</section><section class="surface"><h3>조건부 전염 경로</h3><p class="caption">'+esc(d.get('contagion') or '차주 현금흐름 → 담보가치 → 대주단·보증자. 연결성의 존재와 실제 손실 이전은 별도입니다.')+'</p></section><section class="surface"><details class="source-disclosure" id="sources-details"><summary>출처 보기 · '+str(len(source_rows))+'개</summary><p class="caption">'+('저장된 원문 링크입니다. 이번 재배치에서 다시 검증하지 않았습니다.' if legacy else '각 지표의 관측일·비교조건·판정 반영 여부를 함께 확인하세요.')+'</p>'+''.join(source_rows)+'</details></section>'
    kv['EVIDENCE_HTML'] = evidence
    tr = d.get('trend',{})
    trend = '<div class="page-title"><p class="kicker">추세</p><h2>같은 기준의 기록만<br>이어서 봅니다.</h2><p>소수점 점수·기준이 다른 등급을 연결하지 않습니다.</p></div><section class="surface">'+ledger('같은 기준 유효 보고서',str(tr.get('same_rules_count',0))+'개 · 잠정 판정 포함')+ledger('현재 단계 연속 기록',str(d.get('current_level_streak_days',0))+'일 · 누락일 및 판정 보류 시 중단')+ledger('전체 보관 보고서',str(d.get('history_count',0))+'개 · 원자료 관측 수와 다름')+'</section><div class="window-grid">'
    for n in (30,90,180):
        count = tr.get('days_'+str(n),{}).get('available_count',0)
        trend += '<div class="window-card"><span>'+str(n)+'일 분석</span><b>'+('자료 축적 중' if count<n else '기록 확보')+'</b><p>같은 기준 '+str(count)+'개 / '+str(n)+'일<br>보간·평균점수 없음</p></div>'
    trend += '</div>'
    if d.get('monthly_summary',{}).get('available'):
        trend += '<section class="surface"><h3>월간 기록</h3><a href="'+esc(base+'summary/monthly/'+day.strftime('%Y-%m')+'.html')+'">이번 달 요약 보기 →</a><p class="caption">기준 버전·자료 부족을 분리합니다.</p></section>'
    kv['TREND_HTML'] = trend
    kv['PANELS_JSON'] = json.dumps(panels,ensure_ascii=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    css = (ROOT/'templates/approved-layout.css').read_text(encoding='utf-8')
    if hashlib.sha256(css.encode()).hexdigest() != (ROOT/'templates/approved-css.sha256').read_text().strip():
        raise ValueError('Approved CSS changed: review required')
    kv['APPROVED_CSS'] = css
    kv['APPROVED_JS'] = (ROOT/'templates/approved-layout.js').read_text(encoding='utf-8')
    template = (ROOT/'templates/approved-layout.html').read_text(encoding='utf-8')
    missing = set(re.findall(r'@@([A-Z_]+)@@',template))-set(kv)
    if missing: raise ValueError('Unresolved template fields: '+str(missing))
    return re.sub(r'@@([A-Z_]+)@@',lambda m:kv[m[1]],template)
