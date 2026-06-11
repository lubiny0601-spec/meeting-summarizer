import sys
import os
import tempfile
import threading
import queue
import sounddevice as sd
import soundfile as sf
import keyboard
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                               QLineEdit, QFileDialog, QSplitter, QMessageBox, QComboBox)
from PySide6.QtCore import QThread, Signal, Qt

import config

class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.filename = None
        self.samplerate = 16000
        self.channels = 1
        self.q = queue.Queue()
        self.stream = None

    def callback(self, indata, frames, time, status):
        self.q.put(indata.copy())

    def start_recording(self):
        self.is_recording = True
        self.filename = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        self.q = queue.Queue()
        self.stream = sd.InputStream(samplerate=self.samplerate, channels=self.channels, callback=self.callback)
        self.stream.start()
        
        def save_file():
            with sf.SoundFile(self.filename, mode='w', samplerate=self.samplerate, channels=self.channels) as file:
                while self.is_recording or not self.q.empty():
                    file.write(self.q.get())
        threading.Thread(target=save_file).start()

    def stop_recording(self):
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        return self.filename

class HotkeyListener(QThread):
    toggle_record_signal = Signal()
    def run(self):
        keyboard.add_hotkey('ctrl+shift+r', lambda: self.toggle_record_signal.emit())
        keyboard.wait()

class WorkerThread(QThread):
    progress_signal = Signal(str)
    transcript_signal = Signal(str)
    summary_signal = Signal(str)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, audio_path, api_key, model_name, style_name):
        super().__init__()
        self.audio_path = audio_path
        self.api_key = api_key
        self.model_name = model_name
        self.style_name = style_name

    def run(self):
        try:
            self.progress_signal.emit("正在初始化云端引擎...")
            from llm_service import LLMService
            
            llm_svc = LLMService(api_key=self.api_key, model_name=self.model_name)
            
            def cb(msg):
                self.progress_signal.emit(msg)
                
            transcript, summary = llm_svc.process_audio_to_summary(self.audio_path, self.style_name, progress_callback=cb)
            
            if transcript.startswith("发生错误") or summary.startswith("处理失败"):
                self.error_signal.emit(transcript + "\n" + summary)
            else:
                self.transcript_signal.emit(transcript)
                self.summary_signal.emit(summary)
            
        except Exception as e:
            self.error_signal.emit(f"发生错误: {str(e)}")
        finally:
            self.finished_signal.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能会议纪要生成工具 (V3.0 云端增强版)")
        self.resize(1000, 700)
        self.recorder = AudioRecorder()
        
        # 快捷键监听
        self.hotkey_listener = HotkeyListener()
        self.hotkey_listener.toggle_record_signal.connect(self.on_hotkey_toggle)
        self.hotkey_listener.start()
        
        # 主窗口组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧控制面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(300)
        
        # API Key 设置
        left_layout.addWidget(QLabel("🔑 Gemini API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(config.GEMINI_API_KEY)
        left_layout.addWidget(self.api_key_input)
        
        # Model Name 设置
        left_layout.addWidget(QLabel("🤖 Gemini Model Name:"))
        self.model_input = QLineEdit()
        self.model_input.setText(config.GEMINI_MODEL_NAME)
        left_layout.addWidget(self.model_input)
        
        # 输出风格设置
        left_layout.addWidget(QLabel("🎨 输出风格模板:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(list(config.STYLES.keys()))
        left_layout.addWidget(self.style_combo)
        
        left_layout.addSpacing(20)
        
        # 录音/上传区
        self.btn_upload = QPushButton("📁 上传本地录音文件")
        self.btn_upload.clicked.connect(self.on_upload)
        left_layout.addWidget(self.btn_upload)
        
        self.btn_record = QPushButton("🎙️ 开始录音 (Ctrl+Shift+R)")
        self.btn_record.clicked.connect(self.on_record)
        left_layout.addWidget(self.btn_record)
        
        self.lbl_status = QLabel("状态: 闲置")
        left_layout.addWidget(self.lbl_status)
        
        left_layout.addStretch()
        
        # 右侧结果区
        right_panel = QSplitter(Qt.Vertical)
        
        # 逐字稿区
        transcript_widget = QWidget()
        t_layout = QVBoxLayout(transcript_widget)
        t_layout.addWidget(QLabel("📝 原始逐字稿:"))
        self.txt_transcript = QTextEdit()
        self.txt_transcript.setReadOnly(True)
        t_layout.addWidget(self.txt_transcript)
        right_panel.addWidget(transcript_widget)
        
        # 总结区
        summary_widget = QWidget()
        s_layout = QVBoxLayout(summary_widget)
        s_layout.addWidget(QLabel("📑 会议纪要 (Markdown):"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True)
        s_layout.addWidget(self.txt_summary)
        
        # 底部按钮区
        btn_layout = QHBoxLayout()
        self.btn_copy = QPushButton("📋 一键复制纪要")
        self.btn_copy.clicked.connect(self.copy_summary)
        self.btn_export = QPushButton("💾 导出为 PDF")
        self.btn_export.clicked.connect(self.export_pdf)
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_export)
        s_layout.addLayout(btn_layout)
        
        right_panel.addWidget(summary_widget)
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)
        
    def on_hotkey_toggle(self):
        # 触发等同于点击按钮
        if self.btn_record.isEnabled():
            self.on_record()
        
    def copy_summary(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.txt_summary.toPlainText())
        self.lbl_status.setText("状态: 已复制到剪贴板！")
        
    def export_pdf(self):
        text = self.txt_summary.toPlainText()
        if not text:
            QMessageBox.warning(self, "为空", "没有可导出的内容。")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "导出为 PDF", "会议纪要.pdf", "PDF Files (*.pdf)")
        if file_path:
            self.lbl_status.setText("状态: 正在生成 PDF...")
            try:
                import markdown
                import subprocess
                
                html_body = markdown.markdown(text, extensions=['fenced_code', 'tables'])
                html_content = f"<html><head><meta charset='utf-8'><style>body{{font-family: sans-serif; padding: 20px; line-height: 1.6;}}</style></head><body>{html_body}</body></html>"
                
                tmp_html = tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8')
                tmp_html.write(html_content)
                tmp_html.close()
                
                edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
                if os.path.exists(edge_path):
                    cmd = [edge_path, "--headless", "--disable-gpu", f"--print-to-pdf={os.path.abspath(file_path)}", f"file:///{tmp_html.name.replace(chr(92), '/')}"]
                    subprocess.run(cmd, check=True)
                    self.lbl_status.setText(f"状态: 已导出到 {file_path}")
                else:
                    QMessageBox.warning(self, "环境缺失", "未找到 Microsoft Edge，无法生成 PDF。")
                    self.lbl_status.setText("状态: 导出失败")
                    
                os.remove(tmp_html.name)
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出 PDF 时发生错误：{str(e)}")
                self.lbl_status.setText("状态: 导出失败")
        
    def on_upload(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "选择录音文件", "", "Audio Files (*.wav *.mp3 *.m4a *.flac *.ogg)")
        if file_name:
            self.start_processing(file_name)

    def on_record(self):
        if not self.recorder.is_recording:
            self.recorder.start_recording()
            self.btn_record.setText("⏹️ 停止录音 (Ctrl+Shift+R)")
            self.btn_record.setStyleSheet("background-color: #ffcccc;")
            self.lbl_status.setText("状态: 正在录音...")
        else:
            audio_path = self.recorder.stop_recording()
            self.btn_record.setText("🎙️ 开始录音 (Ctrl+Shift+R)")
            self.btn_record.setStyleSheet("")
            
            reply = QMessageBox.question(self, "确认处理", 
                                         "是否要结束录音，并开始生成会议纪要？\n\n(选择 No 将直接丢弃刚才的录音)", 
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            
            if reply == QMessageBox.Yes:
                self.lbl_status.setText("状态: 录音结束，准备处理")
                self.start_processing(audio_path)
            else:
                self.lbl_status.setText("状态: 已取消录音")
                try:
                    import os
                    os.remove(audio_path)
                except:
                    pass

    def start_processing(self, audio_path):
        api_key = self.api_key_input.text().strip()
        model_name = self.model_input.text().strip()
        style_name = self.style_combo.currentText()
        if not api_key:
            QMessageBox.warning(self, "缺少 API Key", "请先在左侧输入 Gemini API Key！")
            return
            
        self.txt_transcript.clear()
        self.txt_summary.clear()
        self.btn_upload.setEnabled(False)
        self.btn_record.setEnabled(False)
        
        self.worker = WorkerThread(audio_path, api_key, model_name, style_name)
        self.worker.progress_signal.connect(self.update_status)
        self.worker.transcript_signal.connect(self.txt_transcript.setPlainText)
        self.worker.summary_signal.connect(self.txt_summary.setPlainText)
        self.worker.error_signal.connect(self.show_error)
        self.worker.finished_signal.connect(self.processing_finished)
        self.worker.start()
        
    def update_status(self, msg):
        self.lbl_status.setText(f"状态: {msg}")
        
    def show_error(self, msg):
        QMessageBox.critical(self, "发生错误", msg)
        self.lbl_status.setText("状态: 发生错误")
        
    def processing_finished(self):
        self.btn_upload.setEnabled(True)
        self.btn_record.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
