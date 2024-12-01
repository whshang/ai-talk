import os
import json
import pytest
import logging
import asyncio
from datetime import datetime
from src.client import AIClient
from src.service import DialogueService
from src.logger import setup_logger, load_config

# 设置基本日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
def config():
    """配置fixture"""
    return load_config()

def test_logger():
    """测试日志功能"""
    logger.info("\n=== 测试日志功能 ===\n")
    
    try:
        # 1. 测试日志设置
        test_logger = setup_logger("test_logger")
        assert test_logger is not None
        
        # 2. 测试日志目录创建
        assert os.path.exists("logs")
        
        # 3. 测试日志文件创建
        test_logger.info("测试日志消息")
        log_files = os.listdir("logs")
        assert len(log_files) > 0
        
        # 4. 测试日志格式
        with open(os.path.join("logs", log_files[-1]), "r", encoding="utf-8") as f:
            last_line = f.readlines()[-1]
            assert "[INFO]" in last_line
            assert "test_logger" in last_line
            assert "测试日志消息" in last_line
            
        logger.info("✓ 日志功能测试通过")
        
    except Exception as e:
        logger.error(f"❌ 日志功能测试失败: {str(e)}")
        raise

def test_config(config):
    """测试配置功能"""
    logger.info("\n=== 测试配置功能 ===\n")
    
    try:
        # 1. 验证基本结构
        assert "environment" in config
        assert "dialogue" in config
        
        # 2. 验证环境配置
        env_config = config["environment"]
        assert "output_dir" in env_config
        assert "log_dir" in env_config
        
        # 3. 验证对话配置
        dialogue_config = config["dialogue"]
        assert "settings" in dialogue_config
        assert "characters" in dialogue_config
        
        # 4. 验证角色配置
        characters = dialogue_config["characters"]
        assert "instances" in characters
        
        logger.info("✓ 配置功能测试通过")
        
    except Exception as e:
        logger.error(f"❌ 配置功能测试失败: {str(e)}")
        raise

@pytest.mark.asyncio
async def test_ai_client(config):
    """测试AI客户端"""
    logger.info("\n=== 测试AI客户端 ===\n")
    
    client = None
    try:
        # 1. 创建客户端
        client = AIClient(config, "character1")
        assert client is not None
        
        # 2. 测试对话
        test_message = "你好，这是一条测试消息。"
        messages = [{"role": "user", "content": test_message}]
        
        response = await client.chat(messages)
        assert response is not None
        
        # 3. 验证响应长度
        content_length = len(response)
        assert client.min_length <= content_length <= client.max_length
        
        logger.info("✓ AI客户端测试通过")
        
    except Exception as e:
        logger.error(f"❌ AI客户端测试失败: {str(e)}")
        raise
    finally:
        if client:
            await client.close()

@pytest.mark.asyncio
async def test_dialogue_service(config):
    """测试对话服务"""
    logger.info("\n=== 测试对话服务 ===\n")
    
    service = None
    try:
        # 1. 创建服务
        service = DialogueService(config)
        assert service is not None
        
        # 2. 验证输出目录
        output_dir = config["environment"]["output_dir"]
        assert os.path.exists(output_dir)
        
        logger.info("✓ 对话服务测试通过")
        
    except Exception as e:
        logger.error(f"❌ 对话服务测试失败: {str(e)}")
        raise
    finally:
        if service:
            await service.close()

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 