"""Modern UI for Audio Recorder with improved styling."""

from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFileDialog,
    QSplitter,
    QFrame,
    QDialog,
    QLineEdit,
    QGroupBox,
    QStatusBar,
    QToolBar,
    QApplication,
    QSizePolicy,
    QSpacerItem,
    QScrollArea,
    QStackedWidget,
)
from PySide6.QtCore import QSize
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QColor, QPalette
import numpy as np

from ..utils.logger import get_logger
from ..utils.config import get_config
from ..audio.capture import AudioCapture, AudioSource, SourceType
from ..speech.asr import TranscriptionManager, TranscriptionResult
from ..speech.diarization import SpeakerDiarization
from ..database.manager import get_database
from ..ai.openrouter import AISuggestionGenerator
from ..ai.priority_queue import get_priority_queue

logger = get_logger(__name__)

# Modern color scheme
COLORS = {
    "primary": "#6366f1",
    "primary_dark": "#4f46e5",
    "secondary": "#8b5cf6",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "background": "#0f172a",
    "surface": "#1e293b",
    "surface_light": "#334155",
    "text": "#f8fafc",
    "text_secondary": "#94a3b8",
    "border": "#334155",
}

SPEAKER_COLORS = [
    "#3b82f6",
    "#ef4444",
    "#10b981",
    "#f59e0b",
    "#8b5cf6",
    "#ec4899",
    "#06b6d4",
    "#f97316",
]


class ModernStyle:
    """Modern UI styles."""

    @staticmethod
    def get_stylesheet():
        return f"""
        QMainWindow {{
            background-color: {COLORS["background"]};
        }}
        
        QWidget {{
            background-color: {COLORS["background"]};
            color: {COLORS["text"]};
            font-family: 'Inter', 'Segoe UI', sans-serif;
            font-size: 13px;
        }}
        
        QPushButton {{
            background-color: {COLORS["surface"]};
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: 500;
        }}
        
        QPushButton:hover {{
            background-color: {COLORS["surface_light"]};
            border-color: {COLORS["primary"]};
        }}
        
        QPushButton:pressed {{
            background-color: {COLORS["primary_dark"]};
        }}
        
        QPushButton#recordButton {{
            background-color: {COLORS["danger"]};
            color: white;
            font-weight: bold;
            padding: 12px 24px;
        }}
        
        QPushButton#recordButton:checked {{
            background-color: {COLORS["surface"]};
            color: {COLORS["text"]};
        }}
        
        QPushButton#recordButton:hover {{
            background-color: #dc2626;
        }}
        
        QComboBox {{
            background-color: {COLORS["surface"]};
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 6px;
            padding: 8px 12px;
            min-width: 200px;
        }}
        
        QComboBox:hover {{
            border-color: {COLORS["primary"]};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {COLORS["surface"]};
            color: {COLORS["text"]};
            selection-background-color: {COLORS["primary"]};
            border: 1px solid {COLORS["border"]};
        }}
        
        QTextEdit {{
            background-color: {COLORS["surface"]};
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 8px;
            padding: 12px;
        }}
        
        QListWidget {{
            background-color: {COLORS["surface"]};
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 8px;
            padding: 8px;
        }}
        
        QListWidget::item {{
            background-color: transparent;
            border-radius: 6px;
            margin: 4px 0;
            padding: 8px;
        }}
        
        QListWidget::item:hover {{
            background-color: {COLORS["surface_light"]};
        }}
        
        QLabel {{
            color: {COLORS["text"]};
        }}
        
        QLabel#headerLabel {{
            font-size: 16px;
            font-weight: 600;
            color: {COLORS["text"]};
        }}
        
        QLabel#subheaderLabel {{
            font-size: 12px;
            color: {COLORS["text_secondary"]};
        }}
        
        QToolBar {{
            background-color: {COLORS["surface"]};
            border: none;
            padding: 8px;
        }}
        
        QStatusBar {{
            background-color: {COLORS["surface"]};
            color: {COLORS["text_secondary"]};
            border-top: 1px solid {COLORS["border"]};
        }}
        
        QGroupBox {{
            background-color: {COLORS["surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 12px;
            font-weight: 600;
        }}
        
        QGroupBox::title {{
            color: {COLORS["text_secondary"]};
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
        }}
        
        QLineEdit {{
            background-color: {COLORS["background"]};
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 6px;
            padding: 8px 12px;
        }}
        
        QLineEdit:focus {{
            border-color: {COLORS["primary"]};
        }}
        
        QSplitter::handle {{
            background-color: {COLORS["border"]};
        }}
        
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        
        QScrollBar:vertical {{
            background-color: {COLORS["surface"]};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {COLORS["surface_light"]};
            border-radius: 6px;
            min-height: 30px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {COLORS["primary"]};
        }}
        
        QMessageBox {{
            background-color: {COLORS["surface"]};
        }}
        
        QMessageBox QPushButton {{
            min-width: 80px;
        }}
        """


class TranscriptionWidget(QTextEdit):
    """Modern transcription display widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Transcriptions will appear here...")
        self.messages = {}
        self.speaker_colors = {}
        self.color_index = 0

    def add_message(
        self, message_id: str, text: str, speaker: Optional[str] = None, is_final: bool = True
    ):
        if speaker and speaker not in self.speaker_colors:
            self.speaker_colors[speaker] = SPEAKER_COLORS[self.color_index % len(SPEAKER_COLORS)]
            self.color_index += 1

        color = self.speaker_colors.get(speaker, COLORS["text_secondary"])
        speaker_label = f"{speaker}" if speaker else "Unknown"

        if is_final:
            html = f"""
            <div style="margin: 8px 0; padding: 12px; background-color: {COLORS["surface"]}; 
                        border-radius: 8px; border-left: 4px solid {color};">
                <div style="color: {color}; font-weight: 600; font-size: 11px; margin-bottom: 4px;">
                    {speaker_label}
                </div>
                <div style="color: {COLORS["text"]}; line-height: 1.5;">
                    {text}
                </div>
            </div>
            """
        else:
            html = f"""
            <div style="margin: 8px 0; padding: 12px; background-color: {COLORS["surface"]};
                        border-radius: 8px; opacity: 0.7;">
                <div style="color: {COLORS["text_secondary"]}; font-style: italic;">
                    {text}...
                </div>
            </div>
            """

        self.messages[message_id] = (speaker, text, is_final)
        self.append(html)

        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_speaker(self, message_id: str, speaker: str):
        if message_id in self.messages:
            old_speaker, text, is_final = self.messages[message_id]
            self.messages[message_id] = (speaker, text, is_final)

    def clear_messages(self):
        self.clear()
        self.messages = {}
        self.speaker_colors = {}
        self.color_index = 0


class AISuggestionsWidget(QListWidget):
    """Modern AI suggestions widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(8)
        self.setFrameShape(QFrame.NoFrame)

    def add_suggestion(self, question: str, response: str):
        item = QListWidgetItem()

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Question
        question_label = QLabel(
            f"<span style='color: {COLORS['primary']}; font-weight: 600;'>Q:</span> {question}"
        )
        question_label.setWordWrap(True)
        question_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px;")
        layout.addWidget(question_label)

        # Response
        response_label = QLabel(
            f"<span style='color: {COLORS['success']}; font-weight: 600;'>A:</span> {response}"
        )
        response_label.setWordWrap(True)
        response_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; line-height: 1.6;")
        layout.addWidget(response_label)

        widget.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS["surface"]};
                border-radius: 8px;
                border: 1px solid {COLORS["border"]};
            }}
            QWidget:hover {{
                border-color: {COLORS["primary"]};
            }}
        """)

        item.setSizeHint(widget.sizeHint() + QSize(0, 20))
        self.addItem(item)
        self.setItemWidget(item, widget)
        self.scrollToBottom()

    def clear_suggestions(self):
        self.clear()


class HeaderWidget(QWidget):
    """Modern header widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)

        # Logo/Title
        title_layout = QVBoxLayout()
        title = QLabel("Audio Recorder STT")
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        subtitle = QLabel("Real-time speech recognition with AI assistance")
        subtitle.setStyleSheet(f"font-size: 12px; color: {COLORS['text_secondary']};")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        layout.addLayout(title_layout)
        layout.addStretch()

        # Status indicator
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"""
            color: {COLORS["success"]};
            font-weight: 500;
            padding: 6px 12px;
            background-color: {COLORS["surface"]};
            border-radius: 16px;
        """)
        layout.addWidget(self.status_label)


class ControlPanel(QWidget):
    """Modern control panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # Source selector
        source_container = QWidget()
        source_layout = QVBoxLayout(source_container)
        source_layout.setSpacing(4)
        source_layout.setContentsMargins(0, 0, 0, 0)

        source_label = QLabel("Audio Source")
        source_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 500;"
        )
        source_layout.addWidget(source_label)

        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(280)
        source_layout.addWidget(self.source_combo)

        layout.addWidget(source_container)

        # Refresh button
        refresh_container = QWidget()
        refresh_layout = QVBoxLayout(refresh_container)
        refresh_layout.setSpacing(4)
        refresh_layout.setContentsMargins(0, 0, 0, 0)

        refresh_label = QLabel("")  # Empty label to match height
        refresh_label.setStyleSheet("font-size: 11px; min-height: 16px;")
        refresh_layout.addWidget(refresh_label)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedWidth(90)
        self.refresh_btn.setFixedHeight(36)  # Match combobox height
        refresh_layout.addWidget(self.refresh_btn)

        layout.addWidget(refresh_container)

        layout.addSpacing(24)

        # Record button container
        record_container = QWidget()
        record_layout = QVBoxLayout(record_container)
        record_layout.setSpacing(4)
        record_layout.setContentsMargins(0, 0, 0, 0)

        record_label = QLabel("")  # Empty label to match height
        record_label.setStyleSheet("font-size: 11px; min-height: 16px;")
        record_layout.addWidget(record_label)

        self.record_btn = QPushButton("Start Recording")
        self.record_btn.setObjectName("recordButton")
        self.record_btn.setCheckable(True)
        self.record_btn.setMinimumWidth(140)
        self.record_btn.setFixedHeight(36)  # Match combobox height
        record_layout.addWidget(self.record_btn)

        layout.addWidget(record_container)

        # Summarize button container
        summarize_container = QWidget()
        summarize_layout = QVBoxLayout(summarize_container)
        summarize_layout.setSpacing(4)
        summarize_layout.setContentsMargins(0, 0, 0, 0)

        summarize_label = QLabel("")  # Empty label to match height
        summarize_label.setStyleSheet("font-size: 11px; min-height: 16px;")
        summarize_layout.addWidget(summarize_label)

        self.summarize_btn = QPushButton("Summarize")
        self.summarize_btn.setEnabled(False)
        self.summarize_btn.setFixedHeight(36)  # Match combobox height
        summarize_layout.addWidget(self.summarize_btn)

        layout.addWidget(summarize_container)

        layout.addStretch()


class MainWindow(QMainWindow):
    """Modern main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Recorder STT")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)

        # Apply modern stylesheet
        self.setStyleSheet(ModernStyle.get_stylesheet())

        # Initialize components
        self.audio_capture = AudioCapture()
        self.transcription_manager = TranscriptionManager()
        self.diarization = SpeakerDiarization()

        # Initialize AI generator with provider from config
        config = get_config()
        self._current_provider = config.get("provider", "openrouter")
        self.ai_generator = AISuggestionGenerator(provider=self._current_provider)

        # Priority queue for AI responses
        self.priority_queue = get_priority_queue()
        self.priority_queue.response_ready.connect(self._on_ai_response_ready)
        self.priority_queue.queue_depth_changed.connect(self._on_queue_depth_changed)
        self.priority_queue.start()

        self.current_session_id: Optional[str] = None
        self._pending_questions: dict = {}
        self.is_recording = False

        self.setup_ui()
        self.setup_connections()
        self.initialize()

    def setup_ui(self):
        """Setup the modern UI."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header
        self.header = HeaderWidget()
        main_layout.addWidget(self.header)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"background-color: {COLORS['border']}; max-height: 1px;")
        main_layout.addWidget(separator)

        # Control panel
        self.control_panel = ControlPanel()
        main_layout.addWidget(self.control_panel)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # Transcription panel
        transcription_container = QWidget()
        transcription_layout = QVBoxLayout(transcription_container)
        transcription_layout.setContentsMargins(24, 16, 12, 24)
        transcription_layout.setSpacing(12)

        transcription_header = QLabel("Live Transcription")
        transcription_header.setObjectName("headerLabel")
        transcription_layout.addWidget(transcription_header)

        self.transcription_widget = TranscriptionWidget()
        transcription_layout.addWidget(self.transcription_widget)

        splitter.addWidget(transcription_container)

        # AI Suggestions panel
        suggestions_container = QWidget()
        suggestions_layout = QVBoxLayout(suggestions_container)
        suggestions_layout.setContentsMargins(12, 16, 24, 24)
        suggestions_layout.setSpacing(12)

        suggestions_header = QLabel("AI Suggestions")
        suggestions_header.setObjectName("headerLabel")
        suggestions_layout.addWidget(suggestions_header)

        suggestions_subheader = QLabel("Questions detected in conversation")
        suggestions_subheader.setObjectName("subheaderLabel")
        suggestions_layout.addWidget(suggestions_subheader)

        # Provider selector
        provider_layout = QHBoxLayout()
        provider_label = QLabel("AI Provider:")
        provider_label.setStyleSheet("color: #94a3b8;")
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["OpenRouter", "Local"])
        self.provider_combo.setCurrentText(
            "OpenRouter" if self._current_provider == "openrouter" else "Local"
        )
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.provider_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 100px;
            }
            QComboBox:focus { border: 1px solid #3b82f6; }
            QComboBox::drop-down { border: none; }
        """)
        provider_layout.addWidget(provider_label)
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()
        suggestions_layout.addLayout(provider_layout)

        self.suggestions_widget = AISuggestionsWidget()
        suggestions_layout.addWidget(self.suggestions_widget)

        splitter.addWidget(suggestions_container)

        splitter.setSizes([900, 500])
        main_layout.addWidget(splitter, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready to record")

        # Toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(settings_action)

        toolbar.addSeparator()

        export_action = QAction("Export", self)
        export_action.triggered.connect(self.export_conversation)
        toolbar.addAction(export_action)

        clear_action = QAction("Clear", self)
        clear_action.triggered.connect(self.clear_conversation)
        toolbar.addAction(clear_action)

    def setup_connections(self):
        """Setup signal connections."""
        # Control panel
        self.control_panel.refresh_btn.clicked.connect(self.refresh_sources)
        self.control_panel.record_btn.clicked.connect(self.toggle_recording)
        self.control_panel.summarize_btn.clicked.connect(self.summarize_conversation)

        # Audio capture
        self.audio_capture.audio_data.connect(self.on_audio_data)
        self.audio_capture.error.connect(self.on_error)

        # Transcription
        self.transcription_manager.transcription_ready.connect(self.on_transcription)
        self.transcription_manager.speaker_updated.connect(self.on_speaker_updated)
        self.transcription_manager.error.connect(self.on_error)

        # Diarization
        self.diarization.speaker_updated.connect(self.on_diarization_speaker)
        self.diarization.error.connect(self.on_error)

    def initialize(self):
        """Initialize the application."""
        db = get_database()

        self.status_bar.showMessage("Loading ASR model...")
        if self.transcription_manager.initialize():
            self.status_bar.showMessage("Ready to record")
            self.header.status_label.setText("Ready")
        else:
            self.status_bar.showMessage("ASR model not loaded - check dependencies")
            self.header.status_label.setText("ASR Error")
            self.header.status_label.setStyleSheet(f"""
                color: {COLORS["danger"]};
                font-weight: 500;
                padding: 6px 12px;
                background-color: {COLORS["surface"]};
                border-radius: 16px;
            """)

        if self.diarization.initialize():
            logger.info("Speaker diarization initialized")

        self.refresh_sources()

    def refresh_sources(self):
        """Refresh the list of audio sources."""
        self.control_panel.source_combo.clear()

        try:
            sources = self.audio_capture.list_all_sources()

            for source in sources:
                display_text = f"{source.description}"
                self.control_panel.source_combo.addItem(display_text, source)

            self.status_bar.showMessage(f"Found {len(sources)} audio sources")

        except Exception as e:
            logger.error("Failed to list audio sources", error=str(e))
            self.status_bar.showMessage("Failed to list audio sources")

    def toggle_recording(self):
        """Toggle recording state."""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Start recording."""
        if self.control_panel.source_combo.count() == 0:
            QMessageBox.warning(self, "No Source", "Please select an audio source first.")
            self.control_panel.record_btn.setChecked(False)
            return

        source = self.control_panel.source_combo.currentData()
        if not source:
            QMessageBox.warning(self, "No Source", "Please select an audio source.")
            self.control_panel.record_btn.setChecked(False)
            return

        # Create new session
        db = get_database()
        self.current_session_id = db.create_session()

        # Start transcription
        self.transcription_manager.start()
        self.diarization.start()

        # Start audio capture
        if self.audio_capture.start_capture(source.name, source.source_type):
            self.is_recording = True
            self.control_panel.record_btn.setText("Stop Recording")
            self.header.status_label.setText("Recording")
            self.header.status_label.setStyleSheet(f"""
                color: {COLORS["danger"]};
                font-weight: 500;
                padding: 6px 12px;
                background-color: {COLORS["surface"]};
                border-radius: 16px;
            """)
            self.status_bar.showMessage(f"Recording from: {source.description}")
            self.control_panel.summarize_btn.setEnabled(False)
        else:
            self.control_panel.record_btn.setChecked(False)
            QMessageBox.critical(self, "Error", "Failed to start recording")

    def stop_recording(self):
        """Stop recording."""
        self.audio_capture.stop_capture()
        self.transcription_manager.stop()
        self.diarization.stop()

        self.is_recording = False
        self.control_panel.record_btn.setText("Start Recording")
        self.control_panel.record_btn.setChecked(False)
        self.header.status_label.setText("Ready")
        self.header.status_label.setStyleSheet(f"""
            color: {COLORS["success"]};
            font-weight: 500;
            padding: 6px 12px;
            background-color: {COLORS["surface"]};
            border-radius: 16px;
        """)
        self.status_bar.showMessage("Recording stopped")
        self.control_panel.summarize_btn.setEnabled(True)

    def on_audio_data(self, data: np.ndarray):
        """Handle incoming audio data."""
        self.transcription_manager.process_audio(data)
        self.diarization.add_audio(data)

    def on_transcription(self, result: TranscriptionResult):
        """Handle transcription result."""
        self.transcription_widget.add_message(
            result.message_id or "unknown", result.text, result.speaker, result.is_final
        )

        if result.is_final and result.message_id:
            import time

            start_time = time.time()
            end_time = start_time + len(result.text.split()) * 0.5

            self.diarization.track_message(result.message_id, start_time, end_time, result.text)

            if self.current_session_id:
                db = get_database()
                db.add_message(
                    self.current_session_id, result.text, result.speaker, result.message_id
                )

                if self.ai_generator.is_question(result.text):
                    # Track pending question
                    self._pending_questions[result.message_id] = result.text
                    # Enqueue to priority queue
                    self.priority_queue.enqueue_question(result.text, result.message_id)

    def on_speaker_updated(self, message_id: str, speaker: str):
        """Handle speaker update from transcription."""
        self.transcription_widget.update_speaker(message_id, speaker)

    def on_diarization_speaker(self, message_id: str, speaker: str):
        """Handle speaker update from diarization."""
        self.transcription_widget.update_speaker(message_id, speaker)

        db = get_database()
        db.update_message_speaker(message_id, speaker)

    def _on_ai_response_ready(self, message_id: str, response: str):
        """Handle AI response from priority queue."""
        self.suggestions_widget.add_suggestion(
            self._pending_questions.get(message_id, "Question"), response
        )
        if self.current_session_id:
            db = get_database()
            db.update_ai_response(message_id, response)

        # Remove from pending
        self._pending_questions.pop(message_id, None)

    def _on_queue_depth_changed(self, priority_count: int, normal_count: int):
        """Update queue depth display."""
        self.status_bar.showMessage(f"Queue: Priority={priority_count} | Normal={normal_count}")

    def _on_provider_changed(self, text: str):
        """Handle AI provider change."""
        new_provider = "openrouter" if text == "OpenRouter" else "local"
        if new_provider != self._current_provider:
            self._current_provider = new_provider
            self.ai_generator.set_provider(new_provider)
            # Save provider preference
            config = get_config()
            config.set("provider", new_provider)
            self.status_bar.showMessage(f"AI Provider: {text}", 3000)
            logger.info("Provider changed", provider=new_provider)

    def summarize_conversation(self):
        """Summarize the current conversation."""
        if not self.current_session_id:
            QMessageBox.information(self, "No Conversation", "No conversation to summarize.")
            return

        db = get_database()
        messages = db.get_session_messages(self.current_session_id)

        if not messages:
            QMessageBox.information(self, "Empty", "No messages to summarize.")
            return

        message_dicts = [{"speaker": m.speaker, "text": m.text} for m in messages]

        import threading

        def generate():
            try:
                summary = self.ai_generator.summarize_conversation_sync(message_dicts)
                if summary:
                    self.suggestions_widget.add_suggestion("Conversation Summary", summary)
            except Exception as e:
                logger.error("Failed to generate summary", error=str(e))

        thread = threading.Thread(target=generate)
        thread.start()

    def export_conversation(self):
        """Export the current conversation."""
        if not self.current_session_id:
            QMessageBox.information(self, "No Conversation", "No conversation to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Conversation",
            f"conversation_{self.current_session_id}.json",
            "JSON Files (*.json);;All Files (*.*)",
        )

        if file_path:
            import json

            db = get_database()
            data = db.export_session(self.current_session_id)

            if data:
                with open(file_path, "w") as f:
                    json.dump(data, f, indent=2)
                QMessageBox.information(self, "Exported", f"Conversation exported to {file_path}")

    def clear_conversation(self):
        """Clear the current conversation."""
        reply = QMessageBox.question(
            self,
            "Clear Conversation",
            "Are you sure you want to clear the current conversation?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.transcription_widget.clear_messages()
            self.suggestions_widget.clear_suggestions()
            self.current_session_id = None
            self.control_panel.summarize_btn.setEnabled(False)

    def show_settings(self):
        """Show settings dialog."""
        from .settings_dialog import SettingsDialog

        dialog = SettingsDialog(self)
        if dialog.exec():
            self.status_bar.showMessage("Settings saved")

    def on_error(self, error_msg: str):
        """Handle errors."""
        logger.error("Application error", error=error_msg)
        self.status_bar.showMessage(f"Error: {error_msg}")

    def closeEvent(self, event):
        """Handle window close event."""
        if self.is_recording:
            self.stop_recording()

        self.priority_queue.stop()

        db = get_database()
        db.close()

        event.accept()
