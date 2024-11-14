import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QSpinBox, QComboBox, QTextEdit, QGroupBox, QInputDialog, QDialog, QDialogButtonBox, QGridLayout)
from PyQt6.QtCore import QThread, pyqtSignal
import json
from ticket import MelonTicket
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
import time

class PreLoginBot(QThread):
    """预先登录线程"""
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(bool, object)  # 改为object类型
    
    def __init__(self, username, password, browser_type, browser_path, driver_path):
        super().__init__()
        self.username = username
        self.password = password
        self.browser_type = browser_type
        self.browser_path = browser_path
        self.driver_path = driver_path
        
    def run(self):
        bot = None
        try:
            self.log_signal.emit("开始预先登录...")
            bot = MelonTicket(self.browser_type, self.browser_path, self.driver_path)
            
            if bot.login(self.username, self.password):
                self.log_signal.emit("预先登录成功！")
                self.status_signal.emit(True, bot)
                bot = None  # 防止finally中关闭浏览器
            else:
                self.log_signal.emit("预先登录失败！")
                self.status_signal.emit(False, bot)  # 传入bot而不是None
        except Exception as e:
            self.log_signal.emit(f"预先登录出错: {str(e)}")
            self.status_signal.emit(False, bot)  # 传入bot而不是None
        # finally:
        #     if bot:  # 只在失败时关闭浏览器
        #         try:
        #             bot.driver.quit()
        #         except:
        #             pass

class TicketBot(QThread):
    # 定义信号
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    
    def __init__(self, config, existing_bot=None):
        super().__init__()
        self.config = config
        self.existing_bot = existing_bot  # 保存已登录的实例
        
    def run(self):
        try:
            if self.existing_bot:
                bot = self.existing_bot
                self.log_signal.emit("使用已登录的会话...")
            else:
                bot = MelonTicket(
                    self.config['browser_type'],
                    self.config['browser_path'],
                    self.config['driver_path'],
                    tesseract_path=self.config['tesseract_path'],
                    captcha_mode=self.config['captcha_mode'],
                    parent=self
                )
                self.log_signal.emit("开始登录...")
                if not bot.login(self.config['username'], self.config['password']):
                    raise Exception("登录失败")
                self.log_signal.emit("登录成功！")
            
            if bot.select_performance(self.config['prod_id']):
                self.log_signal.emit(f"成功进入演出页面 ID: {self.config['prod_id']}")
                self.log_signal.emit("开始抢票...")
                
                retry_count = 0
                max_retries = 3
                
                while not self.isInterruptionRequested():
                    try:
                        # 检查是否有票
                        if bot.check_available_tickets():
                            self.log_signal.emit("发现可用票务！")
                            if bot.book_ticket(
                                self.config['date_index'],
                                self.config['time_index']
                            ):
                                self.log_signal.emit("抢票成功！")
                                break
                        
                        # 没有票，刷新页面
                        self.log_signal.emit("当前无票，继续刷新...")
                        bot.driver.refresh()
                        time.sleep(self.config['refresh_interval'])
                        retry_count = 0  # 重置重试计数
                        
                    except Exception as e:
                        retry_count += 1
                        self.log_signal.emit(f"刷新出错 (尝试 {retry_count}/{max_retries}): {str(e)}")
                        if retry_count >= max_retries:
                            self.log_signal.emit("达到最大重试次数，重新初始化...")
                            # 重新进入演出页面
                            bot.select_performance(self.config['prod_id'])
                            retry_count = 0
                        time.sleep(self.config['refresh_interval'] * 2)
                        
        except Exception as e:
            self.log_signal.emit(f"发生错误: {str(e)}")
        finally:
            pass

class TicketGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.ticket_bot = None
        self.load_config()
        
    def initUI(self):
        """初始化UI"""
        self.setWindowTitle('Melon Ticket 抢票助手')
        self.setGeometry(300, 300, 800, 600)
        
        # 创建主窗口部件和布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建左右分栏布局
        split_layout = QHBoxLayout()
        
        # 左侧设置面板
        left_panel = QVBoxLayout()
        
        # 1. 浏览器设置组
        browser_group = QGroupBox("浏览器设置")
        browser_layout = QGridLayout()
        
        browser_type_label = QLabel("浏览器类型:")
        self.browser_type = QComboBox()
        self.browser_type.addItems(["Firefox", "Chrome"])
        
        browser_path_label = QLabel("浏览器路径:")
        self.browser_path_input = QLineEdit()
        self.browser_path_button = QPushButton("浏览...")
        
        driver_path_label = QLabel("Driver路径:")
        self.driver_path_input = QLineEdit()
        self.driver_path_button = QPushButton("浏览...")
        
        browser_layout.addWidget(browser_type_label, 0, 0)
        browser_layout.addWidget(self.browser_type, 0, 1, 1, 2)
        browser_layout.addWidget(browser_path_label, 1, 0)
        browser_layout.addWidget(self.browser_path_input, 1, 1)
        browser_layout.addWidget(self.browser_path_button, 1, 2)
        browser_layout.addWidget(driver_path_label, 2, 0)
        browser_layout.addWidget(self.driver_path_input, 2, 1)
        browser_layout.addWidget(self.driver_path_button, 2, 2)
        
        browser_group.setLayout(browser_layout)
        
        # 2. OCR设置组
        ocr_group = QGroupBox("OCR设置")
        ocr_layout = QGridLayout()
        
        tesseract_path_label = QLabel("Tesseract路径:")
        self.tesseract_path_input = QLineEdit()
        self.tesseract_path_button = QPushButton("浏览...")
        
        captcha_mode_label = QLabel("验证码模式:")
        self.captcha_mode = QComboBox()
        self.captcha_mode.addItems(["手动识别", "自动识别"])
        
        ocr_layout.addWidget(tesseract_path_label, 0, 0)
        ocr_layout.addWidget(self.tesseract_path_input, 0, 1)
        ocr_layout.addWidget(self.tesseract_path_button, 0, 2)
        ocr_layout.addWidget(captcha_mode_label, 1, 0)
        ocr_layout.addWidget(self.captcha_mode, 1, 1, 1, 2)
        
        ocr_group.setLayout(ocr_layout)
        
        # 3. 账号设置组
        account_group = QGroupBox("账号设置")
        account_layout = QGridLayout()
        
        username_label = QLabel("用户名:")
        self.username_input = QLineEdit()
        password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        account_layout.addWidget(username_label, 0, 0)
        account_layout.addWidget(self.username_input, 0, 1, 1, 2)
        account_layout.addWidget(password_label, 1, 0)
        account_layout.addWidget(self.password_input, 1, 1, 1, 2)
        
        # 预先登录状态和按钮
        pre_login_layout = QHBoxLayout()
        self.pre_login_status = QLabel("未登录")
        self.pre_login_status.setStyleSheet("color: #f44336;")
        self.pre_login_button = QPushButton("预先登录")
        pre_login_layout.addWidget(self.pre_login_status)
        pre_login_layout.addWidget(self.pre_login_button)
        account_layout.addLayout(pre_login_layout, 2, 0, 1, 3)
        
        account_group.setLayout(account_layout)
        
        # 4. 票务设置组
        ticket_group = QGroupBox("票务设置")
        ticket_layout = QGridLayout()
        
        prod_id_label = QLabel("演出ID:")
        self.prod_id_input = QLineEdit()
        
        refresh_label = QLabel("刷新间隔(秒):")
        self.refresh_input = QSpinBox()
        self.refresh_input.setRange(1, 10)
        
        date_index_label = QLabel("日期序号:")
        self.date_index_input = QSpinBox()
        self.date_index_input.setRange(1, 10)
        
        time_index_label = QLabel("时间序号:")
        self.time_index_input = QSpinBox()
        self.time_index_input.setRange(1, 10)
        
        ticket_layout.addWidget(prod_id_label, 0, 0)
        ticket_layout.addWidget(self.prod_id_input, 0, 1, 1, 2)
        ticket_layout.addWidget(refresh_label, 1, 0)
        ticket_layout.addWidget(self.refresh_input, 1, 1, 1, 2)
        ticket_layout.addWidget(date_index_label, 2, 0)
        ticket_layout.addWidget(self.date_index_input, 2, 1, 1, 2)
        ticket_layout.addWidget(time_index_label, 3, 0)
        ticket_layout.addWidget(self.time_index_input, 3, 1, 1, 2)
        
        ticket_group.setLayout(ticket_layout)
        
        # 添加所有设置组到左侧面板
        left_panel.addWidget(browser_group)
        left_panel.addWidget(ocr_group)
        left_panel.addWidget(account_group)
        left_panel.addWidget(ticket_group)
        left_panel.addStretch()
        
        # 右侧日志面板
        right_panel = QVBoxLayout()
        
        # 日志显示区
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        
        # 控制按钮区
        control_layout = QHBoxLayout()
        self.start_button = QPushButton("开始抢票")
        self.stop_button = QPushButton("停止抢票")
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        
        right_panel.addWidget(log_group)
        right_panel.addLayout(control_layout)
        
        # 将左右面板添加到分栏布局
        split_layout.addLayout(left_panel, 1)  # 1是拉伸因子
        split_layout.addLayout(right_panel, 1)
        
        # 添加分栏布局到主布局
        main_layout.addLayout(split_layout)
        
        # 设置主布局
        main_widget.setLayout(main_layout)
        
        # 添加状态栏
        self.statusBar()
        
        # 连接信号和槽
        self.browser_path_button.clicked.connect(
            lambda: self.select_file(self.browser_path_input, "选择浏览器执行文件", "Executable (*.exe)")
        )
        self.driver_path_button.clicked.connect(
            lambda: self.select_file(self.driver_path_input, "选择Driver执行文件", "Executable (*.exe)")
        )
        self.tesseract_path_button.clicked.connect(
            lambda: self.select_file(self.tesseract_path_input, "选择Tesseract执行文件", "Executable (*.exe)")
        )
        self.pre_login_button.clicked.connect(self.pre_login)
        self.start_button.clicked.connect(self.start_ticket)
        self.stop_button.clicked.connect(self.stop_ticket)
        
    def load_config(self):
        try:
            with open('ticket_config.json', 'r') as f:
                config = json.load(f)
                # 添加浏览器设置的加载
                self.browser_type.setCurrentText(config.get('browser_type', 'Firefox'))
                self.browser_path_input.setText(config.get('browser_path', ''))
                self.driver_path_input.setText(config.get('driver_path', ''))
                self.username_input.setText(config.get('username', ''))
                self.password_input.setText(config.get('password', ''))
                self.prod_id_input.setText(config.get('prod_id', ''))
                self.refresh_input.setValue(config.get('refresh_interval', 1))
                self.date_index_input.setValue(config.get('date_index', 1))
                self.time_index_input.setValue(config.get('time_index', 1))
                self.captcha_mode.setCurrentText(config.get('captcha_mode', 'manual'))
                self.tesseract_path_input.setText(config.get('tesseract_path', ''))
                self.captcha_mode.setCurrentText(
                    "自动识别" if config.get('captcha_mode') == 'auto' else "手动识别"
                )
        except FileNotFoundError:
            pass
            
    def save_config(self):
        config = {
            'browser_type': self.browser_type.currentText(),
            'browser_path': self.browser_path_input.text(),
            'driver_path': self.driver_path_input.text(),
            'username': self.username_input.text(),
            'password': self.password_input.text(),
            'prod_id': self.prod_id_input.text(),
            'refresh_interval': self.refresh_input.value(),
            'date_index': self.date_index_input.value(),
            'time_index': self.time_index_input.value(),
            'captcha_mode': 'auto' if self.captcha_mode.currentText() == "自动识别" else 'manual',
            'tesseract_path': self.tesseract_path_input.text(),
            'captcha_mode': 'auto' if self.captcha_mode.currentText() == "自动识别" else 'manual'
        }
        
        with open('ticket_config.json', 'w') as f:
            json.dump(config, f)
        self.log_text.append("配置已保存")
        
    def pre_login(self):
        """预先登录功能"""
        config = {
            'username': self.username_input.text(),
            'password': self.password_input.text(),
            'browser_type': self.browser_type.currentText(),
            'browser_path': self.browser_path_input.text(),
            'driver_path': self.driver_path_input.text()
        }
        
        self.pre_login_button.setEnabled(False)
        
        # 创建预先登录线程
        self.pre_login_bot = PreLoginBot(
            config['username'], 
            config['password'],
            config['browser_type'],
            config['browser_path'],
            config['driver_path']
        )
        self.pre_login_bot.log_signal.connect(self.update_log)
        self.pre_login_bot.status_signal.connect(self.handle_pre_login_result)
        self.pre_login_bot.start()
    
    def handle_pre_login_result(self, success, bot):
        """处理预先登录结果"""
        if success:
            self.logged_in_bot = bot
            self.pre_login_status.setText("已登录")
            self.pre_login_status.setStyleSheet("color: #4CAF50;")
            self.pre_login_button.setText("重新登录")
        else:
            self.pre_login_status.setText("未登录")
            self.pre_login_status.setStyleSheet("color: #f44336;")
            self.logged_in_bot = None
            
        self.pre_login_button.setEnabled(True)
        
    def start_ticket(self):
        """开始抢票"""
        config = {
            'username': self.username_input.text(),
            'password': self.password_input.text(),
            'browser_type': self.browser_type.currentText(),
            'browser_path': self.browser_path_input.text(),
            'driver_path': self.driver_path_input.text(),
            'prod_id': self.prod_id_input.text(),
            'refresh_interval': self.refresh_input.value(),
            'date_index': self.date_index_input.value(),
            'time_index': self.time_index_input.value(),
            'captcha_mode': 'auto' if self.captcha_mode.currentText() == "自动识别" else 'manual',
            'tesseract_path': self.tesseract_path_input.text()
        }
        
        # 如果已经预先登录，使用已登录的实例
        if self.logged_in_bot:
            # 更新验证码设置
            self.logged_in_bot.captcha_mode = config['captcha_mode']
            self.logged_in_bot.tesseract_path = config['tesseract_path']
            self.ticket_bot = TicketBot(config, self.logged_in_bot)
            self.logged_in_bot = None  # 转移所有权
        else:
            self.ticket_bot = TicketBot(config)
            
        self.ticket_bot.log_signal.connect(self.update_log)
        self.ticket_bot.status_signal.connect(self.update_status)
        self.ticket_bot.start()
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pre_login_button.setEnabled(False)
        
    def stop_ticket(self):
        if self.ticket_bot:
            self.ticket_bot.requestInterruption()
            self.ticket_bot.wait()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.pre_login_button.setEnabled(True)
            self.pre_login_status.setText("未登录")
            self.pre_login_status.setStyleSheet("color: #f44336;")
            
    def update_log(self, message):
        self.log_text.append(message)
        
    def update_status(self, status):
        self.statusBar().showMessage(status)
    
    def select_file(self, input_field, title, file_filter):
        """文件选择对话框"""
        from PyQt6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if filename:
            input_field.setText(filename)

class CaptchaDialog(QDialog):
    def __init__(self, img_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("验证码")
        layout = QVBoxLayout()
        
        # 显示验证码图片
        label = QLabel()
        pixmap = QPixmap(img_path)
        label.setPixmap(pixmap)
        layout.addWidget(label)
        
        # 输入框
        self.input = QLineEdit()
        layout.addWidget(self.input)
        
        # 确认按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_input(self):
        return self.input.text()

def show_captcha_dialog(self, img_path):
    """显示验证码输入对话框"""
    dialog = CaptchaDialog(img_path, self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_input()
    return None

def main():
    app = QApplication(sys.argv)
    gui = TicketGUI()
    gui.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
