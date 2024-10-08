import os
import subprocess
import shutil
import stat
import logging
import yaml
from typing import List, Dict
import argparse
import platform

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_path: str) -> Dict:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return {}

def remove_readonly(func, path, _):
    """清除只读属性并重新尝试删除"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def clean_directories(directories: List[str]):
    """清理指定的目录"""
    for dir_name in directories:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name, onerror=remove_readonly)
                logger.info(f"已清理目录: {dir_name}")
            except Exception as e:
                logger.error(f"清理目录 {dir_name} 失败: {e}")

def run_pyinstaller(project_root: str, config: Dict, output_name: str):
    """运行 PyInstaller 打包程序"""
    try:
        system = platform.system()
        icon_path = os.path.join(project_root, 'resources', 'icon.ico' if system == 'Windows' else 'icon.icns' if system == 'Darwin' else 'icon.png')
        
        cmd = [
            "pyinstaller",
            f"--name={output_name}",
            "--onefile",
            f"--icon={icon_path}",
            f"--add-data={os.path.join(project_root, 'resources', 'version.txt')}{';}' if system == 'Windows' else ':'}resources",
            f"--add-data={os.path.join(project_root, 'config.yml')}{';}' if system == 'Windows' else ':'}.",
            f"--add-data={os.path.join(project_root, 'plugins')}{';}' if system == 'Windows' else ':'}plugins",
            f"--add-data={os.path.join(project_root, 'src')}{';}' if system == 'Windows' else ':'}src",
            "--hidden-import=yaml",
            "--hidden-import=asyncio",
            "--clean",
            "--noupx",
            "--strip",
            "--debug", "all",
            os.path.join(project_root, "main.py")
        ]
        
        if system == 'Windows':
            cmd.append('--uac-admin')
        elif system == 'Darwin':
            cmd.append('--windowed')
        elif system == 'Linux':
            cmd.append(f"--add-data={os.path.join(project_root, 'resources', 'icon.png')}:.")
        
        for module in config.get('extra_modules', []):
            cmd.append(f"--collect-submodules={module}")
        
        for module in config.get('exclude_modules', []):
            cmd.append(f"--exclude-module={module}")
        
        cmd.append('--console' if config.get('console', False) else '--windowed')
        
        subprocess.run(cmd, check=True)
        logger.info("PyInstaller 打包完成")
    except subprocess.CalledProcessError as e:
        logger.error(f"PyInstaller 打包失败: {e}")
    except Exception as e:
        logger.error(f"运行 PyInstaller 时发生错误: {e}")

def validate_project_structure(project_root: str):
    required_files = ['main.py', 'config.yml']
    required_dirs = ['src', 'plugins', 'resources']
    
    for file in required_files:
        if not os.path.isfile(os.path.join(project_root, file)):
            logger.error(f"缺少必要文件: {file}")
            return False
    
    for dir in required_dirs:
        if not os.path.isdir(os.path.join(project_root, dir)):
            logger.error(f"缺少必要目录: {dir}")
            return False
    
    icon_file = 'icon.ico' if platform.system() == 'Windows' else 'icon.icns' if platform.system() == 'Darwin' else 'icon.png'
    if not os.path.isfile(os.path.join(project_root, 'resources', icon_file)):
        logger.error(f"缺少图标文件: {icon_file}")
        return False
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='构建掘金小册下载器')
    parser.add_argument('--config', default='build_config.yml', help='构建配置文件路径')
    parser.add_argument('--output-name', required=True, help='输出文件名')
    args = parser.parse_args()

    config = load_config(args.config)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if validate_project_structure(project_root):
        clean_directories(config.get('clean_dirs', ['build', 'dist']))
        run_pyinstaller(project_root, config, args.output_name)
        logger.info("项目构建完成")
    else:
        logger.error("项目结构验证失败，终止构建")