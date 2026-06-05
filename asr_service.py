import logging
from funasr import AutoModel
import config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ASRService:
    def __init__(self):
        """
        初始化 FunASR 模型。
        这里会自动从 ModelScope 下载对应的基础语音识别、端点检测、标点和说话人分离模型。
        """
        logger.info("正在初始化 FunASR 模型，初次运行可能会下载模型文件...")
        try:
            self.model = AutoModel(
                model=config.ASR_MODEL,
                vad_model=config.VAD_MODEL,
                punc_model=config.PUNC_MODEL,
                spk_model=config.SPK_MODEL,
                disable_update=True # 避免每次都检查更新
            )
            logger.info("FunASR 模型初始化成功！")
        except Exception as e:
            logger.error(f"FunASR 模型初始化失败: {str(e)}")
            self.model = None

    def process_audio(self, audio_path: str) -> str:
        """
        处理音频文件，返回包含说话人标识的逐字稿。
        """
        if not self.model:
            raise RuntimeError("ASR 模型未正确初始化，无法处理音频。")

        logger.info(f"开始处理音频: {audio_path}")
        # batch_size_s 表示多少秒的音频进行一个 batch 处理
        res = self.model.generate(input=audio_path, batch_size_s=300)
        
        if not res or len(res) == 0:
            return ""
        
        # 提取句子信息，包含 text 和 spk（speaker id）
        transcript_lines = []
        sentence_info = res[0].get('sentence_info', [])
        
        if sentence_info:
            current_spk = None
            current_text = ""
            
            # 合并同一说话人的连续语句
            for sentence in sentence_info:
                spk = sentence.get('spk', -1)
                text = sentence.get('text', '')
                
                if spk != current_spk:
                    if current_spk is not None:
                        transcript_lines.append(f"Speaker_{current_spk}: {current_text}")
                    current_spk = spk
                    current_text = text
                else:
                    current_text += text
            
            # 追加最后一段
            if current_spk is not None:
                transcript_lines.append(f"Speaker_{current_spk}: {current_text}")
        else:
            # 如果由于某种原因没有说话人信息，直接返回完整的文本
            transcript_lines.append(res[0].get('text', ''))
            
        return "\n\n".join(transcript_lines)
