import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTextEdit, QPushButton, QComboBox, QLabel, QFrame, QHBoxLayout, QFileDialog
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont
import sounddevice as sd
import soundfile as sf
import time
import numpy as np
import requests
import os

class AudioGenerationThread(QThread):
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)
    
    def __init__(self, text, voice_model):
        super().__init__()
        self.text = text
        self.voice_model = voice_model
        
    def run(self):
        try:
            # API endpoint and key
            url = "https://api.deepgram.com/v1/speak"
            api_key = "503498cc5ceb6e71bba5767290a8dfaf996dd10d"
            
            headers = {
                "Authorization": f"Token {api_key}",
                "Content-Type": "text/plain"
            }
            
            params = {
                "model": self.voice_model
            }
            
            # Make the POST request
            response = requests.post(url, headers=headers, params=params, data=self.text)
            
            if response.status_code == 200:
                with open("temp_audio.mp3", "wb") as f:
                    f.write(response.content)
                self.finished.emit(True)
            else:
                self.error.emit(f"API Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            self.error.emit(str(e))

class AudioPlayThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._running = True
        self.custom_file = None
        
    def stop(self):
        self._running = False
        
    def run(self):
        try:
            # Use custom file if available, otherwise use temp file
            audio_file = self.custom_file if self.custom_file else 'temp_audio.mp3'
            
            # Load the audio file
            audio_data, sample_rate = sf.read(audio_file)
            audio_data = audio_data.astype(np.float32)
            
            # Find VB-Cable device
            devices = sd.query_devices()
            vb_cable_device = None
            for i, device in enumerate(devices):
                if 'CABLE Input' in device['name']:
                    vb_cable_device = i
                    break
                    
            if vb_cable_device is None:
                raise Exception("VB-Cable not found")
                
            # Stream to VB-Cable input
            with sd.OutputStream(samplerate=sample_rate, channels=len(audio_data.shape), 
                              device=vb_cable_device) as stream:
                chunk_size = 1024
                for i in range(0, len(audio_data), chunk_size):
                    if not self._running:
                        break
                    chunk = audio_data[i:i + chunk_size]
                    stream.write(chunk)
                    
            # Only delete temp file if it's not a custom file
            if not self.custom_file and os.path.exists('temp_audio.mp3'):
                os.remove('temp_audio.mp3')
                
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))

class TTSPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.voices = {
            "Asteria (American, feminine)": "aura-asteria-en",
            "Orpheus (American, masculine)": "aura-orpheus-en",
            "Angus (Irish, masculine)": "aura-angus-en",
            "Arcas (American, masculine)": "aura-arcas-en",
            "Athena (British, feminine)": "aura-athena-en",
            "Helios (British, masculine)": "aura-helios-en",
            "Hera (American, feminine)": "aura-hera-en",
            "Luna (American, feminine)": "aura-luna-en",
            "Orion (American, masculine) - Use this one": "aura-orion-en",
            "Perseus (American, masculine)": "aura-perseus-en",
            "Stella (American, feminine)": "aura-stella-en",
            "Zeus (American, masculine)": "aura-zeus-en"
        }
        self.audio_gen_thread = None
        self.audio_play_thread = None
        self.custom_audio_file = None
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Deepgram TTS Player')
        self.setGeometry(100, 100, 800, 400)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTextEdit {
                border: 2px solid #ccc;
                border-radius: 5px;
                padding: 8px;
                background-color: white;
                font-size: 12pt;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 12pt;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
            QComboBox {
                border: 2px solid #ccc;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
                font-size: 11pt;
            }
            QLabel {
                font-size: 11pt;
                color: #333;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Left side - TTS Section
        tts_widget = QWidget()
        tts_layout = QVBoxLayout(tts_widget)
        tts_layout.setSpacing(15)

        # Add a title for TTS section
        tts_title = QLabel("Text-to-Speech")
        tts_title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        tts_layout.addWidget(tts_title)

        # Voice selector
        voice_label = QLabel("Select Voice:")
        tts_layout.addWidget(voice_label)

        self.voice_selector = QComboBox()
        self.voice_selector.addItems(self.voices.keys())
        tts_layout.addWidget(self.voice_selector)

        # Text input
        text_label = QLabel("Enter Text:")
        tts_layout.addWidget(text_label)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Type your text here...")
        tts_layout.addWidget(self.text_input)

        # TTS Buttons
        tts_button_layout = QHBoxLayout()
        tts_button_layout.setSpacing(10)

        self.speak_button = QPushButton('Speak')
        self.speak_button.clicked.connect(self.start_speaking)
        tts_button_layout.addWidget(self.speak_button)

        self.stop_button = QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop_speaking)
        self.stop_button.setEnabled(False)
        tts_button_layout.addWidget(self.stop_button)

        tts_layout.addLayout(tts_button_layout)
        main_layout.addWidget(tts_widget)

        # Add vertical separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)

        # Right side - Media Player Section
        media_widget = QWidget()
        media_layout = QVBoxLayout(media_widget)
        media_layout.setSpacing(15)

        # Add a title for Media Player section
        media_title = QLabel("Media Player")
        media_title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        media_layout.addWidget(media_title)

        # File selection info
        self.file_info = QLabel("No file selected")
        self.file_info.setWordWrap(True)
        media_layout.addWidget(self.file_info)

        # Media Player Buttons
        media_button_layout = QVBoxLayout()
        media_button_layout.setSpacing(10)

        self.file_button = QPushButton('Select Media File')
        self.file_button.clicked.connect(self.select_file)
        media_button_layout.addWidget(self.file_button)

        # Add horizontal layout for play and stop media buttons
        media_playback_layout = QHBoxLayout()
        
        self.play_media_button = QPushButton('Play Media')
        self.play_media_button.clicked.connect(self.start_speaking)
        self.play_media_button.setEnabled(False)
        media_playback_layout.addWidget(self.play_media_button)

        self.stop_media_button = QPushButton('Stop Media')
        self.stop_media_button.clicked.connect(self.stop_media)
        self.stop_media_button.setEnabled(False)
        media_playback_layout.addWidget(self.stop_media_button)

        media_button_layout.addLayout(media_playback_layout)
        media_layout.addLayout(media_button_layout)
        media_layout.addStretch()
        main_layout.addWidget(media_widget)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio/Video File",
            "",
            "Audio/Video Files (*.mp3 *.mp4);;All Files (*.*)"
        )
        if file_path:
            self.custom_audio_file = file_path
            self.file_info.setText(f"Selected: {os.path.basename(file_path)}")
            self.play_media_button.setEnabled(True)

    def start_speaking(self):
        if self.sender() == self.play_media_button:  # If media play button was clicked
            self.play_media_button.setEnabled(False)
            self.stop_media_button.setEnabled(True)  # Enable stop media button
            if not os.path.exists(self.custom_audio_file):
                self.on_error("Selected file no longer exists!")
                return
            
            self.audio_play_thread = AudioPlayThread()
            self.audio_play_thread.custom_file = self.custom_audio_file
            self.audio_play_thread.finished.connect(self.on_finished)
            self.audio_play_thread.error.connect(self.on_error)
            self.audio_play_thread.start()
        else:  # If TTS speak button was clicked
            self.speak_button.setEnabled(False)
            if not self.text_input.toPlainText().strip():
                return
            selected_voice = self.voices[self.voice_selector.currentText()]
            self.audio_gen_thread = AudioGenerationThread(self.text_input.toPlainText(), selected_voice)
            self.audio_gen_thread.finished.connect(self.start_playback)
            self.audio_gen_thread.error.connect(self.on_error)
            self.audio_gen_thread.start()
        
    def start_playback(self, success):
        if not success:
            self.on_finished()
            return
            
        self.stop_button.setEnabled(True)
        self.audio_play_thread = AudioPlayThread()
        self.audio_play_thread.finished.connect(self.on_finished)
        self.audio_play_thread.error.connect(self.on_error)
        self.audio_play_thread.start()
        
    def stop_speaking(self):
        if self.audio_play_thread and self.audio_play_thread.isRunning():
            self.audio_play_thread.stop()
            self.audio_play_thread.wait()
            self.on_finished()
            
    def on_finished(self):
        self.speak_button.setEnabled(True)
        self.play_media_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.stop_media_button.setEnabled(False)  # Disable stop media button
        
    def on_error(self, error_msg):
        print(f"Error: {error_msg}")
        self.on_finished()

    def stop_media(self):
        if self.audio_play_thread and self.audio_play_thread.isRunning():
            self.audio_play_thread.stop()
            self.audio_play_thread.wait()
            self.play_media_button.setEnabled(True)
            self.stop_media_button.setEnabled(False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = TTSPlayer()
    player.show()
    sys.exit(app.exec())
