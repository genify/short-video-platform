#!/usr/bin/env bash
# 落地页部署助手（PRO-24 上线整合）——启动 / 停止 / 状态 / 空库重建 / 冒烟调用。
#
# 装置事实：marketing/landing/app.py 是**纯标准库** HTTP 服务，无第三方依赖，
# 因此部署 = 「用固定参数把该进程跑起来 + 用一个可访问 URL 指向它」。本脚本只做这件事，
# 并把 pid / 日志 / 数据库统一放在 marketing/out/ 下（均被 .gitignore 覆盖，不入版本控制）。
#
# 用法：
#   base=marketing/scripts/landing_deploy.sh
#   $base start          启动（幂等：已运行则直接报状态）
#   $base stop           停止
#   $base status         打印 pid / 监听 / /api/health
#   $base fresh-db       停止 → 把当前库改名留档 → 用空库重启（样本门分母只含真实访客）
#   $base smoke-readonly 只读冒烟（不写事件）
#   $base smoke-live     真实 GET 冒烟（⚠️ 写 2 条 page_view，仅用于部署验收）
#
# 环境变量：PD_HOST(默认 0.0.0.0) PD_PORT(默认 8088) PD_DB PD_BASE_URL PD_PHASE(默认 pre_t0)
# 硬门：不得以 PD_PHASE=t0 启动（T0 证据门禁 exit 3；T0 由 PRO-7 交付触发）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${PY:-python3}"
HOST="${PD_HOST:-0.0.0.0}"
PORT="${PD_PORT:-8088}"
PHASE="${PD_PHASE:-pre_t0}"
DB="${PD_DB:-$ROOT/marketing/out/landing.prod.sqlite3}"
BASE_URL="${PD_BASE_URL:-http://127.0.0.1:$PORT}"
OUT="$ROOT/marketing/out"
LOG="$OUT/landing.prod.log"
PIDFILE="$OUT/landing.prod.pid"
APP="$ROOT/marketing/landing/app.py"

running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

case "${1:-}" in
  start)
    if running; then
      echo "[deploy] 已在运行：pid=$(cat "$PIDFILE")"; exit 0
    fi
    if [ "$PHASE" = "t0" ]; then
      echo "[deploy] 拒绝：不得以 --phase t0 启动（T0 证据门禁，exit 3）。T0 由 PRO-7 交付触发。" >&2
      exit 3
    fi
    mkdir -p "$OUT"
    cd "$ROOT"
    nohup setsid "$PY" -u "$APP" --host "$HOST" --port "$PORT" --db "$DB" \
      --phase "$PHASE" --base-url "$BASE_URL" >> "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 1.5
    if running; then
      echo "[deploy] 已启动 pid=$(cat "$PIDFILE") phase=$PHASE db=$DB base=$BASE_URL"
      echo "[deploy] 日志：$LOG"
      echo "[deploy] 启动输出（末 20 行）："; tail -n 20 "$LOG" || true
    else
      echo "[deploy] 启动失败：进程已退出。启动输出（末 20 行）：" >&2
      tail -n 20 "$LOG" >&2 || true
      exit 1
    fi
    ;;
  stop)
    if running; then
      pid="$(cat "$PIDFILE")"; kill "$pid" 2>/dev/null || true; sleep 1
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
      rm -f "$PIDFILE"; echo "[deploy] 已停止 pid=$pid"
    else
      echo "[deploy] 未运行（无 pid 文件或进程不存在）"
    fi
    ;;
  status)
    if running; then
      echo "[deploy] running pid=$(cat "$PIDFILE") host=$HOST port=$PORT phase=$PHASE db=$DB"
      curl -sS -m 5 "http://127.0.0.1:$PORT/api/health" || true; echo
    else
      echo "[deploy] not running"; exit 1
    fi
    ;;
  fresh-db)
    "$0" stop || true
    if [ -f "$DB" ]; then
      stamp="$(date -u +%Y%m%dT%H%M%SZ)"
      mv "$DB" "$OUT/landing.smoke-archive-$stamp.sqlite3"
      echo "[deploy] 旧库已改名留档：marketing/out/landing.smoke-archive-$stamp.sqlite3"
    fi
    PD_DB="$DB" "$0" start
    echo "[deploy] 空库重建完成（样本门分母现在只含后续真实访客）"
    ;;
  smoke-readonly)
    cd "$ROOT"; "$PY" marketing/scripts/landing_smoke.py --mode readonly --base "http://127.0.0.1:$PORT"
    ;;
  smoke-live)
    cd "$ROOT"; "$PY" marketing/scripts/landing_smoke.py --mode live --base "http://127.0.0.1:$PORT"
    ;;
  *)
    sed -n '2,20p' "$0"; exit 1
    ;;
esac
