"""
Model Interface - 模型接口封装
支持 Ollama 等本地模型服务
"""

import json
import httpx
import time
from typing import Dict, Any, Optional, List, Generator
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class GenerationResult:
    """生成结果"""
    text: str
    tokens_used: int = 0
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = None


class ModelInterface:
    """
    模型接口
    
    封装对本地模型（Ollama）的调用
    支持：
    - 同步生成
    - 流式生成
    - 多轮对话
    - 工具调用
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get('name', 'qwen3.5-35b-a3b')
        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 4096)
        self.context_window = config.get('context_window', 32768)
        
        self.client = httpx.Client(base_url=self.base_url, timeout=300.0)
        
        # 对话历史
        self.conversation_history: List[Dict[str, str]] = []
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None) -> str:
        """
        同步生成文本
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度（覆盖配置）
            max_tokens: 最大token数（覆盖配置）
            
        Returns:
            生成的文本
        """
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        messages = []
        
        # 系统提示
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # 历史对话
        messages.extend(self.conversation_history)
        
        # 当前提示
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # 构建请求
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": max_tok
            }
        }
        
        try:
            response = self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            
            result = response.json()
            generated_text = result.get('message', {}).get('content', '')
            
            # 更新历史
            self.conversation_history.append({
                "role": "user",
                "content": prompt
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": generated_text
            })
            
            # 限制历史长度
            self._trim_history()
            
            return generated_text
            
        except httpx.HTTPError as e:
            raise Exception(f"模型调用失败: {e}")
    
    def generate_stream(self, prompt: str, 
                        system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        """
        流式生成
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            
        Yields:
            生成的文本片段
        """
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.extend(self.conversation_history)
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self.temperature
            }
        }
        
        try:
            with self.client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                
                full_text = ""
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if 'message' in data:
                                chunk = data['message'].get('content', '')
                                full_text += chunk
                                yield chunk
                            
                            if data.get('done'):
                                # 更新历史
                                self.conversation_history.append({
                                    "role": "user",
                                    "content": prompt
                                })
                                self.conversation_history.append({
                                    "role": "assistant",
                                    "content": full_text
                                })
                                self._trim_history()
                                break
                        except json.JSONDecodeError:
                            continue
                            
        except httpx.HTTPError as e:
            raise Exception(f"流式生成失败: {e}")
    
    def chat(self, messages: List[Dict[str, str]], 
             system_prompt: Optional[str] = None) -> str:
        """
        多轮对话
        
        Args:
            messages: 消息列表 [{"role": "user/assistant", "content": "..."}]
            system_prompt: 系统提示
            
        Returns:
            助手回复
        """
        all_messages = []
        
        if system_prompt:
            all_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        all_messages.extend(messages)
        
        payload = {
            "model": self.model_name,
            "messages": all_messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        }
        
        try:
            response = self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result.get('message', {}).get('content', '')
            
        except httpx.HTTPError as e:
            raise Exception(f"对话失败: {e}")
    
    def generate_with_tools(self, prompt: str, 
                            tools: List[Dict[str, Any]],
                            system_prompt: Optional[str] = None,
                            max_tool_calls: int = 5) -> str:
        """
        带工具调用的生成
        
        Args:
            prompt: 用户提示
            tools: 工具定义列表
            system_prompt: 系统提示
            max_tool_calls: 最大工具调用次数
            
        Returns:
            最终回复
        """
        # 构建工具提示
        tool_descriptions = self._format_tools(tools)
        
        full_system = system_prompt or ""
        full_system += f"\n\n你可以使用以下工具:\n{tool_descriptions}\n"
        full_system += """
当你需要使用工具时，请按以下格式输出:
```tool_call
{
    "tool": "工具名称",
    "params": {"参数名": "参数值"}
}
```
"""
        
        current_prompt = prompt
        tool_calls_count = 0
        tool_results = []
        
        while tool_calls_count < max_tool_calls:
            response = self.generate(current_prompt, full_system)
            
            # 检查是否有工具调用
            tool_call = self._extract_tool_call(response)
            
            if not tool_call:
                # 没有工具调用，返回结果
                if tool_results:
                    # 添加工具结果到最终回复
                    return self._add_tool_context(response, tool_results)
                return response
            
            # 执行工具调用
            tool_calls_count += 1
            tool_name = tool_call.get('tool')
            tool_params = tool_call.get('params', {})
            
            # 这里需要通过 ToolManager 执行
            # 暂时记录工具调用请求
            tool_results.append({
                'call': tool_call,
                'result': None  # 由调用方填充
            })
            
            # 更新提示，请求继续生成
            current_prompt += f"\n\n[工具调用: {tool_name}]\n请基于工具结果继续回答。"
        
        return response
    
    def _format_tools(self, tools: List[Dict[str, Any]]) -> str:
        """格式化工具描述"""
        descriptions = []
        for tool in tools:
            name = tool.get('name', 'unknown')
            desc = tool.get('description', '')
            schema = tool.get('schema', {})
            
            descriptions.append(
                f"- {name}: {desc}\n  参数: {json.dumps(schema, ensure_ascii=False)}"
            )
        
        return "\n".join(descriptions)
    
    def _extract_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """提取工具调用"""
        import re
        
        pattern = r'```tool_call\s*(.*?)\s*```'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
        
        return None
    
    def _add_tool_context(self, response: str, 
                          tool_results: List[Dict]) -> str:
        """添加工具上下文到回复"""
        # 实际实现中，这里应该重新生成包含工具结果的回复
        return response
    
    def _trim_history(self):
        """修剪历史对话，保持在上下文窗口内"""
        # 简单策略：保留最近 10 轮对话
        max_history = 20  # 10轮 = 20条消息
        
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self.conversation_history.copy()
    
    def check_model(self) -> bool:
        """检查模型是否可用"""
        try:
            response = self.client.get("/api/tags")
            response.raise_for_status()
            
            models = response.json().get('models', [])
            model_names = [m.get('name') for m in models]
            
            return self.model_name in model_names
            
        except:
            return False
    
    def pull_model(self) -> bool:
        """拉取模型"""
        try:
            payload = {
                "name": self.model_name
            }
            
            with self.client.stream("POST", "/api/pull", json=payload) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        if 'error' in data:
                            raise Exception(data['error'])
                        if data.get('status') == 'success':
                            return True
                
                return True
                
        except Exception as e:
            raise Exception(f"拉取模型失败: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        try:
            response = self.client.post("/api/show", json={
                "name": self.model_name
            })
            response.raise_for_status()
            return response.json()
        except:
            return {}
    
    def generate_simple(self, prompt: str) -> str:
        """
        简单生成（不维护历史）
        
        用于内部调用，不影响对话历史
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        }
        
        try:
            response = self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
            
        except httpx.HTTPError as e:
            raise Exception(f"生成失败: {e}")
