#!/bin/bash
# 双击打开浏览器控制面板
cd "$(dirname "$0")"
PORT=5001
if [ -f "auth/web_port.txt" ]; then
  PORT=$(cat auth/web_port.txt 2>/dev/null | tr -d '[:space:]')
fi
# 兜底：如果指定端口没响应，回退到 5001
if ! curl -sf "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1; then
  for P in 5001 5002 5003 5004 5005; do
    if curl -sf "http://127.0.0.1:$P/api/status" >/dev/null 2>&1; then
      PORT=$P
      break
    fi
  done
fi
open "http://localhost:$PORT"
