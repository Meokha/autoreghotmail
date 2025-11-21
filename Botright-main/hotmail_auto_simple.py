"""
TỰ ĐỘNG TẠO TÀI KHOẢN HOTMAIL/OUTLOOK
Version 7.0 - Botright Official API
Date: Nov 11, 2025 - 6:15 PM
"""
import asyncio
import botright
import random
import string
import datetime
import json
import csv
import os
import time

from db import upsert_account

async def auto_handle_post_captcha(page):
    try:
        post_captcha_selectors = [
            "button:has-text('Kế tiếp')",
            "button:has-text('Tiếp theo')",
            "button:has-text('Tiếp tục')",
            "button:has-text('OK')",
            "button:has-text('Bỏ qua ngay bây giờ')",
            "button:has-text('Bỏ qua bây giờ')",
            "button:has-text('Bỏ qua')",
            "button:has-text('Got it')",
            "button:has-text('Continue')",
            "button:has-text('Yes')",
            "button:has-text('No')",
            "button:has-text('Có')",
            "button:has-text('Không')",
            "button:has-text('Accept')",
            "button:has-text('Allow')",
            "button:has-text('Skip for now')",
        ]
        for _ in range(15):
            for sel in post_captcha_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn:
                        try:
                            await page.evaluate("el => el.scrollIntoView({block: 'center'})", btn)
                        except Exception:
                            pass
                        print(f"☑️ Đã tìm thấy và bấm {sel}")
                        await btn.click()
                        # Chờ trang xử lý một nhịp
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except Exception:
                            await asyncio.sleep(2)
                except Exception:
                    continue
            # Kiểm tra inbox/account đã xuất hiện?
            try:
                inbox_found = await page.query_selector("button[aria-label='New mail'], span:has-text('Inbox'), [data-icon-name='NewMail']")
                if inbox_found:
                    print("✅ Đã vào inbox/account!")
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
        print("⚠️ Qua nhiều bước mà chưa vào được inbox. Có thể cần xử lý thêm.")
        return False
    except Exception as e:
        print(f"⚠️ Lỗi auto_handle_post_captcha: {e}")
        return False

async def ensure_press_hold_visible(page):
    """Đảm bảo khối Press & Hold thực sự hiện rõ (không mờ/blur) và nằm trong viewport."""
    try:
        sel_candidates = [
            "[aria-label='Press & Hold Human Challenge']",
            "div[aria-label*='Press'][aria-label*='Hold' i]",
            "#PWEIcCxDoTELNND[role='button'][aria-label*='Press'][aria-label*='Hold']",
            "a[aria-label='Accessible challenge']",
            "//p[contains(normalize-space(.), 'Press and hold')]/ancestor::div[1]",
        ]
        target = None
        for sel in sel_candidates:
            try:
                el = await page.query_selector(sel)
                if el:
                    target = el
                    break
            except Exception:
                continue
        if not target:
            return False

        try:
            await page.evaluate("el => el.scrollIntoView({block: 'center'})", target)
        except Exception:
            pass

        # Bỏ filter/opacity có thể gây mờ
        try:
            await page.add_style_tag(content="""
                *[style*='filter'], *[style*='opacity'] { filter: none !important; opacity: 1 !important; }
            """)
        except Exception:
            pass
        try:
            await page.evaluate("el => { el.style.filter='none'; el.style.opacity='1'; }", target)
        except Exception:
            pass

        try:
            await target.hover()
        except Exception:
            pass

        try:
            # chờ visible một nhịp
            await page.wait_for_selector("[aria-label='Press & Hold Human Challenge']", state="visible", timeout=3000)
        except Exception:
            pass
        return True
    except Exception:
        return False

async def fallback_press_and_hold(page, hold_seconds: float | None = None):
    """Mô phỏng nhấn-và-giữ nút Press and Hold."""
    try:
        hold = hold_seconds or random.uniform(3.0, 5.0)
        button_selectors = [
            "#PWEIcCxDoTELNND[role='button']",
            "[aria-label='Press & Hold Human Challenge']",
            "div[aria-label*='Press'][aria-label*='Hold' i]",
        ]
        btn = None
        for sel in button_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    btn = el
                    break
            except Exception:
                continue
        if not btn:
            return False

        box = await btn.bounding_box()
        if not box:
            return False

        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        await page.mouse.move(x, y, steps=5)
        await asyncio.sleep(0.2)
        print(f"✊ [Press & Hold] Giữ {hold:.1f}s…")
        await page.mouse.down()
        await asyncio.sleep(hold)
        await page.mouse.up()
        print("✅ [Press & Hold] Đã thả chuột")
        return True
    except Exception as e:
        print(f"⚠️ Fallback press-and-hold lỗi: {e}")
        return False

async def auto_press_and_hold_button(page, hold_duration=4.0):
    """
    Tự động bấm và giữ nút 'Press and hold' của PerimeterX
    """
    try:
        print(" 🖱️ Đang tự động bấm nút 'Press and hold'...")
        # Danh sách selector cho nút (nhiều biến thể)
        button_selectors = [
            "button:has-text('Press and hold')",
            "[aria-label*='Press and hold' i]",
            "button[data-action='press-and-hold']",
            "div.press-hold-button",
            "button.challenge-button",
        ]
        button = None
        for sel in button_selectors:
            try:
                button = await page.wait_for_selector(sel, state="visible", timeout=5000)
                if button:
                    print(f" ✓ Tìm thấy nút: {sel}")
                    break
            except Exception:
                continue
        if not button:
            print(" ⚠️ Không tìm thấy nút 'Press and hold'")
            return False
        # Lấy vị trí nút
        box = await button.bounding_box()
        if not box:
            print(" ⚠️ Không lấy được tọa độ nút")
            return False
        # Tính toán tâm nút
        x = box['x'] + box['width'] / 2
        y = box['y'] + box['height'] / 2
        print(f" 🎯 Vị trí nút: ({x:.0f}, {y:.0f})")
        # Di chuyển chuột đến nút
        await page.mouse.move(x, y, steps=5)
        await asyncio.sleep(0.3)
        # Bấm và giữ
        print(f" 👇 Bấm và giữ trong {hold_duration}s...")
        await page.mouse.down()
        await asyncio.sleep(hold_duration)
        await page.mouse.up()
        print(" ✅ Đã thả chuột - chờ xử lý...")
        await asyncio.sleep(3)
        return True
    except Exception as e:
        print(f" ❌ Lỗi auto press-and-hold: {e}")
        return False

async def auto_click_iframe_directly(page, hold_duration=4.5):
    """
    Tự động tìm iframe của PerimeterX trong shadow DOM và click-giữ trực tiếp bằng tọa độ.
    """
    try:
        print(" 🖱️ Đang tìm vị trí iframe để click...")
        coords_script = """
        (() => {
            const pxCaptcha = document.querySelector('#px-captcha');
            if (!pxCaptcha || !pxCaptcha.shadowRoot) return null;
            const iframes = pxCaptcha.shadowRoot.querySelectorAll('iframe');
            for (let iframe of iframes) {
                const style = window.getComputedStyle(iframe);
                if (style && style.display !== 'none' && style.visibility !== 'hidden' && parseFloat(style.opacity || '1') > 0) {
                    const rect = iframe.getBoundingClientRect();
                    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, width: rect.width, height: rect.height };
                }
            }
            return null;
        })();
        """
        coords = await page.evaluate(coords_script)
        if not coords:
            print(" ⚠️ Không tìm thấy iframe")
            return False
        x = coords['x']
        y = coords['y']
        print(f" 🎯 Vị trí iframe: ({x:.0f}, {y:.0f})")
        await page.mouse.move(x, y, steps=10)
        await asyncio.sleep(0.5)
        print(f" 👇 Bấm và giữ {hold_duration}s...")
        await page.mouse.down()
        await asyncio.sleep(hold_duration)
        await page.mouse.up()
        print(" ✅ Đã thả chuột!")
        await asyncio.sleep(5)
        return True
    except Exception as e:
        print(f" ❌ Lỗi: {e}")
        return False

async def wait_px_ready(page, timeout=45000):
    """Đợi form PerimeterX PxCaptcha hiển thị đầy đủ trước khi thao tác."""
    start = time.time()
    selectors = [
        "a[aria-label='Accessible challenge']",
        "div[role='button'][aria-label*='Press']",
        "div:has-text('Press and hold')",
        "#px-captcha",
    ]
    while (time.time() - start) * 1000 < timeout:
        try:
            # Trực tiếp qua các selector phổ biến
            for sel in selectors:
                el = await page.query_selector(sel)
                if el:
                    try:
                        if await el.is_visible():
                            return True
                    except Exception:
                        return True
            # Kiểm tra iframe/URL chứa PX
            for fr in page.frames:
                try:
                    url = (fr.url or "").lower()
                    if any(k in url for k in ["perimeterx", "px", "challenge", "captcha"]):
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        await asyncio.sleep(0.3)
    return False

class HotmailAccountCreator:
    def __init__(self):
        """Khởi tạo danh sách tên ngẫu nhiên"""
        self.first_names = [
            "John", "David", "Michael", "Chris", "Mike", "Robert", 
            "James", "William", "Peter", "Tuan", "Alex", "Tom",
            "Daniel", "Kevin", "Brian", "Steven", "Mark", "Paul"
        ]
        self.last_names = [
            "Smith", "Jones", "Williams", "Taylor", "Brown", "Davies", 
            "Evans", "Wilson", "Thomas", "Nguyen", "Johnson", "Lee",
            "Martin", "Garcia", "Rodriguez", "Martinez", "Anderson", "White"
        ]
        self.last_full_email = None
        self.last_password = None
    
    def generate_random_email(self, prefix="user"):
        """Tạo email ngẫu nhiên"""
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        return f"{prefix}{random_str}"
    
    def generate_strong_password(self, length=16):
        """Tạo mật khẩu mạnh ngẫu nhiên"""
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        symbols = "!@#$%^&*"
        
        # Đảm bảo có ít nhất 1 ký tự mỗi loại
        password = [
            random.choice(lowercase),
            random.choice(uppercase),
            random.choice(digits),
            random.choice(symbols)
        ]
        
        # Thêm các ký tự ngẫu nhiên còn lại
        all_chars = lowercase + uppercase + digits + symbols
        password += random.choices(all_chars, k=length-4)
        
        # Trộn ngẫu nhiên
        random.shuffle(password)
        return ''.join(password)

    async def wait_inbox_ready(self, page) -> bool:
        """Chờ đến khi hộp thư Outlook tải thành công.
        - Xử lý một số màn hình trung gian: Stay signed in, chào mừng, v.v.
        - Trả về True nếu phát hiện thành phần đặc trưng của inbox.
        """
        try:
            # Một số site sẽ hiện dialog "Stay signed in?"
            try:
                # Ưu tiên click nút primary (Yes/Đúng)
                stay_selectors_primary = [
                    "button[data-testid='primaryButton']",
                    "button:has-text('Yes')",
                    "button:has-text('Đúng')",
                ]

                clicked_stay = False
                for sel in stay_selectors_primary:
                    btn_yes = await page.query_selector(sel)
                    if btn_yes:
                        await btn_yes.click()
                        await asyncio.sleep(2)
                        clicked_stay = True
                        break

                # Nếu không tìm thấy nút primary thì fallback click "No" như cũ
                if not clicked_stay:
                    btn_no = await page.query_selector("button:has-text('No')")
                    if btn_no:
                        await btn_no.click()
                        await asyncio.sleep(2)
            except Exception:
                pass

            # Điều hướng thẳng đến mail nếu đang ở trang khác
            try:
                if not page.url.startswith("https://outlook.live.com/"):
                    await page.goto("https://outlook.live.com/mail/0/", wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass

            # Xử lý màn hình chào mừng (Skip/Continue)
            for _ in range(3):
                try:
                    for sel in [
                        "button:has-text('Skip')",
                        "button:has-text('Continue')",
                        "button:has-text('Got it')",
                        "button:has-text('OK')",
                    ]:
                        btn = await page.query_selector(sel)
                        if btn:
                            await btn.click()
                            await asyncio.sleep(2)
                except Exception:
                    pass

            # Chờ các selector đặc trưng của hộp thư
            inbox_selectors = [
                "button[aria-label='New mail']",
                "[data-icon-name='NewMail']",
                "div[role='tree']",  # danh sách folder
                "[aria-label='Folders']",
                "span:has-text('Inbox')",
            ]

            end_time = asyncio.get_event_loop().time() + 90
            while asyncio.get_event_loop().time() < end_time:
                for sel in inbox_selectors:
                    el = await page.query_selector(sel)
                    if el:
                        return True
                await asyncio.sleep(2)
            return False
        except Exception:
            return False
    
    async def human_type(self, element, text):
        """Gõ phím từng ký tự như người thật"""
        print(f"   ...đang gõ '{text[:20]}...'")
        for char in text:
            await element.type(char, delay=random.uniform(80, 250))
    
    async def human_click(self, element):
        """Click với delay tự nhiên"""
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await element.click()
    
    async def select_dropdown_option(self, page, dropdown_id, option_text):
        """Chọn option từ dropdown"""
        try:
            print(f"   ...đang chọn {option_text}...")
            
            # Click vào dropdown
            try:
                dropdown = await page.wait_for_selector(f"#{dropdown_id}", state="attached", timeout=5000)
                try:
                    await dropdown.scroll_into_view_if_needed()
                except Exception:
                    pass
            except Exception:
                dropdown = None
            await page.click(f"#{dropdown_id}")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Đợi listbox xuất hiện
            listbox = await page.wait_for_selector("div[role='listbox']", state="visible", timeout=10000)
            await asyncio.sleep(random.uniform(0.3, 0.6))
            
            # Tìm option theo text (dùng normalize-space để tránh lỗi khoảng trắng)
            option_locator = page.locator(f"//div[@role='option' and normalize-space()='{option_text}']")
            
            # Cố gắng scroll vào view và click trực tiếp
            try:
                await option_locator.first.scroll_into_view_if_needed()
                await option_locator.first.click()
                await asyncio.sleep(random.uniform(0.5, 1.0))
                print(f"   ✓ Đã chọn: {option_text}")
                return True
            except Exception:
                pass
            
            # Fallback: cuộn trong listbox bằng PageDown để tìm option
            for _ in range(30):
                try:
                    count = await option_locator.count()
                    if count > 0:
                        try:
                            await option_locator.first.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        try:
                            await option_locator.first.click()
                            await asyncio.sleep(random.uniform(0.3, 0.6))
                            print(f"   ✓ Đã chọn: {option_text}")
                            return True
                        except Exception:
                            pass
                except Exception:
                    pass
                # Cuộn tiếp danh sách xuống dưới
                try:
                    if listbox:
                        await listbox.press("PageDown")
                    else:
                        await page.keyboard.press("PageDown")
                except Exception:
                    # Nếu không bấm được, thử dùng evaluate để tăng scrollTop
                    try:
                        await page.evaluate("lb => lb.scrollTop = lb.scrollTop + 200", listbox)
                    except Exception:
                        pass
                await asyncio.sleep(0.15)
            
            # Lần cuối thử click theo XPath trực tiếp (trong trường hợp option trở nên hiển thị)
            try:
                await page.click(f"//div[@role='option' and normalize-space()='{option_text}']", timeout=1000)
                await asyncio.sleep(random.uniform(0.3, 0.6))
                print(f"   ✓ Đã chọn: {option_text}")
                return True
            except Exception:
                pass

            # Fallback cuối: gõ giá trị và Enter để chọn (hữu ích với số như '16')
            try:
                await listbox.type(str(option_text))
                await listbox.press("Enter")
                await asyncio.sleep(random.uniform(0.3, 0.6))
                print(f"   ✓ Đã chọn (gõ): {option_text}")
                return True
            except Exception:
                pass
            
            print(f"   ✗ Không thể chọn: {option_text}")
            return False
            
        except Exception as e:
            print(f"   ✗ Lỗi chọn dropdown: {e}")
            return False
    
    async def save_account_info(self, account_info):
        """Lưu thông tin tài khoản vào các file"""
        # Lưu TXT
        try:
            with open('hotmail_accounts.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Email: {account_info['email']}\n")
                f.write(f"Password: {account_info['password']}\n")
                f.write(f"Name: {account_info['firstname']} {account_info['lastname']}\n")
                f.write(f"Birth: {account_info['birthdate']}\n")
                f.write(f"Created: {account_info['created_time']}\n")
                f.write(f"{'='*60}\n")
            print("   ✓ Đã lưu hotmail_accounts.txt")
        except Exception as e:
            print(f"   ✗ Lỗi lưu TXT: {e}")
        
        # Lưu JSON
        try:
            json_file = "hotmail_accounts.json"
            if os.path.exists(json_file):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        accounts = json.load(f)
                    if not isinstance(accounts, list):
                        accounts = []
                except json.JSONDecodeError:
                    accounts = []
            else:
                accounts = []
            
            accounts.append(account_info)
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, indent=4, ensure_ascii=False)
            print(f"   ✓ Đã lưu {json_file} ({len(accounts)} tài khoản)")
        except Exception as e:
            print(f"   ✗ Lỗi JSON: {e}")
        
        # Lưu CSV
        try:
            csv_file = "hotmail_accounts.csv"
            file_exists = os.path.exists(csv_file)
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=account_info.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(account_info)
            print(f"   ✓ Đã lưu {csv_file}")
        except Exception as e:
            print(f"   ✗ Lỗi CSV: {e}")

        # Lưu SQLite
        try:
            upsert_account(account_info)
            print("   ✓ Đã lưu hotmail_accounts.db")
        except Exception as e:
            print(f"   ✗ Lỗi SQLite: {e}")
    
    async def create_account(self, page, email_prefix="myuser", domain="hotmail", password: str | None = None):
        """Tạo tài khoản Hotmail/Outlook với Botright"""
        try:
            self.last_full_email = None
            self.last_password = None
            print("="*70)
            print("BẮT ĐẦU TẠO TÀI KHOẢN HOTMAIL/OUTLOOK VỚI BOTRIGHT")
            print("="*70)
            
            # ===== BƯỚC 1: Truy cập trang đăng ký =====
            print("\n[BƯỚC 1] Truy cập trang tạo email Microsoft")
            random_uaid = ''.join(random.choices(string.hexdigits.lower(), k=32))
            signup_url = f"https://signup.live.com/signup?wa=wsignin1.0&rpsnv=13&ct=1699000000&rver=7.0.6738.0&wp=MBI_SSL&wreply=https%3a%2f%2foutlook.live.com%2fowa%2f%3fnlp%3d1%26signup%3d1&id=292841&aadredir=1&CBCXT=out&lw=1&fl=dob%2cflname%2cwld&cobrandid=90015&lic=1&uaid={random_uaid}"
            
            await page.goto(signup_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(random.uniform(3.0, 5.0))
            print("   ✓ Đã load trang thành công")
            
            # ===== BƯỚC 2: Điền email =====
            print("\n[BƯỚC 2] Điền địa chỉ email mới")
            email_name = self.generate_random_email(email_prefix)
            
            # Thử nhiều selector để tìm input email
            email_input = None
            for selector_id in ["#floatingLabelInput4", "#floatingLabelInput5", "#MemberName", "#liveSwitch"]:
                try:
                    email_input = await page.wait_for_selector(selector_id, state="visible", timeout=3000)
                    if email_input:
                        print(f"   ✓ Tìm thấy input email: {selector_id}")
                        break
                except:
                    continue
            
            if not email_input:
                raise Exception("❌ Không tìm thấy ô nhập email!")
            
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await self.human_click(email_input)
            # Clear chắc chắn trước khi gõ
            try:
                await email_input.fill("")
            except Exception:
                pass
            try:
                await email_input.press("Control+A")
                await email_input.press("Backspace")
            except Exception:
                pass
            # Hiển thị preview đang gõ
            print(f"   ...đang gõ '{email_name[:20]}...'")
            # Gõ chậm hoàn toàn bằng bàn phím (không dùng JS), luôn ép caret về cuối
            # và xác minh tiền tố sau mỗi ký tự. Nếu lệch, backspace và gõ lại ký tự đó (tối đa 2 lần)
            typed_prefix = ""
            for ch in email_name:
                # gõ ký tự
                await email_input.type(ch, delay=random.uniform(80, 160))
                # ép caret về cuối
                try:
                    await email_input.press("End")
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(0.02, 0.06))

                # xác minh tiền tố
                typed_prefix += ch
                ok_char = False
                for _ in range(2):  # tối đa 2 lần sửa cho mỗi ký tự
                    try:
                        current_val = await email_input.input_value()
                    except Exception:
                        current_val = ""
            try:
                typed_val = await email_input.input_value()
            except Exception:
                typed_val = ""
            if typed_val.strip() != email_name:
                # Chiến lược B: gõ nguyên chuỗi với delay cao (không sửa từng ký tự)
                print("   ⚠️ fill() chưa khớp. Fallback: type() nguyên chuỗi với delay cao…")
                try:
                    await email_input.press("Control+A")
                    await email_input.press("Backspace")
                except Exception:
                    pass
                await email_input.type(email_name, delay=random.uniform(150, 300))
                await asyncio.sleep(0.5)
                try:
                    typed_val = await email_input.input_value()
                except Exception:
                    typed_val = ""
                if typed_val.strip() != email_name:
                    print(f"   ✗ Nhập email không chính xác (got='{typed_val}'). Dừng.")
                    return None
            print(f"   ✓ Đã nhập email: {email_name}")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # ===== BƯỚC 3: Chọn domain =====
            print("\n[BƯỚC 3] Chọn domain (@hotmail.com hoặc @outlook.com)")
            full_email = f"{email_name}@outlook.com"
            self.last_full_email = full_email
            
            try:
                await page.click("#domainDropdownId")
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                if domain.lower() == "hotmail":
                    try:
                        await page.click("div[role='option']:has-text('hotmail.com')")
                        full_email = f"{email_name}@hotmail.com"
                        print("   ✓ Đã chọn @hotmail.com")
                    except:
                        print("   ⚠ Không tìm thấy hotmail.com, dùng outlook.com")
                else:
                    print("   ✓ Dùng @outlook.com mặc định")
                
                await asyncio.sleep(random.uniform(0.5, 1.0))
            except Exception as e:
                print(f"   ⚠ Không thấy dropdown domain: {e}")
                full_email = f"{email_name}@{domain}.com"
            
            self.last_full_email = full_email
            print(f"   ✓ Email hoàn chỉnh: {full_email}")
            
            # Click Next
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await page.click("button[type='submit']")
            print("   ✓ Đã click Next")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # ===== BƯỚC 4: Điền mật khẩu =====
            print("\n[BƯỚC 4] Tạo và điền mật khẩu")
            if not password:
                password = self.generate_strong_password()
            
            self.last_password = password
            password_input = await page.wait_for_selector("input[type='password']", state="visible", timeout=15000)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await self.human_click(password_input)
            await password_input.fill("")
            await self.human_type(password_input, password)
            print(f"   ✓ Đã nhập mật khẩu: {password}")
            await asyncio.sleep(random.uniform(1.5, 2.5))

            next_btn = None
            try:
                next_btn = await page.wait_for_selector("button[type='submit']", state="visible", timeout=5000)
            except Exception:
                try:
                    next_btn = await page.query_selector("button:has-text('Next')")
                except Exception:
                    next_btn = None

            if next_btn:
                try:
                    try:
                        await page.evaluate("el => el.scrollIntoView({block: 'center'})", next_btn)
                    except Exception:
                        pass
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    await self.human_click(next_btn)
                except Exception:
                    try:
                        await page.keyboard.press("Enter")
                    except Exception:
                        await page.click("button[type='submit']", force=True)
            else:
                try:
                    await page.keyboard.press("Enter")
                except Exception:
                    await page.click("button[type='submit']", force=True)

            print("   ✓ Đã click Next")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # ===== BƯỚC 5: Điền ngày sinh =====
            print("\n[BƯỚC 5] Điền thông tin ngày sinh ngẫu nhiên")
            
            # Tạo ngày sinh ngẫu nhiên
            current_year = datetime.datetime.now().year
            birth_year = random.randint(current_year - 50, current_year - 18)
            birth_day = random.randint(1, 28)
            months = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            birth_month = random.choice(months)
            
            birth_month_str = birth_month
            birth_day_str = str(birth_day)
            birth_year_str = str(birth_year)
            
            print(f"   ℹ Ngày sinh: {birth_month} {birth_day}, {birth_year}")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # Chọn tháng
            await self.select_dropdown_option(page, "BirthMonthDropdown", birth_month)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Chọn ngày
            await self.select_dropdown_option(page, "BirthDayDropdown", str(birth_day))
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Điền năm
            try:
                year_input = await page.wait_for_selector("[name='BirthYear']", state="visible", timeout=5000)
                print("   ✓ Tìm thấy input năm (name=BirthYear)")
            except:
                try:
                    year_input = await page.wait_for_selector("#BirthYear", state="visible", timeout=5000)
                    print("   ✓ Tìm thấy input năm (id=BirthYear)")
                except:
                    year_input = await page.wait_for_selector("input[aria-label*='year' i]", state="visible", timeout=5000)
                    print("   ✓ Tìm thấy input năm (aria-label)")
            
            await self.human_click(year_input)
            await year_input.fill("")
            await self.human_type(year_input, str(birth_year))
            print(f"   ✓ Đã nhập năm: {birth_year}")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Click Next với kiểm tra và tự sửa DOB nếu chưa qua bước tiếp
            attempts = 0
            advanced = False
            while attempts < 3 and not advanced:
                await page.click("button[type='submit']")
                print("   ✓ Đã click Next")
                try:
                    next_form = await page.wait_for_selector(
                        "[name='firstNameInput'], input[aria-label*='first' i], input[placeholder*='First' i]",
                        state="visible",
                        timeout=5000,
                    )
                    if next_form:
                        advanced = True
                        break
                except Exception:
                    pass

                # Kiểm tra tháng/ngày/năm đã chọn
                try:
                    month_el = await page.query_selector("#BirthMonthDropdown")
                    month_text = await page.evaluate("el => el ? el.textContent.trim() : ''", month_el) if month_el else ""
                except Exception:
                    month_text = ""
                try:
                    day_el = await page.query_selector("#BirthDayDropdown")
                    day_text = await page.evaluate("el => el ? el.textContent.trim() : ''", day_el) if day_el else ""
                except Exception:
                    day_text = ""
                try:
                    year_val = await year_input.input_value()
                except Exception:
                    year_val = ""

                need_month = (not month_text) or (month_text.lower() in ["month", "tháng"]) or (month_text not in months)
                need_day = (not day_text) or (day_text.lower() in ["day", "ngày"]) or (not day_text.isdigit())
                need_year = (not year_val) or (len(year_val.strip()) < 4)

                if need_month:
                    await self.select_dropdown_option(page, "BirthMonthDropdown", birth_month)
                    await asyncio.sleep(0.4)
                if need_day:
                    await self.select_dropdown_option(page, "BirthDayDropdown", str(birth_day))
                    await asyncio.sleep(0.4)
                if need_year:
                    try:
                        await self.human_click(year_input)
                        await year_input.fill("")
                        await self.human_type(year_input, str(birth_year))
                    except Exception:
                        pass
                    await asyncio.sleep(0.4)

                attempts += 1
                print(f"   ↻ Thử lại Next (lần {attempts}) sau khi kiểm tra DOB")
                continue
            
            # ===== BƯỚC 6: Điền họ tên =====
            print("\n[BƯỚC 6] Điền họ tên ngẫu nhiên")

            # Tạo tên ngẫu nhiên
            first_name = random.choice(self.first_names)
            last_name = random.choice(self.last_names)

            first_name_str = first_name
            last_name_str = last_name

            print(f"   ℹ Họ tên: {first_name} {last_name}")

            try:
                # Sau bước trước có thể điều hướng; chờ trang ổn định và kéo lên đầu trang
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                try:
                    await page.evaluate("window.scrollTo(0, 0)")
                except Exception:
                    pass

                # Thử nhiều selector cho First/Last Name (đa ngôn ngữ/biến thể UI)
                first_selectors = [
                    "[name='firstNameInput']",
                    "#firstNameInput",
                    "input[aria-label*='first' i]",
                    "input[placeholder*='first' i]",
                    "input[name='FirstName']",
                    "input#FirstName",
                ]
                last_selectors = [
                    "[name='lastNameInput']",
                    "#lastNameInput",
                    "input[aria-label*='last' i]",
                    "input[placeholder*='last' i]",
                    "input[name='LastName']",
                    "input#LastName",
                ]

                first_name_input = None
                for sel in first_selectors:
                    try:
                        first_name_input = await page.wait_for_selector(sel, state="visible", timeout=5000)
                        if first_name_input:
                            break
                    except Exception:
                        continue
                if not first_name_input:
                    # Thử chờ thêm một nhịp lâu hơn trước khi bỏ cuộc
                    for sel in first_selectors:
                        try:
                            first_name_input = await page.wait_for_selector(sel, state="visible", timeout=10000)
                            if first_name_input:
                                break
                        except Exception:
                            continue
                if not first_name_input:
                    raise TimeoutError("Không tìm thấy ô First Name với các selector dự phòng")

                await self.human_click(first_name_input)
                await first_name_input.fill("")
                await self.human_type(first_name_input, first_name)
                print(f"   ✓ Đã nhập tên: {first_name}")
                await asyncio.sleep(random.uniform(0.5, 1.0))

                last_name_input = None
                for sel in last_selectors:
                    try:
                        last_name_input = await page.wait_for_selector(sel, state="visible", timeout=5000)
                        if last_name_input:
                            break
                    except Exception:
                        continue
                if not last_name_input:
                    for sel in last_selectors:
                        try:
                            last_name_input = await page.wait_for_selector(sel, state="visible", timeout=10000)
                            if last_name_input:
                                break
                        except Exception:
                            continue
                if not last_name_input:
                    raise TimeoutError("Không tìm thấy ô Last Name với các selector dự phòng")

                await self.human_click(last_name_input)
                await last_name_input.fill("")
                await self.human_type(last_name_input, last_name)
                print(f"   ✓ Đã nhập họ: {last_name}")
                await asyncio.sleep(random.uniform(1.0, 2.0))

                # Click Next an toàn (scroll vào giữa + fallback Enter/force)
                try:
                    next_btn = await page.query_selector("button[type='submit']")
                    if next_btn:
                        try:
                            await page.evaluate("el => el.scrollIntoView({block: 'center'})", next_btn)
                        except Exception:
                            pass
                        await asyncio.sleep(random.uniform(0.2, 0.5))
                        await self.human_click(next_btn)
                    else:
                        await page.keyboard.press("Enter")
                except Exception:
                    try:
                        await page.keyboard.press("Enter")
                    except Exception:
                        await page.click("button[type='submit']", force=True)

                print("   ✓ Đã click Next")
                await asyncio.sleep(random.uniform(1.0, 2.0))

            except Exception as e:
                print(f"   ✗ Lỗi BƯỚC 6: {e}")
                raise e
            
            # ===== BƯỚC 7: GIẢI PERIMETERX (MANUAL METHOD) =====
            print("\n[BƯỚC 7] Đang giải PerimeterX...")

            try:
                # 0️⃣ CHỜ FORM CAPTCHA LOAD XONG TRƯỚC KHI LÀM GÌ ĐÓ
                captcha_dialog = None
                try:
                    captcha_dialog = await page.wait_for_selector(
                        "[role='dialog']:has-text('Press and hold')",
                        timeout=15000
                    )
                    print(" ✅ Form CAPTCHA đã xuất hiện")
                except Exception:
                    print(" ⚠️ Không tìm thấy form '[role=dialog]' có text 'Press and hold' trong 15s")
                    # Thử tìm các selector khác
                    for sel in [
                        "[role='dialog']",
                        "div:has-text('Press and hold')",
                        "div:has-text('Press & Hold')",
                        "#px-captcha",
                    ]:
                        try:
                            captcha_dialog = await page.query_selector(sel)
                            if captcha_dialog:
                                print(f" ✅ Tìm thấy captcha với selector: {sel}")
                                break
                        except Exception:
                            continue

                # Scroll vào view để đảm bảo captcha hiển thị đầy đủ
                if captcha_dialog:
                    try:
                        await captcha_dialog.scroll_into_view_if_needed()
                        print(" ✅ Đã scroll captcha vào view")
                    except Exception:
                        try:
                            await page.evaluate("el => el.scrollIntoView({block: 'center', behavior: 'smooth'})", captcha_dialog)
                            print(" ✅ Đã scroll captcha vào giữa màn hình")
                        except Exception:
                            pass
                    await asyncio.sleep(1)  # Chờ scroll animation

                # Thử chờ network/DOM ổn định thêm một chút (nếu detect được)
                try:
                    await page.wait_for_load_state("networkidle", timeout=20000)
                    print(" ✅ Network idle")
                except Exception:
                    pass

                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=20000)
                    print(" ✅ DOM ready")
                except Exception:
                    pass

                # Đệm thêm 3s cho CSS/animation hết mờ và captcha render đầy đủ
                base_delay = random.uniform(3, 5)
                extra_delay = random.uniform(5, 10)
                wait_time = base_delay + extra_delay
                print(f" ⏳ Đang chờ captcha hiển thị hoàn toàn, thời gian chờ: {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
                
                # Thêm mouse movement tự nhiên (hover qua captcha)
                try:
                    if captcha_dialog:
                        box = await captcha_dialog.bounding_box()
                        if box:
                            # Di chuyển chuột qua captcha một cách tự nhiên
                            hover_x = box['x'] + box['width'] / 2 + random.uniform(-20, 20)
                            hover_y = box['y'] + box['height'] / 2 + random.uniform(-20, 20)
                            await page.mouse.move(hover_x, hover_y, steps=random.randint(10, 20))
                            await asyncio.sleep(random.uniform(0.5, 1.5))
                except Exception:
                    pass
                
                # Kiểm tra và scroll lại nếu cần
                if captcha_dialog:
                    try:
                        await captcha_dialog.scroll_into_view_if_needed()
                    except Exception:
                        pass

                # ✅ BƯỚC 1: CHỤP SCREENSHOT
                print(" � Chụp screenshot...")
                await page.screenshot(path="captcha_step1.png", full_page=True)
                print(" ✅ Đã chụp: captcha_step1.png")
                print(" � Mở Paint → Quét tọa độ nút Accessibility Challenge")
                await asyncio.sleep(random.uniform(8, 12))  # Random delay 8-12s
                
                # ✅ BƯỚC 2: CLICK ICON (TỌA ĐỘ MANUAL)
                print("\n � Click icon...")
                
                ICON_X = 130   # ← THAY THEO SCREENSHOT CỦA BẠN
                ICON_Y = 465   # ← THAY THEO SCREENSHOT CỦA BẠN
                
                # Di chuyển chuột đến icon một cách tự nhiên
                await page.mouse.move(ICON_X + random.uniform(-5, 5), ICON_Y + random.uniform(-5, 5), steps=random.randint(15, 25))
                await asyncio.sleep(random.uniform(0.3, 0.7))
                await page.mouse.click(ICON_X, ICON_Y)
                print(" ✅ Đã click!")
                await asyncio.sleep(random.uniform(2, 4))  # Random delay 2-4s
                
                # ✅ BƯỚC 3: CHỤP SCREENSHOT LẦN 2
                # print(" 📸 Chụp screenshot lần 2...")
                # await page.screenshot(path="captcha_step2.png", full_page=True)
                # print(" ✅ Đã chụp: captcha_step2.png")
                print(" � Mở Paint → Quét tọa độ nút 'Press and Hold'")
                await asyncio.sleep(random.uniform(4, 7))  # Random delay 4-7s
                
                # ✅ BƯỚC 4: GIỮ NÚT "PRESS AND HOLD"
                print("\n 🔍 Giữ nút 'Press and Hold'...")
                
                PRESS_HOLD_X = 270  # ← THAY THEO SCREENSHOT CỦA BẠN
                PRESS_HOLD_Y = 470  # ← THAY THEO SCREENSHOT CỦA BẠN
                
                # Di chuyển chuột đến nút một cách tự nhiên với nhiều điểm dừng
                await page.mouse.move(PRESS_HOLD_X + random.uniform(-10, 10), PRESS_HOLD_Y + random.uniform(-10, 10), steps=random.randint(20, 30))
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # Thêm hover nhẹ trước khi click
                await page.mouse.move(PRESS_HOLD_X, PRESS_HOLD_Y, steps=5)
                await asyncio.sleep(random.uniform(0.2, 0.5))
                
                await page.mouse.down()
                print(" � Nhấn xuống...")
                
                # Giữ với thời gian random tự nhiên hơn
                hold_time = random.uniform(2.0, 3.5)  # Giữ 2-3.5 giây (tự nhiên hơn)
                await asyncio.sleep(hold_time)
                
                # Thêm micro-movement nhỏ trong khi giữ (như người thật)
                try:
                    await page.mouse.move(PRESS_HOLD_X + random.uniform(-2, 2), PRESS_HOLD_Y + random.uniform(-2, 2), steps=3)
                    await asyncio.sleep(0.1)
                except Exception:
                    pass
                
                await page.mouse.up()
                print(" 👆 Thả chuột!")
                
                await asyncio.sleep(random.uniform(2, 4))  # Random delay sau khi thả
                print(" ✅ Hoàn thành BƯỚC 7! Đang đợi trang xử lý captcha...")

                # Đợi trang/captcha xử lý xong, load sang bước tiếp theo
                try:
                    await page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    # Nếu không detect được load_state thì chỉ chờ thêm một chút
                    await asyncio.sleep(3)
                else:
                    # Sau khi network idle, vẫn chờ thêm một chút cho UI ổn định
                    await asyncio.sleep(2)

                # Kiểm tra nếu bị chặn tạo tài khoản (trang lỗi "We can't create your account")
                try:
                    block_el = await page.query_selector("text=We can't create your account")
                except Exception:
                    block_el = None

                if block_el:
                    print("\n❌ Microsoft hiển thị trang 'We can't create your account' -> kết thúc phiên làm việc.")
                    try:
                        await page.screenshot(path=f"blocked_{int(time.time())}.png", full_page=True)
                        print(" 📸 Đã chụp màn hình lỗi blocked_*.png")
                    except Exception:
                        pass
                    return None
            except Exception as e:
                print(f" ❌ Lỗi BƯỚC 7 (manual): {e}")
                import traceback
                traceback.print_exc()
            # bước 8: xử lý dialog Stay signed in?
            # Sau khi qua CAPTCHA, nếu xuất hiện dialog với nút Yes (Stay signed in?) thì click Yes
            try:
                btn_yes = await page.query_selector(
                    "button[data-testid='primaryButton']:has-text('Yes')"
                )
                if btn_yes:
                    print(" 🔘 Tìm thấy nút Yes (primaryButton), đang click...")
                    await btn_yes.click()
                    await asyncio.sleep(2)
            except Exception:
                pass

            # ===== BƯỚC 9: CHỈ LƯU KHI ĐÃ VÀO INBOX =====
            print("\n[BƯỚC 9] Kiểm tra đã vào inbox chưa...")
            inbox_ok = await self.wait_inbox_ready(page)

            if not inbox_ok:
                print(" ❌ Chưa vào được inbox, KHÔNG lưu tài khoản.")
                try:
                    screenshot = f"inbox_not_ready_{int(time.time())}.png"
                    await page.screenshot(path=screenshot, full_page=True)
                    print(f" 📸 Đã chụp màn hình: {screenshot}")
                except Exception:
                    pass
                return None

            # ===== BƯỚC 10: LƯU THÔNG TIN (Chỉ khi đã vào inbox)====            
            # print("\n[BƯỚC 10] Lưu thông tin tài khoản")
            account_info = {
                "email": full_email,
                "password": password,
                "firstname": first_name_str,
                "lastname": last_name_str,
                "birthdate": f"{birth_month_str} {birth_day_str}, {birth_year_str}",
                "created_time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Lưu vào các file
            await self.save_account_info(account_info)
            
            # ===== HOÀN TẤT =====
            print("\n" + "="*70)
            print("✅ HOÀN THÀNH TẠO TÀI KHOẢN!")
            print("="*70)
            print(f"📧 Email: {account_info['email']}")
            print(f"🔑 Password: {account_info['password']}")
            print(f"👤 Name: {account_info['firstname']} {account_info['lastname']}")
            print(f"🎂 Birth: {account_info['birthdate']}")
            print(f"⏰ Created: {account_info['created_time']}")
            print("="*70)
            print("\n💾 Thông tin đã được lưu vào:")
            print("   - hotmail_accounts.txt")
            print("   - hotmail_accounts.json")
            print("   - hotmail_accounts.csv")
            print("="*70)
            return account_info
            
        except Exception as e:
            print(f"\n❌ LỖI: {e}")
            import traceback
            traceback.print_exc()            
            # Chụp ảnh màn hình lỗi
            try:
                screenshot = f"error_{int(time.time())}.png"
                await page.screenshot(path=screenshot, full_page=True)
                print(f"   📸 Đã lưu ảnh lỗi: {screenshot}")
            except:
                pass
            # Sau khi đã lưu xong account_info và in ra thông tin
            return None
        

async def main():
    """Hàm chính để chạy chương trình"""
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "TẠO TÀI KHOẢN HOTMAIL/OUTLOOK TỰ ĐỘNG" + " "*15 + "║")
    print("║" + " "*20 + "Version 7.0 - Botright Official" + " "*20 + "║")
    print("║" + " "*18 + "Date: Nov 11, 2025 - 6:20 PM" + " "*19 + "║")
    print("╚" + "="*68 + "╝\n")
    
    print("🚀 Đang khởi động Botright (Chống phát hiện bot tự động)...")
    
    # Khởi tạo Botright client
    botright_client = await botright.Botright(
        headless=False  # Hiển thị trình duyệt để user có thể giải CAPTCHA
    )
    
    browser = None
    page = None
    
    try:
        print("   ✓ Đang khởi tạo Botright Client...")
        
        # Tạo browser với Botright (tự động bypass anti-bot)
        browser = await botright_client.new_browser(
            viewport={"width": 900, "height": 600}
        )
        print("   ✓ Đã khởi động Chrome với Botright")
        
        page = await browser.new_page()
        print("   ✓ Đã tạo trang mới")
        # Tăng timeout mặc định để tránh lỗi Timeout 30s trên các trang nặng của Microsoft
        try:
            await page.set_default_timeout(60000)  # 60s cho thao tác element
            await page.set_default_navigation_timeout(90000)  # 90s cho điều hướng
        except Exception:
            pass
        
        print("\n🛡️  Botright đã tự động bypass:")
        print("   • WebDriver Detection")
        print("   • Canvas Fingerprinting")
        print("   • Audio Fingerprinting")
        print("   • WebGL Fingerprinting")
        print("   • Font Fingerprinting")
        print("   • Plugin Detection")
        print("   • Timezone/Language Spoofing")
        
        # Tạo instance của HotmailAccountCreator
        creator = HotmailAccountCreator()
        
        # Hỏi người dùng chọn domain
        print("\n" + "-"*70)
        print("📮 Chọn domain email:")
        print("   1. @hotmail.com")
        print("   2. @outlook.com")
        print("   3. Ngẫu nhiên (Random)")
        print("-"*70)
        
        domain_choice = input("Nhập lựa chọn (1/2/3) [mặc định: 3]: ").strip()
        
        if domain_choice == "1":
            domain = "hotmail"
            print(f"\n✓ Đã chọn: @HOTMAIL.COM")
        elif domain_choice == "2":
            domain = "outlook"
            print(f"\n✓ Đã chọn: @OUTLOOK.COM")
        else:
            domain = random.choice(["hotmail", "outlook"])
            print(f"\n✓ Đã chọn: @{domain.upper()}.COM (ngẫu nhiên)")
        
        # Tạo tài khoản đầu tiên
        print("\n" + "="*70)
        print("🎯 BẮT ĐẦU TẠO TÀI KHOẢN ĐẦU TIÊN...")
        print("="*70)
        
        account = await creator.create_account(page, email_prefix="myuser", domain=domain)
        
        if account:
            print("\n🎉 TẠO TÀI KHOẢN ĐẦU TIÊN THÀNH CÔNG!")
            
            # Hỏi có muốn tạo thêm không
            while True:
                print("\n" + "-"*70)
                choice = input("❓ Bạn có muốn tạo thêm tài khoản khác không? (y/n): ").strip().lower()
                
                if choice == 'y' or choice == 'yes':
                    print("\n" + "="*70)
                    print("🔄 ĐANG TẠO TÀI KHOẢN MỚI...")
                    print("="*70)
                    
                    # Chọn domain ngẫu nhiên cho tài khoản mới
                    new_domain = random.choice(["hotmail", "outlook"])
                    print(f"   ℹ Domain ngẫu nhiên: @{new_domain.upper()}.COM")
                    
                    # Mở trang mới cho tài khoản mới (giữ nguyên browser)
                    new_page = await browser.new_page()
                    new_account = await creator.create_account(new_page, email_prefix="myuser", domain=new_domain)
                    
                    if new_account:
                        print("\n🎉 TẠO TÀI KHOẢN MỚI THÀNH CÔNG!")
                        
                        # Đóng trang cũ để tiết kiệm tài nguyên
                        try:
                            await new_page.close()
                        except:
                            pass
                    else:
                        print("\n❌ TẠO TÀI KHOẢN MỚI THẤT BẠI!")
                        print("   💡 Gợi ý: Có thể Microsoft đang chặn. Hãy thử lại sau vài phút.")
                        break
                        
                elif choice == 'n' or choice == 'no':
                    print("\n👋 Cảm ơn bạn đã sử dụng công cụ!")
                    break
                else:
                    print("⚠️  Vui lòng nhập 'y' (có) hoặc 'n' (không)")
        else:
            print("\n❌ TẠO TÀI KHOẢN ĐẦU TIÊN THẤT BẠI!")
            print("   💡 Gợi ý:")
            print("      - Kiểm tra kết nối Internet")
            print("      - Xem file ảnh lỗi (nếu có)")
            print("      - Thử chạy lại sau vài phút")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Đã dừng chương trình (Ctrl+C)")
    
    except Exception as e:
        print(f"\n❌ Lỗi không mong đợi: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Đóng browser và botright client
        print("\n🔄 Đang đóng trình duyệt và dọn dẹp...")
        try:
            if browser:
                await browser.close()
                print("   ✓ Đã đóng browser")
            
            await botright_client.close()
            print("   ✓ Đã đóng Botright client")
        except Exception as e:
            print(f"   ⚠️  Lỗi khi đóng: {e}")
        
        print("\n" + "="*70)
        print("👋 TẠM BIỆT! HẸN GẶP LẠI!")
        print("="*70)


if __name__ == "__main__":
    print("\n⚡ KHỞI ĐỘNG CHƯƠNG TRÌNH...\n")
    asyncio.run(main())
