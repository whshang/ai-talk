import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

def load_config() -> Dict[str, Any]:
    """加载配置"""
    try:
        # 加载环境变量
        load_dotenv()
        
        # 加载主配置
        with open("main.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            
        return config
        
    except FileNotFoundError as e:
        raise Exception(f"配置文件不存在: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"配置文件格式错误: {str(e)}")
    except Exception as e:
        raise Exception(f"加载配置文件失败: {str(e)}")

def setup_logger(
    name: Optional[str] = None,
    level: int = logging.INFO,
    log_dir: str = "logs"
) -> logging.Logger:
    """设置日志记录器"""
    
    # 创建日志目录
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # 获取或创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 如果日志记录器已经有处理器，直接返回
    if logger.handlers:
        return logger
        
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # 创建文件处理器
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"app_{timestamp}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 设置格式化器
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger 