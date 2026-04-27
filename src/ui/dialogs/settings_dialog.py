"""应用设置对话框.

提供应用级别的设置配置界面，包括：
- 通用设置：日志级别、队列大小等
- 输出设置：默认输出尺寸、质量等
- 路径设置：默认输出目录等
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.config_manager import get_config
from src.models.api_config import APIConfig, AIModelConfig
from src.models.process_config import (
    BackgroundRemovalConfig,
    BackgroundRemovalProvider,
)
from src.services.ai_service import get_ai_service
from src.utils.constants import (
    APP_DATA_DIR,
    DEFAULT_OUTPUT_HEIGHT,
    DEFAULT_OUTPUT_QUALITY,
    DEFAULT_OUTPUT_WIDTH,
    MAX_QUEUE_SIZE,
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# 日志级别选项
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class GeneralSettingsWidget(QWidget):
    """通用设置面板."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 日志设置组
        log_group = QGroupBox("日志设置")
        log_layout = QFormLayout(log_group)
        log_layout.setSpacing(8)

        self._log_level_combo = QComboBox()
        self._log_level_combo.addItems(LOG_LEVELS)
        log_layout.addRow("日志级别:", self._log_level_combo)

        layout.addWidget(log_group)

        # 队列设置组
        queue_group = QGroupBox("队列设置")
        queue_layout = QFormLayout(queue_group)
        queue_layout.setSpacing(8)

        self._max_queue_spinbox = QSpinBox()
        self._max_queue_spinbox.setMinimum(1)
        self._max_queue_spinbox.setMaximum(50)
        self._max_queue_spinbox.setValue(MAX_QUEUE_SIZE)
        self._max_queue_spinbox.setToolTip("队列中最多可以添加的任务数量")
        queue_layout.addRow("最大队列大小:", self._max_queue_spinbox)

        self._concurrent_limit_spinbox = QSpinBox()
        self._concurrent_limit_spinbox.setMinimum(1)
        self._concurrent_limit_spinbox.setMaximum(10)
        self._concurrent_limit_spinbox.setValue(3)
        self._concurrent_limit_spinbox.setToolTip("同时并行处理的任务数量\n设置为 1 表示按顺序一个一个处理")
        queue_layout.addRow("并发处理数:", self._concurrent_limit_spinbox)

        layout.addWidget(queue_group)

        # 开发选项组
        dev_group = QGroupBox("开发选项")
        dev_layout = QVBoxLayout(dev_group)
        dev_layout.setSpacing(8)

        self._debug_checkbox = QCheckBox("启用调试模式")
        self._debug_checkbox.setToolTip("启用后将输出更详细的日志信息")
        dev_layout.addWidget(self._debug_checkbox)

        self._dev_tools_checkbox = QCheckBox("启用开发工具")
        self._dev_tools_checkbox.setToolTip("启用额外的开发调试工具")
        dev_layout.addWidget(self._dev_tools_checkbox)

        layout.addWidget(dev_group)

        layout.addStretch()

    def get_settings(self) -> dict:
        """获取当前设置."""
        return {
            "log_level": self._log_level_combo.currentText(),
            "max_queue_size": self._max_queue_spinbox.value(),
            "concurrent_limit": self._concurrent_limit_spinbox.value(),
            "debug": self._debug_checkbox.isChecked(),
            "dev_tools": self._dev_tools_checkbox.isChecked(),
        }

    def set_settings(self, settings: dict) -> None:
        """设置当前值."""
        if "log_level" in settings:
            index = self._log_level_combo.findText(settings["log_level"])
            if index >= 0:
                self._log_level_combo.setCurrentIndex(index)

        if "max_queue_size" in settings:
            self._max_queue_spinbox.setValue(settings["max_queue_size"])

        if "concurrent_limit" in settings:
            self._concurrent_limit_spinbox.setValue(settings["concurrent_limit"])

        if "debug" in settings:
            self._debug_checkbox.setChecked(settings["debug"])

        if "dev_tools" in settings:
            self._dev_tools_checkbox.setChecked(settings["dev_tools"])


class OutputSettingsWidget(QWidget):
    """输出设置面板."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 尺寸设置组
        size_group = QGroupBox("默认输出尺寸")
        size_layout = QFormLayout(size_group)
        size_layout.setSpacing(8)

        # 宽度
        self._width_spinbox = QSpinBox()
        self._width_spinbox.setMinimum(100)
        self._width_spinbox.setMaximum(4096)
        self._width_spinbox.setValue(DEFAULT_OUTPUT_WIDTH)
        self._width_spinbox.setSuffix(" px")
        size_layout.addRow("宽度:", self._width_spinbox)

        # 高度
        self._height_spinbox = QSpinBox()
        self._height_spinbox.setMinimum(100)
        self._height_spinbox.setMaximum(4096)
        self._height_spinbox.setValue(DEFAULT_OUTPUT_HEIGHT)
        self._height_spinbox.setSuffix(" px")
        size_layout.addRow("高度:", self._height_spinbox)

        layout.addWidget(size_group)

        # 质量设置组
        quality_group = QGroupBox("输出质量")
        quality_layout = QVBoxLayout(quality_group)
        quality_layout.setSpacing(8)

        # 质量滑块
        quality_row = QHBoxLayout()
        self._quality_slider = QSlider(Qt.Orientation.Horizontal)
        self._quality_slider.setMinimum(1)
        self._quality_slider.setMaximum(100)
        self._quality_slider.setValue(DEFAULT_OUTPUT_QUALITY)
        self._quality_slider.valueChanged.connect(self._on_quality_changed)
        quality_row.addWidget(self._quality_slider)

        self._quality_label = QLabel(f"{DEFAULT_OUTPUT_QUALITY}%")
        self._quality_label.setFixedWidth(50)
        quality_row.addWidget(self._quality_label)

        quality_layout.addLayout(quality_row)

        # 质量说明
        hint_label = QLabel("较高的质量会产生更大的文件")
        hint_label.setProperty("hint", True)
        # hint_label.setStyleSheet("color: #666; font-size: 11px;")
        quality_layout.addWidget(hint_label)

        layout.addWidget(quality_group)

        layout.addStretch()

    def _on_quality_changed(self, value: int) -> None:
        """质量值变化."""
        self._quality_label.setText(f"{value}%")

    def get_settings(self) -> dict:
        """获取当前设置."""
        return {
            "default_output_width": self._width_spinbox.value(),
            "default_output_height": self._height_spinbox.value(),
            "default_output_quality": self._quality_slider.value(),
        }

    def set_settings(self, settings: dict) -> None:
        """设置当前值."""
        if "default_output_width" in settings:
            self._width_spinbox.setValue(settings["default_output_width"])

        if "default_output_height" in settings:
            self._height_spinbox.setValue(settings["default_output_height"])

        if "default_output_quality" in settings:
            quality = settings["default_output_quality"]
            self._quality_slider.setValue(quality)
            self._quality_label.setText(f"{quality}%")


class AISettingsWidget(QWidget):
    """AI 服务设置面板."""

    config_changed = pyqtSignal(object)  # APIConfig

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config_manager = get_config()
        self._is_password_visible = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # DashScope 配置组
        provider_group = QGroupBox("DashScope (通义千问)")
        provider_layout = QVBoxLayout(provider_group)
        provider_layout.setSpacing(12)

        # API Key 输入
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setFixedWidth(80)
        api_key_layout.addWidget(api_key_label)

        self._api_key_input = QLineEdit()
        self._api_key_input.setPlaceholderText("sk-...")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_layout.addWidget(self._api_key_input)

        self._toggle_key_btn = QPushButton("👁")
        self._toggle_key_btn.setFixedSize(28, 28)
        self._toggle_key_btn.setToolTip("显示/隐藏 API Key")
        self._toggle_key_btn.clicked.connect(self._toggle_api_key_visibility)
        api_key_layout.addWidget(self._toggle_key_btn)

        provider_layout.addLayout(api_key_layout)

        # 模型选择
        model_layout = QHBoxLayout()
        model_label = QLabel("模型:")
        model_label.setFixedWidth(80)
        model_layout.addWidget(model_label)

        self._model_combo = QComboBox()
        # 只显示支持 base64 data URL 的模型
        self._model_combo.addItems([
            "qwen-image-2.0",
            "qwen-image-edit-plus",
            "qwen-image-edit-plus-2025-12-15",
            "qwen-image-edit-plus-2025-10-30",
        ])
        self._model_combo.setToolTip("选择图像编辑模型（仅显示支持 base64 格式的模型）")
        model_layout.addWidget(self._model_combo)

        provider_layout.addLayout(model_layout)

        # 测试连接按钮
        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._test_connection)
        provider_layout.addWidget(self._test_btn)

        layout.addWidget(provider_group)

        # 说明
        hint_label = QLabel(
            "提示：您可以在阿里云 百炼 控制台获取 API Key\n"
            "https://bailian.console.aliyun.com"
        )
        hint_label.setProperty("hint", True)
        # hint_label.setStyleSheet("color: #666; font-size: 11px;")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        layout.addStretch()

    def _toggle_api_key_visibility(self) -> None:
        """切换 API Key 可见性."""
        self._is_password_visible = not self._is_password_visible
        if self._is_password_visible:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_key_btn.setText("🔒")
        else:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_key_btn.setText("👁")

    def _test_connection(self) -> None:
        """测试连接."""
        api_key = self._api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "提示", "请先输入 API Key")
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("正在测试...")

        try:
            config = APIConfig(api_key=api_key)
            # 简单验证配置格式
            QMessageBox.information(
                self, "测试通过",
                "API 配置格式正确\n(实际连接需在处理时验证)"
            )
        except Exception as e:
            QMessageBox.critical(self, "测试失败", f"配置无效: {e}")
        finally:
            self._test_btn.setEnabled(True)
            self._test_btn.setText("测试连接")

    def get_settings(self) -> dict:
        """获取当前设置."""
        return {
            "api_key": self._api_key_input.text().strip(),
            "model": self._model_combo.currentText(),
        }

    def set_settings(self, settings: dict) -> None:
        """设置当前值."""
        if "api_key" in settings and settings["api_key"]:
            self._api_key_input.setText(settings["api_key"])

        if "model" in settings:
            index = self._model_combo.findText(settings["model"])
            if index >= 0:
                self._model_combo.setCurrentIndex(index)


class BackgroundRemovalSettingsWidget(QWidget):
    """抠图服务设置面板."""

    connection_test_finished = pyqtSignal(str, str)  # level, message

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.connection_test_finished.connect(self._on_connection_test_finished)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 抠图服务配置组
        provider_group = QGroupBox("抠图服务配置")
        provider_layout = QVBoxLayout(provider_group)
        provider_layout.setSpacing(12)

        # 服务提供者选择
        provider_row = QHBoxLayout()
        provider_label = QLabel("服务提供者:")
        provider_label.setFixedWidth(100)
        provider_row.addWidget(provider_label)

        self._provider_combo = QComboBox()
        self._provider_combo.addItem("外部API服务", "external_api")
        self._provider_combo.addItem("AI模型", "ai")
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self._provider_combo)

        provider_layout.addLayout(provider_row)

        layout.addWidget(provider_group)

        # 外部API配置容器 (不使用 GroupBox 避免边框挤压布局)
        self._api_group = QWidget()
        api_layout = QVBoxLayout(self._api_group)
        api_layout.setSpacing(10)
        api_layout.setContentsMargins(10, 0, 10, 0)

        # 标题
        api_title = QLabel("外部API设置")
        api_title.setProperty("subheading", True)
        # api_title.setStyleSheet("font-weight: bold; color: #333;")
        api_layout.addWidget(api_title)

        # 辅助函数：创建固定高度的行
        def create_row(label_text: str, widget: QWidget, extra_widget: Optional[QWidget] = None) -> QWidget:
            row_widget = QWidget()
            row_widget.setFixedHeight(40)  # 强制固定行高，彻底杜绝重叠
            
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            
            lbl = QLabel(label_text)
            lbl.setFixedWidth(90)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(lbl)
            
            row_layout.addWidget(widget, 1)  # Stretch factor 1
            
            if extra_widget:
                row_layout.addWidget(extra_widget)
                
            return row_widget

        # API URL
        self._api_url_input = QLineEdit()
        self._api_url_input.setPlaceholderText("http://localhost:5000/api/remove-background")
        self._api_url_input.setText("http://localhost:5000/api/remove-background")
        self._api_url_input.setMinimumHeight(32)
        api_layout.addWidget(create_row("API 地址:", self._api_url_input))

        # API Key
        self._api_key_input = QLineEdit()
        self._api_key_input.setPlaceholderText("可选，留空则不验证")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setMinimumHeight(32)
        
        self._toggle_key_btn = QPushButton("👁")
        self._toggle_key_btn.setFixedSize(36, 32)
        self._toggle_key_btn.setToolTip("显示/隐藏 API Key")
        self._toggle_key_btn.clicked.connect(self._toggle_api_key_visibility)
        
        api_layout.addWidget(create_row("API 密钥:", self._api_key_input, self._toggle_key_btn))

        # 代理设置
        self._proxy_input = QLineEdit()
        self._proxy_input.setPlaceholderText("可选，如 http://127.0.0.1:7890")
        self._proxy_input.setMinimumHeight(32)
        api_layout.addWidget(create_row("代理设置:", self._proxy_input))

        # 请求超时
        self._timeout_spinbox = QSpinBox()
        self._timeout_spinbox.setMinimum(10)
        self._timeout_spinbox.setMaximum(600)
        self._timeout_spinbox.setValue(120)
        self._timeout_spinbox.setSuffix(" 秒")
        self._timeout_spinbox.setMinimumHeight(32)
        self._timeout_spinbox.setFixedWidth(120)
        
        # 超时行特殊处理，不需要填满整行
        timeout_row = QWidget()
        timeout_row.setFixedHeight(40)
        timeout_layout = QHBoxLayout(timeout_row)
        timeout_layout.setContentsMargins(0, 0, 0, 0)
        timeout_layout.setSpacing(10)
        
        t_lbl = QLabel("请求超时:")
        t_lbl.setFixedWidth(90)
        t_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        timeout_layout.addWidget(t_lbl)
        timeout_layout.addWidget(self._timeout_spinbox)
        timeout_layout.addStretch()
        
        api_layout.addWidget(timeout_row)

        # 测试连接按钮
        self._test_btn = QPushButton("测试连接")
        self._test_btn.setFixedHeight(36)
        self._test_btn.clicked.connect(self._test_connection)
        
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(100, 5, 0, 0) # 左边距对齐输入框
        btn_row.addWidget(self._test_btn)
        api_layout.addLayout(btn_row)

        layout.addWidget(self._api_group)

        # 说明
        hint_label = QLabel(
            "提示：外部API服务需要返回 PNG 蒙版图片\n"
            "白色区域=保留主体，黑色区域=透明背景"
        )
        hint_label.setProperty("hint", True)
        # hint_label.setStyleSheet("color: #666; font-size: 11px;")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        layout.addStretch()

        # 初始状态
        self._is_password_visible = False

    def _on_provider_changed(self, index: int) -> None:
        """服务提供者变更."""
        provider = self._provider_combo.currentData()
        # 外部API时显示配置组
        self._api_group.setVisible(provider == "external_api")

    def _toggle_api_key_visibility(self) -> None:
        """切换 API Key 可见性."""
        self._is_password_visible = not self._is_password_visible
        if self._is_password_visible:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_key_btn.setText("🔒")
        else:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_key_btn.setText("👁")

    def _test_connection(self) -> None:
        """测试连接."""
        api_url = self._api_url_input.text().strip()
        if not api_url:
            QMessageBox.warning(self, "提示", "请先输入 API 地址")
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("正在测试...")

        import threading

        def worker() -> None:
            try:
                import httpx
                with httpx.Client(timeout=10) as client:
                    response = client.options(api_url)
                    if response.status_code in (200, 204, 405):
                        self.connection_test_finished.emit(
                            "info", f"API 服务可达\n状态码: {response.status_code}"
                        )
                    else:
                        self.connection_test_finished.emit(
                            "warning", f"服务可连接但返回状态码: {response.status_code}"
                        )
            except Exception as e:
                self.connection_test_finished.emit("error", f"连接失败: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_connection_test_finished(self, level: str, message: str) -> None:
        """处理异步连接测试结果."""
        if level == "info":
            QMessageBox.information(self, "测试通过", message)
        elif level == "warning":
            QMessageBox.warning(self, "测试警告", message)
        else:
            QMessageBox.critical(self, "测试失败", message)

        self._test_btn.setEnabled(True)
        self._test_btn.setText("测试连接")

    def get_settings(self) -> dict:
        """获取当前设置."""
        provider = self._provider_combo.currentData()
        return {
            "provider": provider,
            "api_url": self._api_url_input.text().strip(),
            "api_key": self._api_key_input.text().strip(),
            "proxy": self._proxy_input.text().strip() or None,
            "timeout": self._timeout_spinbox.value(),
        }

    def set_settings(self, settings: dict) -> None:
        """设置当前值."""
        if "provider" in settings:
            index = self._provider_combo.findData(settings["provider"])
            if index >= 0:
                self._provider_combo.setCurrentIndex(index)
            self._on_provider_changed(index)

        if "api_url" in settings and settings["api_url"]:
            self._api_url_input.setText(settings["api_url"])

        if "api_key" in settings and settings["api_key"]:
            self._api_key_input.setText(settings["api_key"])

        if "proxy" in settings and settings["proxy"]:
            self._proxy_input.setText(settings["proxy"])

        if "timeout" in settings:
            self._timeout_spinbox.setValue(settings["timeout"])


class PathSettingsWidget(QWidget):
    """路径设置面板."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 输出目录设置组
        output_group = QGroupBox("输出目录")
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(8)

        # 输出目录选择
        output_row = QHBoxLayout()
        self._output_dir_input = QLineEdit()
        self._output_dir_input.setPlaceholderText("选择默认输出目录...")
        self._output_dir_input.setReadOnly(True)
        output_row.addWidget(self._output_dir_input)

        self._browse_output_btn = QPushButton("浏览...")
        self._browse_output_btn.clicked.connect(self._browse_output_dir)
        output_row.addWidget(self._browse_output_btn)

        output_layout.addLayout(output_row)

        # 说明
        hint_label = QLabel("处理完成的图片将保存到此目录")
        hint_label.setProperty("hint", True)
        # hint_label.setStyleSheet("color: #666; font-size: 11px;")
        output_layout.addWidget(hint_label)

        layout.addWidget(output_group)

        # 数据目录信息组
        data_group = QGroupBox("应用数据")
        data_layout = QFormLayout(data_group)
        data_layout.setSpacing(8)

        # 数据目录（只读）
        data_dir_label = QLabel(str(APP_DATA_DIR))
        data_dir_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        data_dir_label.setProperty("hint", True)
        # data_dir_label.setStyleSheet("color: #666;")
        data_layout.addRow("数据目录:", data_dir_label)

        # 打开数据目录按钮
        open_data_btn = QPushButton("打开数据目录")
        open_data_btn.clicked.connect(self._open_data_dir)
        data_layout.addRow("", open_data_btn)

        layout.addWidget(data_group)

        layout.addStretch()

    def _browse_output_dir(self) -> None:
        """浏览输出目录."""
        current = self._output_dir_input.text()
        start_dir = current if current else str(Path.home())

        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            start_dir,
            QFileDialog.Option.ShowDirsOnly,
        )

        if dir_path:
            self._output_dir_input.setText(dir_path)

    def _open_data_dir(self) -> None:
        """打开数据目录."""
        import subprocess
        import sys

        if sys.platform == "darwin":
            subprocess.run(["open", str(APP_DATA_DIR)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(APP_DATA_DIR)])
        else:
            subprocess.run(["xdg-open", str(APP_DATA_DIR)])

    def get_settings(self) -> dict:
        """获取当前设置."""
        output_dir = self._output_dir_input.text().strip()
        return {
            "default_output_dir": output_dir if output_dir else None,
        }

    def set_settings(self, settings: dict) -> None:
        """设置当前值."""
        if "default_output_dir" in settings and settings["default_output_dir"]:
            self._output_dir_input.setText(settings["default_output_dir"])


class SettingsDialog(QDialog):
    """应用设置对话框.

    提供应用级别配置的统一设置界面。

    Signals:
        settings_changed: 设置已变更信号
        ai_config_changed: AI 配置变更信号
    """

    settings_changed = pyqtSignal()
    ai_config_changed = pyqtSignal(object)  # APIConfig

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config_manager = get_config()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """设置 UI."""
        self.setWindowTitle("应用设置")
        self.setMinimumSize(500, 450)
        self.resize(550, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 标签页
        self._tab_widget = QTabWidget()

        # AI 服务设置标签页（放在第一个）
        self._ai_widget = AISettingsWidget()
        self._tab_widget.addTab(self._ai_widget, "AI 服务")

        # 抠图服务设置标签页
        self._bg_removal_widget = BackgroundRemovalSettingsWidget()
        self._tab_widget.addTab(self._bg_removal_widget, "抠图服务")

        # 通用设置标签页
        self._general_widget = GeneralSettingsWidget()
        self._tab_widget.addTab(self._general_widget, "通用")

        # 输出设置标签页
        self._output_widget = OutputSettingsWidget()
        self._tab_widget.addTab(self._output_widget, "输出")

        # 路径设置标签页
        self._path_widget = PathSettingsWidget()
        self._tab_widget.addTab(self._path_widget, "路径")

        layout.addWidget(self._tab_widget)

        # 按钮区域
        btn_layout = QHBoxLayout()

        # 重置按钮
        self._reset_btn = QPushButton("重置为默认")
        self._reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(self._reset_btn)

        btn_layout.addStretch()

        # 标准按钮
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)
        self._button_box.button(
            QDialogButtonBox.StandardButton.Apply
        ).clicked.connect(self._on_apply)

        btn_layout.addWidget(self._button_box)

        layout.addLayout(btn_layout)

    def _load_settings(self) -> None:
        """从配置管理器加载设置."""
        try:
            # 加载应用设置
            settings = self._config_manager.settings

            general_settings = {
                "log_level": settings.log_level,
                "max_queue_size": settings.max_queue_size,
                "concurrent_limit": settings.concurrent_limit,
                "debug": settings.debug,
                "dev_tools": settings.dev_tools,
            }
            self._general_widget.set_settings(general_settings)

            output_settings = {
                "default_output_width": settings.default_output_width,
                "default_output_height": settings.default_output_height,
                "default_output_quality": settings.default_output_quality,
            }
            self._output_widget.set_settings(output_settings)

            # 加载用户配置
            user_config = self._config_manager._load_user_config()
            path_settings = {
                "default_output_dir": user_config.get("default_output_dir"),
            }
            self._path_widget.set_settings(path_settings)

            # 加载 AI 配置
            api_config = self._config_manager.get_user_config("api_config", {})
            ai_settings = {
                "api_key": api_config.get("api_key", ""),
                "model": api_config.get("model", {}).get("model", "qwen-image-edit-plus"),
            }
            self._ai_widget.set_settings(ai_settings)

            # 加载抠图服务配置
            bg_removal_config = self._config_manager.get_user_config("background_removal", {})
            bg_removal_settings = {
                "provider": bg_removal_config.get("provider", "external_api"),
                "api_url": bg_removal_config.get("api_url", "http://localhost:5000/api/remove-background"),
                "api_key": bg_removal_config.get("api_key", ""),
                "proxy": bg_removal_config.get("proxy"),
                "timeout": bg_removal_config.get("timeout", 120),
            }
            self._bg_removal_widget.set_settings(bg_removal_settings)

            logger.debug("设置对话框加载完成")

        except Exception as e:
            logger.error(f"加载设置失败: {e}")

    def _save_settings(self) -> bool:
        """保存设置.

        Returns:
            是否保存成功
        """
        try:
            # 收集所有设置
            general = self._general_widget.get_settings()
            output = self._output_widget.get_settings()
            path = self._path_widget.get_settings()
            ai = self._ai_widget.get_settings()

            # 合并并保存通用设置
            all_settings = {**general, **output, **path}
            self._config_manager.save_user_config(all_settings)

            # 保存 AI 配置（允许空 key，支持用户清空已保存凭据）
            api_config_data = {
                "api_key": ai.get("api_key", ""),
                "model": {"model": ai.get("model", "qwen-image-edit-plus")}
            }
            self._config_manager.set_user_config("api_config", api_config_data)

            # 仅在 key 非空时更新 AI 服务单例
            if ai.get("api_key"):
                try:
                    api_config = APIConfig(
                        api_key=ai["api_key"],
                        model=AIModelConfig(model=ai.get("model", "qwen-image-edit-plus"))
                    )
                    get_ai_service(config=api_config)
                    self.ai_config_changed.emit(api_config)
                    logger.info("AI 服务配置已更新")
                except Exception as e:
                    logger.warning(f"更新 AI 服务失败: {e}")

            # 保存抠图服务配置
            bg_removal = self._bg_removal_widget.get_settings()
            bg_removal_config_data = {
                "provider": bg_removal.get("provider", "external_api"),
                "api_url": bg_removal.get("api_url", "http://localhost:5000/api/remove-background"),
                "api_key": bg_removal.get("api_key", ""),
                "proxy": bg_removal.get("proxy"),
                "timeout": bg_removal.get("timeout", 120),
            }
            self._config_manager.set_user_config("background_removal", bg_removal_config_data)
            logger.info("抠图服务配置已更新")

            # 重新加载配置以应用变更
            self._config_manager.reload()

            self.settings_changed.emit()
            logger.info("设置已保存")
            return True

        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存设置失败: {e}")
            return False

    def _on_accept(self) -> None:
        """确定按钮点击."""
        if self._save_settings():
            self.accept()

    def _on_apply(self) -> None:
        """应用按钮点击."""
        if self._save_settings():
            QMessageBox.information(self, "提示", "设置已应用")

    def _on_reset(self) -> None:
        """重置按钮点击."""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要将所有设置重置为默认值吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._config_manager.reset_to_defaults()
                self._load_settings()
                self.settings_changed.emit()
                QMessageBox.information(self, "提示", "设置已重置为默认值")
                logger.info("设置已重置为默认值")
            except Exception as e:
                logger.error(f"重置设置失败: {e}")
                QMessageBox.critical(self, "错误", f"重置设置失败: {e}")

    def get_all_settings(self) -> dict:
        """获取所有当前设置.

        Returns:
            所有设置的字典
        """
        general = self._general_widget.get_settings()
        output = self._output_widget.get_settings()
        path = self._path_widget.get_settings()
        ai = self._ai_widget.get_settings()
        bg_removal = self._bg_removal_widget.get_settings()
        return {**general, **output, **path, "ai": ai, "background_removal": bg_removal}
