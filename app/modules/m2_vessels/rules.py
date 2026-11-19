from app.numbers import number
from app.report import report,quarantine
from app.errors import BusinessError
from app.timeops import instant
from app.pending import make_item
from decimal import Decimal

def depth(value,unit):
    if unit not in {"m","cm"}:raise BusinessError("UNIT","水深单位无效")
    return number(value)/(100 if unit=="cm" else 1)

def apply(ctx):
    rows=[];failed_ships={}
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
        except (BusinessError,ValueError) as e:
            code=getattr(e,"code","VERSION")
            quarantine(ctx,r,code)
            # 未核实的船舶申请进入待定区，而不是在排程里消失。
            if r.get("kind")=="ship" and r.get("id"):
                failed_ships.setdefault(r["id"],[]).append({"line":r.get("line"),"reason":code,"raw":dict(r)})
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
    # 失败的最新申请不能被旧版本悄悄顶替：若失败记录的版本不低于当前有效版本，
    # 或版本无法判定、整船没有有效版本，则该船整船待定，不参与排程。
    effective_versions={r["id"]:r["version_value"] for r in effective if r["kind"]=="ship"}
    pending=[];pending_ids=set()
    for ident,errors in failed_ships.items():
        newest=effective_versions.get(ident)
        if newest is None:
            pending.append(make_item(ident,errors));pending_ids.add(ident);continue
        failed_versions=[]
        for error in errors:
            try:failed_versions.append(int(error["raw"]["version"]))
            except (TypeError,ValueError):failed_versions.append(None)
        if any(v is None or v>=newest for v in failed_versions):
            pending.append(make_item(ident,errors));pending_ids.add(ident)
    if pending_ids:
        effective=[r for r in effective if not (r["kind"]=="ship" and r["id"] in pending_ids)]
    pending.sort(key=lambda p:p["id"])
    ctx["tide_conflict_times"]=conflict_times
    ctx["normalized"]=rows;ctx["effective"]=effective;ctx["pending"]=pending
    return report(ctx["effective"],船舶=sum(r["kind"]=="ship" for r in effective),有效版本=len(effective),待定=len(pending))
