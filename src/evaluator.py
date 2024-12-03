import logging
import asyncio
from typing import Dict, Any
from src.client import AIClient

logger = logging.getLogger(__name__)

class DialogueEvaluator:
    """对话评估器"""
    
    def __init__(self, config: dict):
        """初始化评估器"""
        self.config = config
        self.client = None
        
        if config["evaluation"]["enabled"]:
            # 创建评估专用客户端配置
            evaluator_config = {
                "dialogue": {
                    "characters": {
                        "instances": {
                            "evaluator": {
                                **config["evaluation"]["character"],
                                "model": config["evaluation"]["model"]
                            }
                        }
                    }
                },
                "performance": config["performance"]  # 继承性能配置
            }
            
            # 合并配置
            evaluator_config.update({k:v for k,v in config.items() if k not in ["dialogue", "performance"]})
            
            self.client = AIClient(evaluator_config, "evaluator")
            
    async def evaluate(self, dialogue_file: str) -> str:
        """评估对话"""
        try:
            # 读取对话文件
            with open(dialogue_file, "r", encoding="utf-8") as f:
                dialogue = f.read()
                
            # 提取对话内容部分
            dialogue_content = []
            in_dialogue_section = False
            for line in dialogue.split('\n'):
                if line.startswith("## 对话内容"):
                    in_dialogue_section = True
                    continue
                elif line.startswith("## 评估结果"):
                    in_dialogue_section = False
                    break
                elif in_dialogue_section and line.strip():
                    dialogue_content.append(line)
            
            if not dialogue_content:
                logger.error("未找到有效对话内容")
                return "评估失败：未找到有效对话内容"
                
            # 准备评估提示
            prompt = self.config["evaluation"]["character"]["prompt"].format(
                dialogue="\n".join(dialogue_content)
            )
            
            # 添加重试机制
            max_attempts = self.config["performance"]["retry"]["max_attempts"]
            min_wait = self.config["performance"]["retry"]["min_wait"]
            max_wait = self.config["performance"]["retry"]["max_wait"]
            multiplier = self.config["performance"]["retry"]["multiplier"]
            
            attempt = 0
            last_error = None
            
            while attempt < max_attempts:
                try:
                    # 发送评估请求
                    response = await self.client.chat([
                        {"role": "user", "content": prompt}
                    ])
                    
                    # 获取评估结果
                    if isinstance(response, dict) and "choices" in response:
                        evaluation = response["choices"][0]["message"]["content"]
                    else:
                        evaluation = response
                    
                    # 验证评估结果格式
                    if self._validate_evaluation_result(evaluation):
                        return evaluation
                        
                    logger.warning("评估结果格式不正确，重试中...")
                    
                except Exception as e:
                    logger.warning(f"评估失败: {str(e)} (尝试 {attempt + 1}/{max_attempts})")
                    last_error = str(e)
                    
                attempt += 1
                if attempt < max_attempts:
                    wait_time = min(max_wait, min_wait * (multiplier ** attempt))
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                    
            error_msg = f"评估失败 (已重试 {max_attempts} 次): {last_error}"
            logger.error(error_msg)
            return error_msg
            
        except Exception as e:
            logger.error(f"评估过程出错: {str(e)}")
            return f"评估失败: {str(e)}"
            
    def _validate_evaluation_result(self, result: str) -> bool:
        """验证评估结果格式"""
        try:
            # 检查必要的评分项
            required_items = [
                "对话自然度：",
                "内容相关性：",
                "角色表现：",
                "总体评价："
            ]
            
            # 检查每一项是否都存在
            for item in required_items:
                if item not in result:
                    logger.warning(f"缺少评估项：{item}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.warning(f"评估结果验证出错: {str(e)}")
            return False
            
    async def close(self):
        """关闭评估器"""
        if self.client:
            await self.client.close()