from app.report import report
from app.timeops import display

def version_changed(old,new):
    if new<=old:raise ValueError("修订版本必须递增")
    return new-old

def apply(ctx):
    changes=[]
    for effective in ctx["effective"]:
        older=sorted({r["version_value"] for r in ctx["normalized"] if r["kind"]==effective["kind"] and r["id"]==effective["id"] and r["version_value"]<effective["version_value"]})
        delta=version_changed(older[-1],effective["version_value"]) if older else 0
        changes.append({"id":effective["id"],"effective_version":effective["version_value"],"superseded_versions":older,"revision_delta":delta,"status":"REPLACED" if older else "INITIAL","line":effective["line"]})
    ctx["change_log"]=changes
    final=[]
    for r in ctx["checked"]:
        x=dict(r);x["start"]=display(r["start_s"]) if r["start_s"] is not None else "未安排";x["end"]=display(r["end_s"]) if r["end_s"] is not None else "未安排";final.append(x)
    ctx["final"]=final;ctx["blocked"]=bool(ctx["conflicts"]) or any(r["status"]!="SCHEDULED" for r in final)
    return report(changes,修订=sum(r["status"]=="REPLACED" for r in changes),待复核=len(final),结论="阻断" if ctx["blocked"] else "可复核")
