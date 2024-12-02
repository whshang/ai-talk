import logging
from typing import Dict, Any
from src.client import AIClient

logger = logging.getLogger(__name__)

class DialogueEvaluator:
    """对话评估器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化评估器"""
        self.config = config
        
        # 获取评估模型
        evaluation_model = config["evaluation"]["model"]
        
        # 创建评估专用客户端配置
        evaluator_config = {
            "dialogue": {
                "characters": {
                    "instances": {
                        "evaluator": {
                            **self.config["evaluation"]["character"],
                            "model": evaluation_model
                        }
                    }
                }
            }
        }
        
        # 合并配置
        evaluator_config.update({k:v for k,v in config.items() if k != "dialogue"})
        
        self.client = AIClient(evaluator_config, "evaluator")
        
    async def evaluate(self, dialogue_file: str) -> str:
        """评估对话"""
        try:
            with open(dialogue_file, "r", encoding="utf-8") as f:
                dialogue = f.read()
                
            prompt = self.config["evaluation"]["character"]["prompt"].format(
                dialogue=dialogue
            )
            
            evaluation = await self.client.chat([
                {
                    "role": "user",
                    "content": prompt
                }
            ])
            
            return evaluation if evaluation else "评估失败：未获得有效响应"
            
        except Exception as e:
            logger.error(f"评估对话时出错: {str(e)}")
            return f"评估失败: {str(e)}"
            
    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.close()