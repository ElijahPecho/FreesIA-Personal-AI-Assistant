# ==============================================================================
# FreesIA - Custom GUI Application
# Clean, minimal interface with centered logo and modern design
# ==============================================================================

# Suppress console output for cleaner GUI launch
import sys
import os
if hasattr(sys, 'frozen') or os.environ.get('PYTHONW_LAUNCHER'):
    # Redirect stdout/stderr to null when running as frozen app or pythonw
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

# ==================== IMPORTS ====================
import json
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel,
                            QScrollArea, QFrame, QSplashScreen, QGraphicsOpacityEffect,
                            QMenu, QInputDialog, QCheckBox, QDialog, QComboBox, QStackedWidget,
                            QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPixmap, QIcon, QPainter, QColor, QMovie

# Import FreesIA
import importlib.util
spec = importlib.util.spec_from_file_location("project_freesia", Path(__file__).parent / "Project FreesIA.py")
project_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project_module)
FreesIA = project_module.FreesIA


# ==================== LOADING THREAD ====================

class LoadingThread(QThread):
    """Load FreesIA in background"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)
    
    def run(self):
        try:
            self.progress.emit("Initializing FreesIA...")
            assistant = FreesIA()
            self.progress.emit("Ready!")
            self.finished.emit(assistant)
        except Exception as e:
            import traceback
            error_message = f"Error: {str(e)}\n" + traceback.format_exc()
            # Log error to file
            with open(str(Path(__file__).parent / "freesia_error.log"), "w", encoding="utf-8") as f:
                f.write(error_message)
            self.progress.emit(error_message)
            self.finished.emit(None)


# ==================== SPLASH SCREEN ====================

class SplashScreen(QWidget):
    """Loading splash screen"""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set splash screen size and center it
        splash_width = 600
        splash_height = 500
        self.setFixedSize(splash_width, splash_height)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - splash_width) // 2
        y = (screen.height() - splash_height) // 2
        self.move(x, y)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo (already contains FreesIA text)
        logo_path = Path(__file__).parent / "FreesIA Logo.png"
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("margin-bottom: 40px;")
            layout.addWidget(logo_label)
        
        # Loading spinner (using text animation)
        self.spinner = QLabel("◐")
        self.spinner.setStyleSheet("""
            font-size: 32px;
            color: #6B6B6B;
        """)
        self.spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.spinner)
        
        # Loading text
        self.status_label = QLabel("Loading Assets... This might take awhile...")
        self.status_label.setStyleSheet("""
            font-size: 14px;
            color: #6B6B6B;
            margin-top: 20px;
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Style
        self.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
            }
        """)
        
        # Animate spinner
        self.spinner_chars = ['◐', '◓', '◑', '◒']
        self.spinner_index = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_spinner)
        self.timer.start(150)
    
    def update_spinner(self):
        """Animate the loading spinner"""
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
        self.spinner.setText(self.spinner_chars[self.spinner_index])
    
    def update_status(self, text):
        """Update status text"""
        self.status_label.setText(text)


# ==================== AI THREAD (STREAMING RESPONSES) ====================

class AIThread(QThread):
    """Process AI requests in background with streaming"""
    response = pyqtSignal(str)
    chunk = pyqtSignal(str)  # New signal for streaming chunks
    finished_streaming = pyqtSignal(str)  # Signal when streaming completes with full text
    
    def __init__(self, assistant, message, original_message=None):
        super().__init__()
        self.assistant = assistant
        self.message = message
        self.original_message = original_message or message  # Store original before context added
        self._is_running = True
    
    def run(self):
        try:
            if not self._is_running:
                return
            
            # Collect full response while streaming
            full_response = ""
            
            # Use original message for streaming (without context) to detect quick responses and proper model selection
            for chunk_text in self.assistant.chat_with_ai_streaming(self.message, original_message=self.original_message):
                if not self._is_running:
                    return
                full_response += chunk_text
                self.chunk.emit(chunk_text)
            
            # Emit the full response (not empty string)
            self.finished_streaming.emit(full_response)
        except Exception as e:
            self.response.emit(f"Error: {str(e)}")
# Move main() to the bottom of the file

def main():
    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()

    def on_loading_finished(assistant):
        splash.close()
        if assistant is None:
            # Show error dialog if loading failed
            error_dialog = QDialog()
            error_dialog.setWindowTitle("FreesIA - Error")
            layout = QVBoxLayout(error_dialog)
            label = QLabel("Failed to initialize FreesIA. Please check your setup.\n\nSee freesia_error.log for details.")
            layout.addWidget(label)
            # Show error details if available
            try:
                with open(str(Path(__file__).parent / "freesia_error.log"), "r", encoding="utf-8") as f:
                    error_details = f.read()
                error_box = QTextEdit()
                error_box.setReadOnly(True)
                error_box.setText(error_details)
                error_box.setMinimumHeight(200)
                layout.addWidget(error_box)
            except Exception:
                pass
            error_dialog.exec()
            sys.exit(1)
        window = MainWindow(assistant)
        window.show()

    def on_progress(status):
        splash.update_status(status)

    # Start loading
    loader = LoadingThread()
    loader.finished.connect(on_loading_finished)
    loader.progress.connect(on_progress)
    loader.start()

    sys.exit(app.exec())

# ==================== UI COMPONENTS ====================

class MessageBubble(QFrame):
    """Individual message bubble with code highlighting and copy support"""
    def __init__(self, text, is_user=False):
        super().__init__()
        self.setMaximumWidth(900)
        self.is_user = is_user
        
        # Style based on sender
        if is_user:
            self.setStyleSheet("""
                QFrame {
                    background-color: #E8E8E8;
                    border-radius: 16px;
                    padding: 12px 16px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #F0F0F0;
                    border-radius: 16px;
                    padding: 12px 16px;
                }
            """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Message text with code highlighting - using QTextEdit for better copy/paste support
        self.msg_text = QTextEdit()
        self.msg_text.setReadOnly(True)
        from PyQt6.QtGui import QTextOption
        self.msg_text.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.msg_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                color: {'#1A1A1A' if is_user else '#4A4A4A'};
                font-size: 15px;
                margin: 0px;
                padding: 0px;
            }}
            QTextEdit:focus {{
                border: none;
            }}
        """)
        # Enable text selection and copying via keyboard shortcuts
        self.msg_text.setCursor(Qt.CursorShape.IBeamCursor)
        self.set_text(text)
        layout.addWidget(self.msg_text)
    
    def set_text(self, text):
        """Set text with code block highlighting"""
        # Detect and highlight code blocks
        formatted_text = self.format_code_blocks(text)
        self.msg_text.setHtml(formatted_text)
    
    def append_text(self, text):
        """Append text for streaming (without formatting until complete)"""
        current = self.msg_text.toPlainText()
        self.msg_text.setPlainText(current + text)
    
    def format_code_blocks(self, text):
        """Format code blocks with syntax highlighting"""
        import re
        # Escape HTML first
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Match code blocks with triple backticks
        pattern = r'```([\s\S]*?)```'
        
        def replace_code(match):
            code = match.group(1).strip()
            # Detect language if specified
            lines = code.split('\n')
            lang = ''
            if lines and not ' ' in lines[0] and len(lines[0]) < 20:
                lang = lines[0]
                code = '\n'.join(lines[1:])
            
            return f'''<div style="background-color: #2D2D2D; color: #D4D4D4; 
                       padding: 12px; border-radius: 8px; margin: 8px 0; 
                       font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; 
                       white-space: pre-wrap; word-wrap: break-word;">
                       {f'<div style="color: #858585; font-size: 11px; margin-bottom: 4px;">{lang}</div>' if lang else ''}
                       {code}</div>'''
        
        text = re.sub(pattern, replace_code, text)
        
        # Match inline code with single backticks
        inline_pattern = r'`([^`]+)`'
        text = re.sub(inline_pattern, 
                     r'<code style="background-color: #E8E8E8; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 13px;">\1</code>', 
                     text)
        
        # Convert newlines to <br>
        text = text.replace('\n', '<br>')
        
        return text


class LoadingBubble(QFrame):
    """Loading indicator bubble with animated dots"""
    def __init__(self):
        super().__init__()
        self.setMaximumWidth(900)
        
        self.setStyleSheet("""
            QFrame {
                background-color: #F0F0F0;
                border-radius: 16px;
                padding: 12px 16px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Loading text with animated dots
        self.msg_label = QLabel("●")
        self.msg_label.setStyleSheet("""
            color: #4A4A4A;
            font-size: 15px;
            line-height: 1.5;
        """)
        layout.addWidget(self.msg_label)
        
        # Animate the dots
        self.dot_count = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_dots)
        self.timer.start(400)  # Update every 400ms
    
    def update_dots(self):
        """Cycle through dot animation"""
        dots = ["●", "●●", "●●●"]
        self.dot_count = (self.dot_count + 1) % len(dots)
        self.msg_label.setText(dots[self.dot_count])
    
    def stop_animation(self):
        """Stop the timer when removing the bubble"""
        if self.timer:
            self.timer.stop()


# ==================== CHAT HISTORY ITEM ====================

class ChatHistoryItem(QWidget):
    """Individual chat history item with options menu"""
    def __init__(self, chat_id, chat_name, parent_window):
        super().__init__()
        self.chat_id = chat_id
        self.chat_name = chat_name
        self.parent_window = parent_window
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Chat name button
        self.name_btn = QPushButton(chat_name)
        self.name_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1A1A1A;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #ECECEC;
            }
        """)
        self.name_btn.clicked.connect(self.load_chat)
        layout.addWidget(self.name_btn, 1)
        
        # Options button (3 dots)
        self.options_btn = QPushButton("⋮")
        self.options_btn.setFixedSize(24, 24)
        self.options_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: #6B6B6B;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ECECEC;
            }
        """)
        self.options_btn.clicked.connect(self.show_options_menu)
        layout.addWidget(self.options_btn)
    
    def load_chat(self):
        """Load this chat"""
        self.parent_window.load_chat(self.chat_id)
    
    def show_options_menu(self):
        """Show rename/delete menu"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F0F0F0;
            }
        """)
        
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec(self.options_btn.mapToGlobal(self.options_btn.rect().bottomLeft()))
        
        if action == rename_action:
            self.rename_chat()
        elif action == delete_action:
            self.delete_chat()
    
    def rename_chat(self):
        """Rename this chat"""
        new_name, ok = QInputDialog.getText(self, "Rename Chat", "Enter new name:", text=self.chat_name)
        if ok and new_name.strip():
            self.chat_name = new_name.strip()
            self.name_btn.setText(self.chat_name)
            self.parent_window.rename_chat(self.chat_id, self.chat_name)
    
    def delete_chat(self):
        """Delete this chat"""
        self.parent_window.delete_chat(self.chat_id)


class AppListItem(QWidget):
    """Individual app list item"""
    def __init__(self, app_name, icon_path=None):
        super().__init__()
        self.app_name = app_name
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # App icon
        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        
        # Try to load actual icon
        if icon_path and self.load_icon(icon_path, icon_label):
            pass  # Icon loaded successfully
        else:
            # Fallback to emoji
            icon_label.setText("📱")
            icon_label.setStyleSheet("font-size: 18px;")
            icon_label.setFixedSize(24, 24)
        
        layout.addWidget(icon_label)
        
        # App name
        name_label = QLabel(app_name)
        name_label.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 13px;
            }
        """)
        layout.addWidget(name_label, 1)
        
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-radius: 8px;
            }
            QWidget:hover {
                background-color: #F0F0F0;
            }
        """)
    
    def load_icon(self, icon_path, label):
        """Load icon from path, handling .exe and .ico files"""
        try:
            import os
            
            # Clean up icon path (remove quotes and parameters)
            icon_path = icon_path.strip('"').split(',')[0]
            
            if not os.path.exists(icon_path):
                return False
            
            # Use QIcon to load from .exe or .ico
            icon = QIcon(icon_path)
            if not icon.isNull():
                pixmap = icon.pixmap(20, 20)
                label.setPixmap(pixmap)
                label.setScaledContents(False)
                return True
            
            return False
        except:
            return False


class SettingsDialog(QDialog):
    """Settings panel popup"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(700, 500)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 12px;
            }
        """)
        
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left navigation panel
        nav_panel = QWidget()
        nav_panel.setFixedWidth(220)
        nav_panel.setStyleSheet("""
            QWidget {
                background-color: #F8F8F8;
                border-right: 1px solid #E0E0E0;
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
            }
        """)
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(8, 8, 8, 8)
        nav_layout.setSpacing(4)
        
        # Settings title
        title_label = QLabel("Settings")
        title_label.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 18px;
                font-weight: bold;
                padding: 12px 12px 8px 12px;
            }
        """)
        nav_layout.addWidget(title_label)
        
        # Navigation menu items
        self.nav_buttons = {}
        menu_items = [
            ("⚙", "General"),
            ("🎨", "Personalization"),
            ("⚡", "Shortcuts"),
            ("📱", "Apps"),
            ("🔒", "Security"),
            ("👤", "Account")
        ]
        
        for icon, text in menu_items:
            btn = self.create_nav_button(icon, text)
            nav_layout.addWidget(btn)
            self.nav_buttons[text] = btn
        
        nav_layout.addStretch()
        main_layout.addWidget(nav_panel)
        
        # Right content panel
        content_panel = QWidget()
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Header with close button
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 12, 12)
        
        header_layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #1A1A1A;
                font-size: 18px;
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: #F0F0F0;
            }
        """)
        header_layout.addWidget(close_btn)
        content_layout.addWidget(header)
        
        # Stacked widget for content pages
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("QStackedWidget { background-color: #FFFFFF; }")
        
        # Create content pages
        self.content_stack.addWidget(self.create_general_page())
        self.content_stack.addWidget(self.create_personalization_page())
        self.content_stack.addWidget(self.create_shortcuts_page())
        self.content_stack.addWidget(self.create_apps_page())
        self.content_stack.addWidget(self.create_security_page())
        self.content_stack.addWidget(self.create_placeholder_page("Account"))
        
        content_layout.addWidget(self.content_stack)
        main_layout.addWidget(content_panel, 1)
        
        # Show General page by default
        self.switch_page("General")
    
    def create_nav_button(self, icon, text):
        """Create a navigation button"""
        btn = QPushButton(f"{icon}  {text}")
        btn.setFixedHeight(40)
        btn.setCheckable(True)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #1A1A1A;
                font-size: 14px;
                text-align: left;
                padding-left: 16px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
            QPushButton:checked {
                background-color: #FFFFFF;
                font-weight: bold;
            }
        """)
        btn.clicked.connect(lambda: self.switch_page(text))
        return btn
    
    # ==================== SETTINGS PAGE NAVIGATION ====================
    
    def switch_page(self, page_name):
        """Switch to a different settings page"""
        pages = {
            "General": 0,
            "Personalization": 1,
            "Shortcuts": 2,
            "Apps": 3,
            "Security": 4,
            "Account": 5
        }
        
        if page_name in pages:
            self.content_stack.setCurrentIndex(pages[page_name])
            
            # Update button states
            for name, btn in self.nav_buttons.items():
                btn.setChecked(name == page_name)
    
    # ==================== GENERAL SETTINGS PAGE ====================
    
    def create_general_page(self):
        """Create General settings page with language selector"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)
        
        # Page title
        title = QLabel("General")
        title.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 24px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title)
        
        # Language section
        lang_container = QWidget()
        lang_layout = QVBoxLayout(lang_container)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        lang_layout.setSpacing(8)
        
        lang_label = QLabel("Language")
        lang_label.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        lang_layout.addWidget(lang_label)
        
        # Language dropdown
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "English (United States)",
            "Spanish (Spain)",
            "French (France)",
            "German (Germany)",
            "Japanese (Japan)",
            "Chinese (Simplified)",
            "Portuguese (Brazil)",
            "Korean (South Korea)",
            "Italian (Italy)",
            "Russian (Russia)"
        ])
        self.language_combo.setFixedHeight(36)
        self.language_combo.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 8px 12px;
                color: #1A1A1A;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #A0A0A0;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #1A1A1A;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                selection-background-color: #F0F0F0;
                selection-color: #1A1A1A;
                padding: 4px;
            }
        """)
        lang_layout.addWidget(self.language_combo)
        
        layout.addWidget(lang_container)
        layout.addStretch()
        
        return page
    
    # ==================== PERSONALIZATION PAGE ====================
    
    def create_personalization_page(self):
        """Create Personalization settings page with About You section"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)
        
        # Page title
        title = QLabel("Personalization")
        title.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 24px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(0, 0, 0, 0.35);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        
        # About You section
        about_section = QLabel("About You")
        about_section.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 16px;
                font-weight: bold;
                padding-top: 8px;
            }
        """)
        content_layout.addWidget(about_section)
        
        about_desc = QLabel("Tell FreesIA about yourself so it can personalize conversations")
        about_desc.setStyleSheet("""
            QLabel {
                color: #6B6B6B;
                font-size: 13px;
            }
        """)
        content_layout.addWidget(about_desc)
        
        # Nickname field
        nickname_label = QLabel("Nickname / Preferred Name")
        nickname_label.setStyleSheet("color: #1A1A1A; font-size: 13px; font-weight: bold;")
        content_layout.addWidget(nickname_label)
        
        self.nickname_input = QLineEdit()
        self.nickname_input.setPlaceholderText("What should FreesIA call you?")
        self.nickname_input.setText(self.parent().assistant.user_profile.get("nickname", ""))
        self.nickname_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1A1A1A;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #4A90E2;
            }
        """)
        content_layout.addWidget(self.nickname_input)
        
        # Occupation field
        occupation_label = QLabel("Occupation")
        occupation_label.setStyleSheet("color: #1A1A1A; font-size: 13px; font-weight: bold;")
        content_layout.addWidget(occupation_label)
        
        self.occupation_input = QLineEdit()
        self.occupation_input.setPlaceholderText("e.g., Student, Software Engineer, Artist...")
        self.occupation_input.setText(self.parent().assistant.user_profile.get("occupation", ""))
        self.occupation_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1A1A1A;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #4A90E2;
            }
        """)
        content_layout.addWidget(self.occupation_input)
        
        # Visual Description field
        visual_label = QLabel("Visual Description")
        visual_label.setStyleSheet("color: #1A1A1A; font-size: 13px; font-weight: bold;")
        content_layout.addWidget(visual_label)
        
        self.visual_input = QLineEdit()
        self.visual_input.setPlaceholderText("e.g., Brown hair, glasses, tall...")
        self.visual_input.setText(self.parent().assistant.user_profile.get("visual_description", ""))
        self.visual_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1A1A1A;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #4A90E2;
            }
        """)
        content_layout.addWidget(self.visual_input)
        
        # Likes field
        likes_label = QLabel("Likes & Interests")
        likes_label.setStyleSheet("color: #1A1A1A; font-size: 13px; font-weight: bold;")
        content_layout.addWidget(likes_label)
        
        self.likes_input = QTextEdit()
        self.likes_input.setPlaceholderText("What do you enjoy? Hobbies, music, food, activities...")
        self.likes_input.setText(self.parent().assistant.user_profile.get("likes", ""))
        self.likes_input.setMaximumHeight(80)
        self.likes_input.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1A1A1A;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 1px solid #4A90E2;
            }
        """)
        content_layout.addWidget(self.likes_input)
        
        # Dislikes field
        dislikes_label = QLabel("Dislikes")
        dislikes_label.setStyleSheet("color: #1A1A1A; font-size: 13px; font-weight: bold;")
        content_layout.addWidget(dislikes_label)
        
        self.dislikes_input = QTextEdit()
        self.dislikes_input.setPlaceholderText("Things you don't like or want to avoid...")
        self.dislikes_input.setText(self.parent().assistant.user_profile.get("dislikes", ""))
        self.dislikes_input.setMaximumHeight(80)
        self.dislikes_input.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1A1A1A;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 1px solid #4A90E2;
            }
        """)
        content_layout.addWidget(self.dislikes_input)
        
        # Other info field
        other_label = QLabel("Other Information")
        other_label.setStyleSheet("color: #1A1A1A; font-size: 13px; font-weight: bold;")
        content_layout.addWidget(other_label)
        
        self.other_input = QTextEdit()
        self.other_input.setPlaceholderText("Anything else FreesIA should remember about you...")
        self.other_input.setText(self.parent().assistant.user_profile.get("other_info", ""))
        self.other_input.setMaximumHeight(80)
        self.other_input.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1A1A1A;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 1px solid #4A90E2;
            }
        """)
        content_layout.addWidget(self.other_input)
        
        # Save button
        save_btn = QPushButton("Save Profile")
        save_btn.setFixedHeight(40)
        save_btn.clicked.connect(self.save_user_profile)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
        """)
        content_layout.addWidget(save_btn)
        
        # Relationship section
        content_layout.addSpacing(24)
        
        relationship_section = QLabel("Relationship")
        relationship_section.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 16px;
                font-weight: bold;
                padding-top: 8px;
            }
        """)
        content_layout.addWidget(relationship_section)
        
        relationship_desc = QLabel("Manage your relationship progress and memories with FreesIA")
        relationship_desc.setStyleSheet("""
            QLabel {
                color: #6B6B6B;
                font-size: 13px;
            }
        """)
        content_layout.addWidget(relationship_desc)
        
        # Reset relationship button
        reset_relationship_btn = QPushButton("Reset Relationship & Memories")
        reset_relationship_btn.setFixedHeight(40)
        reset_relationship_btn.clicked.connect(self.reset_relationship)
        reset_relationship_btn.setStyleSheet("""
            QPushButton {
                background-color: #E53935;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C62828;
            }
        """)
        content_layout.addWidget(reset_relationship_btn)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return page
    
    def save_user_profile(self):
        """Save user profile information"""
        from PyQt6.QtWidgets import QMessageBox
        
        # Update profile
        self.parent().assistant.user_profile["nickname"] = self.nickname_input.text().strip()
        self.parent().assistant.user_profile["occupation"] = self.occupation_input.text().strip()
        self.parent().assistant.user_profile["visual_description"] = self.visual_input.text().strip()
        self.parent().assistant.user_profile["likes"] = self.likes_input.toPlainText().strip()
        self.parent().assistant.user_profile["dislikes"] = self.dislikes_input.toPlainText().strip()
        self.parent().assistant.user_profile["other_info"] = self.other_input.toPlainText().strip()
        
        # Save to file
        self.parent().assistant.save_user_profile()
        
        QMessageBox.information(self, "Success", "Your profile has been saved! FreesIA will remember this information in conversations.")
    
    def reset_relationship(self):
        """Reset relationship progress and memories with confirmation dialog"""
        from PyQt6.QtWidgets import QMessageBox
        
        # Show confirmation dialog
        reply = QMessageBox.warning(
            self,
            "Reset Relationship?",
            "Are you sure you want to reset your relationship with FreesIA?\n\n"
            "This will:\n"
            "• Erase all relationship progress\n"
            "• Delete all shared memories\n"
            "• Reset to Level 1 (Strangers)\n\n"
            "This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Reset relationship
            self.parent().assistant.relationship_manager.reset()
            QMessageBox.information(
                self,
                "Relationship Reset",
                "Your relationship with FreesIA has been reset to a brand new start."
            )
    
    # ==================== SHORTCUTS PAGE ====================
    
    def create_shortcuts_page(self):
        """Create Shortcuts settings page for custom command shortcuts"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)
        
        # Page title
        title = QLabel("Custom Shortcuts")
        title.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 24px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title)
        
        # Description
        desc = QLabel("Create custom shortcuts to execute multiple commands at once")
        desc.setStyleSheet("""
            QLabel {
                color: #6B6B6B;
                font-size: 13px;
            }
        """)
        layout.addWidget(desc)
        
        # Scroll area for shortcuts list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(0, 0, 0, 0.35);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        
        # List existing shortcuts
        shortcuts = self.parent().assistant.custom_shortcuts
        if shortcuts:
            for name, actions in shortcuts.items():
                shortcut_widget = self.create_shortcut_widget(name, actions)
                content_layout.addWidget(shortcut_widget)
        else:
            no_shortcuts = QLabel("No custom shortcuts yet. Create one below!")
            no_shortcuts.setStyleSheet("color: #9B9B9B; font-size: 13px; padding: 16px;")
            content_layout.addWidget(no_shortcuts)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        
        # Add new shortcut section
        layout.addSpacing(8)
        
        add_section = QLabel("Create New Shortcut")
        add_section.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        layout.addWidget(add_section)
        
        # Shortcut name input
        name_label = QLabel("Shortcut Name")
        name_label.setStyleSheet("color: #1A1A1A; font-size: 13px; font-weight: bold;")
        layout.addWidget(name_label)
        
        self.shortcut_name_input = QLineEdit()
        self.shortcut_name_input.setPlaceholderText("e.g., work, gaming, morning...")
        self.shortcut_name_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1A1A1A;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #4A90E2;
            }
        """)
        layout.addWidget(self.shortcut_name_input)
        
        # Actions input
        actions_label = QLabel("Actions (one per line)")
        actions_label.setStyleSheet("color: #1A1A1A; font-size: 13px; font-weight: bold;")
        layout.addWidget(actions_label)
        
        self.shortcut_actions_input = QTextEdit()
        self.shortcut_actions_input.setPlaceholderText("open chrome\nopen spotify\ncheck weather")
        self.shortcut_actions_input.setMaximumHeight(100)
        self.shortcut_actions_input.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px 12px;
                color: #1A1A1A;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 1px solid #4A90E2;
            }
        """)
        layout.addWidget(self.shortcut_actions_input)
        
        # Create shortcut button
        create_btn = QPushButton("Create Shortcut")
        create_btn.setFixedHeight(40)
        create_btn.clicked.connect(self.create_shortcut)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
        """)
        layout.addWidget(create_btn)
        
        return page
    
    def create_shortcut_widget(self, name, actions):
        """Create a widget displaying a shortcut"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #F8F8F8;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        
        # Header with name and delete button
        header_layout = QHBoxLayout()
        
        name_label = QLabel(f"⚡ {name}")
        name_label.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        header_layout.addWidget(name_label)
        
        header_layout.addStretch()
        
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(24, 24)
        delete_btn.clicked.connect(lambda: self.delete_shortcut(name))
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #E74C3C;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #FFE5E5;
                border-radius: 4px;
            }
        """)
        header_layout.addWidget(delete_btn)
        
        layout.addLayout(header_layout)
        
        # Actions list
        actions_text = "\n".join([f"  • {action}" for action in actions])
        actions_label = QLabel(actions_text)
        actions_label.setStyleSheet("""
            QLabel {
                color: #6B6B6B;
                font-size: 12px;
            }
        """)
        layout.addWidget(actions_label)
        
        return widget
    
    def create_shortcut(self):
        """Create a new shortcut from inputs"""
        name = self.shortcut_name_input.text().strip()
        actions_text = self.shortcut_actions_input.toPlainText().strip()
        
        if not name or not actions_text:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please provide both a shortcut name and at least one action."
            )
            return
        
        # Parse actions (one per line)
        actions = [action.strip() for action in actions_text.split('\n') if action.strip()]
        
        # Add shortcut
        self.parent().assistant.add_shortcut(name, actions)
        
        # Clear inputs
        self.shortcut_name_input.clear()
        self.shortcut_actions_input.clear()
        
        # Refresh the page
        self.refresh_shortcuts_page()
        
        QMessageBox.information(
            self,
            "Shortcut Created",
            f"Shortcut '{name}' created with {len(actions)} action(s)!\n\nUse it by saying: '{name}' or 'run {name}'"
        )
    
    def delete_shortcut(self, name):
        """Delete a shortcut"""
        reply = QMessageBox.question(
            self,
            "Delete Shortcut",
            f"Are you sure you want to delete the '{name}' shortcut?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.parent().assistant.remove_shortcut(name)
            self.refresh_shortcuts_page()
    
    def refresh_shortcuts_page(self):
        """Refresh the shortcuts page to show updated list"""
        # Recreate the shortcuts page
        new_page = self.create_shortcuts_page()
        # Replace the old page in the stack
        self.content_stack.removeWidget(self.content_stack.widget(2))
        self.content_stack.insertWidget(2, new_page)
        # Keep showing the shortcuts page
        self.content_stack.setCurrentIndex(2)
    
    # ==================== APPS PAGE ====================
    
    def create_apps_page(self):
        """Create Apps settings page with installed applications list"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)
        
        # Page title
        title = QLabel("Apps")
        title.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 24px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Installed applications")
        subtitle.setStyleSheet("""
            QLabel {
                color: #6B6B6B;
                font-size: 13px;
            }
        """)
        layout.addWidget(subtitle)
        
        # Scroll area for apps list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(0, 0, 0, 0.35);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        
        # Container for apps
        apps_container = QWidget()
        apps_layout = QVBoxLayout(apps_container)
        apps_layout.setContentsMargins(0, 0, 0, 0)
        apps_layout.setSpacing(2)
        
        # Get installed applications
        apps = self.get_installed_apps()
        
        if apps:
            for app_name, icon_path in apps:
                app_item = AppListItem(app_name, icon_path)
                apps_layout.addWidget(app_item)
        else:
            no_apps = QLabel("No applications found")
            no_apps.setStyleSheet("""
                QLabel {
                    color: #6B6B6B;
                    font-size: 13px;
                    padding: 16px;
                }
            """)
            apps_layout.addWidget(no_apps)
        
        apps_layout.addStretch()
        scroll.setWidget(apps_container)
        layout.addWidget(scroll)
        
        return page
    
    # ==================== SECURITY PAGE ====================
    
    def create_security_page(self):
        """Create Security settings page with all security features"""
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)
        
        # Page title
        title = QLabel("Security")
        title.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: #24px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title)
        
        # Scroll area for all security settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(0, 0, 0, 0.35);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)
        
        # 1. PERMISSIONS MANAGEMENT
        perm_section = self.create_section_label("Permissions")
        content_layout.addWidget(perm_section)
        
        # File Access Permission
        file_perm_widget = self.create_permission_toggle(
            "File Access",
            "Allow FreesIA to search, read, and manage files",
            "file_access"
        )
        content_layout.addWidget(file_perm_widget)
        
        # System Settings Permission
        system_perm_widget = self.create_permission_toggle(
            "System Settings",
            "Allow FreesIA to adjust volume, brightness, and screenshots",
            "system_settings"
        )
        content_layout.addWidget(system_perm_widget)
        
        # Power Control Permission
        power_perm_widget = self.create_permission_toggle(
            "Power Control",
            "Allow FreesIA to lock, sleep, shutdown, or restart",
            "power_control"
        )
        content_layout.addWidget(power_perm_widget)
        
        # 2. PRIVACY CONTROLS
        privacy_section = self.create_section_label("Privacy Controls")
        content_layout.addWidget(privacy_section)
        
        # Save Chat History Toggle
        chat_history_widget = self.create_setting_toggle(
            "Save Chat History",
            "Store conversations for future reference",
            "save_chat_history"
        )
        content_layout.addWidget(chat_history_widget)
        
        # Keep AI Context Toggle
        ai_context_widget = self.create_setting_toggle(
            "Keep AI Context",
            "Remember conversation context between sessions",
            "keep_ai_context"
        )
        content_layout.addWidget(ai_context_widget)
        
        # Clear Chat History Button
        clear_chat_btn = QPushButton("Clear All Chat History")
        clear_chat_btn.setFixedHeight(36)
        clear_chat_btn.clicked.connect(self.clear_all_chat_history)
        clear_chat_btn.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 8px 16px;
                color: #1A1A1A;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
        """)
        content_layout.addWidget(clear_chat_btn)
        
        # Clear AI Memory Button
        clear_ai_btn = QPushButton("Clear AI Conversation Memory")
        clear_ai_btn.setFixedHeight(36)
        clear_ai_btn.clicked.connect(self.clear_ai_memory)
        clear_ai_btn.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 8px 16px;
                color: #1A1A1A;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
        """)
        content_layout.addWidget(clear_ai_btn)
        
        # 3. APPLICATION SECURITY
        app_security_section = self.create_section_label("Application Security")
        content_layout.addWidget(app_security_section)
        
        # PIN Protection Toggle
        pin_widget = QWidget()
        pin_layout = QHBoxLayout(pin_widget)
        pin_layout.setContentsMargins(0, 0, 0, 0)
        
        pin_info = QWidget()
        pin_info_layout = QVBoxLayout(pin_info)
        pin_info_layout.setContentsMargins(0, 0, 0, 0)
        pin_info_layout.setSpacing(2)
        
        pin_label = QLabel("PIN Protection")
        pin_label.setStyleSheet("color: #1A1A1A; font-size: 14px; font-weight: bold;")
        pin_info_layout.addWidget(pin_label)
        
        pin_desc = QLabel("Require PIN to access FreesIA")
        pin_desc.setStyleSheet("color: #6B6B6B; font-size: 12px;")
        pin_info_layout.addWidget(pin_desc)
        
        pin_layout.addWidget(pin_info, 1)
        
        self.pin_checkbox = QCheckBox()
        self.pin_checkbox.setChecked(self.parent().assistant.security_settings.get("pin_enabled", False))
        self.pin_checkbox.stateChanged.connect(self.toggle_pin_protection)
        self.pin_checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #D0D0D0;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #4A90E2;
                border-color: #4A90E2;
            }
        """)
        pin_layout.addWidget(self.pin_checkbox)
        
        content_layout.addWidget(pin_widget)
        
        # Command Logging Toggle
        logging_widget = self.create_setting_toggle(
            "Command Logging",
            "Keep an audit log of executed commands",
            "command_logging"
        )
        content_layout.addWidget(logging_widget)
        
        # 4. COMMAND AUDIT LOG
        audit_section = self.create_section_label("Command Audit Log")
        content_layout.addWidget(audit_section)
        
        # View Command Log Button
        view_log_btn = QPushButton("View Command History")
        view_log_btn.setFixedHeight(36)
        view_log_btn.clicked.connect(self.view_command_log)
        view_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 8px 16px;
                color: #1A1A1A;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
        """)
        content_layout.addWidget(view_log_btn)
        
        # Export Command Log Button
        export_log_btn = QPushButton("Export Command Log")
        export_log_btn.setFixedHeight(36)
        export_log_btn.clicked.connect(self.export_command_log)
        export_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 8px 16px;
                color: #1A1A1A;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
        """)
        content_layout.addWidget(export_log_btn)
        
        # Clear Command Log Button
        clear_log_btn = QPushButton("Clear Command Log")
        clear_log_btn.setFixedHeight(36)
        clear_log_btn.clicked.connect(self.clear_command_log)
        clear_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 8px 16px;
                color: #1A1A1A;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
        """)
        content_layout.addWidget(clear_log_btn)
        
        # 5. DATA MANAGEMENT
        data_section = self.create_section_label("Data Management")
        content_layout.addWidget(data_section)
        
        # Export All Data Button
        export_data_btn = QPushButton("Export All Personal Data")
        export_data_btn.setFixedHeight(36)
        export_data_btn.clicked.connect(self.export_all_data)
        export_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 8px 16px;
                color: #1A1A1A;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
        """)
        content_layout.addWidget(export_data_btn)
        
        # Delete All Data Button (Factory Reset)
        delete_data_btn = QPushButton("Delete All Data (Factory Reset)")
        delete_data_btn.setFixedHeight(36)
        delete_data_btn.clicked.connect(self.factory_reset)
        delete_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFE8E8;
                border: 1px solid #FFCCCC;
                border-radius: 8px;
                padding: 8px 16px;
                color: #CC0000;
                font-size: 13px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #FFD0D0;
            }
        """)
        content_layout.addWidget(delete_data_btn)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return page
    
    def create_section_label(self, text):
        """Create a section header label"""
        label = QLabel(text)
        label.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 16px;
                font-weight: bold;
                padding-top: 8px;
            }
        """)
        return label
    
    def create_permission_toggle(self, name, description, permission_type):
        """Create a permission toggle widget"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 8)
        
        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #1A1A1A; font-size: 14px; font-weight: bold;")
        info_layout.addWidget(name_label)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #6B6B6B; font-size: 12px;")
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)
        
        layout.addWidget(info, 1)
        
        checkbox = QCheckBox()
        checkbox.setChecked(self.parent().assistant.permissions.get(permission_type, False))
        checkbox.stateChanged.connect(lambda state: self.toggle_permission(permission_type, state == 2))
        checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #D0D0D0;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #4A90E2;
                border-color: #4A90E2;
            }
        """)
        layout.addWidget(checkbox)
        
        return widget
    
    def create_setting_toggle(self, name, description, setting_key):
        """Create a security setting toggle widget"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 8)
        
        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #1A1A1A; font-size: 14px; font-weight: bold;")
        info_layout.addWidget(name_label)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #6B6B6B; font-size: 12px;")
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)
        
        layout.addWidget(info, 1)
        
        checkbox = QCheckBox()
        checkbox.setChecked(self.parent().assistant.security_settings.get(setting_key, True))
        checkbox.stateChanged.connect(lambda state: self.toggle_security_setting(setting_key, state == 2))
        checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #D0D0D0;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #4A90E2;
                border-color: #4A90E2;
            }
        """)
        layout.addWidget(checkbox)
        
        return widget
    
    def toggle_permission(self, permission_type, enabled):
        """Toggle a permission"""
        self.parent().assistant.toggle_permission(permission_type, enabled)
    
    def toggle_security_setting(self, setting_key, enabled):
        """Toggle a security setting"""
        self.parent().assistant.security_settings[setting_key] = enabled
        self.parent().assistant.save_security_settings()
    
    def toggle_pin_protection(self, state):
        """Toggle PIN protection"""
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        
        if state == 2:  # Enabled
            pin, ok = QInputDialog.getText(self, "Set PIN", "Enter a 4-digit PIN:", QLineEdit.EchoMode.Password)
            if ok and pin:
                if len(pin) >= 4:
                    confirm_pin, ok = QInputDialog.getText(self, "Confirm PIN", "Re-enter PIN:", QLineEdit.EchoMode.Password)
                    if ok and pin == confirm_pin:
                        self.parent().assistant.set_pin(pin)
                        QMessageBox.information(self, "Success", "PIN protection enabled")
                    else:
                        QMessageBox.warning(self, "Error", "PINs do not match")
                        self.pin_checkbox.setChecked(False)
                else:
                    QMessageBox.warning(self, "Error", "PIN must be at least 4 characters")
                    self.pin_checkbox.setChecked(False)
            else:
                self.pin_checkbox.setChecked(False)
        else:  # Disabled
            self.parent().assistant.disable_pin()
            QMessageBox.information(self, "Success", "PIN protection disabled")
    
    def clear_all_chat_history(self):
        """Clear all chat history"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self, "Clear Chat History",
            "Are you sure you want to delete all chat history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Clear chat history files
            chat_dir = Path(__file__).parent / "ChatHistory"
            if chat_dir.exists():
                for file in chat_dir.glob("*.json"):
                    file.unlink()
            QMessageBox.information(self, "Success", "All chat history has been deleted")
    
    def clear_ai_memory(self):
        """Clear AI conversation memory"""
        from PyQt6.QtWidgets import QMessageBox
        
        self.parent().assistant.clear_ai_history()
        QMessageBox.information(self, "Success", "AI conversation memory cleared")
    
    def view_command_log(self):
        """View command audit log"""
        from PyQt6.QtWidgets import QDialog, QTextEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Command Audit Log")
        dialog.setFixedSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        log = self.parent().assistant.get_command_log()
        if log:
            log_text = ""
            for entry in reversed(log):  # Most recent first
                log_text += f"[{entry['timestamp']}]\n"
                log_text += f"Command: {entry['command']}\n"
                log_text += f"Result: {entry['result']}\n\n"
            text_edit.setPlainText(log_text)
        else:
            text_edit.setPlainText("No commands logged yet")
        
        layout.addWidget(text_edit)
        dialog.exec()
    
    def export_command_log(self):
        """Export command log"""
        from PyQt6.QtWidgets import QMessageBox
        
        result = self.parent().assistant.export_command_log()
        QMessageBox.information(self, "Export Complete", result)
    
    def clear_command_log(self):
        """Clear command log"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self, "Clear Command Log",
            "Are you sure you want to clear the command log?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.parent().assistant.clear_command_log()
            QMessageBox.information(self, "Success", "Command log cleared")
    
    def export_all_data(self):
        """Export all personal data"""
        from PyQt6.QtWidgets import QMessageBox
        
        result = self.parent().assistant.export_all_data()
        QMessageBox.information(self, "Export Complete", result)
    
    def factory_reset(self):
        """Delete all data (factory reset)"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.warning(
            self, "Factory Reset",
            "⚠️ WARNING: This will delete ALL personal data including:\n\n"
            "• All permissions\n"
            "• Security settings and PIN\n"
            "• Command log\n"
            "• AI conversation history\n\n"
            "This action cannot be undone. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = self.parent().assistant.delete_all_data()
            QMessageBox.information(self, "Factory Reset Complete", result)
    
    def create_placeholder_page(self, page_name):
        """Create a placeholder page for unimplemented sections"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)
        
        # Page title
        title = QLabel(page_name)
        title.setStyleSheet("""
            QLabel {
                color: #1A1A1A;
                font-size: 24px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title)
        layout.addStretch()
        
        return page
    
    def get_installed_apps(self):
        """Get list of installed applications from Windows with their icons"""
        apps = []
        try:
            import winreg
            import os
            
            # Check both 64-bit and 32-bit registry locations
            registry_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
            ]
            
            seen_apps = set()
            
            for hkey, path in registry_paths:
                try:
                    key = winreg.OpenKey(hkey, path)
                    for i in range(0, winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            try:
                                app_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                
                                # Try to get icon path
                                icon_path = None
                                try:
                                    icon_path = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                                except:
                                    # If no DisplayIcon, try to get from InstallLocation + exe
                                    try:
                                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                        if install_location and os.path.isdir(install_location):
                                            # Look for .exe files in install location
                                            for file in os.listdir(install_location):
                                                if file.lower().endswith('.exe'):
                                                    icon_path = os.path.join(install_location, file)
                                                    break
                                    except:
                                        pass
                                
                                # Filter out system components and duplicates
                                if app_name and len(app_name) > 1 and app_name not in seen_apps:
                                    if not any(x in app_name.lower() for x in ['update', 'hotfix', 'security', 'kb']):
                                        seen_apps.add(app_name)
                                        apps.append((app_name, icon_path))
                            except:
                                pass
                            winreg.CloseKey(subkey)
                        except:
                            continue
                    winreg.CloseKey(key)
                except:
                    continue
            
            # Sort alphabetically by app name
            apps.sort(key=lambda x: x[0])
            
        except Exception as e:
            print(f"Error getting installed apps: {e}")
        
        return apps


# ==============================================================================
# MAIN WINDOW
# ==============================================================================

class MainWindow(QMainWindow):
    def __init__(self, assistant=None):
        super().__init__()
        self.assistant = assistant
        self.thread = None
        self.loading_bubble_widget = None  # Track loading bubble
        
        # Chat history management
        self.chat_dir = Path(__file__).parent / "ChatHistory"
        self.chat_dir.mkdir(exist_ok=True)
        self.current_chat_id = None
        self.current_chat_messages = []  # List of {"role": "user"/"ai", "content": "..."}
        self.chat_history_layout = None  # Will store the history layout for adding items
        self._chat_count_cache = None  # Cache for chat count
        self._chat_metadata_cache = {}  # Cache for chat metadata {chat_id: {name, created_at}}
        
        # Sidebar state
        self.sidebar_visible = True
        self.sidebar_animation = None
        
        self.init_ui()
    
    # ==================== WINDOW INITIALIZATION ====================
    
    def init_ui(self):
        self.setWindowTitle("FreesIA")
                # Set window icon (taskbar and title bar)
        icon_path = Path(__file__).parent / "FreesIA Icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
                # Set window size (1400x900) and center on screen
        self.setGeometry(100, 100, 1400, 900)
        
        # Center window on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 1400) // 2
        y = (screen.height() - 900) // 2
        self.move(x, y)
        
        # Main container
        main_container = QWidget()
        self.setCentralWidget(main_container)
        main_layout = QHBoxLayout(main_container)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create overlay widget for dimming background (hidden by default)
        self.overlay = QWidget(main_container)
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        self.overlay.setGeometry(main_container.rect())
        self.overlay.hide()
        self.overlay.raise_()
        
        # Sidebar
        self.create_sidebar(main_layout)
        
        # Main content area
        self.create_main_area(main_layout)
        
        # Apply global styles
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #FFFFFF;
                color: #1A1A1A;
            }
        """)
    
    # ==================== SIDEBAR (CHAT HISTORY) ====================
    
    def get_chat_count(self):
        """Get total number of chats (cached)"""
        if self._chat_count_cache is None:
            self._chat_count_cache = len(list(self.chat_dir.glob('*.json')))
        return self._chat_count_cache
    
    def increment_chat_count(self):
        """Increment chat count cache when creating new chat"""
        if self._chat_count_cache is None:
            self._chat_count_cache = len(list(self.chat_dir.glob('*.json')))
        self._chat_count_cache += 1
    
    def decrement_chat_count(self):
        """Decrement chat count cache when deleting a chat"""
        if self._chat_count_cache is None:
            self._chat_count_cache = len(list(self.chat_dir.glob('*.json')))
        else:
            self._chat_count_cache = max(0, self._chat_count_cache - 1)
    
    def create_sidebar(self, parent_layout):
        """Create left sidebar"""
        self.sidebar = QFrame()
        self.sidebar.setMinimumWidth(0)  # Allow collapsing to 0
        self.sidebar.setMaximumWidth(260)  # Default max width
        
        # Set size policy to prevent unwanted resizing
        size_policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.sidebar.setSizePolicy(size_policy)
        
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #F5F5F5;
                border-right: 1px solid #E0E0E0;
            }
        """)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(12)
        
        # Header with collapse button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        self.sidebar_header = QLabel("Chat History")
        self.sidebar_header.setStyleSheet("""
            color: #6B6B6B;
            font-size: 13px;
            font-weight: 500;
            padding: 8px 12px;
        """)
        header_layout.addWidget(self.sidebar_header)
        
        # Collapse button (in sidebar)
        self.collapse_btn = QPushButton("◀")
        self.collapse_btn.setFixedSize(28, 28)
        self.collapse_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #6B6B6B;
                font-size: 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ECECEC;
            }
        """)
        self.collapse_btn.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.collapse_btn)
        
        sidebar_layout.addLayout(header_layout)
        
        # Chat history scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        history_widget = QWidget()
        self.chat_history_layout = QVBoxLayout(history_widget)
        self.chat_history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_history_layout.setSpacing(4)
        scroll.setWidget(history_widget)
        
        # Load existing chats
        self.load_all_chats()
        
        sidebar_layout.addWidget(scroll, 1)
        
        # New Chat button at bottom
        new_chat_btn = QPushButton("+ New Chat")
        new_chat_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
                padding: 12px;
                color: #1A1A1A;
                font-size: 14px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #ECECEC;
            }
        """)
        new_chat_btn.clicked.connect(self.create_new_chat)
        sidebar_layout.addWidget(new_chat_btn)
        
        # Bottom icons (user profile and settings)
        bottom_icons_layout = QHBoxLayout()
        
        # User profile icon
        self.user_icon = QPushButton()
        user_icon_path = Path(__file__).parent / "Icons" / "UserProfileLogo.png"
        if user_icon_path.exists():
            self.user_icon.setIcon(QIcon(str(user_icon_path)))
            self.user_icon.setIconSize(QSize(24, 24))
        self.user_icon.setFixedSize(36, 36)
        self.user_icon.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #ECECEC;
            }
        """)
        bottom_icons_layout.addWidget(self.user_icon)
        
        # Settings icon at bottom
        self.settings_icon = QPushButton()
        settings_icon_path = Path(__file__).parent / "Icons" / "settingsLogo.png"
        if settings_icon_path.exists():
            self.settings_icon.setIcon(QIcon(str(settings_icon_path)))
            self.settings_icon.setIconSize(QSize(24, 24))
        self.settings_icon.setFixedSize(36, 36)
        self.settings_icon.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #ECECEC;
            }
        """)
        self.settings_icon.clicked.connect(self.show_settings)
        bottom_icons_layout.addWidget(self.settings_icon)
        bottom_icons_layout.addStretch()
        
        sidebar_layout.addLayout(bottom_icons_layout)
        
        parent_layout.addWidget(self.sidebar)
    
    # ==================== MAIN CHAT AREA ====================
    
    def create_main_area(self, parent_layout):
        """Create main content area"""
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(0)
        
        # Expand sidebar button (shown when sidebar is collapsed)
        self.expand_btn = QPushButton("☰")
        self.expand_btn.setFixedSize(36, 36)
        self.expand_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                color: #1A1A1A;
                font-size: 16px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #ECECEC;
            }
        """)
        self.expand_btn.clicked.connect(self.toggle_sidebar)
        self.expand_btn.hide()  # Hidden by default
        
        # Position expand button at top-left
        expand_container = QHBoxLayout()
        expand_container.addWidget(self.expand_btn)
        expand_container.addStretch()
        main_layout.addLayout(expand_container)
        
        # Chat display area (scrollable)
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 0, 0, 0.15);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(0, 0, 0, 0.3);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        
        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chat_layout.setSpacing(24)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        
        # Initial centered welcome screen
        self.welcome_container = QWidget()
        welcome_layout = QVBoxLayout(self.welcome_container)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo (already contains FreesIA text)
        logo_path = Path(__file__).parent / "FreesIA Logo.png"
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(800, 800, Qt.AspectRatioMode.KeepAspectRatio, 
                                         Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Super faint transparency (15% opacity)
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0.15)
            logo_label.setGraphicsEffect(opacity_effect)
            welcome_layout.addWidget(logo_label)
        
        # Add suggested prompts
        prompts_container = QWidget()
        prompts_layout = QVBoxLayout(prompts_container)
        prompts_layout.setSpacing(12)
        prompts_layout.setContentsMargins(0, 20, 0, 0)
        
        prompts_title = QLabel("Try asking:")
        prompts_title.setStyleSheet("""
            color: #6B6B6B;
            font-size: 13px;
            font-weight: bold;
        """)
        prompts_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompts_layout.addWidget(prompts_title)
        
        # Suggested prompts
        suggested_prompts = [
            "What's the weather like today?",
            "Help me debug this Python code",
            "Explain quantum computing simply",
            "Open my favorite app"
        ]
        
        for prompt_text in suggested_prompts:
            prompt_btn = QPushButton(prompt_text)
            prompt_btn.setFixedHeight(40)
            prompt_btn.setMaximumWidth(350)
            prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            prompt_btn.setStyleSheet("""
                QPushButton {
                    background-color: #F8F8F8;
                    border: 1px solid #E0E0E0;
                    border-radius: 20px;
                    padding: 8px 20px;
                    color: #4A4A4A;
                    font-size: 13px;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #ECECEC;
                    border-color: #D0D0D0;
                }
            """)
            prompt_btn.clicked.connect(lambda checked, p=prompt_text: self.use_suggested_prompt(p))
            prompts_layout.addWidget(prompt_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        welcome_layout.addWidget(prompts_container)
        
        self.chat_layout.addWidget(self.welcome_container)
        
        self.chat_scroll.setWidget(self.chat_widget)
        main_layout.addWidget(self.chat_scroll, 1)
        
        # Input area at bottom
        self.create_input_area(main_layout)
        
        parent_layout.addWidget(main_area, 1)
    
    # ==================== INPUT AREA ====================
    
    def create_input_area(self, parent_layout):
        """Create bottom input area"""
        input_container = QWidget()
        input_container.setMaximumWidth(1100)
        input_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 20, 0, 0)
        input_layout.setSpacing(0)
        
        # Input wrapper for border and styling
        input_wrapper = QFrame()
        input_wrapper.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 24px;
            }
        """)
        
        wrapper_layout = QHBoxLayout(input_wrapper)
        wrapper_layout.setContentsMargins(20, 12, 12, 12)
        wrapper_layout.setSpacing(8)
        
        # Attachment icon (optional)
        self.attach_btn = QPushButton()
        attach_icon_path = Path(__file__).parent / "Icons" / "ImageLogo.png"
        if attach_icon_path.exists():
            self.attach_btn.setIcon(QIcon(str(attach_icon_path)))
            self.attach_btn.setIconSize(QSize(20, 20))
        self.attach_btn.setFixedSize(32, 32)
        self.attach_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #F0F0F0;
                border-radius: 16px;
            }
        """)
        wrapper_layout.addWidget(self.attach_btn)
        
        # Mic icon (optional)
        self.mic_btn = QPushButton()
        mic_icon_path = Path(__file__).parent / "Icons" / "MicLogo.png"
        if mic_icon_path.exists():
            self.mic_btn.setIcon(QIcon(str(mic_icon_path)))
            self.mic_btn.setIconSize(QSize(20, 20))
        self.mic_btn.setFixedSize(32, 32)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #F0F0F0;
                border-radius: 16px;
            }
        """)

        self.mic_btn.clicked.connect(self.handle_mic_button)
        wrapper_layout.addWidget(self.mic_btn)

        # Text input
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Type 'Help' for more commands...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: none;
                font-size: 15px;
                color: #1A1A1A;
                padding: 4px;
            }
            QLineEdit::placeholder {
                color: #9B9B9B;
            }
        """)
        self.input_box.returnPressed.connect(self.send_message)
        wrapper_layout.addWidget(self.input_box, 1)
        # Send button
        self.send_btn = QPushButton()
        send_icon_path = Path(__file__).parent / "Icons" / "SendLogo.png"
        if send_icon_path.exists():
            self.send_btn.setIcon(QIcon(str(send_icon_path)))
            self.send_btn.setIconSize(QSize(22, 22))
        self.send_btn.setFixedSize(40, 40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #D0D0D0;
                border: none;
                border-radius: 20px;
                color: #FFFFFF;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B0B0B0;
            }
            QPushButton:disabled {
                background-color: #E8E8E8;
                color: #C0C0C0;
            }
        """)
        self.send_btn.clicked.connect(self.send_message)
        wrapper_layout.addWidget(self.send_btn)
        input_layout.addWidget(input_wrapper)
        # Center the input container
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(input_container)
        bottom_layout.addStretch()
        parent_layout.addLayout(bottom_layout)

    def handle_mic_button(self):
        """Handle mic button click: start voice recognition"""
        if hasattr(self, 'assistant') and self.assistant:
            self.assistant.start_listening_background()
            # Optionally, show feedback in the chat
            self.add_ai_message("Listening...")
        else:
            self.add_ai_message("Assistant not ready.")
        
        # Text input
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Type 'Help' for more commands...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: none;
                font-size: 15px;
                color: #1A1A1A;
                padding: 4px;
            }
            QLineEdit::placeholder {
                color: #9B9B9B;
            }
        """)
        self.input_box.returnPressed.connect(self.send_message)
        wrapper_layout.addWidget(self.input_box, 1)
        
        # Send button
        self.send_btn = QPushButton()
        send_icon_path = Path(__file__).parent / "Icons" / "SendLogo.png"
        if send_icon_path.exists():
            self.send_btn.setIcon(QIcon(str(send_icon_path)))
            self.send_btn.setIconSize(QSize(22, 22))
        self.send_btn.setFixedSize(40, 40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #D0D0D0;
                border: none;
                border-radius: 20px;
                color: #FFFFFF;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B0B0B0;
            }
            QPushButton:disabled {
                background-color: #E8E8E8;
                color: #C0C0C0;
            }
        """)
        self.send_btn.clicked.connect(self.send_message)
        wrapper_layout.addWidget(self.send_btn)
        
        input_layout.addWidget(input_wrapper)
        
        # Center the input container
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(input_container)
        bottom_layout.addStretch()
        
        parent_layout.addLayout(bottom_layout)
    
    def new_chat(self):
        """Start a new chat"""
        # Stop any running AI thread
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(1000)  # Wait up to 1 second for thread to finish
            if self.thread.isRunning():
                self.thread.terminate()  # Force terminate if still running
        
        # Remove loading bubble if exists
        if self.loading_bubble_widget and self.loading_bubble_widget.parent():
            loading_layout = self.loading_bubble_widget.layout()
            if loading_layout:
                loading_item = loading_layout.itemAt(0)
                if loading_item and loading_item.widget():
                    loading_widget = loading_item.widget()
                    if isinstance(loading_widget, LoadingBubble):
                        loading_widget.stop_animation()
            self.loading_bubble_widget.deleteLater()
            self.loading_bubble_widget = None
        
        # Re-enable input
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        
        # Clear messages
        while self.chat_layout.count():
            child = self.chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Switch back to center alignment for welcome screen
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Show welcome screen again
        self.welcome_container = QWidget()
        welcome_layout = QVBoxLayout(self.welcome_container)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        logo_path = Path(__file__).parent / "FreesIA Logo.png"
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(800, 800, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Super faint transparency (15% opacity)
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0.15)
            logo_label.setGraphicsEffect(opacity_effect)
            welcome_layout.addWidget(logo_label)
        
        self.chat_layout.addWidget(self.welcome_container)
    
    # ==================== MESSAGE PROCESSING ====================
    
    def is_system_command(self, text: str) -> bool:
        """Check if text is a system command (not a conversation)"""
        text_lower = text.lower().strip()
        
        # Command keywords that indicate system commands
        command_keywords = [
            # Apps
            'open ', 'close ', 'launch ', 'start ',
            # System
            'volume', 'brightness', 'screenshot', 'battery', 'system info',
            'lock', 'sleep', 'restart', 'shutdown',
            # Files
            'find ', 'search ', 'create folder', 'recent files',
            # Web/Time
            'weather', 'what time', 'what date', 'open website',
            # Media
            'media play', 'media pause', 'media next', 'media previous', 'media stop',
            # Settings
            'wifi', 'bluetooth', 'control panel',
            # Apps list
            'list apps', 'show apps',
            # Mic/TTS
            'mic on', 'mic off', 'tts on', 'tts off', 'toggle tts',
            # Permissions
            'show permissions', 'revoke permissions',
            # AI management
            'clear ai history', 'clear conversation', 'reload personality', 'change model', 'switch model',
            # Shortcuts
            'create shortcut', 'add shortcut', 'remove shortcut', 'delete shortcut',
            'list shortcuts', 'show shortcuts', 'my shortcuts',
            'run ', 'execute ',
            # Help
            'help', 'command', 'what can you do'
        ]
        
        # Check if text starts with or contains command keywords
        return any(text_lower.startswith(keyword) or keyword in text_lower for keyword in command_keywords)
    
    def send_message(self):
        """Send user message with context awareness"""
        text = self.input_box.text().strip()
        if not text:
            return
        
        # Prevent sending if AI is already responding
        if self.thread and self.thread.isRunning():
            return
        
        # Add context awareness to message
        context = self.assistant.get_active_window_context()
        message_with_context = f"{context}\n{text}" if context else text
        
        # Create new chat if none exists
        if not self.current_chat_id:
            self.current_chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_chat_messages = []
            
            # Create initial chat file
            chat_name = f"Chat {self.get_chat_count() + 1}"
            chat_data = {
                "id": self.current_chat_id,
                "name": chat_name,
                "created_at": datetime.now().isoformat(),
                "messages": []
            }
            
            chat_file = self.chat_dir / f"{self.current_chat_id}.json"
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)
            
            # Increment cache after creating
            self.increment_chat_count()
            
            # Cache metadata
            self._chat_metadata_cache[self.current_chat_id] = {
                "name": chat_name,
                "created_at": chat_data["created_at"]
            }
            
            # Add to sidebar (at the top)
            chat_item = ChatHistoryItem(self.current_chat_id, chat_name, self)
            self.chat_history_layout.insertWidget(0, chat_item)
        
        # Keep welcome screen/logo visible, just switch to top alignment for messages
        if self.welcome_container and self.welcome_container.parent():
            # Switch to top alignment for messages but keep logo
            self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Track message in current chat (without context)
        self.current_chat_messages.append({"role": "user", "content": text})
        
        # Add user message (align right)
        user_bubble = MessageBubble(text, is_user=True)
        bubble_container = QHBoxLayout()
        bubble_container.addStretch()
        bubble_container.addWidget(user_bubble)
        
        container_widget = QWidget()
        container_widget.setLayout(bubble_container)
        self.chat_layout.addWidget(container_widget)
        
        self.input_box.clear()
        self.input_box.setEnabled(False)
        self.send_btn.setEnabled(False)
        
        # Scroll to bottom
        self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        )
        
        # Add loading bubble (align left like AI messages)
        loading_bubble = LoadingBubble()
        bubble_container = QHBoxLayout()
        bubble_container.addWidget(loading_bubble)
        bubble_container.addStretch()
        
        self.loading_bubble_widget = QWidget()
        self.loading_bubble_widget.setLayout(bubble_container)
        self.chat_layout.addWidget(self.loading_bubble_widget)
        
        # Scroll to show loading bubble
        self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        )
        
        # Check if this is a system command (handle directly without AI for speed)
        if self.is_system_command(text):
            # Process command directly (instant execution)
            command_result = self.assistant.process_command(text)
            
            # Remove loading bubble
            if self.loading_bubble_widget and self.loading_bubble_widget.parent():
                loading_layout = self.loading_bubble_widget.layout()
                if loading_layout:
                    loading_item = loading_layout.itemAt(0)
                    if loading_item and loading_item.widget():
                        loading_widget = loading_item.widget()
                        if isinstance(loading_widget, LoadingBubble):
                            loading_widget.stop_animation()
                self.loading_bubble_widget.deleteLater()
                self.loading_bubble_widget = None
            
            # Display command result if returned (for help/list commands)
            if command_result:
                self.current_chat_messages.append({"role": "ai", "content": command_result})
                self.save_current_chat()
                
                ai_bubble = MessageBubble(command_result, is_user=False)
                bubble_container = QHBoxLayout()
                bubble_container.addWidget(ai_bubble)
                bubble_container.addStretch()
                
                container_widget = QWidget()
                container_widget.setLayout(bubble_container)
                self.chat_layout.addWidget(container_widget)
                
                # Scroll to bottom
                self.chat_scroll.verticalScrollBar().setValue(
                    self.chat_scroll.verticalScrollBar().maximum()
                )
            else:
                # Command was executed but returned nothing
                # Provide context-aware feedback with A2 personality
                text_lower = text.lower()
                if 'open' in text_lower:
                    ack_message = "...Opening."
                elif 'close' in text_lower:
                    ack_message = "...Closing."
                elif 'volume' in text_lower or 'brightness' in text_lower:
                    ack_message = "Adjusted."
                elif 'screenshot' in text_lower:
                    ack_message = "Screenshot saved."
                elif any(word in text_lower for word in ['lock', 'sleep', 'restart', 'shutdown']):
                    ack_message = "Executing."
                elif 'shortcut' in text_lower:
                    ack_message = "Done."
                else:
                    ack_message = "Done."
                
                self.current_chat_messages.append({"role": "ai", "content": ack_message})
                self.save_current_chat()
                
                ai_bubble = MessageBubble(ack_message, is_user=False)
                bubble_container = QHBoxLayout()
                bubble_container.addWidget(ai_bubble)
                bubble_container.addStretch()
                
                container_widget = QWidget()
                container_widget.setLayout(bubble_container)
                self.chat_layout.addWidget(container_widget)
                
                # Scroll to bottom
                self.chat_scroll.verticalScrollBar().setValue(
                    self.chat_scroll.verticalScrollBar().maximum()
                )
            
            # Re-enable input
            self.input_box.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.input_box.setFocus()
            return
        
        # Get AI response with streaming
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(500)
        
        # Pass both message with context and original message (for quick response detection)
        self.thread = AIThread(self.assistant, message_with_context, original_message=text)
        self.thread.response.connect(self.add_ai_message)
        self.thread.chunk.connect(self.handle_ai_chunk)
        self.thread.finished_streaming.connect(self.finalize_ai_message)
        self.thread.finished.connect(self.enable_input)
        self.thread.start()
        
        # Prepare for streaming
        self.streaming_bubble = None
    
    def add_ai_message(self, text):
        """Add AI response message (fallback for non-streaming)"""
        # Remove loading bubble if it exists
        if self.loading_bubble_widget and self.loading_bubble_widget.parent():
            # Stop the animation timer
            loading_layout = self.loading_bubble_widget.layout()
            if loading_layout:
                loading_item = loading_layout.itemAt(0)
                if loading_item and loading_item.widget():
                    loading_widget = loading_item.widget()
                    if isinstance(loading_widget, LoadingBubble):
                        loading_widget.stop_animation()
            self.loading_bubble_widget.deleteLater()
            self.loading_bubble_widget = None
        try:
            # Track message in current chat
            self.current_chat_messages.append({"role": "ai", "content": text})
            self.save_current_chat()  # Auto-save after each AI response
            ai_bubble = MessageBubble(text, is_user=False)
        except Exception as e:
            import traceback
            error_msg = f"AI error: {str(e)}\n" + traceback.format_exc()
            # Log error to file
            with open(str(Path(__file__).parent / "freesia_error.log"), "a", encoding="utf-8") as f:
                f.write(error_msg + "\n")
            ai_bubble = MessageBubble("[AI Error] " + str(e), is_user=False)
        bubble_container = QHBoxLayout()
        bubble_container.addWidget(ai_bubble)
        bubble_container.addStretch()
        container_widget = QWidget()
        container_widget.setLayout(bubble_container)
        self.chat_layout.addWidget(container_widget)
        # Scroll to bottom
        self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        )
    
    def handle_ai_chunk(self, chunk):
        """Handle streaming AI response chunks"""
        try:
            # Remove loading bubble on first chunk
            if self.loading_bubble_widget and self.loading_bubble_widget.parent():
                loading_layout = self.loading_bubble_widget.layout()
                if loading_layout:
                    loading_item = loading_layout.itemAt(0)
                    if loading_item and loading_item.widget():
                        loading_widget = loading_item.widget()
                        if isinstance(loading_widget, LoadingBubble):
                            loading_widget.stop_animation()
                self.loading_bubble_widget.deleteLater()
                self.loading_bubble_widget = None

            # Create bubble on first chunk
            if not self.streaming_bubble:
                self.streaming_bubble = MessageBubble("", is_user=False)
                bubble_container = QHBoxLayout()
                bubble_container.addWidget(self.streaming_bubble)
                bubble_container.addStretch()

                container_widget = QWidget()
                container_widget.setLayout(bubble_container)
                self.chat_layout.addWidget(container_widget)

            # Append chunk to bubble
            self.streaming_bubble.append_text(chunk)

            # Scroll to bottom
            self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            )
        except Exception as e:
            import traceback
            error_msg = f"[AI Streaming Error] {str(e)}\n" + traceback.format_exc()
            # Log error to file
            with open("freesia_error.log", "a", encoding="utf-8") as f:
                f.write(error_msg + "\n")
            # Show error in chat
            ai_bubble = MessageBubble("[AI Error] " + str(e), is_user=False)
            bubble_container = QHBoxLayout()
            bubble_container.addWidget(ai_bubble)
            bubble_container.addStretch()
            container_widget = QWidget()
            container_widget.setLayout(bubble_container)
            self.chat_layout.addWidget(container_widget)
            self.streaming_bubble = None
            self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            )
    
    def finalize_ai_message(self, full_text):
        """Finalize streaming AI message - keep bubble intact with accumulated text."""
        try:
            # Don't overwrite bubble - it already has all the streamed chunks!
            # Just finalize the history tracking
            
            # Track message in current chat (accumulate all chunks)
            self.current_chat_messages.append({"role": "ai", "content": full_text})
            self.save_current_chat()
            
            # Reset streaming bubble for next message
            self.streaming_bubble = None
            
            # Scroll to bottom
            self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            )
        except Exception as e:
            import traceback
            error_msg = f"[AI Finalize Error] {str(e)}\n" + traceback.format_exc()
            with open("freesia_error.log", "a", encoding="utf-8") as f:
                f.write(error_msg + "\n")
            ai_bubble = MessageBubble("[AI Error] " + str(e), is_user=False)
            bubble_container = QHBoxLayout()
            bubble_container.addWidget(ai_bubble)
            bubble_container.addStretch()
            container_widget = QWidget()
            container_widget.setLayout(bubble_container)
            self.chat_layout.addWidget(container_widget)
            self.streaming_bubble = None
            self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            )
    
    def use_suggested_prompt(self, prompt):
        """Use a suggested prompt"""
        self.input_box.setText(prompt)
        self.send_message()
    
    def load_all_chats(self):
        """Load all saved chats from ChatHistory folder and display them"""
        if not self.chat_dir.exists():
            return
        
        # Get all JSON files sorted by modification time (newest first)
        chat_files = sorted(self.chat_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        for chat_file in chat_files:
            try:
                with open(chat_file, 'r', encoding='utf-8') as f:
                    chat_data = json.load(f)
                    chat_id = chat_data.get("id", chat_file.stem)
                    chat_name = chat_data.get("name", f"Chat {chat_id}")
                    
                    # Add chat to sidebar
                    chat_item = ChatHistoryItem(chat_id, chat_name, self)
                    self.chat_history_layout.addWidget(chat_item)
            except Exception as e:
                print(f"Error loading chat {chat_file}: {e}")
    
    # ==================== SIDEBAR TOGGLE ====================
    
    def toggle_sidebar(self):
        """Toggle sidebar visibility with animation"""
        # Stop any ongoing animation
        if self.sidebar_animation and self.sidebar_animation.state() == QPropertyAnimation.State.Running:
            self.sidebar_animation.stop()
        
        # Create animation
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.sidebar_animation.setDuration(200)  # 200ms for smooth animation
        self.sidebar_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        if self.sidebar_visible:
            # Collapse sidebar
            self.sidebar_animation.setStartValue(260)
            self.sidebar_animation.setEndValue(0)
            self.sidebar_animation.finished.connect(lambda: self.sidebar.setVisible(False))
            self.collapse_btn.hide()
            self.expand_btn.show()
            self.sidebar_visible = False
        else:
            # Expand sidebar
            self.sidebar.setVisible(True)
            self.sidebar_animation.setStartValue(0)
            self.sidebar_animation.setEndValue(260)
            self.collapse_btn.show()
            self.expand_btn.hide()
            self.sidebar_visible = True
        
        self.sidebar_animation.start()
    
    # ==================== CHAT OPERATIONS ====================
    
    def create_new_chat(self):
        """Create a new chat"""
        # Prevent creating new chat while AI is responding
        if self.thread and self.thread.isRunning():
            return
        
        # Save current chat if exists
        if self.current_chat_id and self.current_chat_messages:
            self.save_current_chat()
        
        # Generate new chat ID using Chat_N format for readable filenames
        chat_number = self.get_chat_count() + 1
        self.current_chat_id = f"Chat_{chat_number}"
        self.current_chat_messages = []
        
        # Clear the chat area
        self.new_chat()
        
        # Create initial chat file
        chat_name = f"Chat {chat_number}"
        chat_data = {
            "id": self.current_chat_id,
            "name": chat_name,
            "created_at": datetime.now().isoformat(),
            "messages": []
        }
        
        chat_file = self.chat_dir / f"{self.current_chat_id}.json"
        with open(chat_file, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=2, ensure_ascii=False)
        
        # Increment cache after creating
        self.increment_chat_count()
        
        # Cache metadata
        self._chat_metadata_cache[self.current_chat_id] = {
            "name": chat_name,
            "created_at": chat_data["created_at"]
        }
        
        # Add to sidebar (at the top)
        chat_item = ChatHistoryItem(self.current_chat_id, chat_name, self)
        self.chat_history_layout.insertWidget(0, chat_item)
    
    def load_chat(self, chat_id):
        """Load a specific chat by ID"""
        # Prevent loading chat while AI is responding
        if self.thread and self.thread.isRunning():
            return
        
        # Save current chat first
        if self.current_chat_id and self.current_chat_messages:
            self.save_current_chat()
        
        chat_file = self.chat_dir / f"{chat_id}.json"
        if not chat_file.exists():
            return
        
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            self.current_chat_id = chat_id
            self.current_chat_messages = chat_data.get("messages", [])
            
            # Clear chat area
            while self.chat_layout.count():
                child = self.chat_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # If no messages, show welcome screen
            if not self.current_chat_messages:
                self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.welcome_container = QWidget()
                welcome_layout = QVBoxLayout(self.welcome_container)
                welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                logo_path = Path(__file__).parent / "FreesIA Logo.png"
                if logo_path.exists():
                    logo_label = QLabel()
                    pixmap = QPixmap(str(logo_path))
                    scaled_pixmap = pixmap.scaled(800, 800, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
                    logo_label.setPixmap(scaled_pixmap)
                    logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    opacity_effect = QGraphicsOpacityEffect()
                    opacity_effect.setOpacity(0.15)
                    logo_label.setGraphicsEffect(opacity_effect)
                    welcome_layout.addWidget(logo_label)
                
                self.chat_layout.addWidget(self.welcome_container)
            else:
                # Display all messages
                self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                
                for msg in self.current_chat_messages:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    
                    if role == "user":
                        bubble = MessageBubble(content, is_user=True)
                        bubble_container = QHBoxLayout()
                        bubble_container.addStretch()
                        bubble_container.addWidget(bubble)
                    else:  # AI message
                        bubble = MessageBubble(content, is_user=False)
                        bubble_container = QHBoxLayout()
                        bubble_container.addWidget(bubble)
                        bubble_container.addStretch()
                    
                    container_widget = QWidget()
                    container_widget.setLayout(bubble_container)
                    self.chat_layout.addWidget(container_widget)
                
                # Scroll to bottom
                self.chat_scroll.verticalScrollBar().setValue(
                    self.chat_scroll.verticalScrollBar().maximum()
                )
        
        except Exception as e:
            print(f"Error loading chat {chat_id}: {e}")
    
    def save_current_chat(self):
        """Save the current chat to file"""
        if not self.current_chat_id:
            return
        
        chat_file = self.chat_dir / f"{self.current_chat_id}.json"
        
        try:
            # Use cached metadata if available
            if self.current_chat_id in self._chat_metadata_cache:
                chat_data = {
                    "id": self.current_chat_id,
                    "name": self._chat_metadata_cache[self.current_chat_id]["name"],
                    "created_at": self._chat_metadata_cache[self.current_chat_id]["created_at"]
                }
            else:
                # Load from file if not cached
                if chat_file.exists():
                    with open(chat_file, 'r', encoding='utf-8') as f:
                        chat_data = json.load(f)
                else:
                    chat_data = {
                        "id": self.current_chat_id,
                        "name": f"Chat {self.get_chat_count()}",
                        "created_at": datetime.now().isoformat()
                    }
                
                # Cache it for next time
                self._chat_metadata_cache[self.current_chat_id] = {
                    "name": chat_data["name"],
                    "created_at": chat_data["created_at"]
                }
            
            # Update messages
            chat_data["messages"] = self.current_chat_messages
            chat_data["updated_at"] = datetime.now().isoformat()
            
            # Save to file
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            print(f"Error saving chat: {e}")
    
    def rename_chat(self, chat_id, new_name):
        """Rename a chat"""
        chat_file = self.chat_dir / f"{chat_id}.json"
        if not chat_file.exists():
            return
        
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            chat_data["name"] = new_name
            
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)
            
            # Update cache
            if chat_id in self._chat_metadata_cache:
                self._chat_metadata_cache[chat_id]["name"] = new_name
        
        except Exception as e:
            print(f"Error renaming chat: {e}")
    
    def delete_chat(self, chat_id):
        """Delete a chat"""
        chat_file = self.chat_dir / f"{chat_id}.json"
        
        try:
            if chat_file.exists():
                chat_file.unlink()
            
            # Decrement chat count cache
            self.decrement_chat_count()
            
            # Remove from metadata cache
            if chat_id in self._chat_metadata_cache:
                del self._chat_metadata_cache[chat_id]
            
            # Remove from sidebar
            for i in range(self.chat_history_layout.count()):
                item = self.chat_history_layout.itemAt(i)
                if item:
                    widget = item.widget()
                    if isinstance(widget, ChatHistoryItem) and widget.chat_id == chat_id:
                        # Remove from layout first, then delete
                        self.chat_history_layout.removeWidget(widget)
                        widget.setParent(None)
                        widget.deleteLater()
                        break
            
            # If this was the current chat, start a new one
            if self.current_chat_id == chat_id:
                self.create_new_chat()
        
        except Exception as e:
            print(f"Error deleting chat: {e}")
    
    # ==================== SETTINGS DIALOG ====================
    
    def show_settings(self):
        """Show settings dialog with dimmed background"""
        # Update overlay size and show it
        self.overlay.setGeometry(self.centralWidget().rect())
        self.overlay.show()
        self.overlay.raise_()
        
        settings_dialog = SettingsDialog(self)
        # Center the dialog on the main window
        parent_center = self.rect().center()
        dialog_rect = settings_dialog.rect()
        dialog_rect.moveCenter(parent_center)
        settings_dialog.move(self.mapToGlobal(dialog_rect.topLeft()))
        
        # Show dialog and hide overlay when done
        settings_dialog.exec()
        self.overlay.hide()
    
    # ==================== UTILITY METHODS ====================
    
    def enable_input(self):
        """Re-enable input after response"""
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_box.setFocus()
    
    def resizeEvent(self, event):
        """Handle window resize to update overlay size"""
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(self.centralWidget().rect())


# ==============================================================================
# APPLICATION ENTRY POINT
# ==============================================================================

def main():
    app = QApplication(sys.argv)
    
    # Set app-wide font
    font = QFont("Inter", 10)
    app.setFont(font)
    
    # Show splash screen
    splash = SplashScreen()
    splash.show()
    app.processEvents()
    
    # Load FreesIA in background
    main_window = None
    
    def on_loading_finished(assistant):
        nonlocal main_window
        if assistant:
            # Create and show main window
            main_window = MainWindow(assistant)
            main_window.show()
            splash.close()
        else:
            splash.update_status("Failed to load. Please restart.")
    
    def on_progress(status):
        splash.update_status(status)
    
    # Start loading
    loader = LoadingThread()
    loader.finished.connect(on_loading_finished)
    loader.progress.connect(on_progress)
    loader.start()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
