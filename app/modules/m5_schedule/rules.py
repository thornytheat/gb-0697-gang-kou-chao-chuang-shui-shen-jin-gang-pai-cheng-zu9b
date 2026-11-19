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
    assigned=[];occupied=[]
    for ship in ships:
        windows=[(w["start_s"],w["end_s"]) for w in ctx["channel_windows"] if w["id"]==ship["id"]]
        hit=first_fit(windows,pilots,ship["duration"],occupied)
        if hit:occupied.append(hit);assigned.append({"id":ship["id"],"start_s":hit[0],"end_s":hit[1],"status":"SCHEDULED","line":ship["line"]})
        else:assigned.append({"id":ship["id"],"start_s":None,"end_s":None,"status":"NO_SAFE_SLOT","line":ship["line"]})
    ctx["assigned"]=assigned;return report(assigned,已排=sum(r["status"]=="SCHEDULED" for r in assigned),待排=sum(r["status"]!="SCHEDULED" for r in assigned))
