from app.reader import read_rows
from app.report import report,quarantine
FIELDS="id kind start end value aux version unit".split()
def apply(ctx):
    rows,bad,blank=read_rows(ctx["text"],FIELDS);ctx["quarantine"].extend(bad);ctx["blank_rows"]=blank;ctx["input_count"]=len(rows)+len(bad)+blank
    kept=[];seen=set()
    for r in rows:
        key=(r["kind"],r["id"],r["version"])
        if not r["id"]:quarantine(ctx,r,"ID_REQUIRED");continue
        if key in seen:quarantine(ctx,r,"KEY_CONFLICT");continue
        seen.add(key);kept.append(r)
    ctx["raw"]=kept;return report(kept,接收=len(kept),隔离=len(ctx["quarantine"]))
