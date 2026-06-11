import logging
from google import genai
import config
import re
import time

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_key: str = None, model_name: str = None):
        key = api_key or config.GEMINI_API_KEY
        self.model_name = model_name or config.GEMINI_MODEL_NAME
        if key:
            self.client = genai.Client(api_key=key)
        else:
            self.client = None

    def update_api_key(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def process_audio_to_summary(self, audio_path: str, style_name: str, progress_callback=None) -> tuple[str, str]:
        if not self.client:
            raise ValueError("请先配置 Gemini API Key")

        style_prompt = config.STYLES.get(style_name, config.STYLES.get("详细长篇纪要 (Detailed)"))
        prompt = config.MULTIMODAL_PROMPT.replace("{style_prompt}", style_prompt)

        try:
            if progress_callback:
                progress_callback("正在将音频加密上传至云端大脑...")
            
            # 使用 File API 上传音频文件
            audio_file = self.client.files.upload(file=audio_path)
            
            if progress_callback:
                progress_callback("正在让 AI 聆听并解析音频内容...")
            
            # 给 Google 后台一点点时间初始化文件状态
            time.sleep(2) 

            if progress_callback:
                progress_callback(f"AI 正在同时执行听写与【{style_name}】生成，请稍候...")
                
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[audio_file, prompt]
            )
            
            text = response.text
            
            # 解析 XML tag
            transcript_match = re.search(r'<Transcript>(.*?)</Transcript>', text, re.DOTALL | re.IGNORECASE)
            summary_match = re.search(r'<Summary>(.*?)</Summary>', text, re.DOTALL | re.IGNORECASE)
            
            transcript = transcript_match.group(1).strip() if transcript_match else "未提取到规范的逐字稿格式内容，原始返回如下：\n\n" + text
            summary = summary_match.group(1).strip() if summary_match else "未提取到规范的总结格式内容，请参考逐字稿框内的原始返回。"

            # 隐私保护：处理完毕后立即删除云端文件
            try:
                self.client.files.delete(name=audio_file.name)
                if progress_callback:
                    progress_callback("云端临时音频已安全销毁。处理完成！")
            except Exception as e:
                logger.warning(f"Failed to delete remote file {audio_file.name}: {e}")

            return transcript, summary

        except Exception as e:
            return f"发生错误: {str(e)}", f"处理失败: {str(e)}"
