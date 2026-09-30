from __future__ import annotations
import json,os,html
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from openai import OpenAI
from defense_report_schema import SCHEMA
ROOT=Path(__file__).resolve().parent; KST=ZoneInfo("Asia/Seoul")
LEVEL={"GREEN":("안정","g"),"YELLOW":("주의","y"),"ORANGE":("경계","o"),"RED":("위기","r"),"UNKNOWN":("확인 제한","x")}
AXNAME={"orders":"수주·백로그 질","budget":"국방예산·정책","execution":"생산·납기·공급망","profitability":"수익성·원가·환율"}
def stamp(): return datetime.now(KST).isoformat(timespec="seconds")
def research(day):
    r=OpenAI(api_key=os.environ["OPENAI_API_KEY"],timeout=240,max_retries=1).responses.create(
      model=os.environ.get("OPENAI_MODEL") or "gpt-5.6",reasoning={"effort":"medium"},store=False,
      tools=[{"type":"web_search"}],tool_choice="required",include=["web_search_call.action.sources"],
      max_tool_calls=20,max_output_tokens=16000,text={"format":{"type":"json_schema","name":"defense_risk","schema":SCHEMA,"strict":True}},
      input=[{"role":"developer","content":(ROOT/"defense_prompt.txt").read_text(encoding="utf-8")},{"role":"user","content":"한국 기준일 "+day}])
    d=json.loads(r.output_text); d["generated_at"]=stamp(); d["api_response_id"]=r.id; return d
def industry_level(d):
    a=d["industry_axes"]
    if any(x["stress"] and x["status"]=="RED" for x in a): return "RED"
    if sum(x["stress"] and x["status"]=="ORANGE" for x in a)>=2:return "ORANGE"
    if any(x["stress"] or x["status"] in ("YELLOW","ORANGE") for x in a):return "YELLOW"
    if all(x["status"]=="GREEN" and x["coverage"]=="sufficient" for x in a):return "GREEN"
    return "UNKNOWN"
def regime(p):
    v=[x for x in (p.get("hanwha_drawdown_pct"),p.get("lig_drawdown_pct")) if isinstance(x,(int,float))]
    if not v:return "확인 제한"
    m=sum(v)/len(v)
    return "깊은 조정" if m<=-35 else "눌림" if m<=-20 else "정상조정" if m<=-10 else "고점권"
def e(x): return html.escape(str(x if x is not None else "확인 제한"),quote=True)
def render(d):
    lv=industry_level(d); ko,t=LEVEL[lv]; p=d["price"]
    holdings="".join('<div class="card"><div class="top"><b>'+e(h["name"])+'</b><span class="pill '+LEVEL[h["status"]][1]+'">'+LEVEL[h["status"]][0]+' · '+e(h["change"])+'</span></div><p>'+e(h["reason"])+'</p></div>' for h in d["holdings"])
    axes="".join('<div class="axis"><span>'+AXNAME[a["id"]]+'</span><b class="pill '+LEVEL[a["status"]][1]+'">'+LEVEL[a["status"]][0]+'</b></div>' for a in d["industry_axes"])
    events="".join('<div class="ev"><b>'+e(x["date"])+' · '+e(x["title"])+'</b><small>'+e(x["summary"])+'</small></div>' for x in sorted(d["events"],key=lambda z:z["date"]))
    sources="".join('<a href="'+e(s["url"])+'" target="_blank" rel="noopener">'+e(s["id"])+' · '+e(s["name"])+' ↗</a>' for s in d["sources"])
    return """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="report-layout-version" content="defense-risk-v1.0"><title>방산 투자리스크</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans KR",sans-serif;color:#181a1e}main{max-width:430px;margin:auto;background:#fff;min-height:100vh;padding:22px 17px 82px}h1{font-size:25px;margin:5px 0}.muted,small{color:#747b84;font-size:11px}.hero,.card{border:1px solid #e4e7ea;border-radius:19px;padding:15px;margin-top:12px}.hero h2{font-size:21px;line-height:1.35}.top,.axis{display:flex;justify-content:space-between;align-items:center;gap:8px}.pill{font-size:11px;padding:6px 9px;border-radius:20px}.g{background:#e8f7ee;color:#176c3b}.y{background:#fff3ce;color:#775900}.o{background:#ffe7cf;color:#9a5314}.r{background:#fdecec;color:#9c3333}.x{background:#eef0f3;color:#66707a}.section{font-size:12px;font-weight:800;color:#6f7680;margin:22px 3px 8px}.price{background:#faf8f2}.grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:10px}.m{background:#f5f6f7;border-radius:12px;padding:10px}.m b,.m small{display:block}.axis{padding:12px 3px;border-bottom:1px solid #eee;font-size:12px}.ev{padding:10px 0;border-bottom:1px solid #eee}.ev b,.ev small{display:block}#trend,#evidence{display:none}#evidence a{display:block;padding:10px 0;border-bottom:1px solid #eee;color:#2456a0;text-decoration:none;font-size:11px}nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:min(430px,100%);height:62px;background:#fffffff2;border-top:1px solid #e5e7ea;display:grid;grid-template-columns:repeat(3,1fr)}nav button{border:0;background:none;font-weight:800}</style></head><body><main><section id="today"><div class="muted">DEFENSE RISK · """+e(d["date"])+"""</div><h1>방산 투자리스크 센싱</h1><div class="hero"><div class="top"><b>산업 Risk</b><span class="pill """+t+"""">"""+ko+"""</span></div><h2>"""+e(d["headline"])+"""</h2><p>"""+e(d["reason"])+"""</p></div><div class="section">시장가격 · 조정국면</div><div class="card price"><div class="top"><b>가격 위치</b><span class="pill y">"""+regime(p)+"""</span></div><div class="grid"><div class="m"><small>한화 종가 / 고점대비</small><b>"""+e(p["hanwha_close"])+""" / """+e(p["hanwha_drawdown_pct"])+"""%</b></div><div class="m"><small>LIG 종가 / 고점대비</small><b>"""+e(p["lig_close"])+""" / """+e(p["lig_drawdown_pct"])+"""%</b></div><div class="m"><small>한화 2026E PER</small><b>"""+e(p["hanwha_per_2026"])+"""</b></div><div class="m"><small>LIG 2026E PER</small><b>"""+e(p["lig_per_2026"])+"""</b></div></div><p>"""+e(p["interpretation"])+"""</p></div><div class="section">내 포트폴리오 Risk</div>"""+holdings+"""<div class="section">산업 Risk · 4축</div><div class="card">"""+axes+"""</div><div class="section">다음 확인사항</div><div class="card"><b>"""+e(d["next_check"])+"""</b><p>"""+e(d["investor_view"])+"""</p></div></section><section id="trend"><h1>180일 Risk·사건 추세</h1><p class="muted">검증된 사건 변곡점 · 날짜 사이 임의 점수/보간 없음</p>"""+events+"""</section><section id="evidence"><h1>근거</h1>"""+sources+"""</section></main><nav><button onclick="tab('today')">오늘</button><button onclick="tab('trend')">추세</button><button onclick="tab('evidence')">근거</button></nav><script>function tab(id){['today','trend','evidence'].forEach(x=>document.getElementById(x).style.display=x===id?'block':'none')}</script></body></html>"""
def main():
    day=datetime.now(KST).date().isoformat(); out=ROOT/"public/defense-risk"; out.mkdir(parents=True,exist_ok=True)
    d=research(day); d["industry_risk"]=industry_level(d); d["price_regime"]=regime(d["price"])
    page=render(d); (out/"latest.json").write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8"); (out/"latest.html").write_text(page,encoding="utf-8")
    a=out/"archive"/day[:4]/day[5:7]; a.mkdir(parents=True,exist_ok=True); (a/(day+".json")).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8"); (a/(day+".html")).write_text(page,encoding="utf-8")
    (out/"status.json").write_text(json.dumps({"date":day,"generated_at":d["generated_at"],"industry_risk":d["industry_risk"],"price_regime":d["price_regime"]},ensure_ascii=False,indent=2),encoding="utf-8"); (ROOT/"public/.nojekyll").touch()
if __name__=="__main__": main()
