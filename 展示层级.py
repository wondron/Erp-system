import os
import argparse
from typing import Iterable, List, Set, Optional


def generate_project_structure(
    root_dir: str,
    exclude: Optional[Set[str]] = None,
    show_files: bool = True,
    no_files_in: Optional[Set[str]] = None,
) -> str:
    """
    生成项目目录结构的文本表示

    Args:
        root_dir: 项目根目录路径
        exclude: 需要排除的「条目名」集合（文件或目录，命中即整项跳过；目录会整棵子树跳过）
        show_files: 是否显示文件；False 则全局只显示目录
        no_files_in: 仅对这些目录（匹配目录名，不含路径）及其子孙目录，「不显示任何文件」
                     但仍显示目录层级
    """
    if exclude is None:
        exclude = {
            "__pycache__", ".git", ".svn", ".hg", ".idea", ".vscode",
            "venv", "env", "node_modules", ".DS_Store", "dist", "build",
            ".gitignore", ".gitattributes", ".env", ".env.local",
            ".md", ".txt", "explain.md", "explain.txt",
            "展示层级.py", "template.txt", "data-pg", "data-redis",
        }
    no_files_in = set(no_files_in or set())

    root_abs = os.path.abspath(root_dir)
    root_name = os.path.basename(root_abs) or root_abs
    lines: List[str] = [root_name + "/"]

    def list_entries_safe(dir_path: str):
        try:
            with os.scandir(dir_path) as it:
                entries = [e for e in it]
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            return []
        # 过滤 exclude（按「名称」过滤）
        entries = [e for e in entries if e.name not in exclude]
        # 目录优先，名称排序稳定
        entries.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
        return entries

    def traverse(dir_path: str, prefix: str, in_no_files_subtree: bool):
        entries = list_entries_safe(dir_path)
        total = len(entries)
        for idx, entry in enumerate(entries):
            is_last = (idx == total - 1)
            connector = "└── " if is_last else "├── "
            next_prefix = prefix + ("    " if is_last else "│   ")
            entry_path = os.path.join(dir_path, entry.name)

            # 目录
            if entry.is_dir(follow_symlinks=False):
                lines.append(prefix + connector + entry.name + "/")
                # 进入子目录时，如果该目录名命中 no_files_in，则整棵子树都在“隐藏文件模式”
                next_in_no_files = in_no_files_subtree or (entry.name in no_files_in)
                traverse(entry_path, next_prefix, next_in_no_files)
            else:
                # 文件
                if show_files and not in_no_files_subtree:
                    lines.append(prefix + connector + entry.name)
                # 否则（全局不展示文件 或 当前在 no_files 子树内）就不追加

    # 根是否属于 no_files_in
    start_in_no_files = os.path.basename(root_abs) in no_files_in
    traverse(root_abs, "", start_in_no_files)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="生成项目目录结构")
    parser.add_argument("directory", nargs="?", default=".", help="要生成结构的目录路径（默认为当前目录）")
    parser.add_argument("--no-files", action="store_true", help="不显示任何文件，只显示目录")
    parser.add_argument("--output", help="输出文件路径（默认为标准输出）")
    parser.add_argument("--exclude", nargs="*", help="额外需要排除的文件或目录（按名称过滤）")
    parser.add_argument(
        "--no-files-in",
        nargs="*",
        metavar="DIRNAME",
        help="这些目录（按名称匹配）及其子孙目录中不显示任何文件，但仍显示目录结构",
    )

    args = parser.parse_args()

    # 默认排除清单（修复了你原代码中漏掉逗号导致的连接问题）
    exclude = {
        "__pycache__", ".git", ".svn", ".hg", ".idea", ".vscode",
        "venv", "env", "node_modules", ".DS_Store", "dist", "build",
        ".gitignore", ".gitattributes", ".env", ".env.local",
        ".md", ".txt", "explain.md", "explain.txt",
        "展示层级.py", "template.txt", "data-pg", "data-redis",
    }
    if args.exclude:
        exclude.update(args.exclude)

    no_files_in = set(args["no_files_in"] if isinstance(args, dict) else (args.no_files_in or []))

    try:
        structure = generate_project_structure(
            args.directory,
            exclude=exclude,
            show_files=not args.no_files,
            no_files_in=set(no_files_in),
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(structure)
            print(f"目录结构已保存到 {args.output}")
        else:
            print(structure)
    except Exception as e:
        print(f"发生错误: {e}")


if __name__ == "__main__":
    main()
