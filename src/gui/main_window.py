"""Modern UI for Audio Recorder with improved styling."""

import re
import uuid

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..ai.openrouter import AISuggestionGenerator, NotConfiguredError
from ..ai.priority_queue import get_priority_queue
from ..audio.capture import AudioCapture
from ..database.manager import get_database
from ..rag import EmbeddingWorker
from ..speech.asr import TranscriptionManager, TranscriptionResult
from ..speech.diarization import SpeakerDiarization
from ..utils.config import get_config
from ..utils.logger import get_logger

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


class DocumentDropZone(QFrame):
    """Drop zone for document upload with drag-and-drop support."""

    document_dropped = Signal(str)  # filepath

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(300, 150)
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {COLORS["border"]};
                border-radius: 8px;
                background-color: {COLORS["surface"]};
            }}
            QFrame:hover {{
                border-color: {COLORS["primary"]};
            }}
        """)

        # Layout for drop zone content
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel("📄 Drop TXT files here\nor click Upload")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: 14px;
            padding: 20px;
        """)
        layout.addWidget(self.label)

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(f"""
                QFrame {{
                    border: 2px dashed {COLORS["primary"]};
                    border-radius: 8px;
                    background-color: {COLORS["surface_light"]};
                }}
            """)

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {COLORS["border"]};
                border-radius: 8px;
                background-color: {COLORS["surface"]};
            }}
            QFrame:hover {{
                border-color: {COLORS["primary"]};
            }}
        """)

    def dropEvent(self, event):
        """Handle file drop event."""
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            if filepath.endswith(".txt"):
                self.document_dropped.emit(filepath)
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {COLORS["border"]};
                border-radius: 8px;
                background-color: {COLORS["surface"]};
            }}
            QFrame:hover {{
                border-color: {COLORS["primary"]};
            }}
        """)


class DocumentListWidget(QListWidget):
    """List widget for displaying uploaded documents."""

    delete_requested = Signal(str)  # document_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(4)
        self.setFrameShape(QFrame.NoFrame)
        self.document_items = {}  # document_id -> QListWidgetItem

    def add_document(self, doc_info: dict):
        """Add a document to the list.

        Args:
            doc_info: Dict with 'document_id' and 'source' keys
        """
        doc_id = doc_info.get("document_id", "unknown")
        source = doc_info.get("source", "unknown")

        # Check if already exists
        if doc_id in self.document_items:
            return

        item = QListWidgetItem(f"📄 {source}")
        item.setData(Qt.UserRole, doc_id)
        self.addItem(item)
        self.document_items[doc_id] = item

    def remove_document(self, document_id: str):
        """Remove a document from the list.

        Args:
            document_id: ID of document to remove
        """
        if document_id in self.document_items:
            item = self.document_items.pop(document_id)
            self.takeItem(self.row(item))


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
        self.messages: dict[str, tuple[str | None, str, bool]] = {}
        self.message_order: list[str] = []
        self.speaker_colors = {}
        self.color_index = 0

    def _render_message(
        self, message_id: str, speaker: str | None, text: str, is_final: bool
    ) -> str:
        """Generate HTML for a single message."""
        color = self.speaker_colors.get(speaker, COLORS["text_secondary"])
        speaker_label = f"{speaker}" if speaker else "Unknown"

        if is_final:
            return (
                f'<div style="margin: 8px 0; padding: 12px;'
                f" background-color: {COLORS['surface']};"
                f' border-radius: 8px; border-left: 4px solid {color};">'
                f'<div style="color: {color}; font-weight: 600;'
                f' font-size: 11px; margin-bottom: 4px;">'
                f"{speaker_label}</div>"
                f'<div style="color: {COLORS["text"]};'
                f' line-height: 1.5;">{text}</div></div>'
            )
        else:
            return (
                f'<div style="margin: 8px 0; padding: 12px;'
                f" background-color: {COLORS['surface']};"
                f' border-radius: 8px; opacity: 0.7;">'
                f'<div style="color: {COLORS["text_secondary"]};'
                f' font-style: italic;">{text}...</div></div>'
            )

    def _rebuild_html(self):
        """Regenerate all message HTML from stored state."""
        parts = []
        for mid in self.message_order:
            speaker, text, is_final = self.messages[mid]
            parts.append(self._render_message(mid, speaker, text, is_final))
        scrollbar = self.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 20
        self.setHtml("".join(parts))
        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())

    def add_message(
        self, message_id: str, text: str, speaker: str | None = None, is_final: bool = True
    ):
        if speaker and speaker not in self.speaker_colors:
            self.speaker_colors[speaker] = SPEAKER_COLORS[self.color_index % len(SPEAKER_COLORS)]
            self.color_index += 1

        is_update = message_id in self.messages
        self.messages[message_id] = (speaker, text, is_final)

        if is_update:
            self._rebuild_html()
        else:
            self.message_order.append(message_id)
            html = self._render_message(message_id, speaker, text, is_final)
            self.append(html)
            scrollbar = self.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def update_speaker(self, message_id: str, speaker: str):
        if message_id in self.messages:
            if speaker and speaker not in self.speaker_colors:
                self.speaker_colors[speaker] = SPEAKER_COLORS[
                    self.color_index % len(SPEAKER_COLORS)
                ]
                self.color_index += 1
            old_speaker, text, is_final = self.messages[message_id]
            self.messages[message_id] = (speaker, text, is_final)
            self._rebuild_html()

    def clear_messages(self):
        self.clear()
        self.messages = {}
        self.message_order = []
        self.speaker_colors = {}
        self.color_index = 0


class AISuggestionsWidget(QListWidget):
    """Modern AI suggestions widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(8)
        self.setFrameShape(QFrame.NoFrame)
        # Prevent horizontal scrollbar - word-wrap the content instead
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setResizeMode(QListWidget.Adjust)
        self.setWordWrap(True)
        # Disable built-in item hover/selection tint - the item widgets style themselves
        self.setSelectionMode(QListWidget.NoSelection)
        self.setStyleSheet(
            "QListWidget { background: transparent; border: none; padding: 0; }"
            "QListWidget::item { background: transparent; border: none; margin: 0; padding: 0; }"
            "QListWidget::item:hover { background: transparent; }"
            "QListWidget::item:selected { background: transparent; }"
        )

    def resizeEvent(self, event):
        """Recompute item heights when the list is resized so wrapped text fits."""
        super().resizeEvent(event)
        self._recompute_item_sizes()

    def _available_item_width(self) -> int:
        """Width available for an item widget inside the viewport."""
        return max(50, self.viewport().width() - 2 * self.spacing())

    def _recompute_item_sizes(self) -> None:
        """Ask each row's widget for its actual height at the current list width."""
        w = self._available_item_width()
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if widget is None:
                continue
            widget.setFixedWidth(w)
            widget.adjustSize()
            h = widget.sizeHint().height()
            item.setSizeHint(QSize(w, h))
            # Show scrollbar if needed
            if self.verticalScrollBar().maximum() > 0:
                self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

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

        self.addItem(item)
        self.setItemWidget(item, widget)
        # Size based on actual wrapped height at current list width
        w = self._available_item_width()
        widget.setFixedWidth(w)
        widget.adjustSize()
        item.setSizeHint(QSize(w, widget.sizeHint().height()))
        self.scrollToBottom()

    def add_summary(self, text: str) -> None:
        """Add a flat summary card (header band + body text).

        No nested scroll area and no hover outline: the enclosing QListWidget
        scrolls vertically if the summary is taller than the viewport.
        """
        item = QListWidgetItem()
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)

        # Outer card - single flat frame, no border, no hover
        widget = QFrame()
        widget.setObjectName("summaryCard")
        widget.setStyleSheet(
            f"#summaryCard {{"
            f"  background-color: {COLORS['surface']};"
            f"  border-radius: 8px;"
            f"  border: none;"
            f"}}"
        )
        outer_layout = QVBoxLayout(widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Header band (indigo)
        header = QFrame()
        header.setObjectName("summaryHeader")
        header.setFixedHeight(40)
        header.setStyleSheet(
            f"#summaryHeader {{"
            f"  background-color: {COLORS['primary']};"
            f"  border-top-left-radius: 8px;"
            f"  border-top-right-radius: 8px;"
            f"}}"
        )
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(14, 0, 8, 0)
        hlayout.setSpacing(8)

        hlabel = QLabel("Summary")
        hlabel.setStyleSheet(
            "color: white; font-weight: 700; font-size: 13px; background: transparent;"
        )
        hlabel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        hlayout.addWidget(hlabel, 1, Qt.AlignVCenter)

        xbtn = QPushButton("✕")
        xbtn.setFixedSize(24, 24)
        xbtn.setCursor(Qt.PointingHandCursor)
        xbtn.setToolTip("Close summary")
        xbtn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            "  color: white;"
            "  font-size: 12px;"
            "  font-weight: 700;"
            "  border: none;"
            "  border-radius: 4px;"
            "  padding: 0;"
            "}"
            "QPushButton:hover { background-color: rgba(255,255,255,0.18); }"
            "QPushButton:pressed { background-color: rgba(255,255,255,0.08); }"
        )
        xbtn.clicked.connect(lambda: self._remove_summary_item(item))
        hlayout.addWidget(xbtn, 0, Qt.AlignVCenter)

        # Body (plain surface, no inner scroll, no divider line)
        body = QFrame()
        body.setObjectName("summaryBody")
        body.setStyleSheet(
            f"#summaryBody {{"
            f"  background-color: {COLORS['surface']};"
            f"  border-bottom-left-radius: 8px;"
            f"  border-bottom-right-radius: 8px;"
            f"}}"
        )
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 14)
        body_layout.setSpacing(0)

        body_label = QLabel(text)
        body_label.setTextFormat(Qt.TextFormat.PlainText)
        body_label.setWordWrap(True)
        body_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        body_label.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 13px; background: transparent;"
        )
        body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body_layout.addWidget(body_label)

        outer_layout.addWidget(header)
        outer_layout.addWidget(body, 1)

        self.addItem(item)
        self.setItemWidget(item, widget)
        # Size based on wrapped height at current list width
        w = self._available_item_width()
        widget.setFixedWidth(w)
        widget.adjustSize()
        item.setSizeHint(QSize(w, widget.sizeHint().height()))
        self.scrollToBottom()

    def _remove_summary_item(self, item: QListWidgetItem) -> None:
        """Remove a summary item when its close button is clicked."""
        try:
            row = self.row(item)
            if row < 0:
                return
            taken = self.takeItem(row)
            if taken:
                w = self.itemWidget(taken)
                if w:
                    w.deleteLater()
                logger.debug("summary_card_removed", row=row)
        except Exception as e:
            logger.error("Failed to remove summary item", error=str(e))

    def clear_suggestions(self) -> None:
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

        # Screenshot button container
        screenshot_container = QWidget()
        screenshot_layout = QVBoxLayout(screenshot_container)
        screenshot_layout.setSpacing(4)
        screenshot_layout.setContentsMargins(0, 0, 0, 0)

        screenshot_label = QLabel("")  # Empty label to match height
        screenshot_label.setStyleSheet("font-size: 11px; min-height: 16px;")
        screenshot_layout.addWidget(screenshot_label)

        self.screenshot_btn = QPushButton("Enable Screenshots")
        self.screenshot_btn.setCheckable(True)
        self.screenshot_btn.setFixedHeight(36)
        screenshot_layout.addWidget(self.screenshot_btn)

        layout.addWidget(screenshot_container)

        layout.addStretch()


class MainWindow(QMainWindow):
    """Modern main application window."""

    # Signals for thread-safe communication from background threads to GUI
    summary_ready = Signal(str)  # summary text (empty string on no-summary)
    summary_failed = Signal(str)  # error message

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

        self.current_session_id: str | None = None
        self._pending_questions: dict = {}
        self._dispatched_segments: dict = {}
        self.is_recording = False

        self.setup_ui()
        self.setup_connections()

        # Connect summary signals to GUI-thread handlers (QueuedConnection by default across threads)
        self.summary_ready.connect(self._on_summary_ready)
        self.summary_failed.connect(self._on_summary_failed)

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
        self.control_panel.screenshot_btn.clicked.connect(self.on_screenshot_toggle)

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

    # Matches complete sentences (ending in . ! ?) inside interim transcriptions.
    _SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+")

    @staticmethod
    def _extract_complete_sentences(text: str) -> list[str]:
        """Return the list of complete sentences in ``text``."""
        return [m.group(0).strip() for m in MainWindow._SENTENCE_RE.finditer(text)]

    @staticmethod
    def _normalize_sentence(s: str) -> str:
        """Normalize a sentence for duplicate detection."""
        return re.sub(r"\W+", " ", s).strip().lower()

    def _maybe_dispatch_complete_questions(self, segment_id: str, text: str) -> None:
        """Scan ``text`` for completed question sentences and dispatch any new ones."""
        if not self.current_session_id:
            return
        dispatched = self._dispatched_segments.setdefault(segment_id, set())
        for sentence in self._extract_complete_sentences(text):
            if len(sentence) < 10:
                continue
            key = self._normalize_sentence(sentence)
            if key in dispatched:
                continue
            if not self.ai_generator.is_question(sentence):
                continue

            dispatched.add(key)
            question_id = str(uuid.uuid4())
            self._pending_questions[question_id] = sentence
            self.last_transcription = sentence

            logger.info(
                "dispatched_question_early",
                segment_id=segment_id[:8],
                question_id=question_id[:8],
                preview=sentence[:60],
            )
            self.priority_queue.enqueue_question(sentence, question_id)

    def on_transcription(self, result: TranscriptionResult):
        """Handle transcription result (interim OR final)."""
        self.transcription_widget.add_message(
            result.message_id or "unknown", result.text, result.speaker, result.is_final
        )

        if not result.message_id:
            return

        # Early dispatch: fire the LLM as soon as a complete question sentence
        # exists inside the interim text. Deduplicated per segment.
        self._maybe_dispatch_complete_questions(result.message_id, result.text)

        if result.is_final:
            import time

            start_time = time.time()
            end_time = start_time + len(result.text.split()) * 0.5
            self.diarization.track_message(result.message_id, start_time, end_time, result.text)

            if self.current_session_id:
                db = get_database()
                db.add_message(
                    self.current_session_id, result.text, result.speaker, result.message_id
                )

                # Safety net: if Qwen only puts a terminator on the final,
                # the early path would have missed this question.
                self._maybe_dispatch_complete_questions(result.message_id, result.text)

                # Backwards-compat: if no terminator anywhere, treat whole
                # utterance as a potential question (old behaviour).
                if not self._extract_complete_sentences(
                    result.text
                ) and self.ai_generator.is_question(result.text):
                    dispatched = self._dispatched_segments.setdefault(result.message_id, set())
                    key = self._normalize_sentence(result.text)
                    if key not in dispatched:
                        dispatched.add(key)
                        question_id = str(uuid.uuid4())
                        self._pending_questions[question_id] = result.text
                        self.last_transcription = result.text
                        self.priority_queue.enqueue_question(result.text, question_id)

            # Segment closed -- drop tracking so memory doesn't grow unbounded.
            self._dispatched_segments.pop(result.message_id, None)

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

    def summarize_conversation(self):
        """Summarize the current conversation."""
        logger.info("summarize_button_clicked", session_id=self.current_session_id)
        if not self.current_session_id:
            QMessageBox.information(self, "No Conversation", "No conversation to summarize.")
            return

        db = get_database()
        messages = db.get_session_messages(self.current_session_id)
        logger.info("summarize_messages_loaded", msg_count=len(messages))

        if not messages:
            QMessageBox.information(self, "Empty", "No messages to summarize.")
            return

        message_dicts = [{"speaker": m.speaker, "text": m.text} for m in messages]
        logger.info("summarize_starting", provider=self._current_provider)

        # Show loading state on the button
        btn = self.control_panel.summarize_btn
        btn.setEnabled(False)
        btn.setText("Generating...")
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['surface']}; "
            f"color: {COLORS['text_secondary']}; border: 1px solid {COLORS['border']}; "
            f"border-radius: 8px; padding: 10px 20px; font-weight: 500; }}"
        )

        # Cancel any previous timeout timer
        if hasattr(self, "_summary_timeout_timer") and self._summary_timeout_timer is not None:
            self._summary_timeout_timer.stop()

        SUMMARY_TIMEOUT_MS = 90_000

        def restore():
            if getattr(self, "_summary_timeout_timer", None):
                self._summary_timeout_timer.stop()
                self._summary_timeout_timer = None
            btn.setText("Summarize")
            btn.setStyleSheet("")
            btn.setEnabled(True)

        def on_summary_timeout():
            logger.warning("summarize_conversation timed out after 90 s")
            QMessageBox.warning(
                self,
                "Summary Timeout",
                "The AI did not respond in time. Check your connection and API key.",
            )
            restore()

        self._summary_timeout_timer = QTimer()
        self._summary_timeout_timer.setSingleShot(True)
        self._summary_timeout_timer.timeout.connect(on_summary_timeout)
        self._summary_timeout_timer.start(SUMMARY_TIMEOUT_MS)

        # Store restore callback for signal handlers to access
        self._summary_restore = restore

        def generate():
            logger.info("generate_thread_started")
            try:
                logger.info("generate_thread_calling_sync")
                summary = self.ai_generator.summarize_conversation_sync(message_dicts)
                logger.info(
                    "generate_thread_got_summary", summary_len=len(summary) if summary else 0
                )
                # Emit Qt signal - QueuedConnection dispatches to GUI thread's event loop
                logger.info("generate_thread_emitting_signal")
                self.summary_ready.emit(summary or "")
                logger.info("generate_thread_signal_emitted")
            except NotConfiguredError as e:
                logger.error("summarize_conversation: not configured", error=str(e))
                self.summary_failed.emit(
                    "OpenRouter API key is not configured. Go to Settings > AI Provider tab."
                )
            except Exception as e:
                logger.error("Failed to generate summary", error=str(e))
                self.summary_failed.emit(str(e))

        import threading

        thread = threading.Thread(target=generate, daemon=True)
        thread.start()

    def _on_summary_ready(self, summary: str):
        """Handle summary ready signal (runs on GUI thread)."""
        logger.info("_on_summary_ready_called", has_summary=bool(summary), length=len(summary))
        # Stop the timeout timer
        if getattr(self, "_summary_timeout_timer", None):
            self._summary_timeout_timer.stop()
            self._summary_timeout_timer = None
        # Update UI
        if summary:
            self.suggestions_widget.add_summary(summary)
        # Restore button state
        if getattr(self, "_summary_restore", None):
            self._summary_restore()
            self._summary_restore = None

    def _on_summary_failed(self, error_msg: str):
        """Handle summary failed signal (runs on GUI thread)."""
        logger.info("_on_summary_failed_called", error=error_msg)
        # Stop the timeout timer
        if getattr(self, "_summary_timeout_timer", None):
            self._summary_timeout_timer.stop()
            self._summary_timeout_timer = None
        QMessageBox.warning(self, "Summary Failed", f"Failed to generate summary:\n{error_msg}")
        # Restore button state
        if getattr(self, "_summary_restore", None):
            self._summary_restore()
            self._summary_restore = None

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

    def on_upload_document(self):
        """Open file dialog to upload a document."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "", "Text files (*.txt)"
        )

        if file_path:
            self.on_document_dropped(file_path)

    def on_document_dropped(self, filepath: str):
        """Handle document drop or selection.

        Args:
            filepath: Path to the dropped/selected file
        """
        from pathlib import Path

        filepath_path = Path(filepath)
        if not filepath_path.exists():
            self.status_bar.showMessage(f"File not found: {filepath}", 3000)
            return

        if not filepath.endswith(".txt"):
            self.status_bar.showMessage("Only .txt files are supported", 3000)
            return

        # Generate document ID
        import time

        self._current_document_id = f"doc_{int(time.time() * 1000)}"

        # Chunk the document
        self.status_bar.showMessage(f"Indexing {filepath_path.name}...")
        self.rag_progress.setText(f"Parsing {filepath_path.name}...")

        try:
            chunks = self.chunker.chunk_file(filepath_path)
            if not chunks:
                self.status_bar.showMessage("Failed to parse document", 3000)
                return

            # Store chunks for embedding
            self._current_chunks = [
                {"text": chunk.text, "metadata": chunk.metadata} for chunk in chunks
            ]
            self._current_source = filepath_path.name

            # Start embedding worker
            chunk_texts = [chunk.text for chunk in chunks]
            self.rag_progress.setText(f"Computing embeddings for {len(chunks)} chunks...")

            self._embedding_worker = EmbeddingWorker(chunk_texts)
            self._embedding_worker.progress.connect(self.on_embedding_progress)
            self._embedding_worker.complete.connect(self.on_embedding_complete)
            self._embedding_worker.error.connect(self.on_embedding_error)
            self._embedding_worker.start()

        except Exception as e:
            logger.error("Failed to process document", filepath=filepath, error=str(e))
            self.status_bar.showMessage(f"Error: {str(e)}", 3000)

    def on_embedding_progress(self, current: int, total: int):
        """Handle embedding progress update."""
        self.rag_progress.setText(f"Indexing: {current}/{total} batches...")

    def on_embedding_complete(self, embeddings: list):
        """Handle embedding completion.

        Args:
            embeddings: List of embedding vectors
        """
        try:
            # Add to ChromaDB
            self.rag_manager.add_document(
                self._current_document_id, self._current_chunks, embeddings
            )

            # Add to UI list
            self.doc_list_widget.add_document(
                {"document_id": self._current_document_id, "source": self._current_source}
            )

            self.rag_progress.setText(f"✓ Indexed: {self._current_source}")
            self.status_bar.showMessage(f"Document indexed: {self._current_source}", 3000)

        except Exception as e:
            logger.error("Failed to index document", error=str(e))
            self.status_bar.showMessage(f"Indexing failed: {str(e)}", 3000)

    def on_embedding_error(self, error: str):
        """Handle embedding error."""
        logger.error("Embedding failed", error=error)
        self.status_bar.showMessage(f"Embedding failed: {error}", 3000)
        self.rag_progress.setText("")

    def on_indexing_progress(self, current: int, total: int):
        """Handle document indexing progress."""
        self.rag_progress.setText(f"Indexing: {current}/{total} chunks...")

    def on_indexing_complete(self, document_id: str):
        """Handle document indexing completion."""
        self.rag_progress.setText("Indexing complete")
        logger.info("Document indexed successfully", document_id=document_id)
        # Enable search button since documents now exist
        self.btn_rag_search.setEnabled(True)

    def on_document_delete(self, document_id: str):
        """Handle document deletion request.

        Args:
            document_id: ID of document to delete
        """
        try:
            # Delete from ChromaDB
            self.rag_manager.delete_document(document_id)

            # Remove from UI
            self.doc_list_widget.remove_document(document_id)

            # Check if any documents remain
            docs = self.rag_manager.list_documents()
            self.btn_rag_search.setEnabled(len(docs) > 0)

            self.status_bar.showMessage("Document removed", 3000)

        except Exception as e:
            logger.error("Failed to delete document", document_id=document_id, error=str(e))
            self.status_bar.showMessage(f"Delete failed: {str(e)}", 3000)

    def on_rag_search_clicked(self):
        """Handle manual RAG search button click."""
        # Get the last transcribed text as question
        question = ""
        if hasattr(self, "last_transcription"):
            question = self.last_transcription

        if not question:
            self.status_bar.showMessage("No question to search", 3000)
            return

        # Check if documents exist
        docs = self.rag_manager.list_documents()
        if not docs:
            self.status_bar.showMessage("Upload documents first", 3000)
            return

        # Disable button during search
        self.btn_rag_search.setEnabled(False)
        self.status_bar.showMessage("Searching knowledge base...")

        # Run async search
        import asyncio

        asyncio.create_task(self._run_rag_search(question))

    async def _run_rag_search(self, question: str):
        """Run RAG search asynchronously.

        Args:
            question: Question to search for
        """
        try:
            result = await self.rag_search.answer_with_context(question, top_k=3)

            if result["has_context"] and result["answer"]:
                # Display answer with citations
                citations = " ".join(result["citations"])
                display_text = f"{result['answer']}\n\n{citations}"
                self.display_ai_response(display_text)
                self.status_bar.showMessage("Search complete", 3000)
            else:
                self.status_bar.showMessage("No relevant documents found", 3000)
        except Exception as e:
            logger.error("RAG search failed", error=str(e))
            self.status_bar.showMessage(f"Search failed: {str(e)}", 3000)
        finally:
            self.btn_rag_search.setEnabled(True)

    def get_current_question_text(self) -> str:
        """Get text from current transcription or selection to use as question."""
        if hasattr(self, "last_transcription"):
            text = self.last_transcription
            if self.ai_generator.is_question(text):
                return text
        return ""

    def display_ai_response(self, text: str):
        """Display AI response in suggestions widget with citation formatting.

        Args:
            text: Response text which may include citation badges (📄 DocumentName.txt)
        """
        # Split answer and citations if newline separation exists
        parts = text.split("\n\n")
        if len(parts) > 1:
            answer = parts[0]
            citations = parts[1]
            display_text = (
                f"{answer}\n\n<span style='color: #94a3b8; font-size: 12px;'>{citations}</span>"
            )
        else:
            display_text = text

        self.suggestions_widget.add_suggestion("Knowledge Base", display_text)

    def on_error(self, error_msg: str):
        """Handle errors."""
        logger.error("Application error", error=error_msg)
        self.status_bar.showMessage(f"Error: {error_msg}")

    def on_screenshot_toggle(self, checked: bool):
        """Handle screenshot mode toggle.

        Args:
            checked: True if screenshot mode is being enabled
        """
        config = get_config()

        if checked:
            # Start screenshot capture
            interval = config.get("screenshot.interval", 30)
            if self.screenshot_capture.start(interval):
                config.set("screenshot.enabled", True)
                self.control_panel.screenshot_btn.setText("Disable Screenshots")
                self.status_bar.showMessage("Screenshot mode enabled")
                logger.info("Screenshot mode enabled", interval=interval)
            else:
                # Failed to start, uncheck the button
                self.control_panel.screenshot_btn.setChecked(False)
                self.status_bar.showMessage("Failed to enable screenshot mode")
        else:
            # Stop screenshot capture
            self.screenshot_capture.stop()
            config.set("screenshot.enabled", False)
            self.control_panel.screenshot_btn.setText("Enable Screenshots")
            self.status_bar.showMessage("Screenshot mode disabled")
            logger.info("Screenshot mode disabled")

    def _on_screenshot_ready(self, image):
        """Handle captured screenshot.

        Args:
            image: PIL Image from ScreenshotCapture
        """
        # Store screenshot using storage (handles circular buffer eviction)
        saved_path = self.screenshot_storage.add(image)
        if saved_path:
            logger.debug("Screenshot stored", path=saved_path)
            # Analyze for actionable tasks
            self.screenshot_analyzer.process_screenshot(saved_path)

    def _on_screenshot_tasks_found(self, tasks: list):
        """Display screenshot tasks in side panel.

        Args:
            tasks: List of {task, solution, priority} dicts from analyzer
        """
        for task_info in tasks:
            task = task_info.get("task", "")
            solution = task_info.get("solution", "")
            priority = task_info.get("priority", "medium")

            # Format with priority indicator
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            display_text = f"{priority_emoji} Screenshot Task\n\n{task}\n\n📋 Solution:\n{solution}"

            # Truncate task for title if too long
            title = f"Screenshot: {task[:50]}..." if len(task) > 50 else f"Screenshot: {task}"

            self.suggestions_widget.add_suggestion(title, display_text)

        if tasks:
            logger.info("Screenshot tasks displayed", count=len(tasks))

    def closeEvent(self, event):
        """Handle window close event."""
        if self.is_recording:
            self.stop_recording()

        self.priority_queue.stop()
        self.ai_generator._stop_worker()

        db = get_database()
        db.close()

        event.accept()
