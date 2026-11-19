from app.report import report

def overlaps(rows):
    ordered=sorted((r["start_s"],r["end_s"],r["id"]) for r in rows if r["status"]=="SCHEDULED")
    return [(a[2],b[2]) for a,b in zip(ordered,ordered[1:]) if a[1]>b[0]]

def apply(ctx):
    conflicts=overlaps(ctx["assigned"]);ctx["conflicts"]=conflicts
    ctx["balance"]={"input":ctx["input_count"],"accepted":ctx["input_count"]-len(ctx["quarantine"])-ctx["blank_rows"],"quarantined":len(ctx["quarantine"]),"blank":ctx["blank_rows"]}
    rows=[dict(r,check="CONFLICT" if any(r["id"] in c for c in conflicts) else "CLEAR") for r in ctx["assigned"]]
    ctx["checked"]=rows;return report(rows,排程冲突=len(conflicts),船舶=len(rows))
