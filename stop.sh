#!/bin/bash
# 停止 AI 测试平台服务
launchctl remove com.lisa.aitest 2>/dev/null
pkill -f "testing-platform/run.py" 2>/dev/null
pkill -f "app.run(host" 2>/dev/null
rm -f "$(dirname "$0")/server.pid"
echo "测试平台服务已停止。"
