import os
import json
import html
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI


ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
AI_RISK_DIR = PUBLIC_DIR / "ai-risk"
ARCHIVE_DIR = AI_RISK_DIR / "archive"
PROMPT_FILE = ROOT / "prompt.txt"

AI_RISK_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST).strftime("%Y-%m-%d")


def load_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise FileNotFoundError("prompt.txt 파일이 저장소 루트에 없습니다.")

    return PROMPT_FILE.read_text(encoding="utf-8")


def get_openai_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 환경변수가 없습니다. "
            "GitHub Repository Secret에 OPENAI_API_KEY를 등록하세요."
        )

    return OpenAI(api_key=api_key)


def extract_json(text: str) -> dict:
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            "모델 응답을 JSON으로 파싱하지 못했습니다.\n"
            f"응답 앞부분:\n{text[:2000]}"
        ) from e


def generate_report_data() -> dict:
    prompt = load_prompt()

    client = get_openai_client()

    full_prompt = f"""
{prompt}

오늘 날짜는 {TODAY}이며 시간대는 Asia/Seoul이다.

반드시 최신 공개자료를 검색해서 오늘 기준으로 작성한다.

최종 응답은 설명문 없이 JSON object 하나만 반환한다.
Markdown code fence도 사용하지 않는다.
"""

    response = client.responses.create(
        model="gpt-5.6",
        reasoning={
            "effort": "medium"
        },
        tools=[
            {
                "type": "web_search"
            }
        ],
        input=full_prompt,
    )

    raw_text = response.output_text

    if not raw_text:
        raise RuntimeError("OpenAI API가 빈 응답을 반환했습니다.")

    data = extract_json(raw_text)

    validate_report_data(data)

    return data


def validate_report_data(data: dict) -> None:
    required_fields = [
        "date",
        "risk_level",
        "risk_score",
        "watch",
        "headline",
        "summary",
        "metrics",
        "alerts",
        "contagion",
        "investor_view",
        "orange_triggers",
        "red_triggers",
        "one_liner",
        "sources",
    ]

    missing = [
        field for field in required_fields
        if field not in data
    ]

    if missing:
        raise RuntimeError(
            f"필수 필드 누락: {', '.join(missing)}"
        )

    try:
        score = float(data["risk_score"])
    except (TypeError, ValueError):
        raise RuntimeError("risk_score는 숫자여야 합니다.")

    if not (1.0 <= score <= 4.0):
        raise RuntimeError(
            f"risk_score 범위 오류: {score}"
        )

    risk_level = str(data["risk_level"]).upper()

    if "GREEN" in risk_level and not (1.0 <= score < 2.0):
        raise RuntimeError(
            "GREEN인데 risk_score가 GREEN 범위가 아닙니다."
        )

    if "YELLOW" in risk_level and not (2.0 <= score < 3.0):
        raise RuntimeError(
            "YELLOW인데 risk_score가 YELLOW 범위가 아닙니다."
        )

    if "ORANGE" in risk_level and not (3.0 <= score < 4.0):
        raise RuntimeError(
            "ORANGE인데 risk_score가 ORANGE 범위가 아닙니다."
        )

    if "RED" in risk_level and score < 4.0:
        raise RuntimeError(
            "RED인데 risk_score가 4.0 미만입니다."
        )


def esc(value) -> str:
    return html.escape(str(value or ""))


def risk_color_class(status: str) -> str:
    status = str(status or "").upper()

    if "RED" in status:
        return "red"

    if "ORANGE" in status:
        return "orange"

    if "YELLOW" in status:
        return "yellow"

    if (
        "GREEN" in status
        or "STABLE" in status
        or "STRONG" in status
        or "NONE" in status
    ):
        return "green"

    return "muted"


def marker_position(score: float) -> float:
    """
    1.0 -> GREEN 시작
    2.0 -> YELLOW 시작
    3.0 -> ORANGE 시작
    4.0 -> RED 끝

    시각적으로 각 단계가 25%씩 차지하도록 변환.
    """

    normalized = (score - 1.0) / 3.0
    pct = normalized * 100

    return max(3.0, min(97.0, pct))


def build_metrics(metrics: list) -> str:
    blocks = []

    for metric in metrics:
        blocks.append(
            f"""
            <div class="metric">
              <div class="k">{esc(metric.get("label"))}</div>
              <div class="v">{esc(metric.get("value"))}</div>
              <div class="sub">{esc(metric.get("note"))}</div>
              <span class="pill {risk_color_class(metric.get("status"))}">
                {esc(metric.get("status"))}
              </span>
            </div>
            """
        )

    return "\n".join(blocks)


def build_alerts(alerts: list) -> str:
    blocks = []

    for alert in alerts:
        status_class = risk_color_class(
            alert.get("status")
        )

        blocks.append(
            f"""
            <div class="alert">
              <div class="pin {status_class}"></div>
              <div>
                <b>{esc(alert.get("title"))}</b>
                <p>{esc(alert.get("detail"))}</p>
              </div>
            </div>
            """
        )

    return "\n".join(blocks)


def build_trigger_list(items: list) -> str:
    return "\n".join(
        f"<li>{esc(item)}</li>"
        for item in items
    )


def build_sources(sources: list) -> str:
    rows = []

    for source in sources:
        name = esc(source.get("name"))
        url = esc(source.get("url"))
        date = esc(source.get("date"))

        if url:
            rows.append(
                f"""
                <li>
                  <a href="{url}"
                     target="_blank"
                     rel="noopener noreferrer">
                    {name}
                  </a>
                  · {date}
                </li>
                """
            )
        else:
            rows.append(
                f"<li>{name} · {date}</li>"
            )

    return "\n".join(rows)


def build_html(data: dict) -> str:
    score = float(data["risk_score"])
    marker_pct = marker_position(score)

    metrics_html = build_metrics(
        data.get("metrics", [])
    )

    alerts_html = build_alerts(
        data.get("alerts", [])
    )

    orange_html = build_trigger_list(
        data.get("orange_triggers", [])
    )

    red_html = build_trigger_list(
        data.get("red_triggers", [])
    )

    sources_html = build_sources(
        data.get("sources", [])
    )

    risk_level = esc(data.get("risk_level"))
    watch = esc(data.get("watch"))
    date = esc(data.get("date"))
    headline = esc(data.get("headline"))
    summary = esc(data.get("summary"))
    contagion = esc(data.get("contagion"))
    investor_view = esc(data.get("investor_view"))
    one_liner = esc(data.get("one_liner"))

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">

<meta
  name="viewport"
  content="width=device-width, initial-scale=1, viewport-fit=cover"
>

<title>
  AI 투자리스크 센싱 · {date}
</title>

<style>

:root {{
  --bg: #090b0e;
  --bg2: #10141a;
  --card: #15191f;
  --card2: #11151a;
  --line: #2a313a;

  --txt: #eef2f5;
  --muted: #97a2ad;

  --green: #36c98f;
  --yellow: #f2c94c;
  --orange: #f2994a;
  --red: #ef6461;
}}

* {{
  box-sizing: border-box;
}}

html,
body {{
  margin: 0;
  min-height: 100%;
  background:
    linear-gradient(
      180deg,
      var(--bg),
      var(--bg2) 55%,
      var(--bg)
    );
  color: var(--txt);

  font-family:
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    "Noto Sans KR",
    Roboto,
    sans-serif;
}}

.wrap {{
  max-width: 480px;
  margin: auto;

  padding:
    calc(18px + env(safe-area-inset-top))
    14px
    calc(38px + env(safe-area-inset-bottom));
}}

.eyebrow {{
  font-size: 11px;
  letter-spacing: .08em;
  color: var(--muted);
}}

h1 {{
  margin: 6px 0 4px;
  font-size: 25px;
}}

.date {{
  font-size: 12px;
  color: var(--muted);
}}

.hero,
.card {{
  margin: 14px 0;
  padding: 16px;

  border-radius: 20px;

  background: rgba(21,25,31,.97);
  border: 1px solid var(--line);
}}

.hero {{
  background:
    linear-gradient(
      135deg,
      #25210f,
      #1c1811 55%,
      #171b21
    );

  border-color: #4d4120;
}}

.row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}}

.badge {{
  display: inline-flex;
  align-items: center;
  gap: 7px;

  padding: 7px 11px;

  border-radius: 999px;

  background:
    rgba(242,201,76,.12);

  border:
    1px solid
    rgba(242,201,76,.35);

  color: #ffe07b;

  font-size: 12px;
  font-weight: 900;
}}

.badge-dot {{
  width: 8px;
  height: 8px;

  border-radius: 50%;

  background: var(--yellow);

  box-shadow:
    0 0 12px
    rgba(242,201,76,.8);
}}

.watch {{
  font-size: 11px;
  color: #ffc58f;
}}

.hero h2 {{
  margin: 14px 0 7px;
  font-size: 19px;
  line-height: 1.35;
}}

.hero p,
.bodytext {{
  margin: 0;

  color: #c7d0d8;

  font-size: 13px;
  line-height: 1.65;
}}

.section {{
  margin: 16px 0;
}}

.section-title {{
  display: flex;
  justify-content: space-between;
  align-items: end;

  margin:
    0 3px 9px;
}}

.section-title h3 {{
  margin: 0;
  font-size: 15px;
}}

.section-title span {{
  font-size: 10px;
  color: var(--muted);
}}

.spectrum-card {{
  padding: 16px;

  border-radius: 20px;

  background:
    linear-gradient(
      135deg,
      #151920,
      #12161b
    );

  border:
    1px solid
    #2d343d;
}}

.spectrum-head {{
  display: flex;
  justify-content: space-between;
  gap: 10px;
}}

.spectrum-head strong {{
  font-size: 15px;
}}

.score {{
  text-align: right;
  font-size: 10px;
  color: #a8b2bc;
  line-height: 1.45;
}}

.spectrum-zone {{
  position: relative;

  margin:
    10px 0 2px;

  padding-top: 38px;
  padding-bottom: 46px;
}}

.spectrum-bar {{
  position: relative;
  z-index: 1;

  display: grid;
  grid-template-columns:
    repeat(4, 1fr);

  height: 16px;

  overflow: hidden;

  border-radius: 999px;
  border:
    1px solid
    #303741;
}}

.segment {{
  display: flex;
  align-items: center;
  justify-content: center;

  color: white;
  font-size: 9px;
  font-weight: 900;
}}

.segment.green {{
  background: #2da977;
}}

.segment.yellow {{
  background: #caa936;
}}

.segment.orange {{
  background: #d87d37;
}}

.segment.red {{
  background: #bf4d48;
}}

.marker {{
  position: absolute;

  left: {marker_pct:.2f}%;

  top: 0;

  z-index: 4;

  transform:
    translateX(-50%);

  display: flex;
  flex-direction: column;
  align-items: center;
}}

.marker-bubble {{
  white-space: nowrap;

  padding: 4px 8px;

  border-radius: 999px;

  background: #fff0b8;
  border: 1px solid #d7bb55;

  color: #463700;

  font-size: 10px;
  font-weight: 900;
}}

.marker-stem {{
  width: 2px;
  height: 20px;

  margin-top: 3px;

  border-radius: 2px;

  background: #ffe07b;
}}

.boundary {{
  position: absolute;

  left: 66.666%;

  top: 38px;

  z-index: 3;

  width: 2px;
  height: 26px;

  transform:
    translateX(-50%);

  background: #f0ad70;
}}

.boundary-label {{
  position: absolute;

  left: 66.666%;
  top: 72px;

  z-index: 4;

  transform:
    translateX(-50%);

  white-space: nowrap;

  padding: 3px 7px;

  border-radius: 999px;

  background: #11151a;
  border: 1px solid #4c3421;

  color: #ffc58f;

  font-size: 9px;
  font-weight: 900;
}}

.spectrum-note {{
  color: #c9d1d8;

  font-size: 12px;
  line-height: 1.6;
}}

.grid {{
  display: grid;

  grid-template-columns:
    1fr 1fr;

  gap: 10px;
}}

.metric {{
  min-height: 118px;

  padding: 13px;

  border-radius: 17px;

  background: var(--card);

  border:
    1px solid
    var(--line);
}}

.metric .k {{
  margin-bottom: 8px;

  color: var(--muted);

  font-size: 10px;
}}

.metric .v {{
  font-size: 20px;
  font-weight: 900;
}}

.metric .sub {{
  margin-top: 6px;

  color: #aeb7c1;

  font-size: 10px;
  line-height: 1.45;
}}

.pill {{
  display: inline-block;

  margin-top: 8px;

  padding:
    3px 7px;

  border-radius: 999px;

  font-size: 9px;
  font-weight: 900;
}}

.pill.green {{
  color: #83e0b8;
  background: rgba(54,201,143,.12);
}}

.pill.yellow {{
  color: #ffe07b;
  background: rgba(242,201,76,.12);
}}

.pill.orange {{
  color: #ffc58f;
  background: rgba(242,153,74,.12);
}}

.pill.red {{
  color: #ffaaa6;
  background: rgba(239,100,97,.12);
}}

.pill.muted {{
  color: #a8b2bc;
  background: #20262e;
}}

.timeline {{
  display: flex;
  flex-direction: column;
}}

.alert {{
  display: grid;

  grid-template-columns:
    12px 1fr;

  gap: 9px;

  padding:
    11px 0;

  border-bottom:
    1px solid
    #242a31;
}}

.alert:last-child {{
  border-bottom: 0;
}}

.pin {{
  width: 9px;
  height: 9px;

  margin-top: 5px;

  border-radius: 50%;
}}

.pin.green {{
  background: var(--green);
}}

.pin.yellow {{
  background: var(--yellow);
}}

.pin.orange {{
  background: var(--orange);
}}

.pin.red {{
  background: var(--red);
}}

.pin.muted {{
  background: #6d7782;
}}

.alert b {{
  font-size: 12px;
}}

.alert p {{
  margin:
    4px 0 0;

  color: #aeb7c1;

  font-size: 11px;
  line-height: 1.55;
}}

.flow {{
  display: flex;
  align-items: center;

  gap: 6px;

  overflow-x: auto;

  padding:
    10px 0 4px;
}}

.node {{
  flex: 0 0 auto;

  padding:
    8px 9px;

  border-radius: 11px;

  background: #101419;

  border:
    1px solid
    #2b323a;

  font-size: 10px;
}}

.arrow {{
  color: #7e8994;
}}

.risk-list {{
  display: flex;
  flex-direction: column;

  gap: 8px;
}}

.risk {{
  padding:
    11px 12px;

  border-radius: 14px;

  background: #12161b;

  border:
    1px solid
    #272e36;

  cursor: pointer;
}}

.risk-head {{
  display: flex;

  align-items: center;
  justify-content: space-between;

  gap: 8px;
}}

.risk-label {{
  display: flex;
  align-items: center;

  gap: 7px;

  font-size: 11px;
}}

.info {{
  display: inline-flex;

  width: 17px;
  height: 17px;

  align-items: center;
  justify-content: center;

  border-radius: 50%;

  background: #20262e;

  border:
    1px solid
    #39414a;

  color: #a5b0ba;

  font-size: 9px;
  font-weight: 900;
}}

.status {{
  font-size: 10px;
  font-weight: 900;
}}

.status.green {{
  color: #83e0b8;
}}

.status.yellow {{
  color: #ffe07b;
}}

.status.orange {{
  color: #ffc58f;
}}

.status.red {{
  color: #ffaaa6;
}}

.status.muted {{
  color: #9aa5b0;
}}

.tip {{
  display: none;

  margin-top: 9px;

  padding:
    9px 10px;

  border-radius: 11px;

  background: #0e1216;

  border:
    1px solid
    #2a3139;

  color: #c6ced6;

  font-size: 10px;
  line-height: 1.55;
}}

.risk.open .tip {{
  display: block;
}}

.triggers {{
  display: grid;

  grid-template-columns:
    1fr 1fr;

  gap: 10px;
}}

.trigger-box {{
  padding: 12px;

  border-radius: 15px;

  background: #11151a;

  border:
    1px solid
    #2a3139;
}}

.trigger-box b {{
  font-size: 11px;
}}

.trigger-box ul {{
  margin:
    7px 0 0;

  padding-left: 17px;
}}

.trigger-box li {{
  margin-bottom: 4px;

  color: #adb6bf;

  font-size: 10px;
  line-height: 1.5;
}}

.source-list {{
  margin: 0;
  padding-left: 18px;
}}

.source-list li {{
  margin-bottom: 6px;

  color: #89949f;

  font-size: 10px;
  line-height: 1.55;
}}

.source-list a {{
  color: #9db8ee;
  text-decoration: none;
}}

.one-liner {{
  font-size: 14px;
  line-height: 1.55;
  font-weight: 800;
}}

.footer {{
  padding: 3px;

  color: #707a84;

  font-size: 9px;
  line-height: 1.5;
}}

</style>
</head>

<body>

<div class="wrap">

  <div class="eyebrow">
    AI CREDIT RISK MONITOR
  </div>

  <h1>
    AI 투자리스크 센싱
  </h1>

  <div class="date">
    {date} · Asia/Seoul · 최신 공개자료 기준
  </div>


  <section class="hero">

    <div class="row">

      <div class="badge">
        <span class="badge-dot"></span>
        {risk_level}
      </div>

      <div class="watch">
        {watch}
      </div>

    </div>

    <h2>
      {headline}
    </h2>

    <p>
      {summary}
    </p>

  </section>


  <section class="section">

    <div class="section-title">
      <h3>전체 위험 스펙트럼</h3>
      <span>현재 위치</span>
    </div>

    <div class="spectrum-card">

      <div class="spectrum-head">

        <strong>
          현재 {risk_level}
        </strong>

        <div class="score">
          위험점수
          {score:.2f} / 4
        </div>

      </div>


      <div class="spectrum-zone">

        <div class="marker">

          <div class="marker-bubble">
            현재 {risk_level}
          </div>

          <div class="marker-stem">
          </div>

        </div>


        <div class="boundary">
        </div>

        <div class="boundary-label">
          ORANGE 경계
        </div>


        <div class="spectrum-bar">

          <div class="segment green">
            GREEN
          </div>

          <div class="segment yellow">
            YELLOW
          </div>

          <div class="segment orange">
            ORANGE
          </div>

          <div class="segment red">
            RED
          </div>

        </div>

      </div>

      <div class="spectrum-note">
        위험점수는 현재 단계와 모순되지 않도록
        제한되어 있으며,
        ORANGE 경계는 별도로 표시됩니다.
      </div>

    </div>

  </section>


  <section class="section">

    <div class="section-title">
      <h3>오늘의 핵심 지표</h3>
      <span>최신 확인값</span>
    </div>

    <div class="grid">
      {metrics_html}
    </div>

  </section>


  <section class="card">

    <div class="section-title">
      <h3>오늘 새로 볼 것</h3>
      <span>중요도 순</span>
    </div>

    <div class="timeline">
      {alerts_html}
    </div>

  </section>


  <section class="card">

    <div class="section-title">
      <h3>신용 전염 지도</h3>
      <span>구조</span>
    </div>

    <div class="flow">

      <div class="node">
        AI 최종 수요자
      </div>

      <div class="arrow">
        →
      </div>

      <div class="node">
        Neocloud / SPV
      </div>

      <div class="arrow">
        →
      </div>

      <div class="node">
        은행 / Private Credit
      </div>

      <div class="arrow">
        →
      </div>

      <div class="node">
        보증 제공 Big Tech
      </div>

    </div>

    <div class="bodytext">
      {contagion}
    </div>

  </section>


  <section class="section">

    <div class="section-title">
      <h3>경보판</h3>
      <span>탭하면 의미 보기</span>
    </div>

    <div class="risk-list">

      <div class="risk">

        <div class="risk-head">

          <div class="risk-label">
            <span class="info">i</span>
            장기금리
          </div>

          <div class="status yellow">
            YELLOW
          </div>

        </div>

        <div class="tip">
          미국 10년·30년물은
          AI 데이터센터 프로젝트의
          기준 할인율입니다.
          높은 금리가 길어질수록
          신규 투자와 차환 경제성이 나빠집니다.
        </div>

      </div>


      <div class="risk">

        <div class="risk-head">

          <div class="risk-label">
            <span class="info">i</span>
            AI 프로젝트 대출가격
          </div>

          <div class="status orange">
            WATCH
          </div>

        </div>

        <div class="tip">
          프로젝트 대출이
          액면가 아래에서 거래되면
          시장이 원금 회수 위험을
          더 크게 보기 시작했다는 뜻입니다.
        </div>

      </div>


      <div class="risk">

        <div class="risk-head">

          <div class="risk-label">
            <span class="info">i</span>
            보증 / Off-Balance-Sheet
          </div>

          <div class="status orange">
            WATCH
          </div>

        </div>

        <div class="tip">
          SPV 부채가 외부에 있어도
          NVIDIA·Meta 등에서 보증을 제공하면
          손실이 스폰서 기업으로
          이전될 수 있습니다.
        </div>

      </div>


      <div class="risk">

        <div class="risk-head">

          <div class="risk-label">
            <span class="info">i</span>
            GPU 임대·중고가격
          </div>

          <div class="status green">
            MONITOR
          </div>

        </div>

        <div class="tip">
          GPU 가격은 실수요와
          담보가치를 동시에 보여줍니다.
          광범위한 가격 급락은
          중요한 신용경보입니다.
        </div>

      </div>


      <div class="risk">

        <div class="risk-head">

          <div class="risk-label">
            <span class="info">i</span>
            Hyperscaler CapEx
          </div>

          <div class="status green">
            MONITOR
          </div>

        </div>

        <div class="tip">
          Microsoft·Google·Meta·Amazon의
          AI 설비투자는
          전체 AI 인프라 수요의 핵심입니다.
          여러 곳의 동시 하향은
          사이클 전환 신호입니다.
        </div>

      </div>


      <div class="risk">

        <div class="risk-head">

          <div class="risk-label">
            <span class="info">i</span>
            Neocloud default
          </div>

          <div class="status green">
            MONITOR
          </div>

        </div>

        <div class="tip">
          CoreWeave·Lambda·Nebius 등의
          실제 디폴트나
          차환 실패는
          신용우려가 가격신호에서
          실제 사건으로 넘어갔다는 뜻입니다.
        </div>

      </div>


      <div class="risk">

        <div class="risk-head">

          <div class="risk-label">
            <span class="info">i</span>
            CDS / 신용스프레드
          </div>

          <div class="status muted">
            DATA CHECK
          </div>

        </div>

        <div class="tip">
          CDS는 주식시장보다 먼저
          신용우려를 반영할 수 있습니다.
          신뢰할 최신 공개값이 없으면
          추정하지 않고
          확인 제한으로 처리합니다.
        </div>

      </div>

    </div>

  </section>


  <section class="card">

    <div class="section-title">
      <h3>투자자 행동 기준</h3>
      <span>조건부</span>
    </div>

    <div class="bodytext">
      {investor_view}
    </div>

  </section>


  <section class="section">

    <div class="section-title">
      <h3>다음 경보 조건</h3>
      <span>격상 기준</span>
    </div>

    <div class="triggers">

      <div class="trigger-box">

        <b style="color:#ffc58f">
          ORANGE
        </b>

        <ul>
          {orange_html}
        </ul>

      </div>

      <div class="trigger-box">

        <b style="color:#ffaaa6">
          RED
        </b>

        <ul>
          {red_html}
        </ul>

      </div>

    </div>

  </section>


  <section class="card">

    <div class="section-title">

      <h3>
        한 줄 인사이트
      </h3>

    </div>

    <div class="one-liner">
      {one_liner}
    </div>

  </section>


  <section class="card">

    <div class="section-title">
      <h3>핵심 출처</h3>
      <span>공개자료</span>
    </div>

    <ul class="source-list">
      {sources_html}
    </ul>

  </section>


  <div class="footer">
    최신 확인 가능한 공개자료만 사용.
    확인하지 못한 CDS 등은 추정하지 않음.
  </div>

</div>


<script>

(function() {{

  const items =
    document.querySelectorAll(
      ".risk"
    );

  items.forEach((item) => {{

    item.addEventListener(
      "click",
      () => {{

        const wasOpen =
          item.classList.contains(
            "open"
          );

        items.forEach((x) => {{
          x.classList.remove(
            "open"
          );
        }});

        if (!wasOpen) {{
          item.classList.add(
            "open"
          );
        }}

      }}
    );

  }});

}})();

</script>

</body>
</html>
"""


def save_outputs(data: dict) -> None:
    date = data.get("date") or TODAY

    report_html = build_html(data)

    data["html_url"] = "./latest.html"

    latest_json = AI_RISK_DIR / "latest.json"
    latest_html = AI_RISK_DIR / "latest.html"

    archive_json = (
        ARCHIVE_DIR /
        f"{date}.json"
    )

    archive_html = (
        ARCHIVE_DIR /
        f"{date}.html"
    )

    latest_json.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    archive_json.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    latest_html.write_text(
        report_html,
        encoding="utf-8",
    )

    archive_html.write_text(
        report_html,
        encoding="utf-8",
    )

    print(
        "Generated:",
        latest_html,
    )

    print(
        "Generated:",
        latest_json,
    )

    print(
        "Archived:",
        archive_html,
    )

    print(
        "Archived:",
        archive_json,
    )


def main():
    data = generate_report_data()
    save_outputs(data)


if __name__ == "__main__":
    main()
