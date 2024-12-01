import os
import json
import logging
from typing import Dict, Any
from datetime import datetime
from src.client import AIClient
from src.evaluator import DialogueEvaluator

logger = logging.getLogger(__name__)

class DialogueService:
    """对话服务"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化服务"""
        self.config = config
        self.max_rounds = config["dialogue"]["rounds"]
        self.current_round = 0
        self.dialogue_history = []
        
        # 创建输出目录和文件
        os.makedirs(config["dialogue"]["output"]["directory"], exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.dialogue_file = os.path.join(
            config["dialogue"]["output"]["directory"],
            f"dialogue_{timestamp}.md"
        )
        
        # 创建客户端和评估器
        self.clients = {
            character_id: AIClient(config, character_id)
            for character_id, character in config["dialogue"]["characters"]["instances"].items()
        }
        self.evaluator = DialogueEvaluator(config)
        
    async def start(self) -> None:
        """开始对话"""
        try:
            # 初始化对话记录
            await self.save_dialogue()
            
            # 开始对话循环
            while self.current_round < self.max_rounds:
                logger.info("\n" + "#" * 50)
                logger.info(f"第 {self.current_round + 1} 轮对话")
                
                # 每个角色轮流发言
                for character_id, client in self.clients.items():
                    # 发送请求
                    response = await client.chat([
                        {
                            "role": "system",
                            "content": self._prepare_system_prompt(character_id)
                        },
                        *[
                            {
                                "role": "user" if msg["character"] != character_id else "assistant",
                                "content": msg["content"]
                            }
                            for msg in self.dialogue_history
                        ]
                    ])
                    
                    if response:
                        # 记录回复并保存
                        self.dialogue_history.append({
                            "character": character_id,
                            "content": response
                        })
                        await self.save_dialogue()
                        
                self.current_round += 1
                
            # 评估对话
            evaluation = await self.evaluator.evaluate(self.dialogue_file)
            if evaluation:
                await self.save_dialogue(evaluation)
                
        except Exception as e:
            logger.error(f"对话过程出错: {str(e)}")
            raise
            
        finally:
            # 关闭客户端
            for client in self.clients.values():
                await client.close()
            await self.evaluator.close()
            
    async def save_dialogue(self, evaluation: str = None) -> None:
        """保存对话记录和评估结果"""
        try:
            # 获取基本信息
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            topic = self.config["discussion"]["topic"]
            background = self.config["discussion"]["background"]
            
            # 格式化角色信息
            characters = []
            for character_id, character in self.config["dialogue"]["characters"]["instances"].items():
                characters.append(f"""
{character["name"]}
性格：{", ".join(character["personality"])}
设定：{character["background"]}
模型：{character["model"]}""".strip())
                
            # 格式化对话内容
            dialogue = []
            for msg in self.dialogue_history:
                character = self.config["dialogue"]["characters"]["instances"][msg["character"]]
                dialogue.append(f"""[{character["name"]}]：
{msg["content"]}""")
                
            # 组合所有内容
            content = f"""## 对话记录
时间：{timestamp}
主题：{topic}
背景：{background}

## 对话角色
{"\n\n".join(characters)}

## 对话内容
{"\n\n".join(dialogue)}"""

            if evaluation:
                content += "\n\n## 评估结果\n" + evaluation
                
            with open(self.dialogue_file, "w", encoding="utf-8") as f:
                f.write(content)
                
            logger.info(f"对话已保存到: {self.dialogue_file}")
            
        except Exception as e:
            logger.error(f"保存对话时出错: {str(e)}")
            raise
            
    def _prepare_system_prompt(self, character_id: str) -> str:
        """准备系统提示"""
        character = self.config["dialogue"]["characters"]["instances"][character_id]
        
        return f"""你现在扮演{character["name"]}，一个{character["role"]}。你的性格是{", ".join(character["personality"])}，对{", ".join(character["interests"])}特别感兴趣。作为{character["background"]}，你会用{character["language_style"]["tone"]}的语气和{character["language_style"]["vocabulary"]}的词汇来表达。请保持{character["language_style"]["formality"]}的交谈风格，{"可以" if character["language_style"]["use_emoji"] else "不要"}使用表情。

当前讨论的话题是：{self.config["discussion"]["topic"]}

背景信息：{self.config["discussion"]["background"]}

你需要：
1. 字数保持在{self.config["response_requirements"]["length"]["min"]}-{self.config["response_requirements"]["length"]["max"]}字之间
2. 用纯文本回复，不使用特殊格式
3. 每次从新的角度切入，避免重复
4. 积极回应他人，提出有见地的问题
5. 展现你的特色，如感性观察或理性分析
6. 推进对话深入，但不要过于跳跃
7. 保持自然的对话节奏，不要生硬"""