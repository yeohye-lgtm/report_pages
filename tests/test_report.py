"""No live market/API calls. All evidence values below are explicit test fixtures."""
import copy
import hashlib
import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from report_ui import AXES,LEVELS,legacy_view,validate,classify,build_html
from history_utils import atomic_write,dump_json,load_daily_reports,history_payload,cleanup_old_html,monthly_summary
from generate_report import save_outputs,failure_report,visited_urls


def fixture():
    d=dict(date='2026-09-29',headline='테스트용 상황판',reason='검증용 데이터이며 시장판정이 아닙니다.',
        summary='테스트 fixture',change='unavailable',changes=[],changes_note='테스트',next_check='다음 확인할 테스트 항목',
        investor_view='테스트 전용. 투자에 사용하지 않습니다.',assessment_reasons=['fixture'],counter_evidence=['fixture'],
        data_gaps=[],contagion='조건부 연결성 테스트',sources=[dict(id='S1',name='TEST ONLY',url='https://example.com/test',published_at='2026-09-28')],
        credit_events=dict(critical_confirmed=False,systemic_confirmed=False,affected_entities=[],source_ids=[],description=''),axes=[])
    for key in AXES:
        d['axes'].append(dict(id=key,status='GREEN',coverage='sufficient',meaning='테스트 상태',change='unavailable',explanation='테스트 전용 자료입니다.',
            stress=False,cashflow_impact=False,event_ids=[],items=[dict(label='테스트 지표',value='TEST',note='테스트',observed_at='2026-09-28',comparison='테스트 기준',source_ids=['S1'],included=True)]))
    return d


class ReportTests(unittest.TestCase):
    def test_green_requires_all_axes(self):
        d=fixture();validate(d);self.assertEqual(classify(d)['risk_level'],'GREEN')
        d['axes'][2]['status']='UNKNOWN';d['axes'][2]['coverage']='limited';d['axes'][2]['items']=[]
        self.assertEqual(classify(d)['risk_level'],'UNKNOWN')

    def test_not_found_is_not_green(self):
        d=fixture();d['axes'][0]['items']=[]
        with self.assertRaises(ValueError):validate(d)

    def test_one_event_not_counted_twice(self):
        d=fixture()
        for a in d['axes'][:2]:a.update(stress=True,cashflow_impact=True,status='ORANGE',event_ids=['same-event'])
        validate(d);self.assertEqual(classify(d)['risk_level'],'YELLOW')
        d['axes'][1]['event_ids']=['different-event'];self.assertEqual(classify(d)['risk_level'],'ORANGE')

    def test_red_needs_actual_transmission(self):
        d=fixture();d['credit_events'].update(systemic_confirmed=True)
        with self.assertRaises(ValueError):validate(d)
        d['credit_events'].update(critical_confirmed=True,affected_entities=['A','B'],source_ids=['S1'],description='TEST ONLY')
        validate(d);self.assertEqual(classify(d)['risk_level'],'RED')

    def test_future_date_rejected(self):
        d=fixture();d['axes'][0]['items'][0]['observed_at']='2099-01-01'
        with self.assertRaises(ValueError):validate(d)

    def test_missing_citations_rejected(self):
        d=fixture();d['axes'][0]['items'][0]['source_ids']=['S99']
        with self.assertRaises(ValueError):validate(d)

    def test_no_evidence_stress_rejected(self):
        d=fixture();d['axes'][0].update(stress=True,event_ids=['test'],items=[])
        with self.assertRaises(ValueError):validate(d)

    def test_legacy_is_not_new_assessment(self):
        d=legacy_view(dict(date='2026-09-27',risk_level='ORANGE',risk_score=3.12,summary='old',metrics=[],sources=[]))
        self.assertIsNone(d['risk_score']);self.assertEqual(d['assessment_state'],'not_revalidated')
        self.assertEqual(d['change'],'unavailable')
        page=build_html(d);self.assertIn('원본 판정 참고',page);self.assertNotIn('3.12',page)

    def test_no_unresolved_template_fields(self):
        page=build_html(classify(fixture()))
        self.assertNotIn('@@',page);self.assertIn('data-layout-revision="2.0.0"',page)
        self.assertEqual(page.count('class="axis-row"'),5)
        self.assertEqual(page.count('class="stage"'),4)
        self.assertEqual(page.count('data-active="true"'),1)

    def test_unknown_has_no_marker(self):
        d=failure_report(date(2026,9,29),ValueError('secret must not leak'),None)
        page=build_html(d)
        self.assertNotIn('data-active="true"',page);self.assertNotIn('secret must not leak',page)

    def test_text_and_json_escape(self):
        d=classify(fixture());d['axes'][0]['explanation']='</script><script>alert(1)</script>'
        page=build_html(d)
        self.assertNotIn('<script>alert(1)</script>',page)
        self.assertIn('\\u003c',page)
        d['sources'][0]['url']='javascript:alert(1)'
        self.assertNotIn('href="javascript:',build_html(d))

    def test_visited_urls_excludes_model_text(self):
        payload={'output':[{'type':'web_search_call','action':{'sources':[{'url':'https://example.com/actual'}]}},
            {'type':'message','content':[{'text':'https://example.com/fake','annotations':[]}]}]}
        self.assertEqual(visited_urls(payload),{'https://example.com/actual'})

    def test_render_only_preserves_archive_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);arch=root/'public/ai-risk/archive/2026/09'
            raw=dict(date='2026-09-27',risk_level='YELLOW',risk_score=2.5,summary='old',metrics=[],sources=[])
            atomic_write(arch/'2026-09-27.json',dump_json(raw));atomic_write(arch/'2026-09-27.html','old bytes')
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in arch.iterdir()}
            data=save_outputs(legacy_view(raw),root=root,render_only=True)
            after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in arch.iterdir()}
            self.assertEqual(before,after);self.assertEqual(data['date'],'2026-09-27')
            self.assertEqual(data['trend']['same_rules_count'],0)

    def test_retention_deletes_html_not_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);today=date(2026,9,29)
            for age in (0,364,365):
                day=today-timedelta(days=age)
                for ext in ('.json','.html'):atomic_write(root/(day.isoformat()+ext),'{}')
            removed=cleanup_old_html(root,today)
            self.assertEqual(len(removed),1);self.assertEqual(len(list(root.glob('*.json'))),3)
            self.assertEqual(len(list(root.glob('*.html'))),2)

    def test_streak_stops_at_missing_day_and_version(self):
        d=classify(fixture());previous=copy.deepcopy(d);previous['date']='2026-09-27'
        data=history_payload([previous],d);self.assertEqual(data['current_level_streak_days'],1)
        self.assertEqual(data['trend']['days_30']['available_count'],2)
        previous['rules_version']='legacy'
        self.assertEqual(history_payload([previous],d)['trend']['same_rules_count'],1)

    def test_monthly_does_not_average_legacy_scores(self):
        d=classify(fixture());old=dict(date='2026-09-27',risk_level='ORANGE',risk_score=3.12)
        monthly=monthly_summary([d,old],'2026-09',date(2026,9,29))
        self.assertNotIn('avg_risk_score',monthly)
        self.assertEqual(monthly['by_rules_version']['legacy']['eligible_count'],0)
        self.assertEqual(monthly['by_rules_version']['1.0']['eligible_count'],1)

    def test_schema_is_strict(self):
        from report_schema import SCHEMA
        def check(node):
            if isinstance(node,dict):
                if node.get('type')=='object':
                    self.assertFalse(node['additionalProperties'])
                    self.assertEqual(set(node['required']),set(node['properties']))
                for child in node.values():check(child)
            elif isinstance(node,list):
                for child in node:check(child)
        check(SCHEMA)


if __name__=='__main__':unittest.main()
