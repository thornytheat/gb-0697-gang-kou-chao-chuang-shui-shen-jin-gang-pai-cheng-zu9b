from decimal import Decimal
from app.report import report

def safe_segment(a,b,ha,hb,threshold):
    if b<=a or b-a>10800:return None
    if ha>=threshold and hb>=threshold:return (a,b)
    if ha<threshold and hb<threshold:return None
    cross=a+(threshold-ha)*(b-a)/(hb-ha)
    return (cross,b) if hb>ha else (a,cross)

def windows(points,threshold,conflicts=()):
    out=[]
    for (a,ha),(b,hb) in zip(points,points[1:]):
        if any(a<=t<=b for t in conflicts):continue
        hit=safe_segment(a,b,ha,hb,threshold)
        if hit and hit[0]<hit[1]:
            if out and out[-1][1]==hit[0]:out[-1]=(out[-1][0],hit[1])
            else:out.append(hit)
    return out

def apply(ctx):
    points=sorted((r["a"],r["depth"]) for r in ctx["effective"] if r["kind"]=="tide")
    out=[]
    for ship in (r for r in ctx["effective"] if r["kind"]=="ship"):
        threshold=ship["depth"]+Decimal(1)-Decimal(8)
        for a,b in windows(points,threshold,ctx.get("tide_conflict_times",[])):
            a,b=max(a,ship["a"]),min(b,ship["b"])
            if a<b:out.append({"id":ship["id"],"start_s":a,"end_s":b,"threshold_m":threshold,"duration":ship["duration"],"line":ship["line"]})
    ctx["tide_windows"]=out;return report(out,潮窗=len(out),基准水深="8m",余量="1m")
