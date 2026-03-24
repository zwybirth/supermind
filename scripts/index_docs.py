#!/usr/bin/env python3
"""
知识库文档索引工具
将文档添加到 SuperMind 的 RAG 系统中
"""

import os
import sys
from pathlib import Path
from typing import List

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from rag_engine import RAGEngine, Document

console = Console()


def load_config():
    """加载配置"""
    config_path = Path(__file__).parent.parent / "config" / "supermind.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def scan_documents(knowledge_dir: Path) -> List[Path]:
    """扫描文档"""
    documents = []
    
    for ext in ['*.md', '*.txt', '*.rst', '*.py', '*.js', '*.java', '*.go']:
        documents.extend(knowledge_dir.rglob(ext))
    
    # 去重并排序
    documents = sorted(set(documents))
    
    return documents


def read_document(doc_path: Path) -> str:
    """读取文档内容"""
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        console.print(f"[red]读取失败 {doc_path}: {e}[/red]")
        return ""


def create_document_objects(doc_paths: List[Path]) -> List[Document]:
    """创建文档对象"""
    documents = []
    
    for doc_path in doc_paths:
        content = read_document(doc_path)
        if not content:
            continue
        
        doc = Document(
            id=str(doc_path.relative_to(Path(__file__).parent.parent)),
            content=content,
            metadata={
                'source': str(doc_path),
                'filename': doc_path.name,
                'type': doc_path.suffix.lstrip('.'),
                'size': len(content)
            }
        )
        documents.append(doc)
    
    return documents


def main():
    """主函数"""
    console.print(Panel.fit(
        "[bold blue]📚 SuperMind 知识库索引工具[/bold blue]\n"
        "将文档添加到 RAG 系统",
        title="文档索引"
    ))
    
    # 加载配置
    config = load_config()
    
    # 知识库目录
    knowledge_dir = Path(__file__).parent.parent / "knowledge"
    
    if not knowledge_dir.exists():
        console.print(f"[red]知识库目录不存在: {knowledge_dir}[/red]")
        return 1
    
    # 扫描文档
    console.print(f"\n[bold]🔍 扫描文档...[/bold]")
    doc_paths = scan_documents(knowledge_dir)
    
    if not doc_paths:
        console.print("[yellow]未找到文档[/yellow]")
        return 0
    
    console.print(f"  找到 {len(doc_paths)} 个文档")
    
    # 初始化 RAG 引擎
    console.print(f"\n[bold]🚀 初始化 RAG 引擎...[/bold]")
    rag_config = config.get('rag', {})
    rag = RAGEngine(rag_config)
    
    # 创建文档对象
    console.print(f"\n[bold]📄 处理文档...[/bold]")
    documents = create_document_objects(doc_paths)
    
    # 添加到 RAG
    console.print(f"\n[bold]⬆️ 添加到向量库...[/bold]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        task = progress.add_task("索引中...", total=None)
        
        try:
            rag.add_documents(documents)
            progress.remove_task(task)
        except Exception as e:
            progress.stop()
            console.print(f"\n[red]索引失败: {e}[/red]")
            return 1
    
    # 统计
    console.print(f"\n[bold green]✅ 索引完成！[/bold green]")
    console.print(f"  文档数: {len(documents)}")
    console.print(f"  总字符数: {sum(len(d.content) for d in documents):,}")
    console.print(f"  向量库路径: {rag_config.get('vector_store', {}).get('path', './data/vector_db')}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
