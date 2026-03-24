"""
Memory System - 分层记忆系统
基于 MemOS 和 OpenViking 的理念
"""

import sqlite3
import json
import time
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class MemoryItem:
    """记忆项"""
    id: str
    content: str
    memory_type: str  # working, short_term, long_term, skill
    metadata: Dict[str, Any]
    timestamp: float
    access_count: int = 0
    last_access: float = 0
    importance: float = 1.0  # 1-10


class WorkingMemory:
    """工作记忆 - 当前会话上下文"""
    
    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.items: List[MemoryItem] = []
        self.current_tokens = 0
    
    def add(self, content: str, metadata: Dict[str, Any] = None):
        """添加工作记忆"""
        item = MemoryItem(
            id=self._generate_id(content),
            content=content,
            memory_type='working',
            metadata=metadata or {},
            timestamp=time.time()
        )
        
        self.items.append(item)
        self.current_tokens += self._estimate_tokens(content)
        
        # 如果超出限制，移除最旧的
        while self.current_tokens > self.max_tokens and len(self.items) > 1:
            removed = self.items.pop(0)
            self.current_tokens -= self._estimate_tokens(removed.content)
    
    def get_recent(self, n: int = 10) -> str:
        """获取最近的记忆"""
        recent = self.items[-n:] if len(self.items) > n else self.items
        return "\n".join([item.content for item in recent])
    
    def get_all(self) -> List[MemoryItem]:
        """获取所有工作记忆"""
        return self.items.copy()
    
    def clear(self):
        """清空工作记忆"""
        self.items = []
        self.current_tokens = 0
    
    def _generate_id(self, content: str) -> str:
        """生成ID"""
        return hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:16]
    
    def _estimate_tokens(self, text: str) -> int:
        """估算token数"""
        # 粗略估算：中文字符 + 英文单词
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_words = len(text.split())
        return chinese_chars + english_words


class ShortTermMemory:
    """短期记忆 - SQLite存储"""
    
    def __init__(self, db_path: str = "./data/short_term.db", 
                 max_items: int = 1000, ttl_hours: int = 24):
        self.db_path = db_path
        self.max_items = max_items
        self.ttl = ttl_hours * 3600  # 转为秒
        
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT DEFAULT 'short_term',
                metadata TEXT,
                timestamp REAL,
                access_count INTEGER DEFAULT 0,
                last_access REAL,
                importance REAL DEFAULT 1.0
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_type ON memories(memory_type)
        ''')
        
        conn.commit()
        conn.close()
    
    def save(self, content: str, memory_type: str = 'short_term',
             metadata: Dict[str, Any] = None, importance: float = 1.0):
        """保存记忆"""
        item = MemoryItem(
            id=hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:16],
            content=content,
            memory_type=memory_type,
            metadata=metadata or {},
            timestamp=time.time(),
            importance=importance
        )
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO memories 
            (id, content, memory_type, metadata, timestamp, access_count, last_access, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item.id, item.content, item.memory_type,
            json.dumps(item.metadata), item.timestamp,
            item.access_count, item.last_access, item.importance
        ))
        
        conn.commit()
        conn.close()
        
        # 清理过期数据
        self._cleanup()
    
    def search(self, query: str, k: int = 5) -> List[MemoryItem]:
        """搜索记忆（简单关键词匹配）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 关键词匹配
        keywords = query.split()
        conditions = []
        params = []
        
        for kw in keywords:
            conditions.append("content LIKE ?")
            params.append(f"%{kw}%")
        
        where_clause = " OR ".join(conditions) if conditions else "1=1"
        
        cursor.execute(f'''
            SELECT * FROM memories 
            WHERE {where_clause}
            ORDER BY importance DESC, timestamp DESC
            LIMIT ?
        ''', params + [k])
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_item(row) for row in rows]
    
    def get_by_type(self, memory_type: str, limit: int = 100) -> List[MemoryItem]:
        """按类型获取记忆"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM memories 
            WHERE memory_type = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (memory_type, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_item(row) for row in rows]
    
    def update_access(self, item_id: str):
        """更新访问计数"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE memories 
            SET access_count = access_count + 1, last_access = ?
            WHERE id = ?
        ''', (time.time(), item_id))
        
        conn.commit()
        conn.close()
    
    def _cleanup(self):
        """清理过期数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 删除过期数据
        cutoff = time.time() - self.ttl
        cursor.execute('''
            DELETE FROM memories 
            WHERE timestamp < ? AND importance < 5
        ''', (cutoff,))
        
        # 限制总数
        cursor.execute('''
            DELETE FROM memories 
            WHERE id NOT IN (
                SELECT id FROM memories 
                ORDER BY importance DESC, timestamp DESC 
                LIMIT ?
            )
        ''', (self.max_items,))
        
        conn.commit()
        conn.close()
    
    def _row_to_item(self, row) -> MemoryItem:
        """数据库行转对象"""
        return MemoryItem(
            id=row[0],
            content=row[1],
            memory_type=row[2],
            metadata=json.loads(row[3]) if row[3] else {},
            timestamp=row[4],
            access_count=row[5],
            last_access=row[6] or 0,
            importance=row[7]
        )
    
    def count(self) -> int:
        """获取记忆数量"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM memories')
        count = cursor.fetchone()[0]
        conn.close()
        return count


class SkillMemory:
    """技能记忆 - 可复用的技能模板"""
    
    def __init__(self, skills_path: str = "./data/skills"):
        self.skills_path = Path(skills_path)
        self.skills_path.mkdir(parents=True, exist_ok=True)
        self.skills: Dict[str, Dict[str, Any]] = {}
        self._load_skills()
    
    def _load_skills(self):
        """加载已保存的技能"""
        for skill_file in self.skills_path.glob("*.json"):
            with open(skill_file, 'r', encoding='utf-8') as f:
                skill = json.load(f)
                self.skills[skill['name']] = skill
    
    def add_skill(self, name: str, pattern: str, template: str,
                  examples: List[str] = None):
        """添加技能"""
        skill = {
            'name': name,
            'pattern': pattern,
            'template': template,
            'examples': examples or [],
            'created_at': time.time(),
            'use_count': 0
        }
        
        self.skills[name] = skill
        
        # 保存到文件
        skill_file = self.skills_path / f"{name}.json"
        with open(skill_file, 'w', encoding='utf-8') as f:
            json.dump(skill, f, ensure_ascii=False, indent=2)
    
    def match_skill(self, query: str) -> Optional[Dict[str, Any]]:
        """匹配技能"""
        best_match = None
        best_score = 0
        
        for name, skill in self.skills.items():
            # 简单关键词匹配
            score = self._calculate_match_score(query, skill)
            if score > best_score and score > 0.5:
                best_score = score
                best_match = skill
        
        return best_match
    
    def _calculate_match_score(self, query: str, skill: Dict) -> float:
        """计算匹配分数"""
        query_lower = query.lower()
        pattern_lower = skill['pattern'].lower()
        
        # 精确匹配
        if pattern_lower in query_lower:
            return 1.0
        
        # 关键词匹配
        query_words = set(query_lower.split())
        pattern_words = set(pattern_lower.split())
        
        if not pattern_words:
            return 0.0
        
        overlap = len(query_words & pattern_words)
        return overlap / len(pattern_words)
    
    def extract_skill(self, task: str, solution: str) -> Optional[str]:
        """从任务-方案对中提取技能"""
        # 简单启发式：如果方案较长且通用，可能是技能
        if len(solution) > 500 and 'function' in solution.lower():
            return self._generate_skill_name(task)
        return None
    
    def _generate_skill_name(self, task: str) -> str:
        """生成技能名称"""
        # 提取关键词
        words = task.split()[:3]
        return "_".join(words).lower().replace(" ", "_")


class MemorySystem:
    """
    分层记忆系统主类
    
    三层架构：
    - 工作记忆：当前会话上下文
    - 短期记忆：最近的重要信息
    - 长期记忆：向量检索的知识
    - 技能记忆：可复用的技能模板
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 初始化各层
        self.working = WorkingMemory(
            max_tokens=config.get('working', {}).get('max_tokens', 8000)
        )
        
        self.short_term = ShortTermMemory(
            db_path=config.get('short_term', {}).get('db_path', './data/short_term.db'),
            max_items=config.get('short_term', {}).get('max_items', 1000),
            ttl_hours=config.get('short_term', {}).get('ttl_hours', 24)
        )
        
        self.skills = SkillMemory(
            skills_path=config.get('skills', {}).get('path', './data/skills')
        )
        
        # 长期记忆通过 RAG 实现
        self.long_term_enabled = config.get('long_term', {}).get('enabled', True)
    
    def save_working(self, content: str):
        """保存到工作记忆"""
        self.working.add(content)
    
    def save_short_term(self, content: str, memory_type: str = 'interaction',
                        importance: float = 1.0):
        """保存到短期记忆"""
        self.short_term.save(content, memory_type, importance=importance)
    
    def save_interaction(self, query: str, response: str):
        """保存交互记录"""
        content = f"Q: {query}\nA: {response}"
        self.save_short_term(content, 'interaction', importance=2.0)
    
    def save_code(self, request: str, code: str, language: str):
        """保存代码"""
        content = f"需求: {request}\n```{language}\n{code}\n```"
        self.save_short_term(content, 'code', importance=3.0)
        
        # 尝试提取技能
        skill_name = self.skills.extract_skill(request, code)
        if skill_name and self.config.get('skills', {}).get('auto_extract', True):
            self.skills.add_skill(
                name=skill_name,
                pattern=request,
                template=code
            )
    
    def build_context(self, query: str, max_tokens: int = 3000) -> str:
        """
        智能构建上下文
        
        优先级：
        1. 工作记忆（当前会话）
        2. 相关短期记忆
        3. 匹配的技能
        """
        context_parts = []
        used_tokens = 0
        
        # 1. 工作记忆（必须包含）
        working_mem = self.working.get_recent()
        if working_mem:
            context_parts.append(f"## 当前会话\n{working_mem}")
            used_tokens += self._estimate_tokens(working_mem)
        
        # 2. 相关短期记忆
        if used_tokens < max_tokens * 0.7:
            relevant = self.short_term.search(query, k=5)
            for item in relevant:
                content = item.content
                tokens = self._estimate_tokens(content)
                if used_tokens + tokens < max_tokens * 0.9:
                    context_parts.append(f"## 相关历史\n{content}")
                    used_tokens += tokens
                    # 更新访问计数
                    self.short_term.update_access(item.id)
        
        # 3. 匹配的技能
        if used_tokens < max_tokens * 0.95:
            skill = self.skills.match_skill(query)
            if skill:
                skill_text = f"## 可用技能: {skill['name']}\n{skill['template']}"
                context_parts.append(skill_text)
        
        return "\n\n".join(context_parts)
    
    def get_working_memory(self) -> str:
        """获取工作记忆"""
        return self.working.get_recent()
    
    def clear_working_memory(self):
        """清空工作记忆"""
        self.working.clear()
    
    def item_count(self) -> int:
        """获取记忆项总数"""
        return self.short_term.count()
    
    def _estimate_tokens(self, text: str) -> int:
        """估算token数"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_words = len(text.split())
        return chinese_chars + english_words
