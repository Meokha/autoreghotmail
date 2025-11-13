import undetected_chromedriver as uc  # pyright: ignore[reportMissingImports]
from fake_useragent import UserAgent  # pyright: ignore[reportMissingImports]
from typing import Optional, Tuple
import os  # Nhập thư viện os
import uuid  # Nhập thư viện uuid
import random
import time

# Định nghĩa một thư mục tạm để lưu trữ các profile tạm thời
PROFILE_DIR_BASE = os.path.join(os.getcwd(), "temp_uc_profiles")
os.makedirs(PROFILE_DIR_BASE, exist_ok=True) # Đảm bảo thư mục gốc tồn tại

def build_chrome(proxy: Optional[str] = None, user_agent: Optional[str] = None, headless: bool = False) -> Tuple[uc.Chrome, str]:
    
    # --- 1. Tạo Profile Sạch (Mục 3) ---
    # Tạo một thư mục profile ngẫu nhiên cho phiên này
    profile_dir = os.path.join(PROFILE_DIR_BASE, str(uuid.uuid4()))
    
    ua = user_agent or UserAgent().random

    options = uc.ChromeOptions()
    
    # --- CÁC TÙY CHỌN CHỐNG PHÁT HIỆN ---
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-agent={ua}")
    
    # THÊM QUAN TRỌNG: Sử dụng profile directory riêng
    options.add_argument(f"--user-data-dir={profile_dir}")
    
    if headless:
        options.add_argument("--headless=new")

    if proxy:
        options.add_argument(f"--proxy-server={proxy}")

    # Khởi tạo Driver với profile tạm
    driver = uc.Chrome(options=options)
    
    # Tiếp tục vá các dấu hiệu Automation (rất tốt!)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Thêm hành động cuộn ngẫu nhiên
    if random.random() < 0.3:
        driver.execute_script("window.scrollBy(0, arguments[0]);", random.randint(-200, 200))
        time.sleep(random.uniform(0.2, 0.7))

    # Trả về driver và user_agent đã dùng
    return driver, ua

# GHI CHÚ: Bạn cần thêm hàm dọn dẹp để xóa thư mục profile_dir sau khi driver.quit()
# Ví dụ về cách sử dụng và dọn dẹp:
# 
# driver, ua = build_chrome(proxy="ip:port")
# try:
#     driver.get("https://some-site.com")
#     # ... làm việc ...
# finally:
#     driver.quit()
#     import shutil
#     shutil.rmtree(profile_dir, ignore_errors=True) # Xóa thư mục tạm