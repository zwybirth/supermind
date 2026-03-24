#!/bin/bash
# SuperMind 快速启动脚本

cd "$(dirname "$0")/.."

echo "🧠 SuperMind 启动中..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 运行主程序
python3 src/main.py "$@"
