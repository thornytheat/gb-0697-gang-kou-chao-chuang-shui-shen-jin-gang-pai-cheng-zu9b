from app.numbers import number
from app.report import report,quarantine
from app.errors import BusinessError
from app.timeops import instant
from decimal import Decimal

def depth(value,unit):
    if unit not in {"m","cm"}:raise BusinessError("UNIT","水深单位无效")
    return number(value)/(100 if unit=="cm" else 1)

def apply(ctx):
    rows=[]
    for r in ctx["raw"]:
        try:
            x=dict(r);x["a"]=instant(r["start"]);x["b"]=instant(r["end"]) if r["end"] else x["a"]
            x["version_value"]=int(r["version"])
            if r["kind"] not in {"tide","ship","pilot","block"}:raise BusinessError("KIND","记录类型无效")
            if r["kind"]!="tide" and x["b"]<=x["a"]:raise BusinessError("INTERVAL","结束须晚于开始")
            x["depth"]=depth(r["value"],r["unit"])
            x["duration"]=number(r["aux"])*60 if r["kind"]=="ship" else Decimal(0)
            if r["kind"]=="ship" and (x["depth"]<=0 or x["duration"]<=0):raise BusinessError("VESSEL","船舶条件无效")
            rows.append(x)
        except (BusinessError,ValueError) as e:quarantine(ctx,r,getattr(e,"code","VERSION"))
    latest={}
    for x in rows:
        key=(x["kind"],x["id"])
        if key not in latest or x["version_value"]>latest[key]["version_value"]:latest[key]=x
    observations={}
    for r in latest.values():
        if r["kind"]=="tide":observations.setdefault(r["a"],[]).append(r)
    removed=set();conflict_times=[]
    for time,group in observations.items():
        if len({r["depth"] for r in group})>1:
            conflict_times.append(time)
            for r in group:
                quarantine(ctx,r,"TIDE_TIME_CONFLICT");removed.add((r["kind"],r["id"]))
        elif len(group)>1:
            for r in sorted(group,key=lambda x:x["id"])[1:]:
                quarantine(ctx,r,"DUPLICATE_OBSERVATION");removed.add((r["kind"],r["id"]))
    effective=[r for key,r in latest.items() if key not in removed]
    ctx["tide_conflict_times"]=conflict_times
    ctx["normalized"]=rows;ctx["effective"]=effective
    return report(ctx["effective"],船舶=sum(r["kind"]=="ship" for r in effective),有效版本=len(effective))
