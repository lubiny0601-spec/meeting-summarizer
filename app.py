import streamlit as st
import os
import tempfile
import config
from asr_service import ASRService
from llm_service import LLMService

# 初始化 session state
if 'transcript' not in st.session_state:
    st.session_state.transcript = ""
if 'summary' not in st.session_state:
    st.session_state.summary = ""

@st.cache_resource
def get_asr_service():
    return ASRService()

@st.cache_resource
def get_llm_service():
    return LLMService()

st.set_page_config(page_title="智能会议纪要生成工具", page_icon="📝", layout="wide")

st.title("🎙️ 智能会议纪要生成工具")
st.markdown("本工具支持本地高精度语音识别与说话人分离，并通过 Gemini 3.1 Flash Lite 自动生成结构化会议纪要。")

with st.sidebar:
    st.header("⚙️ 设置")
    api_key_input = st.text_input("Gemini API Key", value=config.GEMINI_API_KEY, type="password")
    
    st.info("💡 提示：如果您的音频较长，FunASR 处理和大模型摘要可能需要较长时间。")

    if st.button("清空当前结果"):
        st.session_state.transcript = ""
        st.session_state.summary = ""
        st.rerun()

# 更新 API Key 到服务中
llm_svc = get_llm_service()
if api_key_input and api_key_input != config.GEMINI_API_KEY:
    llm_svc.update_api_key(api_key_input)

# 提供两种音频输入方式
tab1, tab2 = st.tabs(["📁 上传本地录音", "🎙️ 实时麦克风录音"])

audio_file = None

with tab1:
    uploaded_file = st.file_uploader("上传会议录音 (支持 wav, mp3, m4a 等格式)", type=['wav', 'mp3', 'm4a', 'flac', 'ogg'])
    if uploaded_file is not None:
        audio_file = uploaded_file

with tab2:
    recorded_file = st.audio_input("点击下方图标开始或结束录音")
    if recorded_file is not None:
        audio_file = recorded_file

if audio_file is not None:
    if st.button("🚀 开始生成会议纪要", type="primary"):
        # 验证 API KEY
        current_api_key = api_key_input or config.GEMINI_API_KEY
        if not current_api_key:
            st.error("请先在左侧边栏输入您的 Gemini API Key！")
            st.stop()
            
        with st.status("正在处理...", expanded=True) as status:
            try:
                # 1. 保存上传文件到临时目录
                st.write("📥 正在保存音频文件...")
                file_name = getattr(audio_file, "name", "record.wav")
                ext_parts = file_name.split('.')
                suffix = f".{ext_parts[-1]}" if len(ext_parts) > 1 else ".wav"
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(audio_file.getvalue())
                    tmp_audio_path = tmp_file.name
                
                # 2. 语音识别
                st.write("🗣️ 正在进行语音识别和说话人分离（视音频长度而定，可能需要一些时间）...")
                asr_svc = get_asr_service()
                transcript = asr_svc.process_audio(tmp_audio_path)
                
                # 删除临时文件
                try:
                    os.unlink(tmp_audio_path)
                except:
                    pass

                if not transcript:
                    status.update(label="处理失败", state="error", expanded=True)
                    st.error("未能识别出语音内容。")
                    st.stop()
                
                st.session_state.transcript = transcript
                st.write("✅ 语音识别完成！")
                
                # 3. LLM 总结
                def update_progress(msg):
                    st.write(f"🧠 {msg}")
                
                st.write("🧠 正在生成会议总结...")
                summary = llm_svc.generate_summary(transcript, progress_callback=update_progress)
                st.session_state.summary = summary
                
                status.update(label="🎉 处理完成！", state="complete", expanded=False)
                
            except Exception as e:
                status.update(label="发生错误", state="error", expanded=True)
                st.error(f"处理过程中发生错误：{str(e)}")
                st.stop()

# 结果展示区
if st.session_state.transcript or st.session_state.summary:
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 原始逐字稿")
        st.text_area("包含说话人标记的逐字稿", value=st.session_state.transcript, height=600, disabled=False, label_visibility="collapsed")
        if st.session_state.transcript:
            st.download_button(
                label="📥 下载逐字稿",
                data=st.session_state.transcript,
                file_name="transcript.txt",
                mime="text/plain"
            )
            
    with col2:
        st.subheader("📑 会议纪要")
        # 用容器包裹 Markdown 实现带边框的定高展示区，或者直接渲染
        with st.container(height=600, border=True):
            if st.session_state.summary:
                st.markdown(st.session_state.summary)
            else:
                st.write("暂无摘要。")
            
        if st.session_state.summary:
            st.download_button(
                label="📥 下载纪要 (Markdown)",
                data=st.session_state.summary,
                file_name="meeting_summary.md",
                mime="text/markdown"
            )
