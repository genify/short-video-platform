# T0 证据留痕位置（约定）

本目录存放 **T0 当日** 的真实证据与启动记录。规则：

1. **T0 证据文件**：`t0-evidence-<YYYY-MM-DD>.json`，结构以
   `marketing/data/t0_evidence.template.json` 为准（`pro7_delivered` / `preconditions_all_green` 为布尔 `true`、
   `preconditions` ≥ 8 条且每条附**真实**证据链接、`evidence_date` 非空）。
2. **启动记录**：`t0-startup-<YYYY-MM-DD>.log`，含 `landing_deploy.sh start` 的启动输出与
   `--phase t0 --t0-evidence <证据文件>` 的启动行。
3. **不得**把模板本身或任何演练件当作证据；演练件一律写在临时目录（见
   `marketing/scripts/t0_evidence_drill.py`）。
4. **门禁能力边界**：`--phase t0` 的前置校验只验**证据信封**（结构完整性），**不验**证据内容真伪 ——
   真实性由本目录的留档 + 人工复核负责。
5. T0 由 PRO-7 交付触发；T0 前本目录应为空（当前为空）。
