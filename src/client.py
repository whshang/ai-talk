import os
import json
import logging
from typing import Dict, List, Any, Optional
import aiohttp
from aiohttp import ClientTimeout, TCPConnector
from datetime import datetime
import asyncio
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

logger = logging.getLogger(__name__)

class AIClient:
    """AI客户端"""
    
    def __init__(self, config: Dict[str, Any], role: str):
        """初始化客户端"""
        self.response_time = 0  # 移到最前面
        self.config = config
        self.role = role
        self.model = self._get_model_name()
        self.model_config = self._get_model_config()
        self.session = None
        
        # 从模型名称获取提供商
        provider = self.model.split("/")[0].upper()
        
        # 获取API配置
        self.api_url = os.getenv(f"{provider}_API_URL")
        self.api_key = os.getenv(f"{provider}_API_KEY")
        
        if not self.api_url:
            raise ValueError(f"未设置{provider}_API_URL环境变量")
        if not self.api_key:
            raise ValueError(f"未设置{provider}_API_KEY环境变量")
        
        # 获取性能配置
        self.performance_config = config.get("performance", {})
        
        # 初始化性能指标
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "total_response_time": 0,
            "max_response_time": 0,
            "min_response_time": float('inf'),
            "retry_count": 0,
            "error_count": 0
        }
        
        # 初始化监控配置
        self.monitoring_config = self.performance_config.get("monitoring", {})
        self.alert_thresholds = self.monitoring_config.get("alert_thresholds", {})
        
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
        
    def _get_model_config(self) -> Dict[str, Any]:
        """获取模型配置"""
        character_config = self.config["dialogue"]["characters"]["instances"][self.role]
        return character_config.get("model_config", {
            "max_tokens": 150,
            "temperature": 0.7,
            "top_p": 0.9,
            "presence_penalty": 0.6,
            "frequency_penalty": 0.6
        })

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
            required_fields = ["name", "role", "personality", "interests", "content", "language_style"]
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
            
    async def ensure_session(self):
        """确保session已创建"""
        if self.session is None or self.session.closed:
            # 获取超时配置
            timeout_config = self.performance_config.get("timeout", {})
            timeout = ClientTimeout(
                total=timeout_config.get("total", 180),
                connect=timeout_config.get("connect", 10),
                sock_connect=timeout_config.get("sock_connect", 10),
                sock_read=timeout_config.get("read", 120)
            )
            
            # 创建新会话
            connector = TCPConnector(
                ssl=False,
                limit=10,  # 限制并发连接数
                ttl_dns_cache=300,  # DNS缓存时间
                keepalive_timeout=60  # keepalive超时
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                connector=connector,
                raise_for_status=True  # 自动抛出HTTP错误
            )
            
    async def close(self):
        """关闭客户端"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
        
    @retry(
        wait=wait_exponential(multiplier=1.5, min=2, max=8),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(
            (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError)
        ),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.INFO)
    )
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """发送聊天请求"""
        start_time = time.time()
        self.metrics["total_requests"] += 1
        response_content = ""  # 初始化返回值
        
        try:
            await self.ensure_session()
            model = self.model
            if not model:
                raise ValueError("模型名称不能为空")

            # 构造请求参数
            params = {
                "model": model.split("/")[-1],  # 只使用模型名称部分
                "messages": messages,
                **self.model_config  # 使用模型特定配置
            }

            # 记录系统提示
            logger.info("\n[系统提示]")
            logger.info("-" * 40)
            logger.info(messages[0]["content"])
            
            # 记录对话开始
            logger.info("\n[对话开始] =========")
            logger.info(f"角色: {self.role}")
            logger.info(f"模型: {self.model}")
            logger.info(f"尝试: {self.metrics['total_requests']}/5")
            
            # 记录请求参数
            logger.info("\n[请求参数]")
            logger.info("-" * 40)
            logger.info(json.dumps(params, indent=2, ensure_ascii=False))
            
            # 发送请求
            async with self.session.post(self.api_url, json=params) as response:
                result = await response.json()
                
                # 更新性能指标
                if "choices" in result and len(result["choices"]) > 0:
                    response_content = result["choices"][0]["message"]["content"]
                else:
                    logger.error("API响应格式错误")
                    self.metrics["failed_requests"] += 1
                    response_content = "API响应格式错误"
                    
                if "usage" in result:
                    self.metrics["total_tokens"] += result["usage"].get("total_tokens", 0)
                    
        except aiohttp.ClientError as e:
            self.metrics["failed_requests"] += 1
            self.metrics["error_count"] += 1
            self.metrics["retry_count"] += 1
            logger.error(f"网络请求失败: {str(e)}")
            raise  # 让重试装饰器处理
            
        except asyncio.TimeoutError as e:
            self.metrics["failed_requests"] += 1
            self.metrics["error_count"] += 1
            self.metrics["retry_count"] += 1
            logger.error(f"请求超时: {str(e)}")
            raise  # 让重试装饰器处理
            
        except Exception as e:
            self.metrics["failed_requests"] += 1
            self.metrics["error_count"] += 1
            logger.error(f"聊天请求失败: {str(e)}")
            response_content = f"请求失败: {str(e)}"
            
        finally:
            # 确保总是设置response_time
            self.response_time = time.time() - start_time
            
            # 更新其他指标
            if response_content and "请求失败" not in response_content:
                self.metrics["successful_requests"] += 1
                self.metrics["total_response_time"] += self.response_time
                self.metrics["max_response_time"] = max(self.metrics["max_response_time"], self.response_time)
                self.metrics["min_response_time"] = min(self.metrics["min_response_time"], self.response_time)
                
            return response_content

    async def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        metrics = self.metrics.copy()
        if metrics["total_requests"] > 0:
            metrics["success_rate"] = metrics["successful_requests"] / metrics["total_requests"]
            metrics["average_response_time"] = metrics["total_response_time"] / metrics["total_requests"]
            metrics["average_tokens_per_request"] = metrics["total_tokens"] / metrics["total_requests"]
            metrics["error_rate"] = metrics["error_count"] / metrics["total_requests"]
        return metrics

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