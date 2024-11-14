import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
import os
from PyQt6.QtCore import QMetaObject, Q_ARG, Qt
import pytesseract
from PIL import Image
import cv2
import numpy as np
import base64
import re

class MelonTicket:
    def __init__(self, browser_type, browser_path, driver_path, tesseract_path=None, captcha_mode="manual", parent=None):
        self.parent = parent
        # 初始化driver为None
        self.driver = None
        
        # 更新基础URL
        self.base_url = "https://tkglobal.melon.com"
        self.login_url = "https://gmember.melon.com/login/login_form.htm?langCd=EN&redirectUrl=https://tkglobal.melon.com/main/index.htm?langCd=EN"
        self.main_url = f"{self.base_url}/main/index.htm?langCd=EN"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            if browser_type == "Firefox":
                firefox_options = webdriver.FirefoxOptions()
                firefox_options.set_preference('dom.webdriver.enabled', False)
                firefox_options.set_preference('useAutomationExtension', False)
                firefox_options.binary_location = browser_path
                
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Firefox(service=service, options=firefox_options)
            else:  # Chrome
                chrome_options = webdriver.ChromeOptions()
                chrome_options.binary_location = browser_path
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                
        except Exception as e:
            print(f"浏览器初始化失败: {str(e)}")
            raise
        
        self.performance_url = f"{self.base_url}/performance/index.htm?langCd=EN&prodId="
        self.captcha_mode = captcha_mode  # "auto" 或 "manual"
        self.tesseract_path = tesseract_path

    def login(self, username, password):
        """登录功能"""
        try:
            # 直接使用完整的登录URL
            self.driver.get(self.login_url)
            
            # 等待登录表单加载
            username_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            password_input = self.driver.find_element(By.ID, "pwd")
            
            # 清除输入框内容并输入
            username_input.clear()
            username_input.send_keys(username)
            password_input.clear()
            password_input.send_keys(password)
            
            # 点击登录按钮
            login_button = self.driver.find_element(By.ID, "formSubmit")
            self.driver.execute_script("arguments[0].click();", login_button)
            
            # 等待登录成功并重定向
            WebDriverWait(self.driver, 10).until(
                EC.url_contains(self.base_url)
            )
            
            return True
        except Exception as e:
            print(f"登录失败: {str(e)}")
            return False

    def select_performance(self, prod_id):
        """进入指定演出页面"""
        try:
            performance_url = f"{self.performance_url}{prod_id}"
            print(f"正在访问: {performance_url}")
            
            self.driver.get(performance_url)
            
            # # 等待页面主要元素加载
            # WebDriverWait(self.driver, 10).until(
            #     EC.presence_of_element_located((By.CLASS_NAME, "wrap_consert_product"))
            # )
            
            return True
            
        except Exception as e:
            print(f"进入演出页面失败: {str(e)}")
            return False

    def book_ticket(self, date_index=1, time_index=1):
        """订票主流程"""
        try:
            print("开始订票流程...")
            
            # 1. 选择日期
            print("正在选择日期...")
            date_selector = "li[data-perfday]"
            dates = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, date_selector))
            )
            
            if date_index < 1 or date_index > len(dates):
                raise Exception(f"日期序号无效: {date_index}, 总共{len(dates)}个日期")
                
            # 点击选择日期
            target_date = dates[date_index - 1]
            print(f"选择日期: {target_date.get_attribute('data-perfday')}")
            self.driver.execute_script("arguments[0].click();", target_date)
            time.sleep(1)  # 等待日期选择生效
            
            # 2. 选择时间
            print("正在选择时间...")
            time_selector = "li.item_time"
            times = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, time_selector))
            )
            
            if time_index < 1 or time_index > len(times):
                raise Exception(f"时间序号无效: {time_index}, 总共{len(times)}个时间")
                
            # 点击选择时间
            target_time = times[time_index - 1]
            time_text = target_time.find_element(By.CSS_SELECTOR, "span.txt").text
            print(f"选择时间: {time_text}")
            self.driver.execute_script("arguments[0].click();", target_time)
            time.sleep(1)  # 等待时间选择生效
            
            # 3. 点击预订按钮
            print("正在点击预订按钮...")
            try:
                # 首先尝试等待按钮可点击
                book_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.reservationBtn"))
                )
                
                # 检查按钮状态
                button_class = book_button.get_attribute("class")
                if "disabled" in button_class:
                    raise Exception("预订按钮不可用")
                
                # 尝试多种点击方式
                try:
                    # 方式1：直接点击
                    book_button.click()
                except:
                    try:
                        # 方式2：使用JavaScript点击
                        self.driver.execute_script("arguments[0].click();", book_button)
                    except:
                        # 方式3：使用更具体的JavaScript选择器
                        self.driver.execute_script("""
                            document.querySelector('button.button.btColorGreen.reservationBtn[data-prodid="210544"]').click();
                        """)
                
                # 等待一下确保点击生效
                time.sleep(2)
                
            except Exception as e:
                print(f"点击预订按钮失败: {str(e)}")
                raise
            
            # 4. 等待新窗口打开
            print("等待订票窗口打开...")
            try:
                WebDriverWait(self.driver, 10).until(lambda d: len(d.window_handles) > 1)
                # 切换到新窗口
                self.driver.switch_to.window(self.driver.window_handles[-1])
            except:
                print("未检测到新窗口，尝试直接处理验证码...")
                
            # 5. 处理验证码
            print("正在处理验证码...")
            try:
                captcha_img = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "captchaImg"))
                )
                
                # 获验证码图片
                img_base64 = captcha_img.get_attribute("src")
                
                # 处理验证码
                if self.captcha_mode == "auto":
                    captcha_text = self.auto_recognize_captcha(img_base64)
                else:
                    captcha_text = self.manual_recognize_captcha(img_base64)
                    
                print(f"验证码识别结果: {captcha_text}")
                
                # 使用正确的ID查找输入框
                captcha_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "label-for-captcha"))
                )
                captcha_input.clear()  # 清除可能存在的内容
                captcha_input.send_keys(captcha_text)
                
                # 使用正确的ID查找提交按钮
                submit_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "btnComplete"))
                )
                
                # 尝试多种点击方式
                try:
                    # 方式1：直接点击
                    submit_button.click()
                except:
                    try:
                        # 方式2：JavaScript点击
                        self.driver.execute_script("arguments[0].click();", submit_button)
                    except:
                        # 方式3：使用更具体的JavaScript选择器
                        self.driver.execute_script("""
                            document.querySelector('#btnComplete').click();
                        """)
                
                # 等待提交后的响应
                time.sleep(2)
                
            except Exception as e:
                print(f"验证码处理失败: {str(e)}")
                
            return True
            
        except Exception as e:
            print(f"订票失败: {str(e)}")
            print(f"当前URL: {self.driver.current_url}")
            return False

    def solve_captcha(self, img_base64):
        """处理验证码"""
        try:
            # 从base64数据中提取图片数据
            img_data = img_base64.split(',')[1]
            import base64
            import io
            
            # 转换为图片对象
            img = Image.open(io.BytesIO(base64.b64decode(img_data)))
            
            # 保存验证码图片
            img.save("captcha.png")
            
            if self.captcha_mode == "auto":
                return self.auto_recognize_captcha("captcha.png")
            else:
                return self.manual_recognize_captcha("captcha.png")
                
        except Exception as e:
            print(f"验证码处理失败: {str(e)}")
            return ""

    def auto_recognize_captcha(self, img_path):
        """自动识别验证码"""
        try:
            # 从base64或文件读取图片
            if img_path.startswith('data:image/png;base64,'):
                # 解码base64图片数据
                img_data = base64.b64decode(img_path.split(',')[1])
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            else:
                img = cv2.imread(img_path)
                
            if img is None:
                print("无法读取验证码图片")
                return ""
                
            # 转换为灰度图
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 二值化处理
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
            
            # 使用tesseract识别
            text = pytesseract.image_to_string(binary, config='--psm 7')
            
            # 清理识别结果
            text = re.sub(r'[^A-Za-z0-9]', '', text)
            
            return text
            
        except Exception as e:
            print(f"自动识别失败: {str(e)}")
            return ""

    def manual_recognize_captcha(self, img_path):
        """手动识别验证码"""
        try:
            # 在主线程中显示对话框
            captcha_text = None
            if self.parent:
                captcha_text = QMetaObject.invokeMethod(
                    self.parent,
                    "show_captcha_dialog",
                    Qt.ConnectionType.BlockingQueuedConnection,
                    Q_ARG(str, img_path)
                )
            
            if captcha_text:
                return captcha_text
            return ""
            
        except Exception as e:
            print(f"手动识别失败: {str(e)}")
            return ""

    def auto_refresh(self, interval=1):
        """自动刷新直到抢到票"""
        try:
            # # 等待页面加载完成
            # WebDriverWait(self.driver, 10).until(
            #     EC.presence_of_element_located((By.CLASS_NAME, "reservationBtn"))
            # )
            
            if self.check_available_tickets():
                print("发现可用票务！")
                if self.book_ticket():
                    print("抢票成功！")
                    return True
            print("当前无票，继续刷新...")
            self.driver.refresh()
            time.sleep(interval)
            return False
        except Exception as e:
            print(f"刷新出错: {str(e)}")
            return False

    def check_available_tickets(self):
        """检查是否有可用票务"""
        try:
            # 检查预订按钮状态
            book_button = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".reservationBtn"))
            )
            print("检查预订按钮状态...")
            # 检查按钮是否可用
            button_class = book_button.get_attribute("class")
            button_disabled = "disabled" in button_class or not book_button.is_enabled()
            
            if button_disabled:
                print("预订按钮不可用")
                return False
                
            return True
            
        except Exception as e:
            print(f"检查票务状态失败: {str(e)}")
            return False

    def __del__(self):
        """清理浏览器实例"""
        # if hasattr(self, 'driver') and self.driver is not None:
        #     try:
        #         self.driver.quit()
        #     except:
        #         pass
