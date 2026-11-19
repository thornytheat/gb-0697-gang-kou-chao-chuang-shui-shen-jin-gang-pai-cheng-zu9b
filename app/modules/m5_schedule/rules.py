from app.modules.m4_channel.rules import subtract
from app.report import report

def first_fit(windows,pilots,duration,occupied):
    candidates=[]
    for a,b in windows:
        for p,q in pilots:
            lo,hi=max(a,p),min(b,q)
            if lo<hi:
                for x,y in subtract((lo,hi),occupied):
                    if y-x>=duration:candidates.append((x,x+duration))
    return min(candidates) if candidates else None

def apply(ctx):
    pilots=[(r["a"],r["b"]) for r in ctx["effective"] if r["kind"]=="pilot"]
    ships=sorted((r for r in ctx["effective"] if r["kind"]=="ship"),key=lambda r:(r["a"],r["id"]))
    # 已发布的船位冻结：先占位，后补船舶只能绕开它们，不能改动它们。
    frozen=ctx.get("frozen") or {}
    assigned=[];occupied=[]
    for ident,slot in sorted(frozen.items()):
        if slot.get("status")=="SCHEDULED":
            occupied.append((slot["start_s"],slot["end_s"]))
    pending=list(ctx.get("pending") or [])
    for ship in ships:
        if ship["id"] in frozen:
            slot=frozen[ship["id"]]
            assigned.append({"id":ship["id"],"start_s":slot.get("start_s"),"end_s":slot.get("end_s"),
                             "status":slot.get("status","SCHEDULED"),"line":ship["line"],
                             "published":slot.get("published",True),"locked":True})
            continue
        windows=[(w["start_s"],w["end_s"]) for w in ctx["channel_windows"] if w["id"]==ship["id"]]
        hit=first_fit(windows,pilots,ship["duration"],occupied)
        if hit:
            occupied.append(hit)
            assigned.append({"id":ship["id"],"start_s":hit[0],"end_s":hit[1],"status":"SCHEDULED","line":ship["line"],"published":False})
        else:
            assigned.append({"id":ship["id"],"start_s":None,"end_s":None,"status":"NO_SAFE_SLOT","line":ship["line"],"published":False})
    seen=set();unique=[]
    for item in pending:
        if item["id"] in seen or item["id"] in frozen:continue
        seen.add(item["id"]);unique.append(item)
    # 已发布船舶即使本次输入里找不到有效行，也要保留其冻结船位，不能从计划里消失。
    scheduled={row["id"] for row in assigned}
    for ident,slot in sorted(frozen.items()):
        if ident not in scheduled:
            assigned.append({"id":ident,"start_s":slot.get("start_s"),"end_s":slot.get("end_s"),
                             "status":slot.get("status","SCHEDULED"),"line":slot.get("line"),
                             "published":slot.get("published",True),"locked":True})
    # 待定区只收未核实的申请；数据有效但无安全窗的船留在排程结果里。
    for item in unique:
        item.setdefault("category","UNVERIFIED")
    ctx["pending"]=sorted(unique,key=lambda p:p["id"])
    ctx["assigned"]=assigned
    return report(assigned,已排=sum(r["status"]=="SCHEDULED" for r in assigned),
                  待排=sum(r["status"]!="SCHEDULED" for r in assigned),冻结=len(frozen))
