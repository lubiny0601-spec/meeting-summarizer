import logging
from google import genai
import config

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_key: str = None):
        """
        初始化 Gemini API 客户端。
        优先使用传入的 api_key，如果没有则使用 config 中加载的配置。
        """
        key = api_key or config.GEMINI_API_KEY
        if key:
            self.client = genai.Client(api_key=key)
        else:
            self.client = None

    def update_api_key(self, api_key: str):
        """在运行时更新 API Key"""
        self.client = genai.Client(api_key=api_key)

    def chunk_text(self, text: str, max_chars: int) -> list[str]:
        """
        按照最大字符数将长文本切分为块，尽量以说话人段落为边界。
        """
        chunks = []
        current_chunk = ""
        # 按照段落（说话人变更）分割
        lines = text.split('\n\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            if len(current_chunk) + len(line) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += ("\n\n" + line) if current_chunk else line
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def generate_summary(self, transcript: str, progress_callback=None) -> str:
        """
        基于会议逐字稿生成摘要。包含分块 Map-Reduce 逻辑。
        """
        if not self.client:
            raise ValueError("未配置 Gemini API Key，请先配置！")
        
        if not transcript.strip():
            return "未检测到有效语音内容。"

        # 分块
        chunks = self.chunk_text(transcript, config.CHUNK_MAX_CHARS)
        
        # 单块情况：无需 Map-Reduce
        if len(chunks) == 1:
            if progress_callback:
                progress_callback("逐字稿较短，正在直接生成最终会议纪要...")
            prompt = config.REDUCE_PROMPT_TEMPLATE.replace("{text}", chunks[0])
            
            response = self.client.models.generate_content(
                model=config.GEMINI_MODEL_NAME,
                contents=prompt,
            )
            return response.text

        # 多块情况：Map-Reduce
        chunk_summaries = []
        total_chunks = len(chunks)
        
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(f"由于文本较长，正在分段分析：处理第 {i+1}/{total_chunks} 部分...")
            
            prompt = config.MAP_PROMPT_TEMPLATE.replace("{text}", chunk)
            try:
                response = self.client.models.generate_content(
                    model=config.GEMINI_MODEL_NAME,
                    contents=prompt,
                )
                chunk_summaries.append(response.text)
            except Exception as e:
                logger.error(f"分析第 {i+1} 块时出错: {str(e)}")
                chunk_summaries.append(f"【分块 {i+1} 分析失败】")
        
        if progress_callback:
            progress_callback("正在整合所有分段结果，生成最终会议纪要...")
            
        # Reduce
        combined_text = "\n\n---\n\n".join(chunk_summaries)
        reduce_prompt = config.REDUCE_PROMPT_TEMPLATE.replace("{text}", combined_text)
        
        try:
            final_response = self.client.models.generate_content(
                model=config.GEMINI_MODEL_NAME,
                contents=reduce_prompt,
            )
            return final_response.text
        except Exception as e:
            logger.error(f"最终整合出错: {str(e)}")
            return f"生成最终摘要时发生错误: {str(e)}\n\n以下是部分总结内容：\n{combined_text}"
