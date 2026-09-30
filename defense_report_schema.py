"""Defense risk strict model-output schema."""
def obj(p): return {"type":"object","properties":p,"required":list(p),"additionalProperties":False}
def arr(i): return {"type":"array","items":i}
S=lambda:{"type":"string"}; NS=lambda:{"type":["string","null"]}; N=lambda:{"type":["number","null"]}; B={"type":"boolean"}
LEVEL={"type":"string","enum":["GREEN","YELLOW","ORANGE","RED","UNKNOWN"]}; CHANGE={"type":"string","enum":["worse","better","unchanged","unavailable"]}
SOURCE=obj({"id":S(),"name":S(),"url":S(),"published_at":NS()})
ITEM=obj({"label":S(),"value":NS(),"observed_at":NS(),"note":S(),"source_ids":arr(S()),"included":B})
AXIS=obj({"id":{"type":"string","enum":["orders","budget","execution","profitability"]},"status":LEVEL,"coverage":{"type":"string","enum":["sufficient","partial","limited"]},"change":CHANGE,"meaning":S(),"stress":B,"event_ids":arr(S()),"items":arr(ITEM)})
HOLDING=obj({"id":{"type":"string","enum":["hanwha_aerospace","lig_nex1"]},"name":S(),"status":LEVEL,"change":CHANGE,"reason":S(),"event_ids":arr(S()),"items":arr(ITEM)})
PRICE=obj({"as_of":S(),"hanwha_close":N(),"hanwha_high_52w":N(),"hanwha_drawdown_pct":N(),"lig_close":N(),"lig_high_52w":N(),"lig_drawdown_pct":N(),"defense_etf_close":N(),"kospi_close":N(),"hanwha_eps_2026":N(),"hanwha_per_2026":N(),"lig_eps_2026":N(),"lig_per_2026":N(),"interpretation":S(),"source_ids":arr(S())})
EVENT=obj({"id":S(),"date":S(),"target":{"type":"string","enum":["industry","hanwha_aerospace","lig_nex1","market"]},"direction":{"type":"string","enum":["positive","negative","mixed"]},"title":S(),"summary":S(),"source_ids":arr(S())})
SCHEMA=obj({"date":S(),"headline":S(),"reason":S(),"next_check":S(),"investor_view":S(),"industry_axes":arr(AXIS),"holdings":arr(HOLDING),"price":PRICE,"events":arr(EVENT),"sources":arr(SOURCE),"data_gaps":arr(S())})
