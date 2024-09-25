import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QCheckBox, QPushButton, QFileDialog, 
                             QMessageBox, QProgressBar, QPlainTextEdit,
                             QStatusBar, QRadioButton, QButtonGroup, QSplitter, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
import asyncio
from src.juejin_downloader import Juejinxiaoce2Markdown
from utils.config import load_config, save_config, get_config_path
from src.utils import get_version

VERSION = get_version()
AUTHOR = "h7ml"
AUTHOR_URL = "https://github.com/h7ml"
COPYRIGHT = f"© {AUTHOR} 2024"
LEGAL_DISCLAIMER = """
警告: 本软件仅供学习和研究使用。用户应当遵守相关法律法规,
尊重著作权,不得将下载的内容用于商业用途或非法传播。
使用本软件造成的任何法律责任由用户自行承担。
"""

class DownloadThread(QThread):
    progress_update = pyqtSignal(int)
    log_update = pyqtSignal(str)
    finished = pyqtSignal()
    detailed_log_update = pyqtSignal(str)
    book_progress_update = pyqtSignal(int, int)
    section_progress_update = pyqtSignal(int, int)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_paused = False
        self.is_cancelled = False

    def run(self):
        try:
            asyncio.run(self._async_run())
        except Exception as e:
            self.log_update.emit(f"下载过程中发生错误: {str(e)}")
            import traceback
            self.detailed_log_update.emit(f"详细错误信息: {traceback.format_exc()}")
        finally:
            self.finished.emit()

    async def _async_run(self):
        helper = Juejinxiaoce2Markdown(
            self.config,
            progress_callback=self.progress_update.emit,
            log_callback=self.log_update.emit,
            detailed_log_callback=self.detailed_log_update.emit,
            book_progress_callback=self.book_progress_update.emit,
            section_progress_callback=self.section_progress_update.emit
        )
        await helper.main(pause_check=self.check_pause, cancel_check=self.check_cancel)

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def cancel(self):
        self.is_cancelled = True

    def check_pause(self):
        while self.is_paused:
            if self.is_cancelled:
                return True
            asyncio.sleep(0.1)
        return False

    def check_cancel(self):
        return self.is_cancelled

class MainWindow(QMainWindow):
    def __init__(self, config=None):
        super().__init__()
        self.config = config or {}  # 使用传入的配置或空字典
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"掘金小册下载器 v{VERSION}")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        splitter.addWidget(top_widget)

        # 添加UI元素
        self.setup_ui(top_layout)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        splitter.addWidget(bottom_widget)

        self.setup_log_display(bottom_layout)

        splitter.setSizes([300, 300])

        # 法律免责声明
        disclaimer_label = QLabel(LEGAL_DISCLAIMER)
        disclaimer_label.setWordWrap(True)
        disclaimer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(disclaimer_label)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage(COPYRIGHT)

        # 加载配置
        self.config = load_config()
        self.config_path = get_config_path()
        self.load_config_to_ui()

    def setup_ui(self, layout):
        # 添加版本和作者信息
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"版本: {VERSION}"))
        info_layout.addWidget(QLabel("作者: "))
        author_link = QLabel(f"<a href='{AUTHOR_URL}' style='color: blue; text-decoration: none;'>{AUTHOR}</a>")
        author_link.setOpenExternalLinks(True)
        info_layout.addWidget(author_link)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Cookie 输入
        cookie_layout = QHBoxLayout()
        cookie_layout.addWidget(QLabel("Cookie:"))
        self.cookie_input = QLineEdit()
        cookie_layout.addWidget(self.cookie_input)
        layout.addLayout(cookie_layout)

        # 保存目录选择
        save_dir_layout = QHBoxLayout()
        save_dir_layout.addWidget(QLabel("保存目录:"))
        self.save_dir_input = QLineEdit()
        save_dir_layout.addWidget(self.save_dir_input)
        self.save_dir_button = QPushButton("选择")
        self.save_dir_button.clicked.connect(self.choose_save_dir)
        save_dir_layout.addWidget(self.save_dir_button)
        layout.addLayout(save_dir_layout)

        # 下载模式选择
        mode_group = QButtonGroup(self)
        self.all_books_radio = QRadioButton("下载所有小册")
        self.single_book_radio = QRadioButton("下载单个小册")
        mode_group.addButton(self.all_books_radio)
        mode_group.addButton(self.single_book_radio)
        self.all_books_radio.setChecked(True)
        layout.addWidget(self.all_books_radio)
        layout.addWidget(self.single_book_radio)

        # 单个小册 ID 输入
        self.book_id_widget = QWidget()
        book_id_layout = QHBoxLayout(self.book_id_widget)
        book_id_layout.addWidget(QLabel("小册 ID(多个用逗号分隔):"))
        self.book_id_input = QLineEdit()
        self.book_id_input.setPlaceholderText("例如: 123456,789012")
        book_id_layout.addWidget(self.book_id_input)
        layout.addWidget(self.book_id_widget)
        self.book_id_widget.setVisible(False)

        self.single_book_radio.toggled.connect(self.toggle_book_id_input)

        # 选项
        self.fetch_online_checkbox = QCheckBox("在线获取小册列表")
        layout.addWidget(self.fetch_online_checkbox)
        self.overwrite_checkbox = QCheckBox("覆盖已存在的文件")
        layout.addWidget(self.overwrite_checkbox)
        self.save_images_checkbox = QCheckBox("保存图片到本地")
        layout.addWidget(self.save_images_checkbox)
        self.resume_download_checkbox = QCheckBox("恢复上次下载")
        layout.addWidget(self.resume_download_checkbox)

        # 保存格式选择
        save_format_layout = QHBoxLayout()
        save_format_layout.addWidget(QLabel("保存格式:"))
        self.save_format_combo = QComboBox()
        self.save_format_combo.addItems(["markdown", "html"])  # 移除 "pdf" 选项
        save_format_layout.addWidget(self.save_format_combo)
        layout.addLayout(save_format_layout)

        # 压缩为 ZIP
        self.compress_to_zip_checkbox = QCheckBox("下载完成后压缩为 ZIP")
        layout.addWidget(self.compress_to_zip_checkbox)

        # 添加新的标签来显示进度
        self.book_progress_label = QLabel("小册进度: 0/0")
        self.section_progress_label = QLabel("章节进度: 0/0")
        layout.addWidget(self.book_progress_label)
        layout.addWidget(self.section_progress_label)

        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # 控制按钮
        control_layout = QHBoxLayout()
        self.start_button = QPushButton("开始下载")
        self.start_button.clicked.connect(self.start_download)
        control_layout.addWidget(self.start_button)

        self.pause_resume_button = QPushButton("暂停")
        self.pause_resume_button.clicked.connect(self.toggle_pause_resume)
        self.pause_resume_button.setEnabled(False)
        control_layout.addWidget(self.pause_resume_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel_download)
        self.cancel_button.setEnabled(False)
        control_layout.addWidget(self.cancel_button)

        self.save_config_button = QPushButton("保存配置")
        self.save_config_button.clicked.connect(self.save_config)
        control_layout.addWidget(self.save_config_button)

        layout.addLayout(control_layout)

        # 添加即时验证
        self.cookie_input.textChanged.connect(self.validate_cookie)
        self.cookie_timer = QTimer(self)
        self.cookie_timer.setSingleShot(True)
        self.cookie_timer.timeout.connect(self.delayed_validate_cookie)

        self.save_dir_input.textChanged.connect(self.validate_save_dir)
        self.book_id_input.textChanged.connect(self.validate_book_ids)

    def setup_log_display(self, layout):
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

        self.detailed_log_display = QPlainTextEdit()
        self.detailed_log_display.setReadOnly(True)
        self.detailed_log_display.setVisible(False)
        layout.addWidget(self.detailed_log_display)

        self.toggle_detailed_log_button = QPushButton("显示详细日志")
        self.toggle_detailed_log_button.clicked.connect(self.toggle_detailed_log)
        layout.addWidget(self.toggle_detailed_log_button)

    def toggle_detailed_log(self):
        is_visible = self.detailed_log_display.isVisible()
        self.detailed_log_display.setVisible(not is_visible)
        self.toggle_detailed_log_button.setText("隐藏详细日志" if not is_visible else "显示详细日志")

    def start_download(self):
        config = self.get_config()
        if not config:
            return  # get_config 方法已经显示了错误消息

        if not self.validate_all_inputs(config):
            return

        self.save_config(config)  # 自动保存配置

        if config['resume_download']:
            self.handle_resume_download(config)

        self.download_thread = DownloadThread(config)
        self.download_thread.progress_update.connect(self.update_progress)
        self.download_thread.log_update.connect(self.update_log)
        self.download_thread.detailed_log_update.connect(self.update_detailed_log)
        self.download_thread.book_progress_update.connect(self.update_book_progress)
        self.download_thread.section_progress_update.connect(self.update_section_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.start()

        self.start_button.setEnabled(False)
        self.pause_resume_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

    def handle_resume_download(self, config):
        import json
        progress_file = os.path.join(config['save_dir'], 'download_progress.json')
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                self.processed_books = progress.get('processed_books', 0)
                self.update_progress(int(self.processed_books / len(config['book_ids']) * 100))
            except json.JSONDecodeError:
                QMessageBox.warning(self, "告", "进度文件损坏，将从头开始下。")
                self.processed_books = 0
        else:
            QMessageBox.warning(self, "警告", "没有找到上次的下载进度，将从头开始下载。")
            self.processed_books = 0

    def toggle_pause_resume(self):
        if self.download_thread.is_paused:
            self.download_thread.resume()
            self.pause_resume_button.setText("暂停")
        else:
            self.download_thread.pause()
            self.pause_resume_button.setText("继续")

    def cancel_download(self):
        if hasattr(self, 'download_thread'):
            self.download_thread.cancel()
            self.start_button.setEnabled(True)
            self.pause_resume_button.setEnabled(False)
            self.cancel_button.setEnabled(False)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_log(self, message):
        self.log_display.appendPlainText(message)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )

    def update_detailed_log(self, message):
        self.detailed_log_display.appendPlainText(message)
        self.detailed_log_display.verticalScrollBar().setValue(
            self.detailed_log_display.verticalScrollBar().maximum()
        )

    def download_finished(self):
        self.start_button.setEnabled(True)
        self.pause_resume_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        QMessageBox.information(self, "下载完成", "小册下载已完成!")

    def get_config(self):
        try:
            config = {
                'cookie': self.cookie_input.text(),
                'save_dir': self.save_dir_input.text(),
                'fetch_book_ids_online': self.fetch_online_checkbox.isChecked(),
                'overwrite_existing': self.overwrite_checkbox.isChecked(),
                'save_images_locally': self.save_images_checkbox.isChecked(),
                'book_ids': [],
                'storage': {
                    'use_vercel': False,
                    'write_to_vercel': False,
                    'local_storage_path': './data'
                },
                'resume_download': self.resume_download_checkbox.isChecked(),
                'save_format': self.save_format_combo.currentText(),
                'compress_to_zip': self.compress_to_zip_checkbox.isChecked(),
            }

            if self.single_book_radio.isChecked():
                book_ids = [id.strip() for id in self.book_id_input.text().split(',') if id.strip()]
                if not book_ids:
                    QMessageBox.warning(self, "警告", "请输入至少一个小册 ID")
                    return None
                config['book_ids'] = book_ids
                config['fetch_book_ids_online'] = False
            else:
                config['fetch_book_ids_online'] = self.fetch_online_checkbox.isChecked()

            if not config['cookie']:
                QMessageBox.warning(self, "警告", "请输入Cookie")
                return None

            if not config['save_dir']:
                QMessageBox.warning(self, "警告", "请选择保存目录")
                return None

            return config
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取配置时发生错误: {str(e)}")
            return None

    def load_config_to_ui(self):
        try:
            self.cookie_input.setText(self.config.get('cookie', ''))
            self.save_dir_input.setText(self.config.get('save_dir', ''))
            self.fetch_online_checkbox.setChecked(self.config.get('fetch_book_ids_online', False))
            self.overwrite_checkbox.setChecked(self.config.get('overwrite_existing', False))
            self.save_images_checkbox.setChecked(self.config.get('save_images_locally', False))
            if self.config.get('book_ids'):
                self.single_book_radio.setChecked(True)
                self.book_id_input.setText(','.join(self.config['book_ids']))
            else:
                self.all_books_radio.setChecked(True)
            if 'resume_download' in self.config:
                self.resume_download_checkbox.setChecked(self.config['resume_download'])
            if 'save_format' in self.config:
                index = self.save_format_combo.findText(self.config['save_format'])
                if index >= 0:
                    self.save_format_combo.setCurrentIndex(index)
            if 'compress_to_zip' in self.config:
                self.compress_to_zip_checkbox.setChecked(self.config['compress_to_zip'])
            
            self.toggle_book_id_input(self.single_book_radio.isChecked())
            self.statusBar.showMessage("配置已加载", 3000)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载配置时发生错误: {str(e)}\n将使用默认设置。")

    def save_config(self, config):
        try:
            save_config(config, self.config_path)
            self.statusBar.showMessage("配置已保存", 3000)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"保存配置时发生错误: {str(e)}")

    def closeEvent(self, event):
        if hasattr(self, 'download_thread') and self.download_thread.isRunning():
            reply = QMessageBox.question(self, '确认退出', 
                                         "下载正在进行中，确定要退出吗？",
                                         QMessageBox.StandardButton.Yes | 
                                         QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.download_thread.cancel()
                self.download_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def choose_save_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if dir_path:
            self.save_dir_input.setText(dir_path)
            self.validate_save_dir(dir_path)

    def toggle_book_id_input(self, checked):
        self.book_id_widget.setVisible(checked)
        self.fetch_online_checkbox.setEnabled(not checked)

    def validate_cookie(self):
        self.cookie_timer.start(500)  # 500ms 延迟

    def delayed_validate_cookie(self):
        cookie = self.cookie_input.text()
        if not cookie:
            self.statusBar.showMessage("请输入 Cookie", 3000)
        elif len(cookie) < 20:  # 假设有效的 Cookie 至少有 20 个字符
            self.statusBar.showMessage("Cookie 可能无效，请检查", 3000)
        else:
            self.statusBar.showMessage("Cookie 格式正确", 3000)

    def validate_save_dir(self, path):
        if not os.path.exists(path):
            self.statusBar.showMessage("所选目录不存在", 3000)
        elif not os.access(path, os.W_OK):
            self.statusBar.showMessage("所选目录没有写入权限", 3000)
        else:
            self.statusBar.showMessage("保存目录有效", 3000)

    def validate_book_ids(self):
        if self.single_book_radio.isChecked():
            book_ids = [id.strip() for id in self.book_id_input.text().split(',') if id.strip()]
            if not book_ids:
                self.statusBar.showMessage("请输入至少一个小册 ID", 3000)
            elif any(not id.isdigit() for id in book_ids):
                self.statusBar.showMessage("小册 ID 应该只包含数字", 3000)
            else:
                self.statusBar.showMessage("小册 ID 格式正确", 3000)

    def validate_all_inputs(self, config):
        if not config['cookie']:
            QMessageBox.warning(self, "警告", "请输入 Cookie")
            return False

        if not config['save_dir']:
            QMessageBox.warning(self, "警告", "请选择保存目录")
            return False

        if not os.path.exists(config['save_dir']):
            QMessageBox.warning(self, "警告", "所选保存目录不存在")
            return False

        if not os.access(config['save_dir'], os.W_OK):
            QMessageBox.warning(self, "警告", "所选保存目录没有写入权限")
            return False

        if self.single_book_radio.isChecked() and not config['book_ids']:
            QMessageBox.warning(self, "警告", "请输入至少一个小册 ID")
            return False

        return True

    def update_book_progress(self, current, total):
        self.book_progress_label.setText(f"小册进度: {current}/{total}")

    def update_section_progress(self, current, total):
        self.section_progress_label.setText(f"章节进度: {current}/{total}")

def run_gui(config_path='config.yml'):
    config = load_config(config_path)
    
    app = QApplication(sys.argv)
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    run_gui()
