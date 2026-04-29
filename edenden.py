import sys
import os
import json
import time
import threading
import ctypes
import pydirectinput
import requests
import numpy as np
import cv2
import webbrowser
import subprocess
from datetime import datetime
from PIL import Image, ImageGrab

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QCheckBox, QStackedWidget, QTextEdit, 
    QScrollArea, QFrame, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPalette, QPainter, QPen

pydirectinput.FAILSAFE = False
pydirectinput.PAUSE = 0.001

CURRENT_VERSION = "v1.0.0"
GITHUB_API_URL = "https://api.github.com/repos/ManasAarohi1/Manas-s-Eden-Detector/releases/latest"

CONFIG_FILE = "config.json"
TEMPLATE_FILENAME = "eden.png"
CONTRACT_FILENAME = "contract.png"
EDEN_PATH_FILENAME = "edenpath.json"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

DEFAULT_CONFIG = {
    "webhook_url": "",
    "ping_id": "",
    "eden_record": False,
    "run_path": True,
    "calibrations": {
        "align_collection": None,
        "align_exit": None,
        "contract_button": None
    }
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception as e:
            print(f"Load Error: {e}")
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(data):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Save Error: {e}")
        raise e

def focus_roblox():
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "Roblox")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            return True
    except:
        pass
    return False

def manual_glide(x, y, duration=0.2):
    start_x, start_y = pydirectinput.position()
    steps = max(1, int(duration * 60))
    for i in range(1, steps + 1):
        t = i / steps
        t = 1 - (1 - t) * (1 - t)
        nx = int(start_x + (x - start_x) * t)
        ny = int(start_y + (y - start_y) * t)
        pydirectinput.moveTo(nx, ny)
        time.sleep(duration / steps)
    pydirectinput.moveTo(int(x), int(y))

class CalibrationOverlay(QWidget):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.drawRect(self.rect())

    def mousePressEvent(self, event):
        x, y = event.pos().x(), event.pos().y()
        self.callback([x, y])
        self.close()

class CalibratorWindow(QDialog):
    def __init__(self, parent_config):
        super().__init__()
        self.config = parent_config
        self.setWindowTitle("Calibrator")
        self.resize(400, 350)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")
        
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setStyleSheet("background-color: #1e1e2e;")
        self.grid = QVBoxLayout(content)
        
        self.add_section("CAMERA ALIGNMENT", ["align_collection", "align_exit"])
        self.add_section("ACTIONS", ["contract_button"])
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        btn_close = QPushButton("CLOSE")
        btn_close.setStyleSheet("background: #a6e3a1; color: #1e1e2e; font-weight: bold; padding: 10px;")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
        self.setLayout(layout)

    def add_section(self, title, keys):
        l = QLabel(f" {title} ")
        l.setStyleSheet("color: #89b4fa; font-weight: bold; margin-top: 10px;")
        self.grid.addWidget(l)
        
        for k in keys:
            row = QHBoxLayout()
            lbl = QLabel(k)
            row.addWidget(lbl)
            
            val = self.config["calibrations"].get(k)
            stat = QLabel("SET" if val else "MISSING")
            stat.setStyleSheet(f"color: {'#a6e3a1' if val else '#f38ba8'};")
            row.addWidget(stat)
            
            btn = QPushButton("Set")
            btn.setStyleSheet("background: #313244; color: #cdd6f4;")
            btn.clicked.connect(lambda _, k=k, s=stat: self.start_calib(k, s))
            row.addWidget(btn)
            self.grid.addLayout(row)

    def start_calib(self, key, label_widget):
        self.hide()
        def cb(data):
            self.show()
            self.config["calibrations"][key] = data
            try:
                save_config(self.config)
                label_widget.setText("SET")
                label_widget.setStyleSheet("color: #a6e3a1;")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save calibration: {e}")
        self.overlay = CalibrationOverlay(cb)

class BotLogic(QObject):
    log_signal = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.stop_event = threading.Event()
        self.prev_frame_small = None

    def log(self, text):
        self.log_signal.emit(text)

    def check_stop(self):
        if self.stop_event.is_set(): raise Exception("Stopped")

    def perform_click(self, key):
        self.check_stop()
        coords = self.config["calibrations"].get(key)
        if coords:
            manual_glide(coords[0], coords[1], 0.2)
            time.sleep(0.1)
            pydirectinput.click()
            time.sleep(0.2)
        else:
            self.log(f"Warning: {key} not calibrated!")

    def run_path_file(self, path_file):
        final_path = path_file
        if not os.path.exists(final_path): final_path = resource_path(path_file)
        
        if not os.path.exists(final_path):
            self.log(f"Warning: {path_file} not found. Skipping path.")
            return

        self.log(f"Running Path: {path_file}")
        
        try:
            with open(final_path, 'r') as f: data = json.load(f)
            events = data.get("events", [])
            if not events: return
            events.sort(key=lambda x: x['t'])
            start_play_time = time.perf_counter()
            first_event_t = events[0]['t']
            
            for event in events:
                if self.stop_event.is_set(): return
                target_offset = event['t'] - first_event_t
                while (time.perf_counter() - start_play_time) < target_offset:
                    if self.stop_event.is_set(): return
                    time.sleep(0.001)
                etype = event['type']
                if etype == 'mouse_move':
                    pydirectinput.moveTo(int(event['x']), int(event['y']))
                elif etype == 'key_down':
                    pydirectinput.keyDown(event['key'])
                elif etype == 'key_up':
                    pydirectinput.keyUp(event['key'])
                elif etype == 'mouse_down':
                    btn = event.get('button', 'left')
                    pydirectinput.mouseDown(button=btn)
                elif etype == 'mouse_up':
                    btn = event.get('button', 'left')
                    pydirectinput.mouseUp(button=btn)
        except Exception as e:
            self.log(f"Path Error: {e}")

    def run_eden_scanner(self):
        self.log("Started Eden Detector")
        
        template_path = TEMPLATE_FILENAME if os.path.exists(TEMPLATE_FILENAME) else resource_path(TEMPLATE_FILENAME)
        if not os.path.exists(template_path):
            self.log(f"Error: {TEMPLATE_FILENAME} not found in folder!")
            return

        try:
            template = cv2.imread(template_path, 0)
        except Exception as e:
            self.log(f"Error loading template: {e}")
            return

        try:
            while not self.stop_event.is_set():
                screen = np.array(ImageGrab.grab())
                screen_gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
                
                small_gray = cv2.resize(screen_gray, (64, 64))
                if self.prev_frame_small is not None:
                    res = cv2.matchTemplate(small_gray, self.prev_frame_small, cv2.TM_CCOEFF_NORMED)
                    similarity = res[0][0]
                    if similarity >= 0.98:
                        time.sleep(1.5)
                        continue
                self.prev_frame_small = small_gray
                
                found = None
                for scale in np.linspace(0.5, 1.5, 20):
                    resized_t = cv2.resize(template, None, fx=scale, fy=scale)
                    r_h, r_w = resized_t.shape[:2]

                    if r_w > screen_gray.shape[1] or r_h > screen_gray.shape[0]:
                        continue

                    res = cv2.matchTemplate(screen_gray, resized_t, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

                    if found is None or max_val > found[0]:
                        found = (max_val, max_loc, scale)

                if found:
                    best_score, best_loc, best_scale = found
                    if best_score >= 0.75:
                        self.log(f"EDEN DETECTED!")
                        self.trigger_sequence()
                        
                        self.log("Cooldown started (60s)...")
                        for _ in range(60): 
                            if self.stop_event.is_set(): break
                            time.sleep(1)
                        self.log("Resuming Scan...")
                
                time.sleep(1.5)
        except Exception as e:
            self.log(f"Scanner Error: {e}")

    def trigger_sequence(self):
        if self.config.get("eden_record", False):
            threading.Thread(target=self.record_screen_session, args=(60,), daemon=True).start()
        self.send_webhook_with_image("Eden Detected!", "eden_detected.png")
        
        time.sleep(25.0)

        if self.config.get("run_path", True):
            self.log("Aligning Camera...")
            self.perform_click("align_collection")
            time.sleep(1.0)
            self.perform_click("align_exit")
            time.sleep(0.5)
            
            pydirectinput.mouseDown(button='right')
            for _ in range(5): 
                pydirectinput.moveRel(0, 50)
                time.sleep(0.01)
            pydirectinput.mouseUp(button='right')
            time.sleep(0.5)

            self.log("Running Eden Path...")
            self.run_path_file(EDEN_PATH_FILENAME)
            time.sleep(0.5)

        pydirectinput.keyDown('e')
        time.sleep(0.1)
        pydirectinput.keyUp('e')
        
        for _ in range(50):
            if self.stop_event.is_set(): return
            time.sleep(0.1)

        self.log("Contracting...")
        self.perform_click("contract_button")
        
        if self.wait_for_image(CONTRACT_FILENAME, timeout=50):
            self.log("EDEN OBTAINED!")
            self.send_webhook_with_image("Eden Obtained!", "eden_obtained.png", color=0xFFD700)
        else:
            self.log("Contract NOT verified (Timeout).")

    def wait_for_image(self, filename, timeout=50):
        path = filename if os.path.exists(filename) else resource_path(filename)
        if not os.path.exists(path):
            self.log(f"Warning: {filename} missing. Cannot verify.")
            return False

        try:
            template = cv2.imread(path, 0)
            start_t = time.time()
            self.log(f"Waiting up to {timeout}s for {filename}...")
            
            while (time.time() - start_t) < timeout:
                if self.stop_event.is_set(): return False
                
                screen = np.array(ImageGrab.grab())
                gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
                res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                
                if max_val >= 0.8:
                    return True
                time.sleep(0.5)
        except Exception as e:
            self.log(f"Image Wait Error: {e}")
        return False

    def send_webhook_with_image(self, title, filename, color=65280):
        url = self.config.get("webhook_url")
        ping = self.config.get("ping_id")
        if not url: return

        try:
            ImageGrab.grab().save(filename)
            content = f"<@{ping}> {title}" if ping else title
                        
            payload = {
                "content": content,
                "embeds": [{
                    "title": title,
                    "color": color,
                    "description": "[Join Manas Biome Hunt!](https://discord.gg/oppression)",
                    "image": {"url": f"attachment://{filename}"},
                    "footer": {"text": f"Manas's Eden Detector | {CURRENT_VERSION}"}
                }]
            }
            with open(filename, "rb") as f:
                files = {"file": (filename, f, "image/png")}
                requests.post(url, data={"payload_json": json.dumps(payload)}, files=files)
        except Exception as e:
            self.log(f"Webhook error: {e}")

    def send_webhook_message(self, title, description, color=0x5865F2):
        url = self.config.get("webhook_url")
        if not url: return

        try:

            payload = {
                "embeds": [{
                    "title": title,
                    "color": color,
                    "description": "[Join Manas Biome Hunt!](https://discord.gg/oppression)",
                    "footer": {"text": f"Manas's Eden Detector | {CURRENT_VERSION}"}
                }]
            }
            requests.post(url, json=payload)
        except Exception as e:
            self.log(f"Webhook message error: {e}")

    def record_screen_session(self, duration=60):
        self.log("Recording screen...")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eden_capture_{timestamp}.avi"
            fps = 20.0
            
            sample_img = ImageGrab.grab()
            sample_frame = np.array(sample_img)
            height, width = sample_frame.shape[:2]
            actual_screen_size = (width, height)
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            
            out = cv2.VideoWriter(filename, fourcc, fps, actual_screen_size)
            
            start_t = time.time()
            while (time.time() - start_t) < duration:
                if self.stop_event.is_set():
                    break
                    
                img = ImageGrab.grab()
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                out.write(frame)
                time.sleep(1/fps)
                
            out.release()
            self.log(f"Saved recording: {filename}")
            
        except Exception as e:
            self.log(f"Recording Error: {e}")

class UpdateSignals(QObject):
    update_available = pyqtSignal(str, str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manas's Eden Detector")
        self.resize(700, 450)
        
        p = QPalette()
        p.setColor(QPalette.ColorRole.Window, QColor(30, 30, 46))
        p.setColor(QPalette.ColorRole.WindowText, QColor(205, 214, 244))
        p.setColor(QPalette.ColorRole.Base, QColor(17, 17, 27))
        p.setColor(QPalette.ColorRole.Text, QColor(205, 214, 244))
        p.setColor(QPalette.ColorRole.Button, QColor(49, 50, 68))
        p.setColor(QPalette.ColorRole.ButtonText, QColor(205, 214, 244))
        self.setPalette(p)

        self.config = load_config()
        self.bot_logic = BotLogic(self.config)
        self.bot_logic.log_signal.connect(self.append_log)
        
        self.scan_thread = None
        self.init_ui()

        self.update_signals = UpdateSignals()
        self.update_signals.update_available.connect(self.prompt_update)
        threading.Thread(target=self.check_for_updates_thread, daemon=True).start()

    def init_ui(self):
        w = QWidget()
        self.setCentralWidget(w)
        layout = QHBoxLayout(w)
        
        side = QFrame()
        side.setFixedWidth(150)
        side.setStyleSheet("background: #181825; border-radius: 10px;")
        sl = QVBoxLayout(side)
        
        btn_home = QPushButton("Detector")
        btn_sets = QPushButton("Settings")
        
        for b in [btn_home, btn_sets]:
            b.setStyleSheet("""
                QPushButton { text-align: left; padding: 12px; background: transparent; border: none; font-size: 14px; color: #cdd6f4; }
                QPushButton:hover { background: #313244; border-radius: 5px; }
            """)
            sl.addWidget(b)
        
        sl.addStretch()

        btn_discord = QPushButton("Join Manas Biome Hunt")
        btn_discord.setStyleSheet("""
            QPushButton { 
                text-align: center; 
                padding: 10px; 
                background: #5865F2; 
                border-radius: 5px; 
                font-size: 10px; 
                font-weight: bold; 
                color: #ffffff; 
                margin-bottom: 5px;
            }
            QPushButton:hover { background: #4752C4; }
        """)
        btn_discord.clicked.connect(lambda: webbrowser.open("https://discord.gg/oppression"))
        sl.addWidget(btn_discord)

        layout.addWidget(side)
        
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        self.page_home = self.create_home_page()
        self.page_settings = self.create_settings_page()
        
        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_settings)
        
        btn_home.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_sets.clicked.connect(lambda: self.stack.setCurrentIndex(1))

    def create_home_page(self):
        p = QWidget()
        l = QVBoxLayout(p)
        l.addWidget(QLabel("Eden Detector", styleSheet="font-size: 24px; font-weight: bold; color: #fab387;"))
        
        self.btn_toggle = QPushButton("START DETECTOR")
        self.btn_toggle.setStyleSheet("background: #a6e3a1; color: #1e1e2e; padding: 15px; font-weight: bold; font-size: 16px; border-radius: 5px;")
        self.btn_toggle.clicked.connect(self.toggle_scanner)
        l.addWidget(self.btn_toggle)
        
        l.addWidget(QLabel("Logs:", styleSheet="margin-top: 10px; font-weight: bold;"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background: #11111b; font-family: Consolas; font-size: 11px;")
        l.addWidget(self.log_box)
        return p

    def create_settings_page(self):
        p = QWidget()
        l = QVBoxLayout(p)
        l.addWidget(QLabel("Settings", styleSheet="font-size: 20px; font-weight: bold;"))
        
        l.addWidget(QLabel("Discord Webhook:"))
        self.txt_web = QLineEdit(self.config.get("webhook_url", ""))
        l.addWidget(self.txt_web)
        
        l.addWidget(QLabel("Ping ID:"))
        self.txt_ping = QLineEdit(self.config.get("ping_id", ""))
        l.addWidget(self.txt_ping)
        
        self.chk_record = QCheckBox("Record Eden Event (60s video)")
        self.chk_record.setChecked(self.config.get("eden_record", False))
        l.addWidget(self.chk_record)

        self.chk_run_path = QCheckBox("Run Path Movement")
        self.chk_run_path.setChecked(self.config.get("run_path", True))
        l.addWidget(self.chk_run_path)
        
        btn_calib = QPushButton("OPEN CALIBRATOR")
        btn_calib.setStyleSheet("background: #fab387; color: #1e1e2e; font-weight: bold; padding: 10px; margin-top: 20px;")
        btn_calib.clicked.connect(lambda: CalibratorWindow(self.config).exec())
        l.addWidget(btn_calib)
        
        btn_save = QPushButton("Save Config")
        btn_save.clicked.connect(self.save_settings)
        btn_save.setStyleSheet("background: #a6e3a1; color: #1e1e2e; padding: 10px; font-weight: bold; margin-top: 10px;")
        l.addWidget(btn_save)
        l.addStretch()
        return p

    def append_log(self, text):
        self.log_box.append(text)
        scrollbar = self.log_box.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def save_settings(self):
        try:
            self.config["webhook_url"] = self.txt_web.text()
            self.config["ping_id"] = self.txt_ping.text()
            self.config["eden_record"] = self.chk_record.isChecked()
            self.config["run_path"] = self.chk_run_path.isChecked()
            save_config(self.config)
            QMessageBox.information(self, "Success", "Configuration saved!")
            self.append_log("Settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings!\n\n{e}")
            self.append_log(f"Failed to save config -> {e}")

    def toggle_scanner(self):
        if self.scan_thread and self.scan_thread.is_alive():
            self.bot_logic.stop_event.set()
            self.btn_toggle.setText("START DETECTOR")
            self.btn_toggle.setStyleSheet("background: #a6e3a1; color: #1e1e2e; padding: 15px; font-weight: bold; font-size: 16px; border-radius: 5px;")
            self.append_log("Stopping...")
            
            self.bot_logic.send_webhook_message("Manas's Eden Detector Stopped", "The Eden Detector has been disabled.", color=0xf38ba8)
        else:
            self.bot_logic.stop_event.clear()
            self.scan_thread = threading.Thread(target=self.bot_logic.run_eden_scanner, daemon=True)
            self.scan_thread.start()
            self.btn_toggle.setText("STOP DETECTOR")
            self.btn_toggle.setStyleSheet("background: #f38ba8; color: #1e1e2e; padding: 15px; font-weight: bold; font-size: 16px; border-radius: 5px;")
            
            self.bot_logic.send_webhook_message("Manas's Eden Detector Started", "The Eden Detector is now actively scanning.", color=0xa6e3a1)
    def check_for_updates_thread(self):
        try:
            response = requests.get(GITHUB_API_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "")
                
                if latest_version and latest_version != CURRENT_VERSION:
                    release_url = data.get("html_url", "https://github.com/ManasAarohi1/Manas-s-Eden-Detector/releases/latest")
                    self.update_signals.update_available.emit(latest_version, release_url)
        except Exception as e:
            self.bot_logic.log(f"Update check failed: {e}")

    def prompt_update(self, latest_version, release_url):
        reply = QMessageBox.question(
            self, 
            "Update Available", 
            f"Version {latest_version} is available!\nYou are currently on {CURRENT_VERSION}.\n\nDo you want to go to GitHub to download the latest update?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
                                     
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(release_url)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
