#!/usr/bin/env python3
"""
SuperMind OpenClaw 自动集成模块
让 OpenClaw 的所有请求自动经过 SuperMind 增强
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass

# 添加 SuperMind 到路径
SUPERMIND_PATH = Path(__file__).parent.parent / "skills" / "supermind"
sys.path.insert(0, str(SUPERMIND_PATH / "src"))

# 延迟导入，避免初始化失败影响 OpenClaw
_rag_engine = None
_agent_orchestrator = None
_memory_system = None
_tool_manager = None
_model_interface = None
_router = None
_supermind = None

def _lazy_init():
    """延迟初始化 SuperMind 组件"""
    global _rag_engine, _agent_orchestrator, _memory_system
    global _tool_manager, _model_interface, _router, _supermind
    
    if _supermind is not None:
        return
    
    try:
        from main import SuperMind
        _supermind = SuperMind()
    except Exception as e:
        print(f"[SuperMind] 初始化失败: {e}", file=sys.stderr)
        _supermind = None


class SuperMindAdapter:
    """
    SuperMind OpenClaw 适配器
    
    自动拦截 OpenClaw 的请求，通过 SuperMind 增强后返回
    """
    
    def __init__(self):
        self.enabled = True
        self.auto_mode = True  # 自动判断是否需要增强
        self.min_complexity = 3  # 复杂度阈值
        
    def should_enhance(self, message: str) -> bool:
        """判断是否需要 SuperMind 增强"""
        if not self.enabled or not self.auto_mode:
            return False
        
        # 简单消息直接过
        if len(message) < 20:
            return False
        
        # 检查是否需要复杂处理
        indicators = [
            '分析', '研究', '调研', '设计', '实现',
            '代码', '编程', '写个', '帮我', '请',
            '如何', '怎么', '为什么', '比较', '对比',
            '优化', '改进', '重构', '架构',
            '步骤', '流程', '方案', '策略'
        ]
        
        message_lower = message.lower()
        for indicator in indicators:
            if indicator in message_lower:
                return True
        
        # 长消息默认增强
        if len(message) > 100:
            return True
        
        return False
    
    def enhance_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """
        增强用户消息
        
        返回优化后的提示，包含：
        - RAG 检索的上下文
        - 相关记忆
        - 系统提示
        """
        _lazy_init()
        
        if _supermind is None:
            return message
        
        try:
            # 使用 SuperMind 的上下文构建能力
            enhanced_parts = [message]
            
            # 检索知识
            rag_context = _supermind.rag.retrieve(message) if _supermind.rag else None
            if rag_context and rag_context.get('documents'):
                context_str = _supermind.rag.format_context(rag_context)
                if context_str:
                    enhanced_parts.insert(0, f"## 参考资料\n{context_str}\n")
            
            # 检索记忆
            mem_context = _supermind.memory.build_context(message) if _supermind.memory else None
            if mem_context:
                enhanced_parts.insert(0, f"## 历史上下文\n{mem_context}\n")
            
            return "\n\n".join(enhanced_parts)
            
        except Exception as e:
            print(f"[SuperMind] 增强失败: {e}", file=sys.stderr)
            return message
    
    def process_response(self, response: str, original_message: str) -> str:
        """
        处理模型响应
        
        - 保存到记忆
        - 提取技能
        - 格式化输出
        """
        _lazy_init()
        
        if _supermind is None:
            return response
        
        try:
            # 保存交互
            if _supermind.memory:
                _supermind.memory.save_interaction(original_message, response)
            
            return response
            
        except Exception as e:
            print(f"[SuperMind] 响应处理失败: {e}", file=sys.stderr)
            return response


class AutoSuperMind:
    """
    自动 SuperMind 模式
    
    完全自动化的集成：
    1. 自动判断是否需要复杂处理
    2. 简单查询 → 直接回答
    3. 复杂任务 → Agent 编排
    4. 代码请求 → 代码生成 + 验证
    5. 知识查询 → RAG 增强
    """
    
    def __init__(self):
        self.adapter = SuperMindAdapter()
        self.mode = "auto"  # auto, simple, always
        
    async def chat(self, message: str, history: list = None) -> str:
        """
        自动处理聊天消息
        
        这是主要的自动集成入口
        """
        _lazy_init()
        
        if _supermind is None:
            return None  # 让 OpenClaw 使用默认模型
        
        try:
            # 路由决策
            if self.mode == "simple":
                # 简单模式 - 仅 RAG 增强
                return await self._simple_enhance(message)
            
            elif self.mode == "always":
                # 总是使用 SuperMind
                return await self._full_process(message)
            
            else:  # auto 模式
                # 自动判断
                return await self._auto_process(message)
                
        except Exception as e:
            print(f"[SuperMind] 处理失败: {e}", file=sys.stderr)
            return None
    
    async def _auto_process(self, message: str) -> str:
        """自动模式处理"""
        
        # 检查是否是代码请求
        code_keywords = ['代码', '编程', '写个', '实现', 'function', 'def ', 'class ']
        if any(kw in message.lower() for kw in code_keywords):
            return _supermind.code(message)
        
        # 检查是否是知识查询
        knowledge_keywords = ['是什么', '什么是', '怎么', '如何', '为什么', '有哪些']
        if any(kw in message.lower() for kw in knowledge_keywords):
            return _supermind.ask(message)
        
        # 检查复杂度
        if len(message) > 100 or '帮我' in message:
            return _supermind.execute(message)
        
        # 简单查询 - RAG 增强后返回
        return await self._simple_enhance(message)
    
    async def _simple_enhance(self, message: str) -> str:
        """简单增强模式"""
        return _supermind.ask(message, use_rag=True)
    
    async def _full_process(self, message: str) -> str:
        """完整处理模式"""
        return _supermind.execute(message)
    
    def set_mode(self, mode: str):
        """设置模式"""
        self.mode = mode
        print(f"[SuperMind] 模式切换为: {mode}")


# 全局实例
auto_supermind = AutoSuperMind()


# OpenClaw 集成的钩子函数
def on_message(message: str, context: dict = None) -> Optional[str]:
    """
    OpenClaw 消息钩子
    
    在 OpenClaw 处理消息前调用
    返回 None 让 OpenClaw 继续处理
    返回字符串则直接使用该结果
    """
    # 检查是否启用
    if not os.environ.get('SUPERMIND_AUTO', '1') == '1':
        return None
    
    # 异步处理
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    result = loop.run_until_complete(auto_supermind.chat(message))
    return result


def on_response(response: str, original_message: str) -> str:
    """
    OpenClaw 响应钩子
    
    在 OpenClaw 生成响应后调用
    可以修改响应内容
    """
    if not os.environ.get('SUPERMIND_AUTO', '1') == '1':
        return response
    
    return auto_supermind.adapter.process_response(response, original_message)


# 命令快捷方式
def sm_ask(question: str) -> str:
    """知识问答"""
    _lazy_init()
    if _supermind:
        return _supermind.ask(question)
    return "SuperMind 未初始化"


def sm_code(request: str, language: str = "python") -> str:
    """代码生成"""
    _lazy_init()
    if _supermind:
        return _supermind.code(request, language)
    return "SuperMind 未初始化"


def sm_execute(task: str) -> str:
    """执行任务"""
    _lazy_init()
    if _supermind:
        return _supermind.execute(task)
    return "SuperMind 未初始化"


def sm_research(topic: str) -> str:
    """深度研究"""
    _lazy_init()
    if _supermind:
        return _supermind.research(topic)
    return "SuperMind 未初始化"


def sm_stats() -> dict:
    """获取统计信息"""
    _lazy_init()
    if _supermind:
        return _supermind.stats()
    return {}


# 便捷命令
commands = {
    '/sm-ask': sm_ask,
    '/sm-code': sm_code,
    '/sm-do': sm_execute,
    '/sm-research': sm_research,
    '/sm-stats': sm_stats,
    '/sm-on': lambda: auto_supermind.set_mode('auto'),
    '/sm-off': lambda: auto_supermind.set_mode('simple'),
}


def handle_command(cmd: str, args: str) -> str:
    """处理 SuperMind 命令"""
    if cmd in commands:
        func = commands[cmd]
        if args:
            return func(args)
        else:
            return func()
    return f"未知命令: {cmd}"


if __name__ == "__main__":
    # 测试
    print("SuperMind Auto Integration Test")
    print("-" * 50)
    
    # 测试初始化
    _lazy_init()
    
    if _supermind:
        print("✓ SuperMind 初始化成功")
        print(f"  模型: {_supermind.config['model']['name']}")
        print(f"  RAG: {'✓' if _supermind.rag else '✗'}")
        print(f"  Agent: {'✓' if _supermind.agent else '✗'}")
        print(f"  Memory: {'✓' if _supermind.memory else '✗'}")
        print(f"  Tools: {'✓' if _supermind.tools else '✗'}")
    else:
        print("✗ SuperMind 初始化失败")
        print("  请确保已运行: python scripts/init.py")
