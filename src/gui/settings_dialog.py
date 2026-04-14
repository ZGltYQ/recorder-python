"""Settings dialog with modern styling."""

from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QFrame,
    QProgressBar,
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QColor, QPalette

from ..utils.config import get_config, LocalLLMConfig
from ..ai.openrouter import OpenRouterClient, ModelInfo


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

        # STT settings
        stt_group = self._create_stt_group()
        content_layout.addWidget(stt_group)

        # Qwen3-ASR settings
        qwen_group = self._create_qwen_group()
        content_layout.addWidget(qwen_group)

        # Diarization settings
        diarization_group = self._create_diarization_group()
        content_layout.addWidget(diarization_group)

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
        group.setTitle("OpenRouter API")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # API Key row
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setFixedWidth(80)
        api_key_layout.addWidget(api_key_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-or-...")
        self.api_key_input.textChanged.connect(self._on_api_key_changed)
        api_key_layout.addWidget(self.api_key_input, 1)

        # Show/hide toggle
        self.toggle_key_btn = QPushButton("👁")
        self.toggle_key_btn.setFixedWidth(36)
        self.toggle_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        provider_label.setFixedWidth(80)
        provider_layout.addWidget(provider_label)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("All Providers", "")
        self.provider_combo.currentIndexChanged.connect(self._filter_models)
        provider_layout.addWidget(self.provider_combo, 1)

        # Refresh button
        self.refresh_models_btn = QPushButton("↻")
        self.refresh_models_btn.setFixedWidth(36)
        self.refresh_models_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_models_btn.setToolTip("Refresh model list")
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
        group.setTitle("Local LLM")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Enable Local LLM
        enable_layout = QHBoxLayout()
        self.local_llm_enable_cb = QCheckBox("Enable Local LLM")
        enable_layout.addWidget(self.local_llm_enable_cb)
        enable_layout.addStretch()
        layout.addLayout(enable_layout)

        # Base URL
        url_layout = QHBoxLayout()
        url_label = QLabel("Base URL:")
        url_label.setFixedWidth(80)
        url_layout.addWidget(url_label)

        self.local_llm_url_input = QLineEdit()
        self.local_llm_url_input.setPlaceholderText("http://localhost:8000/v1")
        url_layout.addWidget(self.local_llm_url_input, 1)
        layout.addLayout(url_layout)

        # Model Name
        model_layout = QHBoxLayout()
        model_label = QLabel("Model Name:")
        model_label.setFixedWidth(80)
        model_layout.addWidget(model_label)

        self.local_llm_model_input = QLineEdit()
        self.local_llm_model_input.setPlaceholderText("local-model")
        model_layout.addWidget(self.local_llm_model_input, 1)
        layout.addLayout(model_layout)

        # API Key (optional)
        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        key_label.setFixedWidth(80)
        key_layout.addWidget(key_label)

        self.local_llm_key_input = QLineEdit()
        self.local_llm_key_input.setPlaceholderText("Optional for local LLMs")
        self.local_llm_key_input.setEchoMode(QLineEdit.Password)
        key_layout.addWidget(self.local_llm_key_input, 1)
        layout.addLayout(key_layout)

        # Timeout
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("Timeout:")
        timeout_label.setFixedWidth(80)
        timeout_layout.addWidget(timeout_label)

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
        """Create STT settings group."""
        group = QGroupBox()
        group.setTitle("Speech Recognition")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Language
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Language:")
        lang_label.setFixedWidth(80)
        lang_layout.addWidget(lang_label)

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

        # Model size
        size_layout = QHBoxLayout()
        size_label = QLabel("Model Size:")
        size_label.setFixedWidth(80)
        size_layout.addWidget(size_label)

        self.size_combo = QComboBox()
        self.size_combo.addItems(["small", "medium", "large"])
        size_layout.addWidget(self.size_combo, 1)

        layout.addLayout(size_layout)

        group.setLayout(layout)
        return group

    def _create_qwen_group(self) -> QGroupBox:
        """Create Qwen3-ASR settings group."""
        group = QGroupBox()
        group.setTitle("Qwen3-ASR Model")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Model size
        qwen_size_layout = QHBoxLayout()
        qwen_size_label = QLabel("Model Size:")
        qwen_size_label.setFixedWidth(80)
        qwen_size_layout.addWidget(qwen_size_label)

        self.qwen_size_combo = QComboBox()
        self.qwen_size_combo.addItem("0.6B (~1.2 GB) - Faster", "0.6B")
        self.qwen_size_combo.addItem("1.7B (~3.4 GB) - More Accurate", "1.7B")
        self.qwen_size_combo.setToolTip(
            "Select Qwen3-ASR model size:\n"
            "• 0.6B: Smaller, faster, good for real-time transcription\n"
            "• 1.7B: Larger, more accurate, requires more VRAM"
        )
        qwen_size_layout.addWidget(self.qwen_size_combo, 1)

        layout.addLayout(qwen_size_layout)

        # Auto-download option
        self.qwen_autodownload_check = QCheckBox("Auto-download model if not present")
        self.qwen_autodownload_check.setToolTip(
            "Automatically download the selected model on first use"
        )
        layout.addWidget(self.qwen_autodownload_check)

        # Download buttons
        download_label = QLabel("Download Models:")
        download_label.setStyleSheet("font-weight: 600; color: #94a3b8;")
        layout.addWidget(download_label)

        download_layout = QHBoxLayout()
        download_layout.setSpacing(8)

        self.download_0_6b_btn = QPushButton("📥 0.6B")
        self.download_0_6b_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_0_6b_btn.setToolTip("Download the 0.6B model (~1.2 GB)")
        self.download_0_6b_btn.clicked.connect(lambda: self._download_qwen_model("0.6B"))
        download_layout.addWidget(self.download_0_6b_btn)

        self.download_1_7b_btn = QPushButton("📥 1.7B")
        self.download_1_7b_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_1_7b_btn.setToolTip("Download the 1.7B model (~3.4 GB)")
        self.download_1_7b_btn.clicked.connect(lambda: self._download_qwen_model("1.7B"))
        download_layout.addWidget(self.download_1_7b_btn)

        download_all_btn = QPushButton("📥 All")
        download_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        download_all_btn.setToolTip("Download both model sizes")
        download_all_btn.clicked.connect(lambda: self._download_qwen_model("all"))
        download_layout.addWidget(download_all_btn)

        download_layout.addStretch()
        layout.addLayout(download_layout)

        group.setLayout(layout)
        return group

    def _create_diarization_group(self) -> QGroupBox:
        """Create diarization settings group."""
        group = QGroupBox()
        group.setTitle("Speaker Diarization")

        layout = QVBoxLayout()

        self.diarization_check = QCheckBox("Enable speaker diarization")
        layout.addWidget(self.diarization_check)

        group.setLayout(layout)
        return group

    def _apply_styles(self):
        """Apply modern dark theme styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            
            QGroupBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
                margin-top: 8px;
                padding-top: 20px;
                padding-left: 16px;
                padding-right: 16px;
                padding-bottom: 16px;
                font-weight: 600;
                font-size: 14px;
                color: #f8fafc;
            }

            QGroupBox::title {
                color: #f8fafc;
                subcontrol-origin: margin;
                left: 12px;
                top: 6px;
                padding: 0 8px;
                background-color: transparent;
            }
            
            QLabel {
                color: #e2e8f0;
                font-size: 13px;
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
                padding: 10px 18px;
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
            self.toggle_key_btn.setText("🔒")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_btn.setText("👁")

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

    def _on_models_fetched(self, models: List[ModelInfo]):
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
        local_llm = config.get("local_llm", {})
        self.local_llm_enable_cb.setChecked(local_llm.get("enabled", False))
        self.local_llm_url_input.setText(local_llm.get("base_url", "http://localhost:8000/v1"))
        self.local_llm_model_input.setText(local_llm.get("model_name", "local-model"))
        self.local_llm_key_input.setText(local_llm.get("api_key", ""))
        self.local_llm_timeout_spin.setValue(local_llm.get("timeout", 300))

        # STT
        lang = config.get("stt.language", "auto")
        lang_text = f"{lang} ({self._get_lang_name(lang)})" if lang != "auto" else "auto (detect)"
        index = self.lang_combo.findText(lang_text)
        if index >= 0:
            self.lang_combo.setCurrentIndex(index)

        size = config.get("stt.model_size", "small")
        index = self.size_combo.findText(size)
        if index >= 0:
            self.size_combo.setCurrentIndex(index)

        # Diarization
        self.diarization_check.setChecked(config.get("diarization.enabled", True))

        # Qwen3-ASR
        qwen_size = config.get("qwen_asr.model_size", "1.7B")
        index = self.qwen_size_combo.findData(qwen_size)
        if index >= 0:
            self.qwen_size_combo.setCurrentIndex(index)

        self.qwen_autodownload_check.setChecked(config.get("qwen_asr.auto_download", True))

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

    def _download_qwen_model(self, model_size: Optional[str] = None):
        """Open dialog to download Qwen3-ASR model(s)."""
        from PySide6.QtWidgets import QMessageBox
        import subprocess
        import sys

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
                script_path = Path(__file__).parent.parent / "scripts" / "download_models.py"
                model_arg = model_size or self.qwen_size_combo.currentData()
                result = subprocess.run(
                    [sys.executable, str(script_path), "--model-size", model_arg],
                    capture_output=True,
                    text=True,
                    timeout=1800,
                )

                if result.returncode == 0:
                    msg = (
                        f"Model downloaded successfully!"
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
        local_llm = config.get("local_llm", {})
        local_llm["enabled"] = self.local_llm_enable_cb.isChecked()
        local_llm["base_url"] = self.local_llm_url_input.text().strip()
        local_llm["model_name"] = self.local_llm_model_input.text().strip()
        local_llm["api_key"] = self.local_llm_key_input.text().strip()
        local_llm["timeout"] = self.local_llm_timeout_spin.value()
        config.set("local_llm", local_llm)

        # STT
        lang_text = self.lang_combo.currentText()
        lang = lang_text.split()[0]
        config.set("stt.language", lang)
        config.set("stt.model_size", self.size_combo.currentText())

        # Diarization
        config.set("diarization.enabled", self.diarization_check.isChecked())

        # Qwen3-ASR
        config.set("qwen_asr.model_size", self.qwen_size_combo.currentData())
        config.set("qwen_asr.auto_download", self.qwen_autodownload_check.isChecked())

        self.accept()
