from typing import List, Dict, Any, Optional
import json
import aiohttp
import os
import logging
from datetime import datetime
import asyncio
import time
from aiohttp import ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)

class AIClient:
    """AI客户端"""
    
    def __init__(self, config: Dict[str, Any], role: str):
        """初始化客户端"""
        self.config = config
        self.role = role
        self.model = self._get_model_name()
        
        # 从模型名称获取提供商
        provider = self.model.split("/")[0].upper()
        
        # 获取API配置
        self.api_url = os.getenv(f"{provider}_API_URL")
        self.api_key = os.getenv(f"{provider}_API_KEY")
        
        if not self.api_url:
            raise ValueError(f"未设置{provider}_API_URL环境变量")
        if not self.api_key:
            raise ValueError(f"未设置{provider}_API_KEY环境变量")
        
        # 创建会话
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        
    def _get_model_name(self):
        """获取模型名称"""
        if "dialogue" not in self.config:
            raise ValueError("配置缺少dialogue字段")
            
        if "characters" not in self.config["dialogue"]:
            raise ValueError("配置缺少characters字段")
            
        if "instances" not in self.config["dialogue"]["characters"]:
            raise ValueError("配置缺少instances字段")
            
        if self.role not in self.config["dialogue"]["characters"]["instances"]:
            raise ValueError(f"找不到角色{self.role}的配置")
            
        return self.config["dialogue"]["characters"]["instances"][self.role]["model"]
        
    def _prepare_system_prompt(self) -> str:
        """准备系统提示"""
        try:
            if "system_prompts" not in self.config:
                raise ValueError("配置缺少system_prompts字段")
                
            if "templates" not in self.config["system_prompts"]:
                raise ValueError("配置缺少templates字段")
                
            if "base" not in self.config["system_prompts"]["templates"]:
                raise ValueError("配置缺少base模板")
                
            base_template = self.config["system_prompts"]["templates"]["base"]
            if not isinstance(base_template, str):
                raise ValueError("base模板必须是字符串类型")
                
            character_config = self.config["dialogue"]["characters"]["instances"][self.role]
            
            # 检查所需字段
            required_fields = ["name", "role", "personality", "interests", "background", "language_style"]
            for field in required_fields:
                if field not in character_config:
                    raise ValueError(f"角色配置缺少{field}字段")
                    
            language_style = character_config["language_style"]
            required_style_fields = ["tone", "formality", "vocabulary", "use_emoji"]
            for field in required_style_fields:
                if field not in language_style:
                    raise ValueError(f"语言风格配置缺少{field}字段")
                    
            # 如果是评估者角色，使用评估模板
            if self.role == "evaluator":
                if "evaluation" not in self.config:
                    raise ValueError("评估配置缺少evaluation字段")
                    
                evaluation_config = self.config["evaluation"]
                if "metrics" not in evaluation_config:
                    raise ValueError("评估配置缺少metrics字段")
                    
                metrics_str = "\n".join([f"- {m}" for m in evaluation_config["metrics"]])
                output_format = evaluation_config["output_format"]
                
                score_format = "分数范围：{}-{}".format(
                    output_format["scores"]["range"][0],
                    output_format["scores"]["range"][1]
                )
                for metric, weight in output_format["scores"]["weight"].items():
                    score_format += f"\n{metric}（权重 {weight}）"
                    
                comment_format = "必须包含以下方面：\n- " + "\n- ".join(
                    output_format["comments"]["required_aspects"]
                )
                comment_format += f"\n\n评语长度不超过{output_format['comments']['max_length']}字"
                
                prompt = base_template.format(
                    metrics=metrics_str,
                    score_format=score_format,
                    comment_format=comment_format
                )
            else:
                # 普通角色使用基础模板
                prompt = base_template.format(
                    name=character_config["name"],
                    role=character_config["role"],
                    personality=", ".join(character_config["personality"]) if isinstance(character_config["personality"], list) else character_config["personality"],
                    interests=", ".join(character_config["interests"]) if isinstance(character_config["interests"], list) else character_config["interests"],
                    background=character_config["background"],
                    tone=language_style["tone"],
                    formality=language_style["formality"],
                    vocabulary=language_style["vocabulary"],
                    use_emoji="可以" if language_style["use_emoji"] else "不要",
                    topic=self.config["discussion"]["topic"] if "discussion" in self.config and "topic" in self.config["discussion"] else "",
                    content=self.config["discussion"]["content"] if "discussion" in self.config and "content" in self.config["discussion"] else ""
                )
            
            return prompt
            
        except KeyError as e:
            raise ValueError(f"配置缺少必需字段: {str(e)}")
        except Exception as e:
            raise ValueError(f"准备系统提示时出错: {str(e)}")
            
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """发送聊天请求"""
        try:
            # 记录系统提示
            logger.info("\n[系统提示]")
            logger.info("-" * 40)
            logger.info(messages[0]["content"])
            
            # 记录对话开始
            logger.info("\n[对话开始] =========")
            logger.info(f"角色: {self.role}")
            logger.info(f"模型: {self.model}")
            logger.info(f"尝试: 1/3")
            
            # 准备请求参数
            params = {
                "model": self.model.split("/")[-1],  # 只使用模型名称部分
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.7,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.5
            }
            
            # 记录请求参数
            logger.info("\n[请求参数]")
            logger.info("-" * 40)
            logger.info(json.dumps(params, indent=2, ensure_ascii=False))
            
            # 发送请求
            async with self.session.post(self.api_url, json=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"API请求失败，状态码: {response.status}, 错误信息: {error_text}")
                    
                result = await response.json()
                
                # 记录API响应
                logger.info("\n[API响应]")
                logger.info("-" * 40)
                logger.info(json.dumps(result, indent=2, ensure_ascii=False))
                
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    logger.error("API响应格式错误")
                    return None
                
        except Exception as e:
            logger.error(f"发送请求时出错: {str(e)}")
            raise

    async def __aenter__(self):
        """进入异步上下文"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出异步上下文"""
        if self.session:
            await self.session.close()
            self.session = None
        if self.connector:
            await self.connector.close()
            self.connector = None
            
    async def close(self):
        """关闭客户端"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    def _summarize_history(self, messages: List[Dict[str, str]]) -> str:
        """生成对话历史摘要"""
        if len(messages) <= 1:  # 如果只有系统提示或空消息列表
            return ""
            
        # 提取最近话内容（过统提示）
        recent_messages = messages[-3:]  # 只保留最近3条消息
        summary_parts = []
        
        for msg in recent_messages:
            role = msg["role"]
            content = msg["content"]
            # 将 assistant 角色替换为实际的角色名
            if role == "assistant":
                role = self.config["dialogue"]["characters"]["instances"][self.role]["name"]
            summary_parts.append(f"- {role}: {content[:50]}...")
            
        return "\n".join(summary_parts) 