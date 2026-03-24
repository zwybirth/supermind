#!/bin/bash
# 一键启用 SuperMind 自动集成

echo "🧠 SuperMind 一键启用"
echo "======================"
echo ""

SUPERMIND_DIR="${HOME}/.openclaw/workspace/skills/supermind"

# 1. 检查 SuperMind 是否存在
if [ ! -d "${SUPERMIND_DIR}" ]; then
    echo "❌ SuperMind 未安装"
    echo "   请先构建 SuperMind 系统"
    exit 1
fi

echo "✓ SuperMind 已安装"

# 2. 设置环境变量
export SUPERMIND_AUTO=1
export SUPERMIND_MODE=auto
export SUPERMIND_PATH="${SUPERMIND_DIR}"
export PYTHONPATH="${PYTHONPATH}:${SUPERMIND_DIR}/src"

echo "✓ 环境变量已设置"

# 3. 检查 Ollama
if ! pgrep -f "ollama" > /dev/null; then
    echo "⚠️  Ollama 未运行，正在启动..."
    ollama serve &
    sleep 2
fi

if pgrep -f "ollama" > /dev/null; then
    echo "✓ Ollama 运行中"
else
    echo "❌ Ollama 启动失败"
    echo "   请手动运行: ollama serve"
    exit 1
fi

# 4. 检查模型
if ! ollama list | grep -q "qwen"; then
    echo "⬇️  正在拉取模型..."
    ollama pull qwen3.5-35b-a3b
fi

echo "✓ 模型就绪"

# 5. 创建快捷方式
cat > /tmp/supermind_activate.sh << 'EOF'
#!/bin/bash
export SUPERMIND_AUTO=1
export SUPERMIND_MODE=auto
export SUPERMIND_PATH="${HOME}/.openclaw/workspace/skills/supermind"
export PYTHONPATH="${PYTHONPATH}:${SUPERMIND_PATH}/src"
echo "🧠 SuperMind 自动模式已激活"
echo "   现在你的所有对话都会经过 SuperMind 增强！"
EOF

echo ""
echo "=============================="
echo "✅ SuperMind 自动集成已启用！"
echo ""
echo "🚀 使用方法:"
echo "   1. 在当前终端运行:"
echo "      source /tmp/supermind_activate.sh"
echo ""
echo "   2. 或者添加到 ~/.zshrc 或 ~/.bashrc:"
echo "      export SUPERMIND_AUTO=1"
echo "      export SUPERMIND_MODE=auto"
echo ""
echo "   3. 直接测试:"
echo "      python ${SUPERMIND_DIR}/src/supermind_api.py"
echo ""
echo "💡 快捷命令:"
echo "   /sm-ask <问题>     - 知识问答"
echo "   /sm-code <需求>    - 代码生成"
echo "   /sm-do <任务>      - 执行任务"
echo "   /sm-stats          - 查看统计"
echo ""
echo "⚙️  切换模式:"
echo "   export SUPERMIND_MODE=auto    # 自动判断"
echo "   export SUPERMIND_MODE=simple  # 仅RAG增强"
echo "   export SUPERMIND_MODE=always  # 完全模式"
echo ""
echo "⏹️  临时关闭:"
echo "   export SUPERMIND_AUTO=0"
echo ""
