"""未核实船舶申请的待定区。

一条船舶申请在条件解析阶段失败（例如吃水为空）时，它既不能进入排程，
也不能被静默丢弃。这里统一保留原始申请行、来源行号和可读原因，供页面、
导出和后续补正使用。
"""

REASON_TEXT = {
    "MISSING": "数值缺失（如吃水为空）",
    "NUMBER": "数值格式错误",
    "UNIT": "水深单位无效",
    "VESSEL": "船舶条件无效",
    "TIME": "时间格式无效",
    "TIMEZONE": "时间未带时区",
    "INTERVAL": "时间区间无效",
    "VERSION": "版本不是整数",
    "KEY_CONFLICT": "同版本记录冲突",
    "ID_REQUIRED": "缺少船舶编号",
    "NO_SAFE_SLOT": "本轮潮窗内无安全可排窗口",
    "UNKNOWN": "无法核实",
}


def reason_text(code):
    return REASON_TEXT.get(code, code or "UNKNOWN")


def make_item(ident, errors):
    """把同一船舶编号的解析失败记录合并成待定区的一项。

    原因取最新一条失败记录（按来源行号顺序），同时保留全部原申请行。
    """
    errors = sorted(errors, key=lambda error: (error.get("line") is None, error.get("line") or 0))
    lines = []
    rows = []
    reasons = []
    for error in errors:
        if error.get("line") is not None:
            lines.append(error["line"])
        if "raw" in error:
            rows.append(error["raw"])
        reasons.append(error.get("reason") or "UNKNOWN")
    reason = reasons[-1] if reasons else "UNKNOWN"
    return {
        "id": ident,
        "reason": reason,
        "reason_text": reason_text(reason),
        "reasons": sorted(set(reasons)),
        "status": "待定",
        "line": lines[-1] if lines else None,
        "lines": lines,
        "raw": rows[-1] if rows else None,
        "rows": rows,
    }
