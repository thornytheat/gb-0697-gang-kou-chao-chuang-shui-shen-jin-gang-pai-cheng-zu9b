from app.report import report

def subtract(interval,blocks):
    fragments=[interval]
    for ba,bb in sorted(blocks):
        new=[]
        for a,b in fragments:
            if bb<=a or ba>=b:new.append((a,b));continue
            if a<ba:new.append((a,ba))
            if bb<b:new.append((bb,b))
        fragments=new
    return fragments

def apply(ctx):
    blocks=[(r["a"],r["b"]) for r in ctx["effective"] if r["kind"]=="block"];out=[]
    for w in ctx["tide_windows"]:
        for a,b in subtract((w["start_s"],w["end_s"]),blocks):out.append(dict(w,start_s=a,end_s=b))
    ctx["channel_windows"]=out;return report(out,可用窗口=len(out),占用=len(blocks))
