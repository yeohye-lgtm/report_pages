"""Strict JSON contract for data-only model output; no model-generated UI."""
def obj(properties):
    return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)
def arr(items):return dict(type='array',items=items)
def string():return dict(type='string')
def nullable():return dict(type=['string','null'])
def enum(values):return dict(type='string',enum=values)
BOOL=dict(type='boolean')
STRINGS=arr(string())
CHANGE=enum(['worse','better','unchanged','unavailable'])
ITEM=obj(dict(label=string(),value=nullable(),note=string(),observed_at=nullable(),comparison=string(),source_ids=STRINGS,included=BOOL))
AXIS=obj(dict(id=enum(['funding','demand','borrower','gpu','contagion']),status=enum(['GREEN','YELLOW','ORANGE','RED','UNKNOWN']),coverage=enum(['sufficient','partial','limited']),meaning=string(),change=CHANGE,explanation=string(),stress=BOOL,cashflow_impact=BOOL,event_ids=STRINGS,items=arr(ITEM)))
SOURCE=obj(dict(id=string(),name=string(),url=string(),published_at=nullable()))
SCHEMA=obj(dict(date=string(),headline=string(),reason=string(),summary=string(),change=CHANGE,changes=STRINGS,changes_note=string(),next_check=string(),investor_view=string(),assessment_reasons=STRINGS,counter_evidence=STRINGS,data_gaps=STRINGS,contagion=string(),axes=arr(AXIS),sources=arr(SOURCE),credit_events=obj(dict(critical_confirmed=BOOL,systemic_confirmed=BOOL,affected_entities=STRINGS,source_ids=STRINGS,description=string()))))
