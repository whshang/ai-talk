import os
import json
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from src.service import DialogueService

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

async def main():
    """主程序"""
    service = None
    try:
        logger.info("\n=== 开始系统自检 ===\n")
        
        # 1. 加载配置
        logger.info("1. 加载配置...")
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            
        # 2. 创建服务
        logger.info("2. 创建客户端...")
        service = DialogueService(config)
        
        # 3. 开始对话
        await service.start()
        
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
        raise
    finally:
        if service:
            await service.close()

if __name__ == "__main__":
    asyncio.run(main())