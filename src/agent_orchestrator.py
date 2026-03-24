"""
Agent Orchestrator - 任务编排系统
基于 CrewAI 和 Dify 的理念实现
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import time


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Task:
    """任务对象"""
    id: str
    description: str
    agent_name: str
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class ExecutionPlan:
    """执行计划"""
    tasks: List[Task]
    parallel_groups: List[List[str]]  # 可并行执行的组


class SubAgent:
    """子代理基类"""
    
    def __init__(self, name: str, system_prompt: str, model_interface):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model_interface
        self.history = []
    
    def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        """执行任务"""
        # 构建提示
        prompt = self._build_prompt(task, context)
        
        # 调用模型
        response = self.model.generate(
            prompt,
            system_prompt=self.system_prompt
        )
        
        # 记录历史
        self.history.append({
            'task': task,
            'response': response,
            'timestamp': time.time()
        })
        
        return response
    
    def _build_prompt(self, task: str, context: Dict[str, Any] = None) -> str:
        """构建任务提示"""
        prompt_parts = [f"## 任务\n{task}\n"]
        
        if context:
            prompt_parts.append("## 上下文")
            for key, value in context.items():
                prompt_parts.append(f"{key}: {value}")
            prompt_parts.append("")
        
        prompt_parts.append("## 执行")
        
        return "\n".join(prompt_parts)


class AgentOrchestrator:
    """
    Agent 编排器
    
    负责：
    1. 任务分解
    2. 执行计划生成
    3. 任务调度与执行
    4. 结果整合
    """
    
    def __init__(self, model, memory, tools, config: Dict[str, Any]):
        self.model = model
        self.memory = memory
        self.tools = tools
        self.config = config
        
        self.max_iterations = config.get('max_iterations', 5)
        self.parallel_execution = config.get('parallel_execution', True)
        self.max_workers = config.get('max_workers', 4)
        
        # 初始化子代理
        self.agents = self._init_agents()
        
        # 执行器
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
    
    def _init_agents(self) -> Dict[str, SubAgent]:
        """初始化子代理"""
        agents_config = self.config.get('sub_agents', [])
        
        default_agents = {
            'analyzer': SubAgent(
                name='analyzer',
                system_prompt='''你是一个需求分析专家。你的职责：
1. 深入理解用户需求
2. 识别关键要素和约束
3. 输出结构化的需求分析
4. 指出潜在的风险和难点''',
                model_interface=self.model
            ),
            'planner': SubAgent(
                name='planner',
                system_prompt='''你是一个任务规划专家。你的职责：
1. 将复杂任务分解为可执行的子任务
2. 确定任务依赖关系
3. 设计最优执行顺序
4. 输出清晰的执行计划''',
                model_interface=self.model
            ),
            'executor': SubAgent(
                name='executor',
                system_prompt='''你是一个执行专家。你的职责：
1. 高质量完成分配的任务
2. 遵循最佳实践
3. 详细记录执行过程
4. 遇到问题及时反馈''',
                model_interface=self.model
            ),
            'reviewer': SubAgent(
                name='reviewer',
                system_prompt='''你是一个质量审查专家。你的职责：
1. 检查结果是否符合要求
2. 识别潜在问题和改进点
3. 给出具体的修改建议
4. 确保最终质量达标''',
                model_interface=self.model
            ),
            'integrator': SubAgent(
                name='integrator',
                system_prompt='''你是一个结果整合专家。你的职责：
1. 汇总各子任务的结果
2. 消除矛盾和不一致
3. 形成完整、连贯的最终输出
4. 确保格式规范、易于理解''',
                model_interface=self.model
            )
        }
        
        # 覆盖自定义配置
        for agent_config in agents_config:
            name = agent_config['name']
            if name in default_agents:
                default_agents[name].system_prompt = agent_config.get(
                    'system_prompt', default_agents[name].system_prompt
                )
        
        return default_agents
    
    def execute(self, task: str, **kwargs) -> str:
        """
        执行复杂任务
        
        Args:
            task: 任务描述
            **kwargs: 额外参数
            
        Returns:
            执行结果
        """
        iteration = 0
        context = kwargs.get('context', {})
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Step 1: 需求分析
            analysis = self._analyze(task, context)
            
            # Step 2: 任务规划
            plan = self._plan(analysis, context)
            
            # Step 3: 执行任务
            results = self._execute_plan(plan, context)
            
            # Step 4: 质量审查
            review = self._review(results, plan)
            
            # Step 5: 检查是否需要迭代
            if review.get('pass', True):
                # 通过审查，整合结果
                final = self._integrate(results, plan)
                return final
            else:
                # 需要修正
                if iteration < self.max_iterations:
                    context['previous_attempt'] = results
                    context['review_feedback'] = review.get('feedback', '')
                    task = f"基于反馈修正: {review.get('feedback')}"
                else:
                    # 达到最大迭代次数，返回当前最佳结果
                    return self._integrate(results, plan)
        
        return self._integrate(results, plan)
    
    def _analyze(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """需求分析"""
        agent = self.agents['analyzer']
        
        prompt = f"""请分析以下任务：

{task}

请输出JSON格式的分析结果：
{{
    "requirements": ["需求1", "需求2", ...],
    "constraints": ["约束1", "约束2", ...],
    "key_points": ["关键点1", "关键点2", ...],
    "difficulty": "easy/medium/hard",
    "suggested_approach": "建议的方法"
}}"""
        
        response = agent.execute(prompt, context)
        
        # 解析JSON
        try:
            # 提取JSON部分
            json_match = self._extract_json(response)
            analysis = json.loads(json_match)
        except:
            analysis = {
                'requirements': [task],
                'constraints': [],
                'key_points': [],
                'difficulty': 'medium',
                'suggested_approach': 'standard',
                'raw_response': response
            }
        
        return analysis
    
    def _plan(self, analysis: Dict[str, Any], 
              context: Dict[str, Any]) -> ExecutionPlan:
        """生成执行计划"""
        agent = self.agents['planner']
        
        prompt = f"""基于以下分析，制定执行计划：

需求分析：
{json.dumps(analysis, ensure_ascii=False, indent=2)}

请输出JSON格式的执行计划：
{{
    "tasks": [
        {{
            "id": "task_1",
            "description": "任务描述",
            "agent": "executor/reviewer/analyzer",
            "dependencies": []
        }}
    ],
    "parallel_groups": [["task_1", "task_2"], ["task_3"]]
}}"""
        
        response = agent.execute(prompt, context)
        
        try:
            json_match = self._extract_json(response)
            plan_data = json.loads(json_match)
            
            tasks = []
            for t in plan_data.get('tasks', []):
                task = Task(
                    id=t['id'],
                    description=t['description'],
                    agent_name=t.get('agent', 'executor'),
                    dependencies=t.get('dependencies', [])
                )
                tasks.append(task)
            
            return ExecutionPlan(
                tasks=tasks,
                parallel_groups=plan_data.get('parallel_groups', [])
            )
        except:
            # 降级为简单计划
            return ExecutionPlan(
                tasks=[Task(
                    id='task_1',
                    description=analysis.get('requirements', ['执行任务'])[0],
                    agent_name='executor'
                )],
                parallel_groups=[['task_1']]
            )
    
    def _execute_plan(self, plan: ExecutionPlan, 
                      context: Dict[str, Any]) -> Dict[str, Any]:
        """执行计划"""
        results = {}
        task_map = {t.id: t for t in plan.tasks}
        
        # 按并行组执行
        for group in plan.parallel_groups:
            if self.parallel_execution and len(group) > 1:
                # 并行执行
                futures = {}
                for task_id in group:
                    task = task_map[task_id]
                    if self._dependencies_met(task, results):
                        future = self.executor.submit(
                            self._execute_task, task, context, results
                        )
                        futures[task_id] = future
                
                # 收集结果
                for task_id, future in futures.items():
                    try:
                        result = future.result(timeout=120)
                        results[task_id] = result
                        task_map[task_id].status = TaskStatus.COMPLETED
                    except Exception as e:
                        task_map[task_id].status = TaskStatus.FAILED
                        task_map[task_id].error = str(e)
                        results[task_id] = f"执行失败: {e}"
            else:
                # 串行执行
                for task_id in group:
                    task = task_map[task_id]
                    if self._dependencies_met(task, results):
                        result = self._execute_task(task, context, results)
                        results[task_id] = result
        
        return results
    
    def _execute_task(self, task: Task, context: Dict[str, Any],
                      previous_results: Dict[str, Any]) -> str:
        """执行单个任务"""
        agent = self.agents.get(task.agent_name, self.agents['executor'])
        
        # 构建上下文
        task_context = {
            **context,
            'task_id': task.id,
            'previous_results': previous_results
        }
        
        # 执行
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        
        try:
            result = agent.execute(task.description, task_context)
            task.status = TaskStatus.COMPLETED
            task.result = result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            result = f"错误: {e}"
        
        task.end_time = time.time()
        return result
    
    def _dependencies_met(self, task: Task, 
                          results: Dict[str, Any]) -> bool:
        """检查依赖是否满足"""
        for dep in task.dependencies:
            if dep not in results:
                return False
        return True
    
    def _review(self, results: Dict[str, Any], 
                plan: ExecutionPlan) -> Dict[str, Any]:
        """质量审查"""
        agent = self.agents['reviewer']
        
        prompt = f"""请审查以下执行结果：

执行结果：
{json.dumps(results, ensure_ascii=False, indent=2)}

原始计划：
{json.dumps([{'id': t.id, 'desc': t.description} for t in plan.tasks], ensure_ascii=False)}

请输出JSON格式的审查结果：
{{
    "pass": true/false,
    "score": 85,
    "issues": ["问题1", "问题2"],
    "feedback": "改进建议",
    "suggestions": ["建议1", "建议2"]
}}"""
        
        response = agent.execute(prompt)
        
        try:
            json_match = self._extract_json(response)
            review = json.loads(json_match)
        except:
            review = {
                'pass': True,
                'score': 80,
                'issues': [],
                'feedback': '审查通过',
                'suggestions': []
            }
        
        return review
    
    def _integrate(self, results: Dict[str, Any], 
                   plan: ExecutionPlan) -> str:
        """整合结果"""
        agent = self.agents['integrator']
        
        # 按任务顺序组织结果
        ordered_results = []
        for task in plan.tasks:
            if task.id in results:
                ordered_results.append({
                    'task': task.description,
                    'result': results[task.id]
                })
        
        prompt = f"""请将以下执行结果整合为完整的输出：

各步骤结果：
{json.dumps(ordered_results, ensure_ascii=False, indent=2)}

要求：
1. 形成连贯的完整回答
2. 消除重复和矛盾
3. 格式清晰、易于阅读
4. 保留所有关键信息"""
        
        final = agent.execute(prompt)
        return final
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        # 尝试找到JSON代码块
        import re
        
        # 匹配 ```json ... ```
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1)
        
        # 匹配 { ... }
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        
        return text
