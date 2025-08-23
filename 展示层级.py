import os
import argparse
from typing import List, Set

def generate_project_structure(
    root_dir: str,
    exclude: Set[str] = None,
    indent: str = "    ",
    show_files: bool = True
) -> str:
    """
    生成项目目录结构的文本表示
    
    Args:
        root_dir: 项目根目录路径
        exclude: 需要排除的文件或目录名集合
        indent: 缩进字符串
        show_files: 是否显示文件，False则只显示目录
    
    Returns:
        目录结构的文本表示
    """
    if exclude is None:
        # 默认排除常见的不需要的文件和目录
        exclude = {
            '__pycache__', '.git', '.svn', '.hg', '.idea', '.vscode',
            'venv', 'env', 'node_modules', '.DS_Store', 'dist', 'build', '展示层级.py',
            '.gitignore', '.gitattributes', '.env', '.env.local', 'explain.txt'
        }
    
    # 获取根目录名称
    root_name = os.path.basename(os.path.abspath(root_dir))
    structure = [root_name + "/"]
    
    def traverse(current_dir: str, prefix: str) -> None:
        """递归遍历目录并构建结构"""
        # 获取当前目录下的所有条目
        entries = os.listdir(current_dir)
        entries.sort()  # 排序，确保结构稳定
        
        for i, entry in enumerate(entries):
            if entry in exclude:
                continue
                
            entry_path = os.path.join(current_dir, entry)
            is_last = (i == len(entries) - 1)
            
            # 确定当前行的前缀
            if is_last:
                line_prefix = prefix + "└── "
                next_prefix = prefix + "    "
            else:
                line_prefix = prefix + "├── "
                next_prefix = prefix + "│   "
            
            # 检查是否是目录
            if os.path.isdir(entry_path):
                structure.append(line_prefix + entry + "/")
                traverse(entry_path, next_prefix)
            elif show_files:
                # 如果是文件且需要显示
                structure.append(line_prefix + entry)
    
    # 开始遍历根目录下的内容
    traverse(root_dir, "")
    
    return "\n".join(structure)

def main():
    parser = argparse.ArgumentParser(description='生成项目目录结构')
    parser.add_argument(
        'directory', 
        nargs='?', 
        default='.', 
        help='要生成结构的目录路径（默认为当前目录）'
    )
    parser.add_argument(
        '--no-files', 
        action='store_true', 
        help='不显示文件，只显示目录'
    )
    parser.add_argument(
        '--output', 
        help='输出文件路径（默认为标准输出）'
    )
    parser.add_argument(
        '--exclude', 
        nargs='*', 
        help='额外需要排除的文件或目录'
    )
    
    args = parser.parse_args()
    
    # 处理排除列表
    exclude = {
        '__pycache__', '.git', '.svn', '.hg', '.idea', '.vscode',
        'venv', 'env', 'node_modules', '.DS_Store', 'dist', 'build',
        '.gitignore', '.gitattributes', '.env', '.env.local', '展示层级.py'
    }
    
    if args.exclude:
        exclude.update(args.exclude)
    
    # 生成目录结构
    try:
        structure = generate_project_structure(
            args.directory,
            exclude=exclude,
            show_files=not args.no_files
        )
        
        # 输出结果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(structure)
            print(f"目录结构已保存到 {args.output}")
        else:
            print(structure)
            
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()
