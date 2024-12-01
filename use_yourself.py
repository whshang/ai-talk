import asyncio
import json
import os
import sys
import subprocess
from typing import List, Dict, Any
from datetime import datetime

class CursorComposerAgent:
    """Cursor Composer Agent - 一个可以自我指导和改进的代理"""
    
    def __init__(self):
        self.improvements_history: List[Dict[str, Any]] = []
        self.current_instruction: str = ""
        self.system_prompt = (
            "你是 Cursor，一个强大的 AI 编程助手。"
            "你需要分析当前项目的状态，并给出改进建议。"
            "你可以直接使用计算机功能来实现改进。"
        )
        
    async def compose_instruction(self, task: str) -> str:
        """根据任务生成指导指令"""
        instruction = (
            f"我是 Cursor，请指导我完成以下任务：\n\n"
            f"{task}\n\n"
            f"请按照以下步骤执行：\n"
            f"1. 分析当前代码和对话历史\n"
            f"2. 找出需要改进的地方\n"
            f"3. 生成具体的改进方案\n"
            f"4. 使用计算机功能实现改进\n"
            f"5. 验证改进效果\n\n"
            f"你可以：\n"
            f"- 读取和分析文件\n"
            f"- 修改代码和配置\n"
            f"- 运行测试和验证\n"
            f"- 持续优化和改进"
        )
        return instruction
        
    async def analyze_project(self) -> Dict[str, Any]:
        """分析项目状态"""
        analysis = {
            "code_quality": [],
            "dialogue_quality": [],
            "improvements": []
        }
        
        print("\n=== 代码分析 ===")
        
        # 分析代码文件
        code_files = [
            'main.py',
            'chat_manager.py',
            'ai_client.py',
            'config_loader.py'
        ]
        
        for file in code_files:
            if os.path.exists(file):
                print(f"\n检查文件: {file}")
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 检查代码长度
                    if len(content.split('\n')) > 300:
                        analysis["code_quality"].append(f"{file} 文件过长，建议拆分")
                    
                    # 检查函数长度
                    functions = content.split('def ')[1:]
                    for func in functions:
                        func_name = func.split('(')[0]
                        func_content = func.split(':')[1].split('def')[0]
                        if len(func_content.split('\n')) > 50:
                            analysis["code_quality"].append(f"{file} 中的 {func_name} 函数过长，建议拆分")
                    
                    # 检查注释
                    if content.count('"""') < 2:
                        analysis["code_quality"].append(f"{file} 缺少文档字符串")
        
        print("\n=== 对话分析 ===")
        
        # 分析对话历史
        chat_dir = 'chat_history'
        if os.path.exists(chat_dir):
            chat_files = [f for f in os.listdir(chat_dir) if f.endswith('.md')]
            if chat_files:
                latest_chat = max(chat_files, key=lambda x: os.path.getctime(os.path.join(chat_dir, x)))
                print(f"\n分析最新对话: {latest_chat}")
                with open(os.path.join(chat_dir, latest_chat), 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 检查对话长度
                    if len(content.split('\n')) < 10:
                        analysis["dialogue_quality"].append("对话过短，建议增加互动")
                    
                    # 检查回复质量
                    responses = content.split('```')
                    for resp in responses:
                        if len(resp.strip()) < 20:
                            analysis["dialogue_quality"].append("存在过短的回复，建议增加内容")
                        if "AI" in resp or "人工智能" in resp:
                            analysis["dialogue_quality"].append("回复中出现机器人相关词汇，建议更自然")
        
        # 生成改进建议
        if not analysis["code_quality"] and not analysis["dialogue_quality"]:
            analysis["improvements"].append("当前项目运行良好，无需重大改进")
        else:
            if analysis["code_quality"]:
                analysis["improvements"].extend([
                    "优化代码结构：",
                    *[f"- {issue}" for issue in analysis["code_quality"]]
                ])
            if analysis["dialogue_quality"]:
                analysis["improvements"].extend([
                    "改进对话质量：",
                    *[f"- {issue}" for issue in analysis["dialogue_quality"]]
                ])
        
        return analysis
        
    async def generate_improvements(self, analysis: Dict[str, Any]) -> str:
        """生成改进指令"""
        improvements = []
        
        # 根据分析结果生成改进指令
        for issue in analysis.get("code_quality", []):
            improvements.append(f"修复代码问题：{issue}")
            
        for issue in analysis.get("dialogue_quality", []):
            improvements.append(f"改进对话质量：{issue}")
            
        # 将改进指令组合成一个完整的指令字符串
        instruction = "\n".join([
            "请执行以下改进：",
            *improvements,
            "\n每个改进完成后，请验证效果并记录结果。"
        ])
        
        return instruction
        
    async def execute_instruction(self, instruction: str):
        """执行指令"""
        print(f"\n=== 执行指令 ===\n{instruction}")
        
        # 这里可以添加实际的执行逻辑
        # 比如调用 Claude 的计算机使用能力
        
    async def verify_improvements(self) -> bool:
        """验证改进效果"""
        try:
            print("\n=== 验证改进 ===")
            
            # 1. 检查文件完整性
            required_files = [
                'main.py',
                'chat_manager.py',
                'ai_client.py',
                'config_loader.py',
                'config.json',
                '.env'
            ]
            
            missing_files = []
            for file in required_files:
                if not os.path.exists(file):
                    missing_files.append(file)
            
            if missing_files:
                print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
                return False
            
            # 2. 验证配置
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    json.load(f)
                print("✅ 配置文件格式正确")
            except json.JSONDecodeError:
                print("❌ 配置文件格式错误")
                return False
            
            # 3. 运行测试
            print("\n运行主程序测试...")
            result = subprocess.run(
                ['python', 'main.py'],
                capture_output=True,
                text=True,
                timeout=5  # 设置超时时间
            )
            
            if result.returncode == 0:
                print("✅ 主程序运行正常")
                return True
            else:
                print(f"❌ 主程序运行失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ 程序运行超时")
            return False
        except Exception as e:
            print(f"❌ 验证时出错: {str(e)}")
            return False
            
    async def run(self, task: str):
        """运行代理"""
        try:
            # 1. 生成指导指令
            instruction = await self.compose_instruction(task)
            
            # 2. 分析项目状态
            print("\n📊 分析项目状态...")
            analysis = await self.analyze_project()
            
            # 3. 生成改进指令
            print("\n💡 生成改进指令...")
            improvements = await self.generate_improvements(analysis)
            
            # 4. 执行改进
            print("\n🔧 执行改进...")
            await self.execute_instruction(improvements)
            
            # 5. 验证改进
            print("\n✅ 验证改进...")
            if await self.verify_improvements():
                print("改进成功！")
            else:
                print("改进失败，需要进一步优化")
                
        except Exception as e:
            print(f"❌ 执行过程中出错: {str(e)}")
            
        print("\n=== 执行完成 ===")

async def use_yourself(instruction: str):
    """使用自己来改进项目"""
    agent = CursorComposerAgent()
    await agent.run(instruction)

def main():
    if len(sys.argv) < 2:
        print("请提供指令参数")
        sys.exit(1)
    
    instruction = sys.argv[1]
    asyncio.run(use_yourself(instruction))

if __name__ == "__main__":
    main() 