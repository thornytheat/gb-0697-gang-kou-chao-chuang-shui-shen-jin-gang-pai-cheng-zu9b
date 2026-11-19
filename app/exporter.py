import csv,io,json
from app.pending import reason_text

def evidence_csv(run):
    out=io.StringIO();writer=csv.writer(out)
    writer.writerow(["run_id","sha256","rule_version","kind","line","reason","evidence"])
    state=run.get("state") or {}
    writer.writerow([run["id"],run["digest"],run["rule_version"],"manifest","","",
                     json.dumps({"balance":run["result"]["balance"],"decision":run["decision"],"revision":run["revision"],
                                 "published":bool(state.get("published")),"published_at":state.get("published_at"),
                                 "correction_round":state.get("correction_round",0)},ensure_ascii=False)])
    for row in run["result"].get("final",[]):
        evidence=dict(row,destination=row.get("destination") or ("已排程" if row.get("status")=="SCHEDULED" else "无安全窗"))
        writer.writerow([run["id"],run["digest"],run["rule_version"],"result",row.get("line",""),row.get("status",""),json.dumps(evidence,ensure_ascii=False)])
    for row in run["result"].get("pending",[]):
        evidence=dict(row,destination="待定区",reason_text=row.get("reason_text") or reason_text(row.get("reason")))
        writer.writerow([run["id"],run["digest"],run["rule_version"],"pending",row.get("line",""),row.get("reason",""),json.dumps(evidence,ensure_ascii=False)])
    for entry in state.get("history",[]):
        for diff in entry.get("diffs",[]):
            evidence={"round":entry.get("round"),"at":entry.get("at"),"id":diff.get("id"),
                      "before":diff.get("before"),"after":diff.get("after"),"changed":diff.get("changed"),
                      "frozen_unchanged":entry.get("frozen_unchanged",[])}
            writer.writerow([run["id"],run["digest"],run["rule_version"],"correction",diff.get("after",{}).get("line",""),
                             "CHANGED" if diff.get("changed") else "UNCHANGED",json.dumps(evidence,ensure_ascii=False)])
    for row in run["result"].get("quarantine",[]):
        writer.writerow([run["id"],run["digest"],run["rule_version"],"quarantine",row.get("line",""),row["reason"],json.dumps(row,ensure_ascii=False)])
    return "﻿"+out.getvalue()
