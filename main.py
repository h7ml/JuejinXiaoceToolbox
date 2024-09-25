import sys
import os
import argparse
from src.gui import run_gui
from src.juejin_downloader import run_from_command_line

# 添加资源文件路径
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

sys.path.append(resource_path('.'))

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

def main():
    parser = argparse.ArgumentParser(description='掘金小册下载器')
    parser.add_argument('--cli', action='store_true', help='使用命令行界面')
    parser.add_argument('--config', type=str, default='config.yml', help='指定配置文件路径')
    args = parser.parse_args()

    config_path = os.path.join(os.path.dirname(__file__), args.config)

    if args.cli:
        run_from_command_line(config_path=config_path)
    else:
        run_gui(config_path=config_path)

if __name__ == '__main__':
    main()