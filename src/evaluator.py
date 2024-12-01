import os
import json
import logging
from typing import Dict, Any
from datetime import datetime
from src.client import AIClient

logger = logging.getLogger(__name__)

class DialogueEvaluator:
    """对话评估器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化评估器"""
        if "evaluation" not in config:
            raise ValueError("配置缺少 'evaluation' 字段")
            
        # 创建评估客户端
        evaluator_config = {
            "dialogue": {
                "characters": {
                    "instances": {
                        "evaluator": {
                            **config["evaluation"]["evaluator"],
                            "model": config["evaluation"]["model"]
                        }
                    }
                }
            },
            "system_prompts": {
                "templates": {
                    "base": config["system_prompts"]["templates"]["evaluator"]
                }
            },
            "discussion": config["discussion"],
            "response_requirements": config["response_requirements"],
            "evaluation": config["evaluation"]
        }
        
        self.client = AIClient(evaluator_config, "evaluator")
        
    async def evaluate(self, dialogue_file: str) -> str:
        """评估对话"""
        try:
            # 读取对话记录
            with open(dialogue_file, "r", encoding="utf-8") as f:
                dialogue = f.read()
                
            # 发送评估请求
            evaluation = await self.client.chat([
                {
                    "role": "system",
                    "content": """请对以下对话进行评估：

1. 总体评分（1-10分）
2. 评分理由
3. 改进建议"""
                },
                {
                    "role": "user",
                    "content": dialogue
                }
            ])
            
            if evaluation:
                return evaluation
            else:
                logger.error("评估失败：未能获取评估结果")
                return None
                
        except Exception as e:
            logger.error(f"评估对话时出错: {str(e)}")
            raise
            
    async def close(self) -> None:
        """关闭评估器"""
        await self.client.close()