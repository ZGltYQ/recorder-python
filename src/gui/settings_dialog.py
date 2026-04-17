"""Settings dialog with modern styling."""

import os
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..ai.openrouter import ModelInfo, OpenRouterClient
from ..utils.config import get_config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# RAG imports - these are optional dependencies
try:
    from ..rag import RAGManager

    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    RAGManager = None


class ModelFetchThread(QThread):
    """Background thread for fetching models."""

    models_fetched = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            client = OpenRouterClient(api_key=self.api_key)
            models = client.get_available_models_sync(force_refresh=True)
            self.models_fetched.emit(models)
        except Exception as e:
            self.error_occurred.emit(str(e))


class SettingsDialog(QDialog):
    """Modern settings dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(550)
        self._available_models = []
        self._fetch_thread = None
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        """Setup the UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QFrame()
        header.setStyleSheet("background-color: #1e293b;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 24, 16)

        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #f8fafc; background: transparent;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        main_layout.addWidget(header)

        # Content area with scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0f172a;
                border: none;
            }
            QScrollBar:vertical {
                background: #1e293b;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 4px;
                min-height: 40px;
            }
            QScrollBar::handle:vertical:hover {
                background: #64748b;
            }
        """)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(24, 20, 24, 20)

        # OpenRouter settings
        openrouter_group = self._create_openrouter_group()
        content_layout.addWidget(openrouter_group)

        # Local LLM settings
        local_llm_group = self._create_local_llm_group()
        content_layout.addWidget(local_llm_group)

        # STT language
        stt_group = self._create_stt_group()
        content_layout.addWidget(stt_group)

        # Unified ASR Model settings (backend selector + active backend's sub-settings)
        asr_group = self._create_asr_model_group()
        content_layout.addWidget(asr_group)

        # Diarization settings
        diarization_group = self._create_diarization_group()
        content_layout.addWidget(diarization_group)

        # Knowledge Base / RAG settings
        rag_group = self._create_rag_group()
        content_layout.addWidget(rag_group)

        content_layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, 1)

        # Footer with buttons
        footer = QFrame()
        footer.setStyleSheet("background-color: #1e293b;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)

        footer_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.save_settings)
        footer_layout.addWidget(save_btn)

        main_layout.addWidget(footer)

        self._apply_styles()

    def _create_openrouter_group(self) -> QGroupBox:
        """Create OpenRouter settings group."""
        group = QGroupBox()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Header with icon and title
        header_layout = QHBoxLayout()
        header_title = QLabel("OpenRouter API")
        header_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #f8fafc;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # API Key row
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setMinimumWidth(100)
        api_key_label.setMinimumHeight(24)
        api_key_layout.addWidget(api_key_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-or-...")
        self.api_key_input.textChanged.connect(self._on_api_key_changed)
        api_key_layout.addWidget(self.api_key_input, 1)

        # Show/hide toggle
        self.toggle_key_btn = QPushButton("Show")
        self.toggle_key_btn.setFixedWidth(50)
        self.toggle_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_key_btn.setStyleSheet("""
            QPushButton {
                background-color: #475569;
                color: #f8fafc;
                border: 1px solid #6366f1;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #6366f1;
            }
        """)
        self.toggle_key_btn.clicked.connect(self._toggle_api_key_visibility)
        api_key_layout.addWidget(self.toggle_key_btn)

        layout.addLayout(api_key_layout)

        # Model selection with search
        model_label = QLabel("Model:")
        layout.addWidget(model_label)

        # Search input
        self.model_search = QLineEdit()
        self.model_search.setPlaceholderText("Search models...")
        self.model_search.textChanged.connect(self._filter_models)
        layout.addWidget(self.model_search)

        # Provider filter
        provider_layout = QHBoxLayout()
        provider_label = QLabel("Provider:")
        provider_label.setMinimumWidth(100)
        provider_label.setMinimumHeight(24)
        provider_layout.addWidget(provider_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("All Providers", "")
        self.provider_combo.currentIndexChanged.connect(self._filter_models)
        provider_layout.addWidget(self.provider_combo, 1)

        # Refresh button
        self.refresh_models_btn = QPushButton("Refresh")
        self.refresh_models_btn.setFixedWidth(70)
        self.refresh_models_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_models_btn.setToolTip("Refresh model list")
        self.refresh_models_btn.setStyleSheet("""
            QPushButton {
                background-color: #475569;
                color: #f8fafc;
                border: 1px solid #6366f1;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #6366f1;
            }
        """)
        self.refresh_models_btn.clicked.connect(self._refresh_models)
        provider_layout.addWidget(self.refresh_models_btn)

        layout.addLayout(provider_layout)

        # Model list
        self.model_list = QListWidget()
        self.model_list.setMaximumHeight(150)
        self.model_list.setAlternatingRowColors(True)
        self.model_list.itemDoubleClicked.connect(self._on_model_selected)
        layout.addWidget(self.model_list)

        # Loading indicator
        self.models_loading = QProgressBar()
        self.models_loading.setRange(0, 0)
        self.models_loading.setFixedHeight(4)
        self.models_loading.setTextVisible(False)
        self.models_loading.setVisible(False)
        layout.addWidget(self.models_loading)

        # Selected model display
        selected_layout = QHBoxLayout()
        selected_label = QLabel("Selected:")
        selected_label.setStyleSheet("color: #94a3b8;")
        selected_layout.addWidget(selected_label)

        self.selected_model_label = QLabel("Not selected")
        self.selected_model_label.setStyleSheet("color: #6366f1; font-weight: 600;")
        selected_layout.addWidget(self.selected_model_label, 1)

        layout.addLayout(selected_layout)

        group.setLayout(layout)
        return group

    def _create_local_llm_group(self) -> QGroupBox:
        """Create Local LLM settings group."""
        group = QGroupBox()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Header with icon and title
        header_layout = QHBoxLayout()
        header_title = QLabel("Local LLM")
        header_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #f8fafc;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Enable Local LLM
        enable_layout = QHBoxLayout()
        self.local_llm_enable_cb = QCheckBox("Enable Local LLM")
        enable_layout.addWidget(self.local_llm_enable_cb)
        enable_layout.addStretch()
        layout.addLayout(enable_layout)

        # Base URL
        url_layout = QHBoxLayout()
        url_label = QLabel("Base URL:")
        url_label.setMinimumWidth(100)
        url_label.setMinimumHeight(24)
        url_layout.addWidget(url_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.local_llm_url_input = QLineEdit()
        self.local_llm_url_input.setPlaceholderText("http://localhost:8000/v1")
        url_layout.addWidget(self.local_llm_url_input, 1)
        layout.addLayout(url_layout)

        # Model Name
        model_layout = QHBoxLayout()
        model_label = QLabel("Model Name:")
        model_label.setMinimumWidth(100)
        model_label.setMinimumHeight(24)
        model_layout.addWidget(model_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.local_llm_model_input = QLineEdit()
        self.local_llm_model_input.setPlaceholderText("local-model")
        model_layout.addWidget(self.local_llm_model_input, 1)
        layout.addLayout(model_layout)

        # API Key (optional)
        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        key_label.setMinimumWidth(100)
        key_label.setMinimumHeight(24)
        key_layout.addWidget(key_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.local_llm_key_input = QLineEdit()
        self.local_llm_key_input.setPlaceholderText("Optional for local LLMs")
        self.local_llm_key_input.setEchoMode(QLineEdit.Password)
        key_layout.addWidget(self.local_llm_key_input, 1)
        layout.addLayout(key_layout)

        # Timeout
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("Timeout:")
        timeout_label.setMinimumWidth(100)
        timeout_label.setMinimumHeight(24)
        timeout_layout.addWidget(timeout_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.local_llm_timeout_spin = QSpinBox()
        self.local_llm_timeout_spin.setMinimum(300)
        self.local_llm_timeout_spin.setMaximum(3600)
        self.local_llm_timeout_spin.setSuffix(" sec")
        self.local_llm_timeout_spin.setValue(300)
        timeout_layout.addWidget(self.local_llm_timeout_spin)
        timeout_layout.addStretch()
        layout.addLayout(timeout_layout)

        group.setLayout(layout)
        return group

    def _create_stt_group(self) -> QGroupBox:
        """Create STT language group (backend + model live in ASR Model group)."""
        group = QGroupBox()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_title = QLabel("Speech Recognition")
        header_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #f8fafc;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        lang_layout = QHBoxLayout()
        lang_label = QLabel("Language:")
        lang_label.setMinimumWidth(100)
        lang_label.setMinimumHeight(24)
        lang_layout.addWidget(lang_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(
            [
                "auto (detect)",
                "en (English)",
                "ru (Russian)",
                "uk (Ukrainian)",
                "es (Spanish)",
                "fr (French)",
                "de (German)",
                "zh (Chinese)",
            ]
        )
        lang_layout.addWidget(self.lang_combo, 1)
        layout.addLayout(lang_layout)

        group.setLayout(layout)
        return group

    def _create_asr_model_group(self) -> QGroupBox:
        """Unified ASR Model group.

        Qwen3-ASR and faster-whisper are both STT backends, so they live as
        sub-sections inside a single group. The Backend selector at the top
        chooses which one is active; only the active backend's sub-controls
        are visible (the inactive set hides to keep the dialog uncluttered).
        """
        group = QGroupBox()
        root = QVBoxLayout()
        root.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        header_title = QLabel("ASR Model")
        header_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #f8fafc;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        root.addLayout(header_layout)

        # ---- Backend selector (top of card) ----
        backend_layout = QHBoxLayout()
        backend_label = QLabel("Backend:")
        backend_label.setMinimumWidth(100)
        backend_label.setMinimumHeight(24)
        backend_layout.addWidget(backend_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Qwen3-ASR (bundled)", "qwen3")
        self.backend_combo.addItem("faster-whisper (CTranslate2)", "faster-whisper")
        self.backend_combo.setToolTip(
            "qwen3:            multilingual Qwen3-ASR model (default, GPU recommended)\n"
            "faster-whisper:   Whisper + CTranslate2, 4-8x faster on GPU, CPU-capable\n"
            "Requires restart to take effect."
        )
        backend_layout.addWidget(self.backend_combo, 1)
        root.addLayout(backend_layout)

        # Thin separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid #334155; margin: 4px 0;")
        root.addWidget(sep)

        # ---- Qwen3 subsection (widget container so we can hide/show) ----
        self.qwen_panel = QWidget()
        qwen_l = QVBoxLayout(self.qwen_panel)
        qwen_l.setContentsMargins(0, 0, 0, 0)
        qwen_l.setSpacing(8)

        qwen_sub_title = QLabel("Qwen3-ASR")
        qwen_sub_title.setStyleSheet("font-weight: 600; color: #e2e8f0; font-size: 12px;")
        qwen_l.addWidget(qwen_sub_title)

        qwen_size_layout = QHBoxLayout()
        qwen_size_label = QLabel("Model Size:")
        qwen_size_label.setMinimumWidth(100)
        qwen_size_label.setMinimumHeight(24)
        qwen_size_layout.addWidget(qwen_size_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.qwen_size_combo = QComboBox()
        self.qwen_size_combo.addItem("0.6B (~1.2 GB) - Faster", "0.6B")
        self.qwen_size_combo.addItem("1.7B (~3.4 GB) - More Accurate", "1.7B")
        self.qwen_size_combo.setToolTip(
            "Select Qwen3-ASR model size:\n"
            "• 0.6B: Smaller, faster, good for real-time transcription\n"
            "• 1.7B: Larger, more accurate, requires more VRAM"
        )
        qwen_size_layout.addWidget(self.qwen_size_combo, 1)
        qwen_l.addLayout(qwen_size_layout)

        self.qwen_autodownload_check = QCheckBox("Auto-download model if not present")
        self.qwen_autodownload_check.setToolTip(
            "Automatically download the selected model on first use"
        )
        qwen_l.addWidget(self.qwen_autodownload_check)

        download_label = QLabel("Download Models:")
        download_label.setStyleSheet("font-weight: 600; color: #94a3b8;")
        qwen_l.addWidget(download_label)

        download_layout = QHBoxLayout()
        download_layout.setSpacing(8)
        self.download_0_6b_btn = QPushButton("0.6B")
        self.download_0_6b_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_0_6b_btn.setToolTip("Download the 0.6B model (~1.2 GB)")
        self.download_0_6b_btn.clicked.connect(lambda: self._download_qwen_model("0.6B"))
        download_layout.addWidget(self.download_0_6b_btn)
        self.download_1_7b_btn = QPushButton("1.7B")
        self.download_1_7b_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_1_7b_btn.setToolTip("Download the 1.7B model (~3.4 GB)")
        self.download_1_7b_btn.clicked.connect(lambda: self._download_qwen_model("1.7B"))
        download_layout.addWidget(self.download_1_7b_btn)
        download_all_btn = QPushButton("All")
        download_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        download_all_btn.setToolTip("Download both model sizes")
        download_all_btn.clicked.connect(lambda: self._download_qwen_model("all"))
        download_layout.addWidget(download_all_btn)
        download_layout.addStretch()
        qwen_l.addLayout(download_layout)

        root.addWidget(self.qwen_panel)

        # ---- faster-whisper subsection ----
        self.fw_panel = QWidget()
        fw_l = QVBoxLayout(self.fw_panel)
        fw_l.setContentsMargins(0, 0, 0, 0)
        fw_l.setSpacing(8)

        fw_sub_title = QLabel("faster-whisper")
        fw_sub_title.setStyleSheet("font-weight: 600; color: #e2e8f0; font-size: 12px;")
        fw_l.addWidget(fw_sub_title)

        fw_size_layout = QHBoxLayout()
        fw_size_label = QLabel("Model Size:")
        fw_size_label.setMinimumWidth(100)
        fw_size_label.setMinimumHeight(24)
        fw_size_layout.addWidget(fw_size_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.fw_size_combo = QComboBox()
        for size, label in [
            ("tiny", "tiny (~75 MB)"),
            ("base", "base (~145 MB)"),
            ("small", "small (~465 MB)"),
            ("medium", "medium (~1.5 GB)"),
            ("large-v3", "large-v3 (~2.9 GB) - accurate"),
            ("large-v3-turbo", "large-v3-turbo (~1.5 GB) - fast+accurate"),
        ]:
            self.fw_size_combo.addItem(label, size)
        self.fw_size_combo.setToolTip(
            "large-v3-turbo is a good default: ~4x faster than large-v3 with "
            "similar quality. Smaller sizes trade accuracy for CPU-friendliness."
        )
        fw_size_layout.addWidget(self.fw_size_combo, 1)
        fw_l.addLayout(fw_size_layout)

        fw_ct_layout = QHBoxLayout()
        fw_ct_label = QLabel("Compute:")
        fw_ct_label.setMinimumWidth(100)
        fw_ct_label.setMinimumHeight(24)
        fw_ct_layout.addWidget(fw_ct_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.fw_compute_combo = QComboBox()
        for ct, label in [
            ("auto", "auto (recommended)"),
            ("int8", "int8 (CPU fast)"),
            ("int8_float16", "int8_float16 (CUDA fast)"),
            ("float16", "float16 (CUDA)"),
            ("float32", "float32 (slowest, most accurate)"),
        ]:
            self.fw_compute_combo.addItem(label, ct)
        self.fw_compute_combo.setToolTip("`auto` picks int8_float16 on CUDA, int8 on CPU.")
        fw_ct_layout.addWidget(self.fw_compute_combo, 1)
        fw_l.addLayout(fw_ct_layout)

        self.fw_vad_check = QCheckBox("Use built-in Silero VAD filter")
        self.fw_vad_check.setToolTip(
            "Pre-filter audio to drop silence/music before transcription. "
            "Recommended on; turn off if you're losing short utterances."
        )
        fw_l.addWidget(self.fw_vad_check)

        root.addWidget(self.fw_panel)

        # Toggle visibility when backend changes.
        self.backend_combo.currentIndexChanged.connect(self._update_backend_panels)

        group.setLayout(root)
        return group

    def _update_backend_panels(self) -> None:
        """Show only the active backend's sub-panel."""
        backend = self.backend_combo.currentData() or "qwen3"
        self.qwen_panel.setVisible(backend == "qwen3")
        self.fw_panel.setVisible(backend == "faster-whisper")

    def _create_diarization_group(self) -> QGroupBox:
        """Create diarization settings group."""
        group = QGroupBox()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Header with icon and title
        header_layout = QHBoxLayout()
        header_title = QLabel("Speaker Diarization")
        header_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #f8fafc;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.diarization_check = QCheckBox("Enable speaker diarization")
        layout.addWidget(self.diarization_check)

        group.setLayout(layout)
        return group

    def _create_rag_group(self) -> QGroupBox:
        """Create Knowledge Base / RAG settings group."""
        group = QGroupBox()
        layout = QVBoxLayout()
        layout.setSpacing(16)

        # Header with icon and title
        header_layout = QHBoxLayout()
        header_title = QLabel("Knowledge Base (RAG)")
        header_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #f8fafc;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Info label
        info_label = QLabel("Upload documents to enable AI-powered knowledge base search.")
        info_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(info_label)

        # Upload button
        self.btn_upload_doc_settings = QPushButton("Upload Document")
        self.btn_upload_doc_settings.setFixedHeight(36)
        self.btn_upload_doc_settings.clicked.connect(self.on_upload_document_settings)
        layout.addWidget(self.btn_upload_doc_settings)

        # Document list
        doc_list_label = QLabel("Uploaded Documents:")
        doc_list_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(doc_list_label)

        self.doc_list_settings = QListWidget()
        self.doc_list_settings.setMinimumHeight(120)
        layout.addWidget(self.doc_list_settings)

        # Delete document button
        self.btn_delete_doc_settings = QPushButton("Delete Selected")
        self.btn_delete_doc_settings.setFixedHeight(32)
        self.btn_delete_doc_settings.setEnabled(False)
        self.btn_delete_doc_settings.clicked.connect(self.on_delete_document_settings)
        self.doc_list_settings.itemSelectionChanged.connect(
            lambda: self.btn_delete_doc_settings.setEnabled(
                len(self.doc_list_settings.selectedItems()) > 0
            )
        )
        layout.addWidget(self.btn_delete_doc_settings)

        # Search button
        self.btn_rag_search_settings = QPushButton("Search Knowledge Base")
        self.btn_rag_search_settings.setFixedHeight(36)
        self.btn_rag_search_settings.setEnabled(False)
        self.btn_rag_search_settings.clicked.connect(self.on_rag_search_settings)
        layout.addWidget(self.btn_rag_search_settings)

        # Progress indicator
        self.rag_progress_settings = QLabel("")
        self.rag_progress_settings.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self.rag_progress_settings)

        group.setLayout(layout)
        return group

    def _init_rag_manager(self):
        """Initialize RAG manager for settings dialog."""
        if not RAG_AVAILABLE:
            return None
        try:
            if not hasattr(self, "_rag_manager") or self._rag_manager is None:
                self._rag_manager = RAGManager()
            return self._rag_manager
        except Exception as e:
            logger.warning(f"RAG manager not available: {e}")
            return None

    def on_upload_document_settings(self):
        """Handle document upload from settings dialog."""
        if not RAG_AVAILABLE:
            QMessageBox.warning(
                self,
                "RAG Not Available",
                "The knowledge base feature requires chromadb.\n"
                "Please install it with: pip install chromadb",
            )
            return

        rag = self._init_rag_manager()
        if rag is None:
            QMessageBox.warning(
                self, "RAG Error", "Failed to initialize knowledge base. Please check the logs."
            )
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Documents", "", "Text Files (*.txt);;All Files (*)"
        )

        if not file_paths:
            return

        self.rag_progress_settings.setText("Indexing documents...")
        self.btn_upload_doc_settings.setEnabled(False)

        try:
            for filepath in file_paths:
                filename = os.path.basename(filepath)
                self._index_document_async(rag, filepath, filename)
        except Exception as e:
            self.rag_progress_settings.setText("")
            self.btn_upload_doc_settings.setEnabled(True)
            QMessageBox.critical(self, "Upload Error", str(e))

    def _index_document_async(self, rag, filepath: str, filename: str):
        """Index a document asynchronously."""
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()

            doc_id = rag.add_document(content, source=filename)
            self._refresh_document_list()

            self.rag_progress_settings.setText(f"Indexed: {filename}")
            self.btn_rag_search_settings.setEnabled(True)
        except Exception as e:
            self.rag_progress_settings.setText(f"Error: {e}")
        finally:
            self.btn_upload_doc_settings.setEnabled(True)

    def _refresh_document_list(self):
        """Refresh the document list in settings."""
        self.doc_list_settings.clear()
        rag = self._init_rag_manager()
        if rag is None:
            return

        try:
            docs = rag.list_documents()
            for doc in docs:
                item = QListWidgetItem(doc.get("title", "Untitled"))
                item.setData(Qt.ItemDataRole.UserRole, doc.get("id"))
                self.doc_list_settings.addItem(item)
        except Exception as e:
            logger.warning(f"Failed to refresh document list: {e}")

    def on_delete_document_settings(self):
        """Handle document deletion from settings dialog."""
        selected = self.doc_list_settings.selectedItems()
        if not selected:
            return

        rag = self._init_rag_manager()
        if rag is None:
            return

        reply = QMessageBox.question(
            self,
            "Delete Document",
            f"Delete {len(selected)} document(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        for item in selected:
            doc_id = item.data(Qt.ItemDataRole.UserRole)
            if doc_id:
                try:
                    rag.delete_document(doc_id)
                except Exception as e:
                    logger.warning(f"Failed to delete document {doc_id}: {e}")

        self._refresh_document_list()

        # Check if any documents remain
        rag = self._init_rag_manager()
        if rag:
            docs = rag.list_documents()
            self.btn_rag_search_settings.setEnabled(len(docs) > 0)

    def on_rag_search_settings(self):
        """Handle knowledge base search from settings dialog."""
        text, ok = (
            QFileDialog.getSaveFileName(
                self, "Search Results", "", "Text Files (*.txt);;All Files (*)"
            )
            if False
            else (None, False)
        )  # Just show a simple input for now

        # For now, just show a message
        QMessageBox.information(
            self,
            "Knowledge Base",
            "Use the AI Suggestions panel to ask questions.\n"
            "The AI will search your knowledge base for relevant context.",
        )

    def _apply_styles(self):
        """Apply modern dark theme styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            
            QGroupBox {
                background-color: transparent;
                border: 1px solid #334155;
                border-radius: 12px;
                margin-top: 8px;
                padding: 12px 16px 16px 16px;
                font-weight: 600;
                font-size: 14px;
                color: #f8fafc;
            }
            
            QLabel {
                color: #e2e8f0;
                font-size: 13px;
                background: transparent;
            }
            
            QLineEdit {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                selection-background-color: #6366f1;
            }
            
            QLineEdit:focus {
                border-color: #6366f1;
                background-color: #1e293b;
            }
            
            QLineEdit::placeholder {
                color: #64748b;
            }
            
            QComboBox {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
            }
            
            QComboBox:hover {
                border-color: #6366f1;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #94a3b8;
                margin-right: 10px;
            }
            
            QPushButton {
                background-color: #334155;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            
            QPushButton:hover {
                background-color: #475569;
                border-color: #6366f1;
            }
            
            QPushButton:pressed {
                background-color: #1e293b;
            }
            
            QCheckBox {
                color: #e2e8f0;
                font-size: 13px;
                spacing: 10px;
            }
            
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 5px;
                border: 2px solid #475569;
                background-color: #0f172a;
            }
            
            QCheckBox::indicator:hover {
                border-color: #6366f1;
            }
            
            QCheckBox::indicator:checked {
                background-color: #6366f1;
                border-color: #6366f1;
            }
            
            QListWidget {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px;
                color: #e2e8f0;
                font-size: 12px;
            }
            
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 6px;
                margin: 2px;
            }
            
            QListWidget::item:selected {
                background-color: #6366f1;
                color: white;
            }
            
            QListWidget::item:hover {
                background-color: #334155;
            }
            
            QProgressBar {
                background-color: #1e293b;
                border: none;
                border-radius: 2px;
            }
            
            QProgressBar::chunk {
                background-color: #6366f1;
            }
        """)

    def _toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_btn.setText("Hide")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_btn.setText("Show")

    def _on_api_key_changed(self, text: str):
        """Handle API key changes."""
        if text and len(text) > 5:
            self._fetch_models(text)
        else:
            self.model_list.clear()
            self._available_models = []
            self.provider_combo.blockSignals(True)
            self.provider_combo.clear()
            self.provider_combo.addItem("All Providers", "")
            self.provider_combo.blockSignals(False)

    def _fetch_models(self, api_key: str):
        """Fetch models from OpenRouter."""
        if self._fetch_thread and self._fetch_thread.isRunning():
            return

        self.models_loading.setVisible(True)
        self.refresh_models_btn.setEnabled(False)

        self._fetch_thread = ModelFetchThread(api_key)
        self._fetch_thread.models_fetched.connect(self._on_models_fetched)
        self._fetch_thread.error_occurred.connect(self._on_models_error)
        self._fetch_thread.start()

    def _refresh_models(self):
        """Force refresh model list."""
        api_key = self.api_key_input.text()
        if api_key and len(api_key) > 5:
            self._fetch_models(api_key)

    def _on_models_fetched(self, models: list[ModelInfo]):
        """Handle successful model fetch."""
        self.models_loading.setVisible(False)
        self.refresh_models_btn.setEnabled(True)

        self._available_models = models

        # Update provider filter
        providers = sorted(set(m.provider for m in models))

        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        self.provider_combo.addItem("All Providers", "")
        for p in providers:
            self.provider_combo.addItem(p, p)
        self.provider_combo.blockSignals(False)

        self._filter_models()

    def _on_models_error(self, error: str):
        """Handle model fetch error."""
        self.models_loading.setVisible(False)
        self.refresh_models_btn.setEnabled(True)

        # Show error in model list temporarily
        self.model_list.clear()
        item = QListWidgetItem(f"Error: {error}")
        item.setForeground(QColor("#ef4444"))
        self.model_list.addItem(item)

    def _filter_models(self):
        """Filter models based on search and provider."""
        query = self.model_search.text()
        provider = self.provider_combo.currentData() or ""

        self.model_list.clear()

        if not self._available_models:
            return

        client = OpenRouterClient()
        filtered = client.filter_models(self._available_models, query, provider)

        # Show max 50 models to avoid lag
        for model in filtered[:50]:
            display_text = f"{model.name} ({model.provider})"
            if model.context_length:
                display_text += f" • {model.context_length // 1000}K"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, model.id)
            self.model_list.addItem(item)

        if len(filtered) > 50:
            self.model_list.addItem(f"... and {len(filtered) - 50} more models")

    def _on_model_selected(self, item):
        """Handle model selection."""
        model_id = item.data(Qt.ItemDataRole.UserRole)
        if model_id:
            self.selected_model_label.setText(model_id)

    def load_settings(self):
        """Load current settings."""
        config = get_config()

        # OpenRouter
        self.api_key_input.setText(config.get("openrouter.api_key", ""))
        if self.api_key_input.text():
            self._fetch_models(self.api_key_input.text())

        model = config.get("openrouter.model", "anthropic/claude-3.5-sonnet")
        self.selected_model_label.setText(model)

        # Local LLM
        local_llm = config.get("local_llm", None)
        if local_llm is not None:
            self.local_llm_enable_cb.setChecked(local_llm.enabled)
            self.local_llm_url_input.setText(local_llm.base_url or "http://localhost:8000/v1")
            self.local_llm_model_input.setText(local_llm.model_name or "local-model")
            self.local_llm_key_input.setText(local_llm.api_key or "")
            self.local_llm_timeout_spin.setValue(local_llm.timeout or 300)
        else:
            self.local_llm_enable_cb.setChecked(False)
            self.local_llm_url_input.setText("http://localhost:8000/v1")
            self.local_llm_model_input.setText("local-model")
            self.local_llm_key_input.setText("")
            self.local_llm_timeout_spin.setValue(300)

        # STT
        lang = config.get("stt.language", "auto")
        lang_text = f"{lang} ({self._get_lang_name(lang)})" if lang != "auto" else "auto (detect)"
        index = self.lang_combo.findText(lang_text)
        if index >= 0:
            self.lang_combo.setCurrentIndex(index)

        # Diarization
        self.diarization_check.setChecked(config.get("diarization.enabled", True))

        # ASR backend selector. Setting this also drives which backend
        # sub-panel is visible (via currentIndexChanged -> _update_backend_panels).
        backend = config.get("stt.backend", "qwen3")
        idx = self.backend_combo.findData(backend)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        # Force a visibility refresh even if the index didn't change (e.g.
        # first dialog open with default qwen3 already selected).
        self._update_backend_panels()

        # Qwen3-ASR
        qwen_size = config.get("qwen_asr.model_size", "1.7B")
        index = self.qwen_size_combo.findData(qwen_size)
        if index >= 0:
            self.qwen_size_combo.setCurrentIndex(index)

        self.qwen_autodownload_check.setChecked(config.get("qwen_asr.auto_download", True))

        # faster-whisper
        fw_size = config.get("faster_whisper.model_size", "large-v3-turbo")
        idx = self.fw_size_combo.findData(fw_size)
        if idx >= 0:
            self.fw_size_combo.setCurrentIndex(idx)

        fw_ct = config.get("faster_whisper.compute_type", "auto")
        idx = self.fw_compute_combo.findData(fw_ct)
        if idx >= 0:
            self.fw_compute_combo.setCurrentIndex(idx)

        self.fw_vad_check.setChecked(bool(config.get("faster_whisper.vad_filter", True)))

        # Knowledge Base / RAG - load documents
        if RAG_AVAILABLE:
            self._rag_manager = None
            self._refresh_document_list()

    def _get_lang_name(self, code: str) -> str:
        """Get language name from code."""
        names = {
            "en": "English",
            "ru": "Russian",
            "uk": "Ukrainian",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "zh": "Chinese",
        }
        return names.get(code, code)

    def _download_qwen_model(self, model_size: str | None = None):
        """Open dialog to download Qwen3-ASR model(s)."""
        import subprocess
        import sys

        from PySide6.QtWidgets import QMessageBox

        if model_size is None:
            model_size = self.qwen_size_combo.currentData()

        if model_size == "all":
            message = (
                "Download both Qwen3-ASR models (0.6B and 1.7B)?\n\n"
                "This will download approximately 4.6 GB of data."
            )
            title = "Download All Models"
        else:
            size_desc = "~1.2 GB" if model_size == "0.6B" else "~3.4 GB"
            message = f"Download Qwen3-ASR-{model_size} model?\n\nThis will download {size_desc}."
            title = f"Download {model_size} Model"

        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                script_path = Path(__file__).parent.parent.parent / "scripts" / "download_models.py"
                model_arg = model_size or self.qwen_size_combo.currentData()
                result = subprocess.run(
                    [sys.executable, str(script_path), "--model-size", model_arg],
                    capture_output=True,
                    text=True,
                    timeout=1800,
                )

                if result.returncode == 0:
                    msg = (
                        "Model downloaded successfully!"
                        if model_size != "all"
                        else "Both models downloaded successfully!"
                    )
                    QMessageBox.information(self, "Success", msg)
                else:
                    QMessageBox.critical(self, "Error", f"Failed: {result.stderr}")
            except subprocess.TimeoutExpired:
                QMessageBox.warning(self, "Timeout", "Download is taking longer than expected.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start download:\n\n{str(e)}")

    def save_settings(self):
        """Save settings."""
        config = get_config()

        # OpenRouter
        config.set("openrouter.api_key", self.api_key_input.text())

        # Get selected model from list or use default
        selected = self.selected_model_label.text()
        if selected and selected != "Not selected":
            config.set("openrouter.model", selected)
        else:
            config.set("openrouter.model", "anthropic/claude-3.5-sonnet")

        # Local LLM
        config.set("local_llm.enabled", self.local_llm_enable_cb.isChecked())
        config.set("local_llm.base_url", self.local_llm_url_input.text().strip())
        config.set("local_llm.model_name", self.local_llm_model_input.text().strip())
        config.set("local_llm.api_key", self.local_llm_key_input.text().strip())
        config.set("local_llm.timeout", self.local_llm_timeout_spin.value())

        # STT
        lang_text = self.lang_combo.currentText()
        lang = lang_text.split()[0]
        config.set("stt.language", lang)

        # Backend selector
        old_backend = config.get("stt.backend", "qwen3")
        new_backend = self.backend_combo.currentData() or "qwen3"
        config.set("stt.backend", new_backend)

        # Diarization
        config.set("diarization.enabled", self.diarization_check.isChecked())

        # Qwen3-ASR
        old_qwen_size = config.get("qwen_asr.model_size", "1.7B")
        new_qwen_size = self.qwen_size_combo.currentData()
        config.set("qwen_asr.model_size", new_qwen_size)
        config.set("qwen_asr.auto_download", self.qwen_autodownload_check.isChecked())

        # faster-whisper
        config.set("faster_whisper.model_size", self.fw_size_combo.currentData())
        config.set("faster_whisper.compute_type", self.fw_compute_combo.currentData())
        config.set("faster_whisper.vad_filter", self.fw_vad_check.isChecked())

        # Hot-reload ASR if the user changed the Qwen model size *and* stayed
        # on the qwen3 backend. Changing the backend itself requires a full
        # app restart (we don't stop/swap to a different backend class at
        # runtime -- too much moving state to do correctly in a hurry).
        if new_backend != old_backend:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Restart Required",
                f"ASR backend changed to '{new_backend}'. "
                "Please restart the app for the change to take effect.",
            )
        elif new_backend == "qwen3" and new_qwen_size != old_qwen_size:
            self._reload_asr_model(new_qwen_size)

        self.accept()

    def _reload_asr_model(self, new_size: str) -> None:
        """Ask MainWindow's TranscriptionManager to swap to ``new_size``.

        Shows a modal progress dialog while the new model loads (10-30 s).
        """
        from PySide6.QtCore import QCoreApplication, Qt
        from PySide6.QtWidgets import QMessageBox, QProgressDialog

        main_window = self.parent()
        manager = getattr(main_window, "transcription_manager", None)
        if manager is None or not hasattr(manager, "reload_model"):
            # Fallback: notify user to restart.
            QMessageBox.information(
                self,
                "Restart required",
                f"Model size changed to {new_size}. Please restart the app to apply.",
            )
            return

        progress = QProgressDialog(
            f"Loading Qwen3-ASR-{new_size}...\nThis may take up to 30 seconds.",
            "",  # empty label hides the cancel button; load is not cancellable
            0,
            0,
            self,
        )
        progress.setCancelButton(None)  # belt-and-braces
        progress.setWindowTitle("Switching ASR model")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QCoreApplication.processEvents()

        try:
            ok = manager.reload_model(new_size)
        finally:
            progress.close()

        if not ok:
            QMessageBox.critical(
                self,
                "Model load failed",
                (
                    f"Failed to load Qwen3-ASR-{new_size}.\n\n"
                    "The model may not be cached locally and no internet is "
                    "available. Try the 'Download' button in this dialog, "
                    "or switch back to a cached model size."
                ),
            )
