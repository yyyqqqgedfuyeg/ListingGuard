"""
Filename: tui.py
Description: Risk-Aware Agent 终端交互程序根目录快速启动入口。
Author: Risk-Aware Agent Team
"""

import sys
from pathlib import Path

# 将项目根目录加入 sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.ui.tui import main

if __name__ == "__main__":
    main()

