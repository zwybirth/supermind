"""
SuperMind - 本地大模型超级化系统
主入口模块
"""

import yaml
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from src.rag_engine import RAGEngine
from src.agent_orchestrator import AgentOrchestrator
from src.memory_system import MemorySystem
from src.tool_manager import ToolManager
from src.model_interface import ModelInterface
from src.router import TaskRouter

console = Console()


@dataclass
class SuperMindConfig:
    """SuperMind 配置"""
    model_name: str = "qwen3.5-35b-a3b"
    provider: str = "ollama"
    temperature: float = 0.7
    show_thinking: bool = True


class SuperMind:
    """
    SuperMind 主类
    
    通过系统工程让本地大模型拥有超级智能：
    - RAG 增强知识
    - Agent 编排复杂任务
    - 分层记忆突破上下文限制
    - 工具调用扩展能力
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 SuperMind
        
        Args:
            config_path: 配置文件路径，默认使用 config/supermind.yaml
        """
        self.config = self._load_config(config_path)
        self.console = Console()
        
        # 初始化各子系统
        self._init_systems()
        
        self.console.print(Panel.fit(
            "[bold green]🧠 SuperMind 系统启动完成[/bold green]\n"
            f"模型: {self.config['model']['name']}\n"
            f"RAG: {'✓' if self.rag else '✗'} | "
            f"Agent: {'✓' if self.agent else '✗'} | "
            f"Memory: {'✓' if self.memory else '✗'} | "
            f"Tools: {'✓' if self.tools else '✗'}",
            title="SuperMind v1.0"
        ))
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置文件"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "supermind.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _init_systems(self):
        """初始化所有子系统"""
        # 模型接口
        self.model = ModelInterface(self.config['model'])
        
        # RAG 引擎
        self.rag = RAGEngine(self.config.get('rag', {}))
        
        # 记忆系统
        self.memory = MemorySystem(self.config.get('memory', {}))
        
        # 工具管理器
        self.tools = ToolManager(self.config.get('tools', {}))
        
        # Agent 编排器
        self.agent = AgentOrchestrator(
            model=self.model,
            memory=self.memory,
            tools=self.tools,
            config=self.config.get('agent', {})
        )
        
        # 任务路由器
        self.router = TaskRouter()
    
    def execute(self, task: str, **kwargs) -> str:
        """
        执行复杂任务（Agent 编排模式）
        
        Args:
            task: 任务描述
            **kwargs: 额外参数
            
        Returns:
            任务执行结果
        """
        if self.config['system'].get('show_thinking', True):
            self.console.print(f"\n[bold blue]🎯 任务:[/bold blue] {task}\n")
        
        # 保存到工作记忆
        self.memory.save_working(f"任务: {task}")
        
        # Agent 编排执行
        result = self.agent.execute(task, **kwargs)
        
        # 保存结果
        self.memory.save_working(f"结果: {result[:200]}...")
        
        return result
    
    def ask(self, question: str, use_rag: bool = True, **kwargs) -> str:
        """
        知识问答（RAG 增强模式）
        
        Args:
            question: 问题
            use_rag: 是否使用 RAG 增强
            **kwargs: 额外参数
            
        Returns:
            回答
        """
        if self.config['system'].get('show_thinking', True):
            self.console.print(f"\n[bold blue]❓ 问题:[/bold blue] {question}\n")
        
        context_parts = []
        
        # 1. RAG 检索
        if use_rag and self.rag:
            with self.console.status("[cyan]检索知识库..."):
                rag_results = self.rag.retrieve(question)
                if rag_results['documents']:
                    context_parts.append("## 相关知识\n" + 
                        self.rag.format_context(rag_results))
        
        # 2. 记忆检索
        with self.console.status("[cyan]检索记忆..."):
            mem_context = self.memory.build_context(question)
            if mem_context:
                context_parts.append("## 历史上下文\n" + mem_context)
        
        # 3. 构建完整提示
        system_prompt = self._build_system_prompt("qa")
        full_prompt = self._build_prompt(question, context_parts, system_prompt)
        
        # 4. 生成回答
        with self.console.status("[green]生成回答..."):
            response = self.model.generate(full_prompt, system_prompt=system_prompt)
        
        # 5. 保存交互
        self.memory.save_interaction(question, response)
        
        if self.config['system'].get('show_thinking', True):
            self.console.print(f"\n[bold green]💡 回答:[/bold green]")
            self.console.print(Markdown(response))
        
        return response
    
    def code(self, request: str, language: str = "python", **kwargs) -> str:
        """
        代码生成与验证
        
        Args:
            request: 代码需求描述
            language: 编程语言
            **kwargs: 额外参数
            
        Returns:
            生成的代码
        """
        if self.config['system'].get('show_thinking', True):
            self.console.print(f"\n[bold blue]📝 代码需求:[/bold blue] {request}\n")
        
        # 1. 检索相关代码示例
        context_parts = []
        if self.rag:
            with self.console.status("[cyan]检索代码示例..."):
                code_results = self.rag.retrieve(
                    f"{language} code {request}",
                    filter={"type": "code"}
                )
                if code_results['documents']:
                    context_parts.append("## 参考代码\n" + 
                        self.rag.format_context(code_results))
        
        # 2. 构建代码生成提示
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
        
        # 3. 生成代码
        with self.console.status("[green]生成代码..."):
            code = self.model.generate(full_prompt, system_prompt=system_prompt)
        
        # 4. 代码验证（如果启用工具）
        if self.tools and 'code_executor' in self.tools.enabled_tools:
            with self.console.status("[yellow]验证代码..."):
                validation = self.tools.execute('code_executor', {
                    'code': code,
                    'language': language,
                    'validate_only': True
                })
                if not validation.get('success'):
                    # 修复代码
                    code = self._fix_code(code, validation.get('error'), language)
        
        if self.config['system'].get('show_thinking', True):
            self.console.print(f"\n[bold green]✅ 生成代码:[/bold green]")
            self.console.print(f"```{language}")
            self.console.print(code)
            self.console.print("```")
        
        # 保存代码到记忆
        self.memory.save_code(request, code, language)
        
        return code
    
    def research(self, topic: str, depth: str = "standard") -> str:
        """
        深度研究（多步骤调研）
        
        Args:
            topic: 研究主题
            depth: 深度 (brief/standard/deep)
            
        Returns:
            研究报告
        """
        if self.config['system'].get('show_thinking', True):
            self.console.print(f"\n[bold blue]🔬 研究主题:[/bold blue] {topic}\n")
        
        # 使用 Agent 编排进行多步骤研究
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
        """构建系统提示"""
        prompts = {
            "qa": """你是一个知识渊博的AI助手。回答问题时：
1. 基于提供的知识进行回答
2. 如果不确定，明确说明
3. 重要信息标注来源
4. 结构清晰，重点突出""",

            "code": """你是一个专业程序员。生成代码时：
1. 代码正确、完整、可运行
2. 添加清晰注释
3. 处理边界情况
4. 遵循最佳实践""",

            "agent": """你是一个智能Agent。执行任务时：
1. 仔细分析需求
2. 制定详细计划
3. 逐步执行并验证
4. 及时汇报进展"""
        }
        return prompts.get(mode, prompts["qa"])
    
    def _build_prompt(self, query: str, context_parts: List[str], 
                      system_prompt: str) -> str:
        """构建完整提示"""
        prompt = system_prompt + "\n\n"
        
        if context_parts:
            prompt += "\n\n".join(context_parts) + "\n\n"
        
        prompt += f"## 用户问题\n{query}\n\n## 回答"
        
        return prompt
    
    def _fix_code(self, code: str, error: str, language: str) -> str:
        """修复代码错误"""
        fix_prompt = f"""以下{language}代码有错误：

```
{code}
```

错误信息：
{error}

请修复代码，只返回修复后的完整代码："""
        
        return self.model.generate(fix_prompt)
    
    def stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        return {
            "model": self.config['model']['name'],
            "rag_documents": self.rag.document_count() if self.rag else 0,
            "memory_items": self.memory.item_count() if self.memory else 0,
            "skills_learned": len(self.memory.skills) if self.memory else 0,
            "tools_available": list(self.tools.enabled_tools) if self.tools else [],
        }


def main():
    """命令行入口"""
    import sys
    
    mind = SuperMind()
    
    if len(sys.argv) > 1:
        # 直接执行命令
        command = " ".join(sys.argv[1:])
        result = mind.execute(command)
        print(result)
    else:
        # 交互模式
        console.print("\n[bold cyan]🧠 SuperMind 交互模式[/bold cyan]")
        console.print("输入 'exit' 退出, 'stats' 查看统计\n")
        
        while True:
            try:
                user_input = console.input("[bold green]You:[/bold green] ")
                
                if user_input.lower() in ['exit', 'quit']:
                    break
                elif user_input.lower() == 'stats':
                    stats = mind.stats()
                    console.print(stats)
                elif user_input.startswith("/code"):
                    mind.code(user_input[6:])
                elif user_input.startswith("/ask"):
                    mind.ask(user_input[5:])
                elif user_input.startswith("/research"):
                    mind.research(user_input[10:])
                else:
                    mind.execute(user_input)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]错误: {e}[/red]")
        
        console.print("\n[bold cyan]再见! 👋[/bold cyan]")


if __name__ == "__main__":
    main()
