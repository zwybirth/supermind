#!/bin/bash
# SuperMind 自动集成安装脚本
# 让 OpenClaw 自动使用 SuperMind 作为后端

set -e

SUPERMIND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OPENCLAW_DIR="${HOME}/.openclaw"
WORKSPACE_DIR="${OPENCLAW_DIR}/workspace"

echo "🧠 SuperMind 自动集成安装"
echo "=============================="
echo ""

# 1. 检查 SuperMind 是否已初始化
echo "📦 检查 SuperMind 状态..."
if [ ! -d "${SUPERMIND_DIR}/data" ]; then
    echo "  SuperMind 未初始化，先运行初始化..."
    cd "${SUPERMIND_DIR}"
    python3 scripts/init.py
fi
echo "  ✓ SuperMind 已就绪"
echo ""

# 2. 创建 OpenClaw 集成配置
echo "⚙️  配置 OpenClaw 集成..."

INTEGRATION_CONFIG="${WORKSPACE_DIR}/supermind_integration.yaml"

cat > "${INTEGRATION_CONFIG}" << 'EOF'
# SuperMind OpenClaw 自动集成配置
supermind:
  enabled: true
  auto_mode: true
  
  # 自动触发条件
  triggers:
    min_length: 20           # 最小消息长度
    complexity_threshold: 3   # 复杂度阈值 (1-10)
    
  # 模式选择
  mode: auto  # auto, simple, always
  
  # 各模式行为
  modes:
    auto:
      description: "自动判断 - 简单查询直接回答，复杂任务用Agent"
      use_rag: true
      use_agent: auto
      use_tools: auto
    
    simple:
      description: "简单模式 - 仅 RAG 增强"
      use_rag: true
      use_agent: false
      use_tools: false
    
    always:
      description: "完全模式 - 总是使用完整SuperMind"
      use_rag: true
      use_agent: true
      use_tools: true
  
  # 快捷命令
  shortcuts:
    "/ask": "sm_ask"           # 知识问答
    "/code": "sm_code"         # 代码生成
    "/do": "sm_execute"        # 执行任务
    "/research": "sm_research" # 深度研究
    "/sm-on": "enable"         # 开启自动模式
    "/sm-off": "disable"       # 关闭自动模式
    "/sm-stats": "stats"       # 查看统计
  
  # 排除模式（不匹配这些模式）
  exclude_patterns:
    - "^/"                    # 以 / 开头的命令
    - "^(hi|hello|hey)$"      # 简单问候
    - "^谢谢"                 # 感谢
    - "^再见"                 # 告别
    
  # 包含模式（匹配这些模式强制使用SuperMind）
  include_patterns:
    - "帮我.*设计"            
    - "帮我.*实现"
    - "帮我.*写"
    - "分析.*架构"
    - "研究.*趋势"
    - "优化.*代码"
EOF

echo "  ✓ 集成配置已创建: ${INTEGRATION_CONFIG}"
echo ""

# 3. 创建环境变量配置
echo "🔧 配置环境变量..."

ENV_FILE="${OPENCLAW_DIR}/supermind.env"

cat > "${ENV_FILE}" << EOF
# SuperMind 环境变量
export SUPERMIND_ENABLED=1
export SUPERMIND_AUTO=1
export SUPERMIND_PATH="${SUPERMIND_DIR}"
export PYTHONPATH="\${PYTHONPATH}:${SUPERMIND_DIR}/src"
EOF

echo "  ✓ 环境变量已配置: ${ENV_FILE}"
echo ""

# 4. 创建快捷命令脚本
echo "🚀 创建快捷命令..."

BIN_DIR="${OPENCLAW_DIR}/bin"
mkdir -p "${BIN_DIR}"

# supermind 主命令
cat > "${BIN_DIR}/supermind" << 'EOF'
#!/bin/bash
# SuperMind 快捷命令

SUPERMIND_DIR="${SUPERMIND_PATH:-${HOME}/.openclaw/workspace/skills/supermind}"

case "$1" in
    start)
        echo "🧠 启动 SuperMind..."
        cd "${SUPERMIND_DIR}"
        python3 src/main.py
        ;;
    init)
        echo "🔧 初始化 SuperMind..."
        cd "${SUPERMIND_DIR}"
        python3 scripts/init.py
        ;;
    index)
        echo "📚 索引知识库..."
        cd "${SUPERMIND_DIR}"
        python3 scripts/index_docs.py
        ;;
    status)
        echo "📊 SuperMind 状态:"
        if pgrep -f "ollama" > /dev/null; then
            echo "  ✓ Ollama 运行中"
        else
            echo "  ✗ Ollama 未运行"
        fi
        ;;
    config)
        ${EDITOR:-nano} "${SUPERMIND_DIR}/config/supermind.yaml"
        ;;
    on)
        export SUPERMIND_AUTO=1
        echo "✅ SuperMind 自动模式已开启"
        ;;
    off)
        export SUPERMIND_AUTO=0
        echo "⏸️  SuperMind 自动模式已关闭"
        ;;
    mode)
        if [ -z "$2" ]; then
            echo "当前模式: ${SUPERMIND_MODE:-auto}"
            echo "可用模式: auto, simple, always"
        else
            export SUPERMIND_MODE="$2"
            echo "✅ 模式已切换为: $2"
        fi
        ;;
    *)
        echo "SuperMind 快捷命令"
        echo ""
        echo "用法: supermind <command>"
        echo ""
        echo "命令:"
        echo "  start    启动交互式界面"
        echo "  init     初始化系统"
        echo "  index    索引知识库"
        echo "  status   查看状态"
        echo "  config   编辑配置"
        echo "  on       开启自动模式"
        echo "  off      关闭自动模式"
        echo "  mode     切换模式 (auto/simple/always)"
        echo ""
        echo "环境变量:"
        echo "  SUPERMIND_AUTO=1    启用自动模式"
        echo "  SUPERMIND_MODE=auto 设置处理模式"
        ;;
esac
EOF

chmod +x "${BIN_DIR}/supermind"

# 添加到 PATH 的提示
echo "  ✓ 快捷命令已创建: ${BIN_DIR}/supermind"
echo ""

# 5. 创建 systemd 服务文件 (Linux/Mac)
echo "🔌 创建服务配置..."

SERVICE_FILE="${OPENCLAW_DIR}/supermind.service"

cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=SuperMind AI Service
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${SUPERMIND_DIR}
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=${SUPERMIND_DIR}/src"
ExecStart=/usr/bin/env python3 ${SUPERMIND_DIR}/src/main.py --server
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

echo "  ✓ 服务配置已创建: ${SERVICE_FILE}"
echo ""

# 6. 创建 README
echo "📝 创建使用说明..."

cat > "${SUPERMIND_DIR}/AUTO_INTEGRATION.md" << 'EOF'
# SuperMind 自动集成指南

## 概述

安装后，OpenClaw 会自动使用 SuperMind 处理消息，无需手动切换。

## 自动触发条件

SuperMind 会在以下情况自动介入：

1. **消息长度 > 20 字符** 且包含以下关键词：
   - 帮我、请、分析、研究、设计、实现
   - 代码、编程、写个、优化、改进
   - 如何、怎么、为什么、比较、对比
   - 步骤、流程、方案、架构

2. **代码相关** - 自动使用代码生成模式
3. **知识查询** - 自动使用 RAG 增强
4. **复杂任务** - 自动使用 Agent 编排

## 快捷命令

在对话中直接使用：

| 命令 | 功能 |
|------|------|
| `/ask 问题` | 知识问答 (RAG增强) |
| `/code 需求` | 代码生成 (自动验证) |
| `/do 任务` | 复杂任务 (Agent编排) |
| `/research 主题` | 深度研究 |
| `/sm-on` | 开启自动模式 |
| `/sm-off` | 关闭自动模式 |
| `/sm-stats` | 查看系统统计 |

## 三种模式

### 1. Auto 模式 (默认)
```bash
supermind mode auto
```
- 自动判断任务类型
- 简单查询 → 直接回答
- 复杂任务 → Agent编排
- 代码请求 → 代码生成+验证
- 知识查询 → RAG增强

### 2. Simple 模式
```bash
supermind mode simple
```
- 所有请求都经过 RAG 增强
- 不使用 Agent 编排
- 响应更快

### 3. Always 模式
```bash
supermind mode always
```
- 所有请求都使用完整 SuperMind
- 包括 Agent 编排和工具调用
- 质量最高但较慢

## 命令行使用

```bash
# 启动交互式界面
supermind start

# 初始化系统
supermind init

# 索引知识库文档
supermind index

# 查看状态
supermind status

# 编辑配置
supermind config

# 开关自动模式
supermind on
supermind off

# 切换模式
supermind mode auto
supermind mode simple
supermind mode always
```

## 环境变量

```bash
# 启用自动集成
export SUPERMIND_AUTO=1

# 设置处理模式
export SUPERMIND_MODE=auto

# 指定 SuperMind 路径
export SUPERMIND_PATH=/path/to/supermind
```

## 配置自定义

编辑 `~/.openclaw/workspace/skills/supermind/config/supermind.yaml`：

```yaml
# 模型配置
model:
  name: "qwen3.5-35b-a3b"
  temperature: 0.7

# RAG 配置
rag:
  vector_store:
    embedding_model: "BAAI/bge-large-zh-v1.5"

# 自动触发条件
auto:
  min_length: 20
  complexity_threshold: 3
```

## 验证安装

发送测试消息：

```
你: 帮我分析一下 Spring Boot 的最佳实践
```

如果看到 SuperMind 的加载信息，说明集成成功！

## 故障排除

### SuperMind 未响应

1. 检查 Ollama 是否运行：
   ```bash
   ollama list
   ```

2. 检查 SuperMind 状态：
   ```bash
   supermind status
   ```

3. 重新初始化：
   ```bash
   supermind init
   ```

### 响应太慢

切换到 Simple 模式：
```bash
supermind mode simple
```

### 不需要自动增强

关闭自动模式：
```bash
supermind off
```

## 完全卸载

```bash
# 删除集成配置
rm ~/.openclaw/supermind_integration.yaml
rm ~/.openclaw/supermind.env
rm ~/.openclaw/bin/supermind
rm ~/.openclaw/supermind.service

# 删除 SuperMind（可选）
rm -rf ~/.openclaw/workspace/skills/supermind
```

---

享受超级智能！🚀
EOF

echo "  ✓ 使用说明已创建: ${SUPERMIND_DIR}/AUTO_INTEGRATION.md"
echo ""

# 7. 添加到 shell 配置
echo "🐚 配置 Shell 集成..."

SHELL_RC=""
if [ -f "${HOME}/.zshrc" ]; then
    SHELL_RC="${HOME}/.zshrc"
elif [ -f "${HOME}/.bashrc" ]; then
    SHELL_RC="${HOME}/.bashrc"
fi

if [ -n "${SHELL_RC}" ]; then
    # 检查是否已添加
    if ! grep -q "supermind.env" "${SHELL_RC}"; then
        echo "" >> "${SHELL_RC}"
        echo "# SuperMind Auto Integration" >> "${SHELL_RC}"
        echo "source ${ENV_FILE}" >> "${SHELL_RC}"
        echo "export PATH=\"\${PATH}:${BIN_DIR}\"" >> "${SHELL_RC}"
        echo "  ✓ 已添加到 ${SHELL_RC}"
    else
        echo "  ✓ Shell 配置已存在"
    fi
else
    echo "  ⚠️  未找到 .zshrc 或 .bashrc"
    echo "     请手动添加以下行到你的 shell 配置:"
    echo "     source ${ENV_FILE}"
    echo "     export PATH=\"\${PATH}:${BIN_DIR}\""
fi
echo ""

# 完成
echo "=============================="
echo "✅ SuperMind 自动集成安装完成！"
echo ""
echo "🚀 快速开始:"
echo "   1. 重新加载 shell 配置:"
echo "      source ${ENV_FILE}"
echo "      export PATH=\"\${PATH}:${BIN_DIR}\""
echo ""
echo "   2. 验证安装:"
echo "      supermind status"
echo ""
echo "   3. 开始使用:"
echo "      supermind start"
echo "      或直接对话，SuperMind 会自动介入"
echo ""
echo "📖 详细说明:"
echo "   ${SUPERMIND_DIR}/AUTO_INTEGRATION.md"
echo ""
echo "⚙️  配置文件:"
echo "   ${INTEGRATION_CONFIG}"
echo ""
