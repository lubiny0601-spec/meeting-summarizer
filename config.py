import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Gemini API 配置
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# 优先使用用户指定的 3.1 Flash Lite 模型名，如果不确定具体的字符串，通常是 gemini-3.1-flash 或类似命名
GEMINI_MODEL_NAME = "gemini-3.1-flash" 

# FunASR 模型配置（默认使用 ModelScope 上的开源模型）
ASR_MODEL = "paraformer-zh" # 语音识别基础模型
VAD_MODEL = "fsmn-vad"      # 语音端点检测
PUNC_MODEL = "ct-punc"      # 标点符号恢复
SPK_MODEL = "cam++"         # 说话人分离 (Speaker Diarization)

# LLM 分块处理 (Map-Reduce) 配置
CHUNK_MAX_CHARS = 10000     # 每个文本块的最大字符数

# Prompts 模板
MAP_PROMPT_TEMPLATE = """
请你作为一位专业的会议助理，对以下【部分】会议逐字稿进行归纳总结。
请提取出这部分内容中涉及的：
1. 讨论的主要议题/重点
2. 达成的初步共识或结论
3. 提到的待办事项 (Action Items)

逐字稿内容如下：
{text}
"""

REDUCE_PROMPT_TEMPLATE = """
请你作为一位高级会议助理，综合以下所有的【部分会议总结】，生成一份最终的、结构化的会议纪要。
请严格使用 Markdown 格式输出，并包含以下几个部分：
1. 会议主题（推断）
2. 核心摘要（一小段总体概括）
3. 主要讨论点（分点详细说明）
4. 关键结论
5. 待办事项（如有）

以下是各个部分的局部总结：
{text}
"""
