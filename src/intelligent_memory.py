"""
智能记忆系统 v2.0 - 从存储到智能
实现 Phase 1-3: 技能自动提取、记忆演化、跨任务迁移

基于 MemOS 理念的增强实现
"""

import os
import sys
import json
import time
import hashlib
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import sqlite3
from collections import defaultdict
import numpy as np


@dataclass
class Skill:
    """技能对象 - 增强版"""
    id: str
    name: str
    pattern: str  # 匹配模式
    template: str  # 技能模板
    description: str
    examples: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # 使用统计
    usage_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    last_used: float = 0.0
    
    # 演化相关
    version: int = 1
    parent_skill_id: Optional[str] = None  # 父技能（演化来源）
    evolved_from: List[str] = field(default_factory=list)  # 演化历史
    
    # 关联任务
    source_tasks: List[str] = field(default_factory=list)  # 来源任务
    similar_tasks: List[str] = field(default_factory=list)  # 相似任务
    
    # 元数据
    tags: List[str] = field(default_factory=list)
    complexity: float = 1.0  # 复杂度 1-10
    domain: str = "general"  # 领域


@dataclass
class TaskExecution:
    """任务执行记录"""
    task_id: str
    task_description: str
    solution: str
    execution_time: float
    success: bool
    quality_score: float  # 0-10
    timestamp: float
    
    # 使用的技能
    skills_used: List[str] = field(default_factory=list)
    
    # 反馈
    user_feedback: Optional[str] = None
    auto_evaluation: Optional[Dict] = None


class SkillAutoExtractor:
    """
    Phase 1: 技能自动提取器
    从成功任务执行中自动提取可复用技能
    """
    
    def __init__(self, min_success_rate: float = 0.8, min_usage_count: int = 2):
        self.min_success_rate = min_success_rate
        self.min_usage_count = min_usage_count
        
        # 成功任务缓存
        self.successful_executions: List[TaskExecution] = []
        
    def record_execution(self, execution: TaskExecution):
        """记录任务执行"""
        self.successful_executions.append(execution)
        
        # 如果执行成功且质量高，尝试提取技能
        if execution.success and execution.quality_score >= 7:
            return self._try_extract_skill(execution)
        
        return None
    
    def _try_extract_skill(self, execution: TaskExecution) -> Optional[Skill]:
        """尝试从执行中提取技能"""
        
        # 1. 分析任务类型
        task_type = self._classify_task(execution.task_description)
        
        # 2. 提取通用模式
        pattern = self._extract_pattern(execution.task_description)
        
        # 3. 提取可复用模板
        template = self._extract_template(execution.solution)
        
        # 4. 检查是否已存在相似技能
        if self._is_duplicate(pattern, template):
            return None
        
        # 5. 创建技能
        skill = Skill(
            id=self._generate_skill_id(),
            name=self._generate_skill_name(execution.task_description),
            pattern=pattern,
            template=template,
            description=f"从任务'{execution.task_description[:50]}...'提取的技能",
            examples=[execution.task_description],
            source_tasks=[execution.task_id],
            domain=task_type,
            complexity=self._calculate_complexity(execution.solution),
            tags=self._extract_tags(execution.task_description)
        )
        
        return skill
    
    def _classify_task(self, task: str) -> str:
        """分类任务类型"""
        task_lower = task.lower()
        
        if any(kw in task_lower for kw in ['代码', '编程', 'function', 'def ', 'class ']):
            return 'code'
        elif any(kw in task_lower for kw in ['分析', '研究', '调研']):
            return 'analysis'
        elif any(kw in task_lower for kw in ['设计', '架构', '系统']):
            return 'design'
        elif any(kw in task_lower for kw in ['写', '创作', '生成']):
            return 'writing'
        else:
            return 'general'
    
    def _extract_pattern(self, task: str) -> str:
        """提取任务模式（泛化）"""
        # 将具体任务泛化为模式
        pattern = task
        
        # 替换具体实体为占位符
        pattern = re.sub(r'\b[A-Z][a-zA-Z]+\b', '{Entity}', pattern)  # 专有名词
        pattern = re.sub(r'\b\d+\b', '{Number}', pattern)  # 数字
        pattern = re.sub(r'["\'][^"\']+["\']', '{String}', pattern)  # 字符串
        
        return pattern
    
    def _extract_template(self, solution: str) -> str:
        """提取解决方案模板"""
        # 提取可复用的代码/结构
        template = solution
        
        # 如果是代码，提取框架
        if '```' in solution:
            # 保留代码结构，注释说明可变部分
            template = self._extract_code_template(solution)
        
        return template
    
    def _extract_code_template(self, code: str) -> str:
        """提取代码模板"""
        lines = code.split('\n')
        template_lines = []
        
        for line in lines:
            # 保留结构，替换具体值
            if re.match(r'\s*#', line):  # 注释
                template_lines.append(line)
            elif '=' in line and not line.strip().startswith('def ') and not line.strip().startswith('class '):
                # 变量赋值 -> 模板化
                template_lines.append(re.sub(r'=\s*.+', '= {VALUE}', line))
            else:
                template_lines.append(line)
        
        return '\n'.join(template_lines)
    
    def _is_duplicate(self, pattern: str, template: str) -> bool:
        """检查是否已存在相似技能"""
        # 简化检查 - 实际应查询技能库
        return False
    
    def _generate_skill_id(self) -> str:
        """生成技能ID"""
        return f"skill_{int(time.time())}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
    
    def _generate_skill_name(self, task: str) -> str:
        """生成技能名称"""
        # 提取关键词
        words = task.split()[:3]
        return '_'.join(words).lower().replace(' ', '_').replace('.', '').replace(',', '')
    
    def _calculate_complexity(self, solution: str) -> float:
        """计算复杂度"""
        # 基于代码行数、逻辑复杂度等
        lines = len(solution.split('\n'))
        loops = solution.count('for ') + solution.count('while ')
        conditions = solution.count('if ') + solution.count('elif ')
        
        complexity = min(10, (lines / 10) + loops * 0.5 + conditions * 0.3)
        return max(1, complexity)
    
    def _extract_tags(self, task: str) -> List[str]:
        """提取标签"""
        tags = []
        keywords = {
            'python': ['python', 'py'],
            'javascript': ['javascript', 'js', 'node'],
            'java': ['java'],
            'go': ['golang', 'go '],
            'web': ['web', 'http', 'api', 'rest'],
            'database': ['database', 'sql', 'db', 'mysql', 'postgresql'],
            'ai': ['ai', 'ml', '模型', '训练', '神经网络'],
            'automation': ['自动化', 'auto', '脚本', 'batch']
        }
        
        task_lower = task.lower()
        for tag, keywords_list in keywords.items():
            if any(kw in task_lower for kw in keywords_list):
                tags.append(tag)
        
        return tags


class SkillRecommender:
    """
    Phase 1: 技能主动推荐器
    根据当前任务主动推荐可能用到的技能
    """
    
    def __init__(self, skills_db: Dict[str, Skill]):
        self.skills = skills_db
        self.task_skill_history: Dict[str, List[str]] = defaultdict(list)
        
    def recommend(self, current_task: str, context: Dict = None, 
                  top_k: int = 3) -> List[Tuple[Skill, float]]:
        """
        推荐技能
        
        Returns: [(skill, confidence_score), ...]
        """
        candidates = []
        
        for skill_id, skill in self.skills.items():
            # 计算多个维度的匹配分数
            scores = {
                'semantic': self._semantic_similarity(current_task, skill),
                'historical': self._historical_association(current_task, skill),
                'success': skill.success_rate,
                'popularity': min(1.0, skill.usage_count / 10),
                'recency': self._recency_score(skill)
            }
            
            # 加权综合分数
            confidence = (
                scores['semantic'] * 0.3 +
                scores['historical'] * 0.2 +
                scores['success'] * 0.25 +
                scores['popularity'] * 0.15 +
                scores['recency'] * 0.1
            )
            
            if confidence > 0.3:  # 阈值
                candidates.append((skill, confidence))
        
        # 排序返回
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]
    
    def _semantic_similarity(self, task: str, skill: Skill) -> float:
        """语义相似度"""
        # 简化实现 - 实际应使用嵌入向量
        task_words = set(task.lower().split())
        pattern_words = set(skill.pattern.lower().split())
        
        if not pattern_words:
            return 0.0
        
        overlap = len(task_words & pattern_words)
        return overlap / len(pattern_words)
    
    def _historical_association(self, task: str, skill: Skill) -> float:
        """历史关联度"""
        # 检查过去类似任务是否使用过这个技能
        # 简化实现
        return 0.5 if skill.usage_count > 0 else 0.0
    
    def _recency_score(self, skill: Skill) -> float:
        """时效性分数"""
        if skill.last_used == 0:
            return 0.5
        
        days_since_use = (time.time() - skill.last_used) / 86400
        # 最近使用过的技能分数更高
        return max(0, 1 - days_since_use / 30)
    
    def record_usage(self, task: str, skill_id: str, success: bool):
        """记录技能使用"""
        self.task_skill_history[task].append(skill_id)
        
        if skill_id in self.skills:
            skill = self.skills[skill_id]
            skill.usage_count += 1
            skill.last_used = time.time()
            
            if success:
                skill.success_count += 1
            
            skill.success_rate = skill.success_count / skill.usage_count


class MemoryEvolution:
    """
    Phase 2: 记忆演化系统
    让记忆动态优化，越用越聪明
    """
    
    def __init__(self, memory_system):
        self.memory = memory_system
        self.evolution_cycle = 0
        
    def evolve(self):
        """
        执行记忆演化周期
        定期调用以优化记忆系统
        """
        self.evolution_cycle += 1
        
        results = {
            'cycle': self.evolution_cycle,
            'reinforced': 0,
            'forgotten': 0,
            'associated': 0,
            'abstracted': 0
        }
        
        # 1. 强化高频记忆
        results['reinforced'] = self._reinforce_frequent_memories()
        
        # 2. 遗忘低价值记忆
        results['forgotten'] = self._forget_low_value_memories()
        
        # 3. 建立新关联
        results['associated'] = self._build_new_associations()
        
        # 4. 抽象提炼
        results['abstracted'] = self._abstract_concrete_experiences()
        
        return results
    
    def _reinforce_frequent_memories(self) -> int:
        """强化高频访问的记忆"""
        count = 0
        
        # 获取所有记忆
        all_memories = self.memory.short_term.get_all()
        
        for mem in all_memories:
            # 高频访问的记忆提升重要性
            if mem.access_count > 5:
                old_importance = mem.importance
                mem.importance = min(10, mem.importance + 0.5)
                
                if mem.importance > old_importance:
                    count += 1
        
        return count
    
    def _forget_low_value_memories(self) -> int:
        """遗忘低价值记忆"""
        count = 0
        
        all_memories = self.memory.short_term.get_all()
        current_time = time.time()
        
        for mem in all_memories:
            # 计算记忆价值分数
            age_days = (current_time - mem.timestamp) / 86400
            
            # 价值 = 重要性 × 访问频率 × 衰减因子
            value = (
                mem.importance *
                (mem.access_count + 1) *
                (0.9 ** age_days)  # 时间衰减
            )
            
            # 低价值且过期的记忆删除
            if value < 2 and age_days > 7:
                self.memory.short_term.delete(mem.id)
                count += 1
        
        return count
    
    def _build_new_associations(self) -> int:
        """建立记忆间的新关联"""
        count = 0
        
        # 获取所有记忆
        all_memories = self.memory.short_term.get_all()
        
        # 计算记忆间相似度，建立关联
        for i, mem1 in enumerate(all_memories):
            for mem2 in all_memories[i+1:]:
                similarity = self._calculate_similarity(mem1, mem2)
                
                if similarity > 0.7:
                    # 建立关联
                    self._create_association(mem1.id, mem2.id, similarity)
                    count += 1
        
        return count
    
    def _abstract_concrete_experiences(self) -> int:
        """从具体经验中抽象通用模式"""
        count = 0
        
        # 查找相似任务组
        task_groups = self._group_similar_tasks()
        
        for group in task_groups:
            if len(group) >= 3:  # 至少3个相似任务
                # 抽象为通用技能
                abstract_skill = self._create_abstract_skill(group)
                if abstract_skill:
                    count += 1
        
        return count
    
    def _calculate_similarity(self, mem1, mem2) -> float:
        """计算两个记忆的相似度"""
        # 基于内容相似度
        words1 = set(mem1.content.lower().split())
        words2 = set(mem2.content.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _create_association(self, mem_id1: str, mem_id2: str, strength: float):
        """创建记忆关联"""
        # 在实际实现中，应在数据库中存储关联
        pass
    
    def _group_similar_tasks(self) -> List[List]:
        """分组相似任务"""
        # 简化实现 - 使用简单的聚类
        return []
    
    def _create_abstract_skill(self, task_group: List) -> Optional[Skill]:
        """从任务组创建抽象技能"""
        # 提取共同模式
        return None


class CrossTaskTransfer:
    """
    Phase 3: 跨任务迁移系统
    识别不同任务间的相似性，实现经验复用
    """
    
    def __init__(self, skill_memory: Dict[str, Skill]):
        self.skills = skill_memory
        self.task_embeddings: Dict[str, List[float]] = {}
        
    def find_transfer_opportunities(self, new_task: str) -> List[Dict]:
        """
        查找可迁移的经验
        
        Returns:
            [{
                'skill': Skill,
                'similarity': float,
                'adaptation_hints': List[str],
                'confidence': float
            }]
        """
        opportunities = []
        
        # 计算新任务与所有历史技能的相似度
        for skill_id, skill in self.skills.items():
            similarity = self._calculate_task_similarity(new_task, skill)
            
            if similarity > 0.6:  # 阈值
                # 生成适配建议
                hints = self._generate_adaptation_hints(new_task, skill)
                
                # 计算置信度
                confidence = similarity * skill.success_rate
                
                opportunities.append({
                    'skill': skill,
                    'similarity': similarity,
                    'adaptation_hints': hints,
                    'confidence': confidence
                })
        
        # 按置信度排序
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        return opportunities
    
    def _calculate_task_similarity(self, task: str, skill: Skill) -> float:
        """计算任务与技能的相似度"""
        # 多维度相似度
        
        # 1. 关键词重叠
        task_words = set(task.lower().split())
        pattern_words = set(skill.pattern.lower().split())
        keyword_sim = len(task_words & pattern_words) / max(len(task_words), len(pattern_words))
        
        # 2. 领域匹配
        domain_sim = 1.0 if self._extract_domain(task) == skill.domain else 0.3
        
        # 3. 复杂度匹配
        task_complexity = self._estimate_complexity(task)
        complexity_diff = abs(task_complexity - skill.complexity)
        complexity_sim = max(0, 1 - complexity_diff / 10)
        
        # 加权综合
        similarity = (
            keyword_sim * 0.5 +
            domain_sim * 0.3 +
            complexity_sim * 0.2
        )
        
        return similarity
    
    def _extract_domain(self, task: str) -> str:
        """提取任务领域"""
        task_lower = task.lower()
        
        domains = {
            'web': ['web', 'http', 'api', 'frontend', 'backend', 'server'],
            'database': ['database', 'sql', 'db', 'query', 'storage'],
            'ai': ['ai', 'ml', 'model', 'train', 'neural', 'deep learning'],
            'automation': ['auto', 'script', 'batch', 'cron', 'schedule'],
            'devops': ['docker', 'k8s', 'kubernetes', 'deploy', 'ci/cd']
        }
        
        for domain, keywords in domains.items():
            if any(kw in task_lower for kw in keywords):
                return domain
        
        return 'general'
    
    def _estimate_complexity(self, task: str) -> float:
        """估算任务复杂度"""
        # 基于关键词和长度
        complexity = len(task) / 50  # 长度因子
        
        # 关键词复杂度
        complex_keywords = ['设计', '架构', '系统', '优化', '算法', '多线程']
        for kw in complex_keywords:
            if kw in task:
                complexity += 1
        
        return min(10, complexity)
    
    def _generate_adaptation_hints(self, new_task: str, skill: Skill) -> List[str]:
        """生成适配建议"""
        hints = []
        
        # 分析差异
        task_domain = self._extract_domain(new_task)
        
        if task_domain != skill.domain:
            hints.append(f"领域从 '{skill.domain}' 适配到 '{task_domain}'")
        
        # 复杂度差异
        task_complexity = self._estimate_complexity(new_task)
        if abs(task_complexity - skill.complexity) > 3:
            if task_complexity > skill.complexity:
                hints.append(f"需要增加复杂度处理（从 {skill.complexity} 到 {task_complexity}）")
            else:
                hints.append(f"可以简化实现（从 {skill.complexity} 到 {task_complexity}）")
        
        # 通用建议
        hints.append("检查边界条件和异常处理")
        hints.append("根据新需求调整变量和配置")
        
        return hints
    
    def suggest_skill_adaptation(self, skill: Skill, new_task: str) -> str:
        """
        建议如何将技能适配到新任务
        """
        hints = self._generate_adaptation_hints(new_task, skill)
        
        suggestion = f"""
基于技能 '{skill.name}' (成功率: {skill.success_rate:.1%})，建议：

适配提示：
{chr(10).join(f"  - {hint}" for hint in hints)}

原始模板：
{skill.template[:200]}...

建议修改：
1. 识别模板中需要替换的变量
2. 根据新任务调整逻辑
3. 保持核心模式不变
"""
        
        return suggestion


class IntelligentMemorySystem:
    """
    智能记忆系统 v2.0
    整合所有增强功能
    """
    
    def __init__(self, base_memory_system):
        self.base = base_memory_system
        
        # Phase 1: 技能系统
        self.skill_extractor = SkillAutoExtractor()
        self.skill_recommender = SkillRecommender({})
        
        # Phase 2: 演化系统
        self.evolution = MemoryEvolution(base_memory_system)
        
        # Phase 3: 迁移系统
        self.transfer = CrossTaskTransfer({})
        
        # 统计
        self.stats = {
            'skills_auto_extracted': 0,
            'skills_recommended': 0,
            'evolution_cycles': 0,
            'transfers_suggested': 0
        }
    
    def record_task_completion(self, task: str, solution: str, 
                               success: bool, quality: float):
        """记录任务完成，触发技能提取"""
        execution = TaskExecution(
            task_id=self._generate_id(),
            task_description=task,
            solution=solution,
            execution_time=0,  # 应由调用者提供
            success=success,
            quality_score=quality,
            timestamp=time.time()
        )
        
        # 尝试自动提取技能
        skill = self.skill_extractor.record_execution(execution)
        
        if skill:
            # 保存技能
            self._save_skill(skill)
            self.stats['skills_auto_extracted'] += 1
            return skill
        
        return None
    
    def get_smart_context(self, query: str, task_type: str = None) -> Dict:
        """获取智能上下文（包含推荐）"""
        context = {
            'base_context': self.base.build_context(query),
            'recommended_skills': [],
            'transfer_hints': [],
            'suggestions': []
        }
        
        # Phase 1: 技能推荐
        recommendations = self.skill_recommender.recommend(query, top_k=3)
        context['recommended_skills'] = [
            {
                'skill': skill,
                'confidence': conf,
                'template_preview': skill.template[:200]
            }
            for skill, conf in recommendations
        ]
        self.stats['skills_recommended'] += len(recommendations)
        
        # Phase 3: 跨任务迁移
        transfers = self.transfer.find_transfer_opportunities(query)
        if transfers:
            context['transfer_hints'] = transfers[:2]
            context['suggestions'].append(
                f"💡 发现 {len(transfers)} 个可复用的经验"
            )
            self.stats['transfers_suggested'] += len(transfers)
        
        return context
    
    def run_evolution(self) -> Dict:
        """运行记忆演化"""
        results = self.evolution.evolve()
        self.stats['evolution_cycles'] += 1
        return results
    
    def _generate_id(self) -> str:
        """生成ID"""
        return f"task_{int(time.time())}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
    
    def _save_skill(self, skill: Skill):
        """保存技能"""
        self.skill_recommender.skills[skill.id] = skill
        self.transfer.skills[skill.id] = skill
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self.stats,
            'total_skills': len(self.skill_recommender.skills),
            'evolution_cycle': self.evolution.evolution_cycle
        }


# 导出
__all__ = [
    'IntelligentMemorySystem',
    'SkillAutoExtractor',
    'SkillRecommender',
    'MemoryEvolution',
    'CrossTaskTransfer',
    'Skill',
    'TaskExecution'
]
