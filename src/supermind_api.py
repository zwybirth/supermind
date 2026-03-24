"""
SuperMind - 本地大模型超级化系统
OpenClaw 自动集成版本

使用方法:
1. 作为独立系统运行: python main.py
2. 作为 OpenClaw 后端: 通过 openclaw_integration.py
"""

import os
import sys
from pathlib import Path

# 确保可以导入其他模块
sys.path.insert(0, str(Path(__file__).parent))

# 基础导入
import yaml
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.status import Status

console = Console()

# 延迟加载 SuperMind 组件
def get_supermind():
    """获取或创建 SuperMind 实例（单例模式）"""
    if not hasattr(get_supermind, '_instance'):
        from rag_engine import RAGEngine
        from agent_orchestrator import AgentOrchestrator
        from memory_system import MemorySystem
        from tool_manager import ToolManager
        from model_interface import ModelInterface
        from router import TaskRouter
        
        class SuperMind:
            def __init__(self, config_path: Optional[str] = None):
                self.config = self._load_config(config_path)
                self.console = Console()
                self._init_systems()
            
            def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
                if config_path is None:
                    config_path = Path(__file__).parent.parent / "config" / "supermind.yaml"
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            
            def _init_systems(self):
                self.model = ModelInterface(self.config['model'])
                self.rag = RAGEngine(self.config.get('rag', {}))
                self.memory = MemorySystem(self.config.get('memory', {}))
                self.tools = ToolManager(self.config.get('tools', {}))
                self.agent = AgentOrchestrator(
                    model=self.model,
                    memory=self.memory,
                    tools=self.tools,
                    config=self.config.get('agent', {})
                )
                self.router = TaskRouter()
            
            def execute(self, task: str, **kwargs) -> str:
                self.memory.save_working(f"任务: {task}")
                result = self.agent.execute(task, **kwargs)
                self.memory.save_working(f"结果: {result[:200]}...")
                return result
            
            def ask(self, question: str, use_rag: bool = True, **kwargs) -> str:
                context_parts = []
                
                if use_rag and self.rag:
                    rag_results = self.rag.retrieve(question)
                    if rag_results['documents']:
                        context_parts.append("## 相关知识\n" + 
                            self.rag.format_context(rag_results))
                
                mem_context = self.memory.build_context(question)
                if mem_context:
                    context_parts.append("## 历史上下文\n" + mem_context)
                
                system_prompt = self._build_system_prompt("qa")
                full_prompt = self._build_prompt(question, context_parts, system_prompt)
                
                response = self.model.generate(full_prompt, system_prompt=system_prompt)
                self.memory.save_interaction(question, response)
                
                return response
            
            def code(self, request: str, language: str = "python", **kwargs) -> str:
                context_parts = []
                if self.rag:
                    code_results = self.rag.retrieve(
                        f"{language} code {request}",
                        filter={"type": "code"}
                    )
                    if code_results['documents']:
                        context_parts.append("## 参考代码\n" + 
                            self.rag.format_context(code_results))
                
                system_prompt = f"""你是一个专业的{language}程序员。要求：
1. 代码必须正确、完整、可运行
2. 添加清晰的注释
3. 包含错误处理
4. 遵循最佳实践"""
                
                full_prompt = self._build_prompt(
                    f"请用{language}实现：{request}",
                    context_parts,
                    system_prompt
                )
                
                code = self.model.generate(full_prompt, system_prompt=system_prompt)
                
                if self.tools and 'code_executor' in self.tools.enabled_tools:
                    validation = self.tools.execute('code_executor', {
                        'code': code,
                        'language': language,
                        'validate_only': True
                    })
                    if not validation.get('success'):
                        code = self._fix_code(code, validation.get('error'), language)
                
                self.memory.save_code(request, code, language)
                return code
            
            def research(self, topic: str, depth: str = "standard") -> str:
                task = f"对'{topic}'进行深度研究，包括：\n"
                task += "1. 概念定义与背景\n"
                task += "2. 核心技术与方法\n"
                task += "3. 最新进展与趋势\n"
                task += "4. 应用案例\n"
                task += "5. 总结与建议\n"
                if depth == "deep":
                    task += "\n请进行充分的网络搜索和资料收集。"
                return self.execute(task)
            
            def _build_system_prompt(self, mode: str) -> str:
                prompts = {
                    "qa": """你是一个知识渊博的AI助手。回答问题时：
1. 基于提供的知识进行回答
2. 如果不确定，明确说明
3. 重要信息标注来源
4. 结构清晰，重点突出"""
                }
                return prompts.get(mode, prompts["qa"])
            
            def _build_prompt(self, query: str, context_parts: List[str], 
                              system_prompt: str) -> str:
                prompt = system_prompt + "\n\n"
                if context_parts:
                    prompt += "\n\n".join(context_parts) + "\n\n"
                prompt += f"## 用户问题\n{query}\n\n## 回答"
                return prompt
            
            def _fix_code(self, code: str, error: str, language: str) -> str:
                fix_prompt = f"""以下{language}代码有错误：\n\n```\n{code}\n```\n\n错误信息：\n{error}\n\n请修复代码，只返回修复后的完整代码："""
                return self.model.generate(fix_prompt)
            
            def stats(self) -> Dict[str, Any]:
                return {
                    "model": self.config['model']['name'],
                    "rag_documents": self.rag.document_count() if self.rag else 0,
                    "memory_items": self.memory.item_count() if self.memory else 0,
                    "skills_learned": len(self.memory.skills) if self.memory else 0,
                    "tools_available": list(self.tools.enabled_tools) if self.tools else [],
                }
        
        get_supermind._instance = SuperMind()
    
    return get_supermind._instance


# 兼容旧接口的函数
def execute(task: str, **kwargs) -> str:
    """执行任务"""
    return get_supermind().execute(task, **kwargs)


def ask(question: str, use_rag: bool = True, **kwargs) -> str:
    """知识问答"""
    return get_supermind().ask(question, use_rag=use_rag, **kwargs)


def code(request: str, language: str = "python", **kwargs) -> str:
    """代码生成"""
    return get_supermind().code(request, language=language, **kwargs)


def research(topic: str, depth: str = "standard") -> str:
    """深度研究"""
    return get_supermind().research(topic, depth=depth)


def stats() -> Dict[str, Any]:
    """获取统计"""
    return get_supermind().stats()


# OpenClaw 集成的关键函数
def auto_process(message: str, context: dict = None) -> Optional[str]:
    """
    自动处理消息 - OpenClaw 集成入口
    
    根据消息特征自动选择处理方式
    """
    # 检查是否启用
    if os.environ.get('SUPERMIND_AUTO', '0') != '1':
        return None
    
    # 检查是否是命令
    if message.startswith('/'):
        return handle_command(message)
    
    # 获取模式
    mode = os.environ.get('SUPERMIND_MODE', 'auto')
    
    try:
        mind = get_supermind()
        
        if mode == 'always':
            # 总是使用完整 SuperMind
            return mind.execute(message)
        
        elif mode == 'simple':
            # 仅 RAG 增强
            return mind.ask(message)
        
        else:  # auto 模式
            # 自动判断
            return _auto_route(message, mind)
            
    except Exception as e:
        console.print(f"[red][SuperMind] 错误: {e}[/red]")
        return None


def _auto_route(message: str, mind) -> str:
    """自动路由消息到合适的处理方式"""
    message_lower = message.lower()
    
    # 1. 代码相关
    code_keywords = ['代码', '编程', '写个', '实现', 'function', 'def ', 'class ']
    if any(kw in message_lower for kw in code_keywords):
        return mind.code(message)
    
    # 2. 知识查询
    knowledge_keywords = ['是什么', '什么是', '怎么', '如何', '为什么', '有哪些']
    if any(kw in message_lower for kw in knowledge_keywords):
        return mind.ask(message)
    
    # 3. 复杂任务
    if len(message) > 100 or '帮我' in message:
        return mind.execute(message)
    
    # 4. 简单查询 - RAG 增强
    return mind.ask(message)


def handle_command(message: str) -> Optional[str]:
    """处理命令"""
    parts = message.split(maxsplit=1)
    cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ""
    
    commands = {
        '/sm-ask': lambda: ask(args),
        '/sm-code': lambda: code(args),
        '/sm-do': lambda: execute(args),
        '/sm-research': lambda: research(args),
        '/sm-stats': lambda: str(stats()),
        '/sm-on': lambda: set_auto_mode(True),
        '/sm-off': lambda: set_auto_mode(False),
    }
    
    if cmd in commands:
        return commands[cmd]()
    
    return None


def set_auto_mode(enabled: bool) -> str:
    """设置自动模式"""
    os.environ['SUPERMIND_AUTO'] = '1' if enabled else '0'
    return f"SuperMind 自动模式已{'开启' if enabled else '关闭'}"


# 主程序入口
def main():
    """命令行入口"""
    import sys
    
    # 显示启动信息
    console.print(Panel.fit(
        "[bold green]🧠 SuperMind 本地大模型超级化系统[/bold green]\n"
        "让 Qwen3.5-35B-A3B 拥有 GPT-4 级别效果",
        title="SuperMind v1.0"
    ))
    
    # 初始化
    try:
        mind = get_supermind()
        stats_info = mind.stats()
        
        console.print("\n[dim]系统状态:[/dim]")
        console.print(f"  模型: {stats_info['model']}")
        console.print(f"  知识库: {stats_info['rag_documents']} 文档")
        console.print(f"  记忆: {stats_info['memory_items']} 条")
        console.print(f"  技能: {stats_info['skills_learned']} 个")
        console.print(f"  工具: {', '.join(stats_info['tools_available'])}")
        
    except Exception as e:
        console.print(f"\n[red]初始化失败: {e}[/red]")
        console.print("[yellow]请先运行: python scripts/init.py[/yellow]")
        return 1
    
    # 处理命令行参数
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        console.print(f"\n[bold blue]🎯 任务:[/bold blue] {command}\n")
        
        with Status("[bold green]SuperMind 思考中..."):
            result = auto_process(command) or mind.execute(command)
        
        console.print(Markdown(result))
        return 0
    
    # 交互模式
    console.print("\n[bold cyan]🧠 SuperMind 交互模式[/bold cyan]")
    console.print("输入 'exit' 退出, 'help' 查看帮助\n")
    
    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ")
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
            
            if user_input.lower() == 'help':
                console.print("""
[bold]可用命令:[/bold]
  /sm-ask <问题>     - 知识问答
  /sm-code <需求>    - 代码生成
  /sm-do <任务>      - 执行任务
  /sm-research <主题> - 深度研究
  /sm-stats          - 查看统计
  /sm-on             - 开启自动模式
  /sm-off            - 关闭自动模式
  help               - 显示帮助
  exit               - 退出
                """)
                continue
            
            if not user_input.strip():
                continue
            
            with Status("[bold green]SuperMind 思考中..."):
                result = auto_process(user_input)
                
                if result is None:
                    result = mind.execute(user_input)
            
            console.print(f"\n[bold blue]SuperMind:[/bold blue]")
            console.print(Markdown(result))
            console.print()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"\n[red]错误: {e}[/red]\n")
    
    console.print("\n[bold cyan]再见! 👋[/bold cyan]\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
