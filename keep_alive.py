from flask import Flask
from threading import Thread
import logging

# Vô hiệu hóa log của Flask để tránh làm rác màn hình Console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('')

@app.route('/')
def home():
    # Trang web tĩnh giúp Render nhận diện Bot vẫn đang hoạt động
    return "Hệ thống Bot Buff Follow đang chạy 24/7!"

def run():
    # Cấu hình Host và Port tiêu chuẩn cho các dịch vụ Cloud
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """Hàm khởi chạy luồng web song song với Bot"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
