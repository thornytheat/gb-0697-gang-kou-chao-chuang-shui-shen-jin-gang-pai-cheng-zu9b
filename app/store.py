import sqlite3, json, hashlib, csv, io
from decimal import Decimal
from datetime import datetime, timezone
from app.config import DATA_DIR, RULE_VERSION
from app.errors import BusinessError
from app.reader import read_rows
from app.pipeline import execute, finish

FIELDS="id kind start end value aux version unit".split()
SHIP_FIELDS=FIELDS

def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"runs.sqlite", timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, decision TEXT NOT NULL DEFAULT '待复核', created TEXT NOT NULL)")
    columns={row[1] for row in db.execute("PRAGMA table_info(runs)")}
    if "source" not in columns: db.execute("ALTER TABLE runs ADD COLUMN source TEXT")
    if "state" not in columns: db.execute("ALTER TABLE runs ADD COLUMN state TEXT")
    db.execute("CREATE TABLE IF NOT EXISTS aliases (digest TEXT PRIMARY KEY, run_id TEXT NOT NULL)")
    return db

def _now(): return datetime.now(timezone.utc).isoformat()

def _initial_state(): return {"published":False,"published_at":None,"frozen":{},"history":[],"correction_round":0}

def _state(row):
    raw=row["state"] if "state" in row.keys() else None
    if not raw: return _initial_state()
    state=json.loads(raw)
    state.setdefault("published",False);state.setdefault("frozen",{})
    state.setdefault("history",[]);state.setdefault("correction_round",0)
    return state

def _decimal_slot(slot):
    value=dict(slot)
    for key in ("start_s","end_s"):
        if value.get(key) is not None: value[key]=Decimal(str(value[key]))
    return value

def frozen_for_run(state):
    return {ident:_decimal_slot(slot) for ident,slot in (state.get("frozen") or {}).items()}

def _scheduled_slots(result,published=True):
    return {row["id"]:{"start_s":row["start_s"],"end_s":row["end_s"],"status":"SCHEDULED",
                       "line":row.get("line"),"published":published}
            for row in result.get("assigned",[]) if row.get("status")=="SCHEDULED" and row.get("start_s") is not None}

def _alias(db,digest):
    row=db.execute("SELECT run_id FROM aliases WHERE digest=?",(digest,)).fetchone()
    if row is None: return None
    return row[0]

def save(text, result):
    digest=hashlib.sha256((RULE_VERSION+"\n"+text).encode()).hexdigest()
    ident=digest[:16]
    state=_initial_state()
    state["pending_visible"]=[item["id"] for item in result.get("pending",[])]
    with connect() as db:
        # 补正后的文本再次提交也归到原批次：不新建批次、不重复占道。
        existing=_alias(db,digest)
        if existing is not None and db.execute("SELECT 1 FROM runs WHERE id=?",(existing,)).fetchone():
            ident=existing
        else:
            db.execute("INSERT OR IGNORE INTO runs(id,digest,result,created,source,state) VALUES(?,?,?,?,?,?)",
                       (ident,digest,json.dumps(dict(result,rule_version=RULE_VERSION),ensure_ascii=False),_now(),text,json.dumps(state)))
            db.execute("INSERT OR IGNORE INTO aliases(digest,run_id) VALUES(?,?)",(digest,ident))
    return get(ident)

def get(ident):
    with connect() as db:
        row=db.execute("SELECT * FROM runs WHERE id=?",(ident,)).fetchone()
    if row is None: raise BusinessError("NOT_FOUND","批次不存在",404)
    item=dict(row);item["result"]=json.loads(item["result"]);item["state"]=_state(row)
    item["rule_version"]=item["result"].get("rule_version","2026.11.18.1")
    return item

def history():
    with connect() as db:
        rows=[dict(r) for r in db.execute("SELECT id,revision,decision,created,state FROM runs ORDER BY created DESC LIMIT 40")]
    for row in rows:
        state=json.loads(row.pop("state") or "{}")
        row["published"]=bool(state.get("published"))
        row["pending"]=len(state.get("pending_visible",[])) if "pending_visible" in state else None
    return rows

def _load(ident):
    return get(ident)

def publish(ident, revision):
    current=_load(ident);state=current["state"];result=current["result"]
    if state.get("published"):
        if revision!=current["revision"]: raise BusinessError("STALE","版本已更新，请刷新",409)
        return current
    if revision!=current["revision"]: raise BusinessError("STALE","版本已更新，请刷新",409)
    if result.get("blocked"):
        raise BusinessError("BLOCKED","存在未排船舶或航道冲突，请先修正",409)
    frozen=_scheduled_slots(result,published=True)
    new_state=dict(state,published=True,published_at=_now(),frozen=frozen,
                   pending_visible=[item["id"] for item in result.get("pending",[])])
    source=current.get("source")
    if source is None: raise BusinessError("NO_SOURCE","批次缺少原始输入，无法发布",409)
    rebuilt=finish(execute(source,frozen_for_run(new_state)))
    rebuilt["published"]=True
    with connect() as db:
        changed=db.execute("UPDATE runs SET revision=revision+1,decision=?,result=?,state=? WHERE id=? AND revision=?",
                           ("已发布",json.dumps(dict(rebuilt,rule_version=RULE_VERSION),ensure_ascii=False),json.dumps(new_state,ensure_ascii=False),ident,revision)).rowcount
        if not changed: raise BusinessError("STALE","版本已更新，请刷新",409)
    return get(ident)

def _corrected_header(source):
    try:
        return list(csv.reader(io.StringIO(source.lstrip("﻿"))))
    except csv.Error:
        raise BusinessError("CORRECTION_INVALID","原批次输入结构无法补正")

def _merge_source(source, corrections):
    """只替换本次补正的船舶行，其余输入原样保留；版本不同则作为新版本追加。"""
    rows=_corrected_header(source)
    if not rows: raise BusinessError("BLANK_FILE","文件只有空行")
    header=[cell.strip() for cell in rows[0]]
    if set(header)!=set(SHIP_FIELDS) or len(header)!=len(SHIP_FIELDS):
        raise BusinessError("CORRECTION_INVALID","原批次输入表头无法补正")
    width=len(header);index={name:header.index(name) for name in SHIP_FIELDS}
    kept=[header]
    for cells in rows[1:]:
        if len(cells)==width and cells!=header:
            kept.append([cell.strip() for cell in cells])
        else:
            kept.append(cells)
    appended=[]
    for correction in corrections:
        target=None
        for position,cells in enumerate(kept[1:],1):
            if len(cells)==width and cells[index["id"]]==correction["id"] and cells[index["kind"]]=="ship" and cells[index["version"]]==correction["version"]:
                target=position
        if target is not None:
            kept[target]=[correction.get(field,"") for field in header]
        else:
            appended.append([correction.get(field,"") for field in header])
    out=io.StringIO();writer=csv.writer(out,lineterminator="\n")
    for cells in kept: writer.writerow(cells)
    for cells in appended: writer.writerow(cells)
    return out.getvalue()

def _after_state(ident, result):
    for item in result.get("pending",[]):
        if item["id"]==ident:
            return {"status":"待定","destination":"待定","reason":item["reason"],"reason_text":item["reason_text"],
                    "raw":item.get("raw"),"line":item.get("line")}
    for row in result.get("final",[]):
        if row.get("id")==ident:
            return {"status":row.get("status"),"destination":row.get("destination"),
                    "start_s":row.get("start_s"),"end_s":row.get("end_s"),
                    "start":row.get("start"),"end":row.get("end"),"line":row.get("line")}
    return {"status":"MISSING","destination":"缺失"}

def correct(ident, revision, text):
    current=_load(ident)
    if revision!=current["revision"]: raise BusinessError("STALE","版本已更新，请刷新",409)
    source=current.get("source")
    if source is None: raise BusinessError("NO_SOURCE","批次缺少原始输入，无法补正",409)
    state=current["state"];result=current["result"]
    rows,bad,blank=read_rows(text,SHIP_FIELDS)
    if bad: raise BusinessError("CORRECTION_INVALID","补正行结构错误，请按表头补齐列数")
    canonical=[list(row.get(field,"") for field in SHIP_FIELDS) for row in rows]
    ids=[]
    for row in rows:
        if row["kind"]!="ship":
            raise BusinessError("CORRECTION_SCOPE",f"补正只能提交船舶申请：{row['id']}")
        if row["id"] in ids:
            raise BusinessError("CORRECTION_DUPLICATE","同一船舶请只提交一行补正")
        ids.append(row["id"])
    if not ids: raise BusinessError("CORRECTION_EMPTY","补正内容为空")
    # 同一补正内容重放不产生新轮次，也不再次占道：先于待定区为空判断返回原批次。
    for entry in state.get("history",[]):
        if entry.get("ids")==ids and entry.get("rows")==canonical:
            return current
    pending_ids={item["id"] for item in result.get("pending",[])}
    if not pending_ids: raise BusinessError("NO_PENDING","该批次没有待定船舶",409)
    for ident_row in ids:
        if ident_row not in pending_ids:
            raise BusinessError("CORRECTION_SCOPE",f"补正只能提交待定区船舶：{ident_row}")
    merged=_merge_source(source,rows)
    digest=hashlib.sha256((RULE_VERSION+"\n"+merged).encode()).hexdigest()
    if any(entry.get("digest")==digest for entry in state.get("history",[])):
        return current
    # 已发布船位和此前补正已落定的船位都冻结；补正只能落在空档上。
    frozen=dict(state.get("frozen") or {})
    before={item["id"]:{"status":"待定","destination":"待定","reason":item["reason"],"reason_text":item["reason_text"],
                        "raw":item.get("raw"),"line":item.get("line")} for item in result.get("pending",[]) if item["id"] in set(ids)}
    rebuilt=finish(execute(merged,frozen_for_run({"frozen":frozen})))
    rebuilt["published"]=bool(state.get("published"))
    # 已有船位继续锁定（含此前补正成功的船），后续补正只能落在空档上。
    locked=dict(frozen)
    for ident_row,slot in _scheduled_slots(rebuilt,published=False).items():
        if ident_row not in locked: locked[ident_row]=slot
    for group in ("assigned","checked","final"):
        for row in rebuilt.get(group,[]):
            if row.get("id") in locked: row["locked"]=True
    diffs=[]
    for ship in ids:
        after=_after_state(ship,rebuilt)
        old=before[ship]
        changed=(old.get("status")!=after.get("status") or old.get("reason")!=after.get("reason")
                 or old.get("raw")!=after.get("raw") or old.get("start_s")!=after.get("start_s"))
        diffs.append({"id":ship,"before":old,"after":after,"changed":changed})
    round_no=int(state.get("correction_round",0))+1
    entry={"round":round_no,"at":_now(),"digest":digest,"ids":ids,"rows":canonical,"diffs":diffs,
           "frozen_unchanged":sorted(frozen.keys())}
    new_state=dict(state,frozen=locked,correction_round=round_no,
                   history=list(state.get("history",[]))+[entry],
                   pending_visible=[item["id"] for item in rebuilt.get("pending",[])])
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO aliases(digest,run_id) VALUES(?,?)",(digest,ident))
        changed=db.execute("UPDATE runs SET revision=revision+1,result=?,state=?,source=? WHERE id=? AND revision=?",
                           (json.dumps(dict(rebuilt,rule_version=RULE_VERSION),ensure_ascii=False),json.dumps(new_state,ensure_ascii=False),merged,ident,revision)).rowcount
        if not changed: raise BusinessError("STALE","版本已更新，请刷新",409)
    return get(ident)

def review(ident,revision,decision):
    if not isinstance(decision,str) or decision not in {"通过","退回"}: raise BusinessError("DECISION","复核决定无效")
    current=get(ident)
    if decision=="通过" and current["result"].get("blocked"):
        raise BusinessError("BLOCKED","存在阻断项，请先修正数据",409)
    with connect() as db:
        changed=db.execute("UPDATE runs SET revision=revision+1,decision=? WHERE id=? AND revision=?",(decision,ident,revision)).rowcount
        if not changed: raise BusinessError("STALE","版本已更新，请刷新",409)
    return get(ident)
