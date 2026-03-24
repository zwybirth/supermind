"""
SuperMind 智能记忆系统集成
将 IntelligentMemorySystem 集成到 SuperMind
"""

import os
from pathlib import Path

# 尝试导入智能记忆系统
try:
    from intelligent_memory import IntelligentMemorySystem
    INTELLIGENT_MEMORY_AVAILABLE = True
except ImportError:
    INTELLIGENT_MEMORY_AVAILABLE = False


def upgrade_memory_system(supermind_instance):
    """
    将基础记忆系统升级为智能记忆系统
    
    Args:
        supermind_instance: SuperMind 实例
        
    Returns:
        升级后的智能记忆系统
    """
    if not INTELLIGENT_MEMORY_AVAILABLE:
        print("[智能记忆] 模块未找到，使用基础记忆系统")
        return supermind_instance.memory
    
    try:
        # 创建智能记忆系统
        smart_memory = IntelligentMemorySystem(supermind_instance.memory)
        
        print("✅ 智能记忆系统已激活")
        print("   - 技能自动提取: 启用")
        print("   - 主动推荐: 启用")
        print("   - 记忆演化: 启用")
        print("   - 跨任务迁移: 启用")
        
        return smart_memory
        
    except Exception as e:
        print(f"[智能记忆] 初始化失败: {e}")
        print("   回退到基础记忆系统")
        return supermind_instance.memory


# 便捷函数
def auto_extract_skill(memory_system, task: str, solution: str, 
                       success: bool = True, quality: float = 8.0):
    """
    自动从任务中提取技能
    
    示例:
        skill = auto_extract_skill(
            memory_system,
            task="写一个Python爬虫",
            solution="import requests...",
            success=True,
            quality=9.0
        )
    """
    if hasattr(memory_system, 'record_task_completion'):
        return memory_system.record_task_completion(task, solution, success, quality)
    return None


def get_smart_recommendations(memory_system, query: str):
    """
    获取智能推荐
    
    示例:
        context = get_smart_recommendations(memory_system, "爬取网页数据")
        for skill in context['recommended_skills']:
            print(f"推荐: {skill['skill'].name}")
    """
    if hasattr(memory_system, 'get_smart_context'):
        return memory_system.get_smart_context(query)
    return {'recommended_skills': [], 'transfer_hints': []}


def run_memory_evolution(memory_system):
    """
    运行记忆演化
    
    示例:
        results = run_memory_evolution(memory_system)
        print(f"强化了 {results['reinforced']} 条记忆")
    """
    if hasattr(memory_system, 'run_evolution'):
        return memory_system.run_evolution()
    return {}


__all__ = [
    'upgrade_memory_system',
    'auto_extract_skill',
    'get_smart_recommendations',
    'run_memory_evolution',
    'INTELLIGENT_MEMORY_AVAILABLE'
]
