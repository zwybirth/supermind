# 🚀 SuperMind 自动使用指南

## 最简单的方式：一键启用

```bash
# 在当前终端启用
source /Users/agents/.openclaw/workspace/skills/supermind/scripts/enable_auto.sh
```

启用后，**你的所有 OpenClaw 对话都会自动经过 SuperMind 增强！**

---

## 三种启用方式

### 方式1: 临时启用（当前终端）

```bash
export SUPERMIND_AUTO=1
export SUPERMIND_MODE=auto
export SUPERMIND_PATH="/Users/agents/.openclaw/workspace/skills/supermind"
export PYTHONPATH="${PYTHONPATH}:${SUPERMIND_PATH}/src"
```

### 方式2: 永久启用（添加到配置文件）

编辑 `~/.zshrc` 或 `~/.bashrc`：

```bash
# SuperMind 自动集成
export SUPERMIND_AUTO=1
export SUPERMIND_MODE=auto
export SUPERMIND_PATH="/Users/agents/.openclaw/workspace/skills/supermind"
export PYTHONPATH="${PYTHONPATH}:${SUPERMIND_PATH}/src"
```

然后：
```bash
source ~/.zshrc  # 或 source ~/.bashrc
```

### 方式3: 完整安装

```bash
cd /Users/agents/.openclaw/workspace/skills/supermind
bash scripts/install_auto.sh
```

这会安装：
- 快捷命令 (`supermind`)
- 服务配置
- 环境变量
- Shell 集成

---

## 自动触发条件

启用后，SuperMind 会在以下情况**自动介入**：

| 场景 | 触发词 | 处理方式 |
|------|--------|----------|
| **代码请求** | 代码、编程、写个、实现、function | 代码生成 + 验证 |
| **知识查询** | 是什么、怎么、如何、为什么 | RAG 增强回答 |
| **复杂任务** | 帮我、分析、设计、研究、优化 | Agent 编排执行 |
| **长消息** | > 100 字符 | 完整 SuperMind 处理 |

---

## 快捷命令

对话中直接输入：

```
/sm-ask Spring Boot 最佳实践是什么？
/sm-code 写个 Python 爬虫
/sm-do 帮我设计一个用户系统
/sm-research AI Agent 最新趋势
/sm-stats
```

---

## 三种处理模式

### Auto 模式（默认）
```bash
export SUPERMIND_MODE=auto
```
- 自动判断任务类型
- 智能选择处理方式

### Simple 模式
```bash
export SUPERMIND_MODE=simple
```
- 仅 RAG 增强，无 Agent
- 响应更快

### Always 模式
```bash
export SUPERMIND_MODE=always
```
- 总是使用完整 SuperMind
- 质量最高

---

## 快速测试

启用后，发送以下测试消息：

```
测试1: 写个 Python 快速排序
→ 应该看到代码生成 + 验证

测试2: 帮我分析微服务架构的优缺点  
→ 应该看到多维度分析

测试3: 如何实现一个线程安全的单例模式
→ 应该看到详细代码 + 解释
```

---

## 开关控制

```bash
# 关闭自动模式（恢复默认）
export SUPERMIND_AUTO=0

# 重新开启
export SUPERMIND_AUTO=1

# 查看当前状态
python -c "import os; print('ON' if os.environ.get('SUPERMIND_AUTO')=='1' else 'OFF')"
```

---

## 故障排除

### 问题: SuperMind 没有响应

```bash
# 1. 检查环境变量
echo $SUPERMIND_AUTO  # 应该输出 1
echo $SUPERMIND_MODE  # 应该输出 auto/simple/always

# 2. 检查 Ollama
ollama list  # 确保模型已下载

# 3. 检查 SuperMind
cd /Users/agents/.openclaw/workspace/skills/supermind
python src/supermind_api.py stats
```

### 问题: 响应太慢

```bash
# 切换到 Simple 模式
export SUPERMIND_MODE=simple
```

### 问题: 不需要某些增强

```bash
# 临时关闭
export SUPERMIND_AUTO=0

# 完成后再开启
export SUPERMIND_AUTO=1
```

---

## 一句话总结

> 设置 `export SUPERMIND_AUTO=1`，然后正常对话即可！

SuperMind 会自动判断何时介入，让你的本地 35B 模型拥有 GPT-4 级别效果 🚀
