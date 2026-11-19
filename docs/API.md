# 接口

`POST /api/run`：{"text":"CSV内容"}。同规则版本与输入摘要只产生一条批次。

`GET/POST /api/1` 至 `/api/7`：独立样例或自定义文件计算。各模块返回 report、quarantine、balance。

`POST /api/publish`：{"id":"批次","revision":整数}。把当前已排船位冻结为发布计划；存在未排船舶或航道冲突时409 `BLOCKED`。重复提交同一版本是幂等的，不会重复占道。旧版本409。

`POST /api/correct`：{"id":"批次","revision":整数,"text":"补正CSV"}。只能提交待定区内的船舶行；越界、重复船舶或补正后仍属待定都会被拒绝。补正只替换对应船舶行，已发布船位保持原时刻；成功后 revision 递增并记录一轮前后差异。同一内容重复提交不新增轮次、不重复占道。旧版本409，待定区为空409 `NO_PENDING`。

`POST /api/review`：id、整数revision、decision取通过或退回。旧版本409；阻断项不能通过。

`GET /api/export/{id}`：唯一证据CSV，含 manifest（发布状态、补正轮次）、result（每船去向）、pending（待定原因与原申请行）、correction（补正前后差异）、quarantine。`GET /health`：存活检查。

错误：结构/数值422，版本冲突409，不存在404，文件过大413。逐行异常进入quarantine；船舶申请无法核实（如吃水为空）同时进入 `result.pending`，保留原申请行与来源行号。
