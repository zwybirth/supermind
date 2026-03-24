#!/usr/bin/env python3
"""
初始化 SuperMind 系统
"""

import os
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def check_dependencies():
    """检查依赖"""
    console.print("\n[bold cyan]🔍 检查依赖...[/bold cyan]\n")
    
    dependencies = [
        ("python", "Python 3.8+"),
        ("pip", "pip"),
    ]
    
    all_ok = True
    for cmd, name in dependencies:
        result = os.system(f"which {cmd} > /dev/null 2>&1")
        if result == 0:
            console.print(f"  ✓ {name}")
        else:
            console.print(f"  ✗ {name} - 未安装")
            all_ok = False
    
    return all_ok


def install_python_packages():
    """安装 Python 包"""
    console.print("\n[bold cyan]📦 安装 Python 依赖...[/bold cyan]\n")
    
    req_file = Path(__file__).parent.parent / "requirements.txt"
    
    if not req_file.exists():
        console.print("[red]requirements.txt 不存在[/red]")
        return False
    
    result = os.system(f"pip install -r {req_file}")
    
    return result == 0


def create_directories():
    """创建必要目录"""
    console.print("\n[bold cyan]📁 创建目录结构...[/bold cyan]\n")
    
    base_dir = Path(__file__).parent.parent
    
    dirs = [
        base_dir / "data" / "vector_db",
        base_dir / "data" / "skills",
        base_dir / "knowledge",
        base_dir / "logs",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        console.print(f"  ✓ {d}")
    
    return True


def check_ollama():
    """检查 Ollama"""
    console.print("\n[bold cyan]🤖 检查 Ollama...[/bold cyan]\n")
    
    result = os.system("which ollama > /dev/null 2>&1")
    
    if result != 0:
        console.print("  ✗ Ollama 未安装")
        console.print("\n  [yellow]请安装 Ollama:[/yellow]")
        console.print("    macOS: brew install ollama")
        console.print("    Linux: curl -fsSL https://ollama.com/install.sh | sh")
        console.print("    或访问: https://ollama.com/download")
        return False
    
    console.print("  ✓ Ollama 已安装")
    
    # 检查服务是否运行
    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            console.print("  ✓ Ollama 服务运行中")
            console.print(f"\n  [dim]可用模型:[/dim]")
            for line in result.stdout.strip().split('\n')[1:]:
                console.print(f"    {line}")
            return True
        else:
            console.print("  ✗ Ollama 服务未运行")
            console.print("\n  [yellow]请启动 Ollama:[/yellow]")
            console.print("    ollama serve")
            return False
    except Exception as e:
        console.print(f"  ✗ 检查失败: {e}")
        return False


def pull_model():
    """拉取模型"""
    console.print("\n[bold cyan]⬇️ 拉取模型...[/bold cyan]\n")
    
    import subprocess
    
    model_name = "qwen3.5-35b-a3b"
    
    # 检查模型是否已存在
    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True
    )
    
    if model_name in result.stdout:
        console.print(f"  ✓ 模型 {model_name} 已存在")
        return True
    
    console.print(f"  正在拉取 {model_name}...")
    console.print(f"  [dim]这可能需要一些时间，请耐心等待...[/dim]\n")
    
    result = os.system(f"ollama pull {model_name}")
    
    if result == 0:
        console.print(f"  ✓ 模型 {model_name} 拉取完成")
        return True
    else:
        console.print(f"  ✗ 模型拉取失败")
        return False


def create_test_knowledge():
    """创建测试知识库"""
    console.print("\n[bold cyan]📚 初始化知识库...[/bold cyan]\n")
    
    base_dir = Path(__file__).parent.parent
    knowledge_dir = base_dir / "knowledge"
    
    # 创建示例文档
    sample_doc = knowledge_dir / "sample.md"
    sample_doc.write_text("""# SuperMind 使用指南

## 简介

SuperMind 是一个本地大模型超级化系统。

## 核心能力

- RAG 增强检索
- Agent 任务编排
- 分层记忆系统
- 工具调用

## 使用方法

```python
from supermind import SuperMind

mind = SuperMind()
result = mind.execute("你的任务")
```

## 配置

编辑 config/supermind.yaml 自定义行为。
""")
    
    console.print(f"  ✓ 创建示例文档: {sample_doc}")
    
    return True


def main():
    """主函数"""
    console.print(Panel.fit(
        "[bold green]🧠 SuperMind 初始化程序[/bold green]\n"
        "让本地大模型拥有超级智能",
        title="SuperMind v1.0"
    ))
    
    steps = [
        ("检查依赖", check_dependencies),
        ("安装 Python 包", install_python_packages),
        ("创建目录", create_directories),
        ("检查 Ollama", check_ollama),
        ("拉取模型", pull_model),
        ("初始化知识库", create_test_knowledge),
    ]
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        for name, func in steps:
            task = progress.add_task(f"{name}...", total=None)
            
            try:
                result = func()
                if not result:
                    progress.stop()
                    console.print(f"\n[red]✗ {name} 失败[/red]")
                    return 1
                progress.remove_task(task)
            except Exception as e:
                progress.stop()
                console.print(f"\n[red]✗ {name} 出错: {e}[/red]")
                return 1
    
    console.print("\n" + "=" * 50)
    console.print(Panel.fit(
        "[bold green]✅ SuperMind 初始化完成！[/bold green]\n\n"
        "启动方式:\n"
        "  python src/main.py\n\n"
        "或交互模式:\n"
        "  python src/main.py",
        title="完成"
    ))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
