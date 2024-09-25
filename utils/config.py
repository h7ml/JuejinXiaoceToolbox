import yaml
import os

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yml')

def load_config(config_path=DEFAULT_CONFIG_PATH):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}  # 如果文件不存在，返回空字典
    except yaml.YAMLError as e:
        print(f"加载配置文件时出错: {e}")
        return {}

def save_config(config, config_path=DEFAULT_CONFIG_PATH):
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)
    except Exception as e:
        print(f"保存配置文件时出错: {e}")

def get_config_path():
    return DEFAULT_CONFIG_PATH
