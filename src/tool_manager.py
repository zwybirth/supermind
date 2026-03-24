"""
Tool Manager - 工具调用管理系统
"""

import re
import json
import subprocess
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = None


class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行工具"""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """获取参数schema"""
        pass


class CalculatorTool(BaseTool):
    """计算器工具 - 精确数学运算"""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="执行数学计算，支持基本运算、函数等"
        )
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行计算"""
        expression = params.get('expression', '')
        
        try:
            # 安全计算：只允许数学表达式
            allowed_names = {
                'abs': abs, 'round': round, 'max': max, 'min': min,
                'sum': sum, 'pow': pow, 'sqrt': lambda x: x ** 0.5,
                'sin': lambda x: __import__('math').sin(x),
                'cos': lambda x: __import__('math').cos(x),
                'pi': __import__('math').pi,
                'e': __import__('math').e
            }
            
            # 清理表达式
            expression = re.sub(r'[^0-9+\-*/().\s]', '', expression)
            
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            
            return ToolResult(
                success=True,
                output=str(result),
                metadata={'expression': expression, 'result': result}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如 '2 + 2' 或 'sqrt(16)'"
                }
            },
            "required": ["expression"]
        }


class CodeExecutionTool(BaseTool):
    """代码执行工具"""
    
    def __init__(self, timeout: int = 30, 
                 allowed_languages: List[str] = None,
                 sandbox: bool = True):
        super().__init__(
            name="code_executor",
            description="执行代码并返回结果"
        )
        self.timeout = timeout
        self.allowed_languages = allowed_languages or ['python']
        self.sandbox = sandbox
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行代码"""
        code = params.get('code', '')
        language = params.get('language', 'python')
        validate_only = params.get('validate_only', False)
        
        if language not in self.allowed_languages:
            return ToolResult(
                success=False,
                output="",
                error=f"不支持的语言: {language}"
            )
        
        if validate_only:
            # 仅验证语法
            return self._validate_code(code, language)
        
        return self._run_code(code, language)
    
    def _validate_code(self, code: str, language: str) -> ToolResult:
        """验证代码语法"""
        try:
            if language == 'python':
                compile(code, '<string>', 'exec')
                return ToolResult(success=True, output="语法正确")
            return ToolResult(success=True, output="验证通过")
        except SyntaxError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"语法错误: {e}"
            )
    
    def _run_code(self, code: str, language: str) -> ToolResult:
        """运行代码"""
        try:
            if language == 'python':
                # 使用子进程执行
                result = subprocess.run(
                    ['python3', '-c', code],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                if result.returncode == 0:
                    return ToolResult(
                        success=True,
                        output=result.stdout,
                        metadata={'execution_time': self.timeout}
                    )
                else:
                    return ToolResult(
                        success=False,
                        output=result.stdout,
                        error=result.stderr
                    )
            
            return ToolResult(
                success=False,
                output="",
                error=f"暂不支持 {language} 的执行"
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"执行超时 (> {self.timeout}s)"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的代码"
                },
                "language": {
                    "type": "string",
                    "enum": self.allowed_languages,
                    "default": "python"
                },
                "validate_only": {
                    "type": "boolean",
                    "description": "仅验证语法，不执行",
                    "default": False
                }
            },
            "required": ["code"]
        }


class WebSearchTool(BaseTool):
    """网络搜索工具"""
    
    def __init__(self, provider: str = 'duckduckgo', max_results: int = 10):
        super().__init__(
            name="web_search",
            description="搜索网络获取实时信息"
        )
        self.provider = provider
        self.max_results = max_results
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行搜索"""
        query = params.get('query', '')
        
        try:
            if self.provider == 'duckduckgo':
                return self._search_duckduckgo(query)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"不支持的搜索提供商: {self.provider}"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def _search_duckduckgo(self, query: str) -> ToolResult:
        """使用 DuckDuckGo 搜索"""
        try:
            from duckduckgo_search import DDGS
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=self.max_results))
                
                formatted = []
                for i, r in enumerate(results, 1):
                    formatted.append(
                        f"[{i}] {r['title']}\n"
                        f"URL: {r['href']}\n"
                        f"摘要: {r['body']}\n"
                    )
                
                return ToolResult(
                    success=True,
                    output="\n".join(formatted),
                    metadata={
                        'query': query,
                        'results_count': len(results),
                        'provider': 'duckduckgo'
                    }
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"搜索失败: {e}"
            )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                }
            },
            "required": ["query"]
        }


class FileSystemTool(BaseTool):
    """文件系统工具"""
    
    def __init__(self, allowed_paths: List[str] = None):
        super().__init__(
            name="file_system",
            description="文件读写操作"
        )
        self.allowed_paths = allowed_paths or ['.']
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行文件操作"""
        operation = params.get('operation', 'read')
        path = params.get('path', '')
        content = params.get('content', '')
        
        # 安全检查
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                output="",
                error="路径不在允许范围内"
            )
        
        try:
            if operation == 'read':
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return ToolResult(success=True, output=content)
            
            elif operation == 'write':
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return ToolResult(success=True, output=f"已写入 {path}")
            
            elif operation == 'list':
                import os
                files = os.listdir(path)
                return ToolResult(success=True, output="\n".join(files))
            
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"不支持的操作: {operation}"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def _is_path_allowed(self, path: str) -> bool:
        """检查路径是否允许访问"""
        import os
        abs_path = os.path.abspath(path)
        for allowed in self.allowed_paths:
            if abs_path.startswith(os.path.abspath(allowed)):
                return True
        return False
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list"]
                },
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "写入内容（write操作）"
                }
            },
            "required": ["operation", "path"]
        }


class DateTimeTool(BaseTool):
    """日期时间工具"""
    
    def __init__(self):
        super().__init__(
            name="datetime",
            description="获取当前日期时间"
        )
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """获取日期时间"""
        from datetime import datetime
        
        format_str = params.get('format', '%Y-%m-%d %H:%M:%S')
        timezone = params.get('timezone', 'local')
        
        now = datetime.now()
        
        return ToolResult(
            success=True,
            output=now.strftime(format_str),
            metadata={
                'timestamp': now.timestamp(),
                'iso': now.isoformat(),
                'timezone': timezone
            }
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "description": "日期格式",
                    "default": "%Y-%m-%d %H:%M:%S"
                },
                "timezone": {
                    "type": "string",
                    "default": "local"
                }
            }
        }


class ToolManager:
    """
    工具管理器
    
    负责：
    1. 工具注册与管理
    2. 工具调用分发
    3. 工具结果处理
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools: Dict[str, BaseTool] = {}
        self.enabled_tools: set = set()
        
        self._init_tools()
    
    def _init_tools(self):
        """初始化工具"""
        enabled = self.config.get('enabled', [])
        
        # 注册工具
        all_tools = {
            'calculator': CalculatorTool(),
            'code_executor': CodeExecutionTool(
                timeout=self.config.get('code_executor', {}).get('timeout', 30),
                sandbox=self.config.get('code_executor', {}).get('sandbox', True)
            ),
            'web_search': WebSearchTool(
                provider=self.config.get('web_search', {}).get('provider', 'duckduckgo'),
                max_results=self.config.get('web_search', {}).get('max_results', 10)
            ),
            'file_system': FileSystemTool(),
            'datetime': DateTimeTool()
        }
        
        # 启用配置的工具
        for tool_name in enabled:
            if tool_name in all_tools:
                self.register_tool(all_tools[tool_name])
    
    def register_tool(self, tool: BaseTool):
        """注册工具"""
        self.tools[tool.name] = tool
        self.enabled_tools.add(tool.name)
    
    def execute(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """执行工具"""
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                output="",
                error=f"未知工具: {tool_name}"
            )
        
        tool = self.tools[tool_name]
        return tool.execute(params)
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具schema"""
        if tool_name in self.tools:
            return self.tools[tool_name].get_schema()
        return None
    
    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """获取所有工具schema"""
        return {
            name: tool.get_schema() 
            for name, tool in self.tools.items()
        }
    
    def detect_tool_need(self, query: str) -> Optional[str]:
        """
        检测是否需要使用工具
        
        返回工具名称或 None
        """
        # 关键词匹配
        patterns = {
            'calculator': r'计算|等于|=?\s*\d+\s*[+\-*/]\s*\d+|sqrt|log|sin|cos',
            'code_executor': r'运行|执行|测试.*代码|验证.*代码',
            'web_search': r'搜索|查找|最新|现在|今天|实时|最新版本|最新发布',
            'file_system': r'读取文件|写入文件|列出.*目录|打开.*文件',
            'datetime': r'现在时间|当前日期|今天日期|timestamp'
        }
        
        for tool_name, pattern in patterns.items():
            if tool_name in self.enabled_tools:
                if re.search(pattern, query, re.IGNORECASE):
                    return tool_name
        
        return None
    
    def augment_prompt_with_tools(self, prompt: str, 
                                   tool_results: Dict[str, ToolResult]) -> str:
        """将工具结果加入提示"""
        if not tool_results:
            return prompt
        
        augmented = prompt + "\n\n## 工具执行结果\n"
        
        for tool_name, result in tool_results.items():
            if result.success:
                augmented += f"\n### {tool_name}\n{result.output}\n"
            else:
                augmented += f"\n### {tool_name} (失败)\n错误: {result.error}\n"
        
        augmented += "\n基于以上信息，"
        
        return augmented
