"""
Router - 智能任务路由
自动选择最优处理策略
"""

import re
from typing import Dict, Any, Optional
from enum import Enum


class TaskType(Enum):
    """任务类型"""
    QA = "qa"                      # 知识问答
    CODE = "code"                  # 代码生成
    RESEARCH = "research"          # 深度研究
    CREATIVE = "creative"          # 创意写作
    ANALYSIS = "analysis"          # 分析任务
    ORCHESTRATION = "orchestration"  # 需要编排的复杂任务
    TOOL = "tool"                  # 需要工具的简单任务
    CHAT = "chat"                  # 闲聊对话


class TaskRouter:
    """
    智能任务路由器
    
    根据输入特征，自动选择：
    - 是否使用 RAG
    - 是否使用 Agent 编排
    - 是否调用工具
    - 使用哪种系统提示
    """
    
    def __init__(self):
        self.patterns = self._init_patterns()
    
    def _init_patterns(self) -> Dict[TaskType, list]:
        """初始化任务类型模式"""
        return {
            TaskType.CODE: [
                r'写代码|实现|function|def |class |import |代码|编程|程序',
                r'用\w+写|写一个|实现一个|写个',
                r'算法|排序|遍历|递归|循环|条件',
                r'API|接口|请求|响应|json|xml'
            ],
            
            TaskType.RESEARCH: [
                r'研究|调研|分析.*现状|现状分析|发展趋势',
                r'对比|比较|vs|versus|区别|优劣',
                r'综述|概述|总结.*领域|领域总结',
                r'文献|论文|文章|报告|调查'
            ],
            
            TaskType.ANALYSIS: [
                r'分析|解析|剖析|诊断|评估|评价',
                r'为什么|原因|原理|机制|逻辑',
                r'优化|改进|提升|性能|效率'
            ],
            
            TaskType.ORCHESTRATION: [
                r'帮我.*并.*然后|先.*再.*最后|步骤|流程',
                r'设计.*实现|开发.*测试|完整.*方案',
                r'项目|系统|架构|模块|组件|服务',
                r'文档|README|技术文档|使用说明'
            ],
            
            TaskType.QA: [
                r'是什么|什么是|怎么|如何|为什么|介绍',
                r'有哪些|有什么|区别|特点|特性|优缺点',
                r'原理|概念|定义|含义|意思'
            ],
            
            TaskType.CREATIVE: [
                r'写.*故事|创作|创意|想象|假设',
                r'诗歌|散文|小说|剧本|文案|广告',
                r'有趣|好玩|幽默|搞笑|浪漫|感人'
            ],
            
            TaskType.TOOL: [
                r'计算|等于|等于几|结果是',
                r'现在时间|今天日期|timestamp',
                r'搜索|查找|最新|实时|现在|今天.*新闻',
                r'运行.*代码|执行.*脚本|测试.*程序'
            ],
            
            TaskType.CHAT: [
                r'你好|嗨|hello|hi|在吗',
                r'谢谢|感谢|辛苦了|真棒',
                r'再见|拜拜|bye|goodbye'
            ]
        }
    
    def route(self, query: str) -> Dict[str, Any]:
        """
        路由任务
        
        Returns:
            {
                'task_type': TaskType,
                'use_rag': bool,
                'use_agent': bool,
                'use_tools': bool,
                'system_prompt': str,
                'strategy': str
            }
        """
        # 识别任务类型
        task_type = self._classify(query)
        
        # 确定策略
        strategy = self._determine_strategy(task_type, query)
        
        return {
            'task_type': task_type,
            'use_rag': strategy['use_rag'],
            'use_agent': strategy['use_agent'],
            'use_tools': strategy['use_tools'],
            'system_prompt': self._get_system_prompt(task_type),
            'strategy': strategy['name']
        }
    
    def _classify(self, query: str) -> TaskType:
        """分类任务类型"""
        query_lower = query.lower()
        
        scores = {}
        for task_type, patterns in self.patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    score += 1
            scores[task_type] = score
        
        # 选择得分最高的类型
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        # 默认类型
        return TaskType.QA
    
    def _determine_strategy(self, task_type: TaskType, 
                           query: str) -> Dict[str, Any]:
        """确定执行策略"""
        
        strategies = {
            TaskType.CODE: {
                'name': 'code_generation',
                'use_rag': True,      # 检索代码示例
                'use_agent': False,   # 代码任务通常单步完成
                'use_tools': True     # 验证代码
            },
            
            TaskType.RESEARCH: {
                'name': 'deep_research',
                'use_rag': True,      # 需要大量知识
                'use_agent': True,    # 需要多步骤
                'use_tools': True     # 可能需要搜索
            },
            
            TaskType.ANALYSIS: {
                'name': 'analysis',
                'use_rag': True,
                'use_agent': len(query) > 100,  # 复杂分析用Agent
                'use_tools': False
            },
            
            TaskType.ORCHESTRATION: {
                'name': 'full_orchestration',
                'use_rag': True,
                'use_agent': True,    # 必须使用Agent
                'use_tools': True
            },
            
            TaskType.QA: {
                'name': 'rag_qa',
                'use_rag': True,      # 知识问答必须用RAG
                'use_agent': False,
                'use_tools': False
            },
            
            TaskType.CREATIVE: {
                'name': 'creative',
                'use_rag': False,     # 创意不需要检索
                'use_agent': False,
                'use_tools': False
            },
            
            TaskType.TOOL: {
                'name': 'tool_direct',
                'use_rag': False,
                'use_agent': False,
                'use_tools': True     # 必须用工具
            },
            
            TaskType.CHAT: {
                'name': 'chat',
                'use_rag': False,
                'use_agent': False,
                'use_tools': False
            }
        }
        
        strategy = strategies.get(task_type, strategies[TaskType.QA])
        
        # 根据查询长度调整
        if len(query) > 200 and not strategy['use_agent']:
            strategy['use_agent'] = True
            strategy['name'] += '_enhanced'
        
        return strategy
    
    def _get_system_prompt(self, task_type: TaskType) -> str:
        """获取系统提示"""
        prompts = {
            TaskType.CODE: """你是一个专业的程序员。生成代码时：
1. 代码正确、完整、可运行
2. 添加清晰的注释
3. 处理边界情况
4. 遵循最佳实践
5. 提供使用示例""",

            TaskType.RESEARCH: """你是一个研究专家。进行研究时：
1. 全面收集信息
2. 多角度分析
3. 引用可靠来源
4. 结构清晰呈现
5. 指出不确定性""",

            TaskType.ANALYSIS: """你是一个分析专家。分析问题时：
1. 逻辑清晰严谨
2. 考虑多种因素
3. 数据支持观点
4. 结论有理有据
5. 给出可行建议""",

            TaskType.ORCHESTRATION: """你是一个项目管理专家。处理复杂任务时：
1. 仔细分析需求
2. 制定详细计划
3. 分步执行验证
4. 及时调整优化
5. 确保最终质量""",

            TaskType.QA: """你是一个知识渊博的助手。回答问题时：
1. 准确可靠
2. 引用来源
3. 结构清晰
4. 适度详细
5. 承认不确定""",

            TaskType.CREATIVE: """你是一个创意专家。创作时：
1. 想象丰富
2. 表达生动
3. 情感真挚
4. 结构完整
5. 引人入胜""",

            TaskType.TOOL: """你是一个工具使用专家。使用工具时：
1. 准确调用
2. 正确处理结果
3. 整合到回答中
4. 解释工具输出""",

            TaskType.CHAT: """你是一个友好的对话伙伴。聊天时：
1. 亲切自然
2. 积极回应
3. 有帮助性
4. 适度幽默
5. 尊重用户"""
        }
        
        return prompts.get(task_type, prompts[TaskType.QA])
    
    def should_use_rag(self, query: str) -> bool:
        """判断是否应该使用 RAG"""
        routing = self.route(query)
        return routing['use_rag']
    
    def should_use_agent(self, query: str) -> bool:
        """判断是否应该使用 Agent"""
        routing = self.route(query)
        return routing['use_agent']
    
    def get_complexity_score(self, query: str) -> int:
        """
        计算任务复杂度分数 (1-10)
        
        用于动态调整策略
        """
        score = 1
        
        # 长度因素
        length = len(query)
        if length > 500:
            score += 3
        elif length > 200:
            score += 2
        elif length > 100:
            score += 1
        
        # 关键词复杂度
        complex_keywords = [
            r'设计|架构|系统|框架',
            r'实现|开发|编写|创建',
            r'分析|研究|调研|对比',
            r'优化|改进|重构|完善',
            r'多.*步骤|流程|pipeline'
        ]
        
        for kw in complex_keywords:
            if re.search(kw, query):
                score += 1
        
        # 问题数量
        question_count = query.count('?') + query.count('？')
        score += min(question_count, 3)
        
        return min(score, 10)
