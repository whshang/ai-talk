import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from src.client import AIClient
from src.evaluator import DialogueEvaluator
import asyncio

logger = logging.getLogger(__name__)

class DialogueService:
    """对话服务"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化服务"""
        self.config = config
        self.max_rounds = config["dialogue"]["rounds"]
        self.current_round = 0
        self.dialogue_history = []
        self.file_lock = asyncio.Lock()  # 添加文件锁
        
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
                
                round_responses = []  # 收集本轮所有回复
                
                # 每个角色轮流发言
                for character_id, client in self.clients.items():
                    # 准备对话历史
                    dialogue_history = []
                    for msg in self.dialogue_history[-4:]:  # 只保留最近4条消息
                        dialogue_history.append({
                            "role": "user" if msg["character"] != character_id else "assistant",
                            "content": msg["content"]
                        })
                    
                    # 发送请求
                    response = await client.chat([
                        {
                            "role": "system",
                            "content": self._prepare_system_prompt(character_id)
                        },
                        *dialogue_history
                    ])
                    
                    if response:
                        # 记录回复
                        round_responses.append({
                            "character": character_id,
                            "content": response
                        })
                
                # 批量更新对话历史并保存
                if round_responses:
                    self.dialogue_history.extend(round_responses)
                    await self.save_dialogue()
                    
                self.current_round += 1
            
            # 评估对话
            evaluation = await self.evaluator.evaluate(self.dialogue_file)
            if evaluation:
                await self.save_dialogue(evaluation)
                
        except Exception as e:
            logger.error(f"对话服务运行出错: {str(e)}")
            raise
            
    async def save_dialogue(self, evaluation: str = None) -> None:
        """保存对话记录和评估结果"""
        async with self.file_lock:  # 使用文件锁
            try:
                # 获取基本信息
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                topic = self.config["discussion"]["topic"]
                content = self.config["discussion"]["content"]
                
                # 格式化角色信息
                characters = []
                for character_id, character in self.config["dialogue"]["characters"]["instances"].items():
                    # 从prompt中提取第一行作为角色描述
                    description = character["prompt"].split('\n')[0]
                    
                    characters.append(f"""
{character["name"]}
角色描述：{description}
模型：{character["model"]}""".strip())
                    
                # 格式化对话内容
                dialogue = []
                for msg in self.dialogue_history:
                    character = self.config["dialogue"]["characters"]["instances"][msg["character"]]
                    dialogue.append(f"""[{character["name"]}] {msg["content"]}""")
                    
                # 组合所有内容
                content = f"""## 对话记录
时间：{timestamp}
主题：{topic}
内容：{content}

## 对话角色
{"\n\n".join(characters)}

## 对话内容
{"\n\n".join(dialogue)}"""

                if evaluation:
                    # 添加评估角色信息
                    evaluator = self.config["evaluation"]["character"]
                    evaluator_info = f"""
评估专家
角色描述：{evaluator["prompt"].split('\\n')[0]}
模型：{self.config["evaluation"]["model"]}""".strip()
                    
                    content += f"""

## 评估结果
{evaluator_info}

{evaluation}"""
                
                # 创建临时文件
                temp_file = f"{self.dialogue_file}.tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write(content)
                
                # 安全地替换原文件
                os.replace(temp_file, self.dialogue_file)
                
                logger.info(f"对话已保存到: {self.dialogue_file}")
                
            except Exception as e:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                logger.error(f"保存对话时出错: {str(e)}")
                raise
            
    def _prepare_system_prompt(self, character_id: str) -> str:
        """准备系统提示"""
        character = self.config["dialogue"]["characters"]["instances"][character_id]
        return character["prompt"].format(
            topic=self.config["discussion"]["topic"],
            content=self.config["discussion"]["content"]
        )
        
    async def close(self):
        """关闭服务"""
        try:
            # 关闭评估器
            if hasattr(self, 'evaluator'):
                await self.evaluator.close()
                
            # 关闭所有客户端
            for client in self.clients.values():
                await client.close()
                
        except Exception as e:
            logger.error(f"关闭服务时出错: {str(e)}")
            raise
        
    def _prepare_evaluation_content(self) -> str:
        """准备评估内容"""
        # 获取基本信息
        topic = self.config["discussion"]["topic"]
        content = self.config["discussion"]["content"]
        
        # 获取角色设定
        characters = []
        for character_id, character in self.config["dialogue"]["characters"]["instances"].items():
            description = character["prompt"].split('\n')[0]
            characters.append(f"{character['name']}\n{description}")
            
        # 格式化对话内容
        dialogue = []
        for msg in self.dialogue_history:
            character = self.config["dialogue"]["characters"]["instances"][msg["character"]]
            dialogue.append(f"[{character['name']}] {msg['content']}")
            
        # 组合评估内容
        return f"""话题：{topic}
背景：{content}

角色设定：
{"\n\n".join(characters)}

对话内容：
{"\n".join(dialogue)}"""
        
    async def _evaluate_dialogue(self) -> str:
        """评估对话质量"""
        try:
            if not self.evaluator:
                return None
                
            # 评估对话
            evaluation = await self.evaluator.evaluate(self.dialogue_file)
            return evaluation
            
        except Exception as e:
            logger.error(f"评估对话时出错: {str(e)}")
            raise