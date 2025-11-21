import tkinter as tk
from tkinter import ttk
import threading
import random
import time
import asyncio
import queue
from datetime import datetime

import botright
import hcaptcha_challenger as solver
from captcha_solver import warmup_account
from db import fetch_pending_accounts, fetch_all_emails
from hotmail_auto_simple import HotmailAccountCreator
from playwright._impl._errors import TargetClosedError


class MultiHotmailGUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Auto hotmail registration")
        self.window.geometry("640x460")
        self.running = False
        self.threads = []
        self.account_list: list[dict] = []
        # Lấy kích thước màn hình để tính layout cửa sổ trình duyệt
        # Gọi update_idletasks để Tk có thể trả về đúng thông số màn hình
        self.window.update_idletasks()
        self.screen_w = self.window.winfo_screenwidth()
        self.screen_h = self.window.winfo_screenheight()
        self.warmup_accounts: list[dict] = []
        self.warmup_running = False
        self.warmup_thread: threading.Thread | None = None
        self.warmup_email_map: dict[str, dict] = {}
        self.warmup_queue: queue.Queue | None = None
        self.warmup_total = 0
        self.warmup_completed = 0
        self.warmup_active_workers = 0
        self.warmup_lock = threading.Lock()
        self.warmup_email_ring: list[str] = []
        self.create_widgets()

    def create_widgets(self):
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True)

        self.create_tab = ttk.Frame(notebook)
        self.warmup_tab = ttk.Frame(notebook)
        notebook.add(self.create_tab, text="Tạo tài khoản")
        notebook.add(self.warmup_tab, text="Nuôi tài khoản")

        self._build_create_tab()
        self._build_warmup_tab()

    # ===== TAB TẠO TÀI KHOẢN =====
    def _build_create_tab(self):
        top = ttk.Frame(self.create_tab)
        top.pack(fill="x", pady=10, padx=10)

        label = ttk.Label(top, text="Số tài khoản cần tạo:")
        label.pack(side="left")

        self.num_accounts = ttk.Entry(top, width=8)
        self.num_accounts.pack(side="left", padx=8)
        self.num_accounts.insert(0, "1")

        self.fast_mode = tk.BooleanVar()
        fast_check = ttk.Checkbutton(top, text="Fast Mode (Tối ưu tốc độ)", variable=self.fast_mode)
        fast_check.pack(side="left", padx=8)

        domain_frame = ttk.Frame(self.create_tab)
        domain_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(domain_frame, text="Domain:").pack(side="left")
        self.domain_choice = ttk.Combobox(domain_frame, values=["random", "hotmail", "outlook"], state="readonly", width=10)
        self.domain_choice.set("random")
        self.domain_choice.pack(side="left", padx=8)

        concurrency_frame = ttk.Frame(self.create_tab)
        concurrency_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(concurrency_frame, text="Số cửa sổ song song (1-3):").pack(side="left")
        self.concurrency_var = tk.IntVar(value=1)
        concurrency_spin = ttk.Spinbox(concurrency_frame, from_=1, to=3, width=5, textvariable=self.concurrency_var)
        concurrency_spin.pack(side="left", padx=8)

        # Password options
        pwd_frame = ttk.Frame(self.create_tab)
        pwd_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(pwd_frame, text="Password:").pack(side="left")
        self.password_mode = tk.StringVar(value="random")
        rb_random = ttk.Radiobutton(pwd_frame, text="Random mỗi tài khoản", value="random", variable=self.password_mode, command=self._toggle_password_entry)
        rb_fixed = ttk.Radiobutton(pwd_frame, text="Cố định cho tất cả", value="fixed", variable=self.password_mode, command=self._toggle_password_entry)
        rb_random.pack(side="left", padx=6)
        rb_fixed.pack(side="left", padx=6)
        self.fixed_password = ttk.Entry(pwd_frame, width=24, show="*")
        self.fixed_password.pack(side="left", padx=8)
        self.fixed_password.configure(state="disabled")

        button_frame = ttk.Frame(self.create_tab)
        button_frame.pack(pady=8)

        start_button = ttk.Button(button_frame, text="Bắt đầu", command=self.start_creation)
        start_button.pack(side="left", padx=5)

        stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_creation)
        stop_button.pack(side="left", padx=5)

        delete_button = ttk.Button(button_frame, text="Delete", command=self.delete_selected)
        delete_button.pack(side="left", padx=5)

        self.tree = ttk.Treeview(
            self.create_tab,
            columns=("stt", "email", "password", "status"),
            show="headings",
            height=12,
        )
        self.tree.heading("stt", text="STT")
        self.tree.heading("email", text="Email")
        self.tree.heading("password", text="Password")
        self.tree.heading("status", text="Trạng thái")
        self.tree.column("stt", width=60, anchor="center")
        self.tree.column("email", width=260, anchor="w")
        self.tree.column("password", width=220, anchor="w")
        self.tree.column("status", width=120, anchor="center")
        self.tree.pack(pady=10, fill="both", expand=True, padx=10)

        status_frame = ttk.Frame(self.create_tab)
        status_frame.pack(fill="x", padx=10, pady=5)
        self.status_var = tk.StringVar(value="Sẵn sàng")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left")

    # ===== TAB NUÔI TÀI KHOẢN =====
    def _build_warmup_tab(self):
        header = ttk.Label(self.warmup_tab, text="Nuôi tài khoản đã tạo (status = created)", font=("Segoe UI", 11, "bold"))
        header.pack(anchor="w", padx=10, pady=(10, 0))

        mode_frame = ttk.Frame(self.warmup_tab)
        mode_frame.pack(fill="x", padx=10, pady=4)
        ttk.Label(mode_frame, text="Chọn cách nuôi:").pack(side="left")
        self.warmup_mode = tk.StringVar(value="auto")
        ttk.Radiobutton(
            mode_frame,
            text="1) Nhập số lượng",
            value="auto",
            variable=self.warmup_mode,
        ).pack(side="left", padx=6)
        ttk.Radiobutton(
            mode_frame,
            text="2) Chọn tài khoản trong bảng",
            value="manual",
            variable=self.warmup_mode,
        ).pack(side="left", padx=6)

        control = ttk.Frame(self.warmup_tab)
        control.pack(fill="x", padx=10, pady=4)

        ttk.Label(control, text="Số tài khoản tải từ DB:").pack(side="left")
        self.warmup_limit_entry = ttk.Entry(control, width=6)
        self.warmup_limit_entry.pack(side="left", padx=6)

        ttk.Label(control, text="Cửa sổ song song (1-3):").pack(side="left", padx=(15, 4))
        self.warmup_concurrency_var = tk.IntVar(value=1)
        warmup_conc_spin = ttk.Spinbox(control, from_=1, to=3, width=4, textvariable=self.warmup_concurrency_var)
        warmup_conc_spin.pack(side="left")

        ttk.Label(control, text="Lọc trạng thái:").pack(side="left", padx=(15, 4))
        self.warmup_status_filter = ttk.Combobox(control, values=["created", "warmup_failed", "warmed", "all"], width=13, state="readonly")
        self.warmup_status_filter.set("created")
        self.warmup_status_filter.pack(side="left")

        button_frame = ttk.Frame(self.warmup_tab)
        button_frame.pack(fill="x", padx=10, pady=6)
        load_btn = ttk.Button(button_frame, text="Tải danh sách", command=self.load_warmup_accounts)
        load_btn.pack(side="left", padx=4)
        start_btn = ttk.Button(button_frame, text="Bắt đầu nuôi", command=self.start_warmup)
        start_btn.pack(side="left", padx=4)
        stop_btn = ttk.Button(button_frame, text="Dừng", command=self.stop_warmup)
        stop_btn.pack(side="left", padx=4)

        self.warmup_tree = ttk.Treeview(
            self.warmup_tab,
            columns=("stt", "email", "status", "last"),
            show="headings",
            height=12,
            selectmode="extended",
        )
        self.warmup_tree.heading("stt", text="STT")
        self.warmup_tree.heading("email", text="Email")
        self.warmup_tree.heading("status", text="Trạng thái")
        self.warmup_tree.heading("last", text="Hoạt động cuối")
        self.warmup_tree.column("stt", width=60, anchor="center")
        self.warmup_tree.column("email", width=260, anchor="w")
        self.warmup_tree.column("status", width=120, anchor="center")
        self.warmup_tree.column("last", width=180, anchor="center")
        self.warmup_tree.pack(fill="both", expand=True, padx=10, pady=10)

        status_frame = ttk.Frame(self.warmup_tab)
        status_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.warmup_status_var = tk.StringVar(value="Chưa tải danh sách")
        ttk.Label(status_frame, textvariable=self.warmup_status_var).pack(side="left")

    def add_account_to_table(self, email: str, password: str, status_text: str):
        stt = len(self.account_list) + 1
        self.account_list.append({"email": email, "password": password, "status": status_text})
        self.tree.insert("", "end", values=(stt, email, password, status_text))
        self.status_var.set(f"Đã xử lý {stt} tài khoản")

    def stop_creation(self):
        self.running = False
        self.status_var.set("Đang dừng...")
        print("⛔ Đang dừng quá trình tạo tài khoản...")

    def delete_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            print("⚠️ Vui lòng chọn tài khoản cần xóa!")
            return
        for item in selected_items:
            values = self.tree.item(item)['values']
            if values:
                email = values[1]
                self.account_list = [item for item in self.account_list if item["email"] != email]
                self.tree.delete(item)
        for idx, item in enumerate(self.tree.get_children(), 1):
            self.tree.set(item, "stt", idx)

    def _toggle_password_entry(self):
        mode = self.password_mode.get()
        if mode == "fixed":
            self.fixed_password.configure(state="normal")
        else:
            self.fixed_password.delete(0, tk.END)
            self.fixed_password.configure(state="disabled")

    def _resolve_domain(self):
        choice = (self.domain_choice.get() or "random").lower()
        if choice == "hotmail":
            return "hotmail"
        if choice == "outlook":
            return "outlook"
        return "random"  # đánh dấu để random từng tài khoản

    def _abort_creation(self, message: str):
        if not self.running:
            return
        self.running = False
        formatted = f"FAIL: {message}"
        print(f"❌ {formatted}")
        self.window.after(0, self.status_var.set, formatted)

    def _calc_window_conf(self, columns_count: int, index: int) -> dict:
        pad = 10
        columns = max(1, min(3, columns_count))
        layout_columns = columns if columns > 1 else 3
        win_w = int((self.screen_w - (layout_columns + 1) * pad) / layout_columns)
        target_height = int(self.screen_h * 0.55)
        win_h = min(target_height, self.screen_h - 2 * pad, 620)
        win_w = max(win_w, 400)
        win_h = max(win_h, 355)
        total_used_w = win_w * layout_columns + pad * (layout_columns + 1)
        if total_used_w > self.screen_w:
            win_w = int((self.screen_w - (layout_columns + 1) * pad) / layout_columns)
        win_h = min(win_h, self.screen_h - 2 * pad)
        col = index % layout_columns
        x = pad + col * (win_w + pad)
        y = pad
        return {
            "viewport": {"width": win_w, "height": win_h},
            "extra_args": [f"--window-position={x},{y}", f"--window-size={win_w},{win_h}"],
        }

    def start_creation(self):
        try:
            if self.running:
                print("⚠️ Đang trong quá trình tạo tài khoản!")
                return
            total = int(self.num_accounts.get())
            if total <= 0:
                print("Số tài khoản phải lớn hơn 0")
                return
            # Giới hạn tối đa 3 cửa sổ chạy song song (mặc định 1 để an toàn)
            try:
                requested_concurrency = int(self.concurrency_var.get())
            except (TypeError, ValueError):
                requested_concurrency = 1
            concurrency = max(1, min(3, requested_concurrency, total))

            self.running = True
            self.status_var.set(f"Đang tạo {total} tài khoản (tối đa {concurrency} cửa sổ song song)...")
            print("🔥 HOTMAIL AUTO CREATOR - GUI VERSION")
            print("=" * 60)
            print(f"Bắt đầu tạo {total} tài khoản Hotmail...")
            print("=" * 60)

            fast_mode_val = self.fast_mode.get()
            chosen_domain = self._resolve_domain()
            if chosen_domain == "random":
                print("Domain: sẽ random @hotmail/@outlook cho từng tài khoản")
            else:
                print(f"Domain cố định: @{chosen_domain}.com")
            mode = self.password_mode.get()
            fixed_pwd_value = None
            if mode == "fixed":
                val = (self.fixed_password.get() or "").strip()
                if not val:
                    print("⚠️ Bạn chọn dùng mật khẩu cố định nhưng chưa nhập. Sẽ dùng random.")
                else:
                    fixed_pwd_value = val

            # Pre-install solver models once to avoid parallel file locks
            try:
                solver.install(upgrade=False)
            except Exception:
                pass

            # Bộ đếm công việc dùng chung giữa các worker
            lock = threading.Lock()
            self.total_to_create = total
            self.created_count = 0

            def worker(fast_mode: bool, domain_choice: str, fixed_pwd: str | None, columns_count: int, index: int):
                async def run_one():
                    bot = None
                    browser = None
                    
                    # Tính toán vị trí và kích thước cửa sổ trước khi vào vòng lặp
                    pad = 10
                    # Giữ kích cỡ popup nhỏ gọn ngay cả khi chỉ chạy 1 cửa sổ bằng cách giả lập layout 3 cột
                    columns = max(1, min(3, columns_count))
                    layout_columns = columns if columns > 1 else 3
                    # Tính kích thước mỗi cửa sổ để chia đều màn hình
                    # Công thức: (màn hình - 4 khoảng padding) / 3 cửa sổ
                    win_w = int((self.screen_w - (layout_columns + 1) * pad) / layout_columns)
                    # Giảm chiều cao để popup thấp hơn màn hình (≈55% chiều cao) nhằm tránh phần trắng phía dưới
                    target_height = int(self.screen_h * 0.55)
                    win_h = min(target_height, self.screen_h - 2 * pad, 620)
                    # Đảm bảo kích thước tối thiểu để hiển thị web
                    win_w = max(win_w, 400)  # Tối thiểu 400px để hiển thị web
                    win_h = max(win_h, 355)  # Tối thiểu 360px để hiển thị web
                    # Tính lại win_w sau khi đảm bảo tối thiểu, chia lại đều để không tràn
                    total_used_w = win_w * layout_columns + pad * (layout_columns + 1)
                    if total_used_w > self.screen_w:
                        win_w = int((self.screen_w - (layout_columns + 1) * pad) / layout_columns)
                    win_h = min(win_h, self.screen_h - 2 * pad)
                    # Vị trí xếp từ trái qua phải lần lượt, chia đều màn hình
                    col = index % layout_columns
                    x = pad + col * (win_w + pad)
                    y = pad
                    
                    # Tạo bot và browser ngay khi worker khởi động (chỉ 1 lần)
                    try:
                        # Luôn hiển thị cửa sổ trong GUI để người dùng quan sát
                        bot = await botright.Botright(
                            headless=False,
                            block_images=fast_mode,
                            user_action_layer=False,
                        )
                        browser = await bot.new_browser(
                            viewport={"width": win_w, "height": win_h},
                            extra_args=[f"--window-position={x},{y}", f"--window-size={win_w},{win_h}"]
                        )
                        page = await browser.new_page()
                        # Đảm bảo cửa sổ hiển thị trước khi thao tác
                        try:
                            await page.bring_to_front()
                        except Exception:
                            pass
                        await asyncio.sleep(1.0)
                        
                        # Khai báo biến trước vòng lặp để dùng trong finally
                        job_decremented = False
                        created_success = False
                        
                        # Vòng lặp tạo tài khoản trong worker này
                        while self.running:
                            with lock:
                                if self.created_count >= self.total_to_create:
                                    break
                                job_idx = self.created_count + 1  # chỉ số hiển thị
                            
                            # Theo dõi sự kiện đóng cửa sổ để trừ mục tiêu ngay lập tức
                            job_decremented = False
                            def _on_page_close(*_args, **_kwargs):
                                nonlocal job_decremented
                                if job_decremented:
                                    return
                                with lock:
                                    if self.total_to_create > self.created_count:
                                        self.total_to_create -= 1
                                        remain = self.total_to_create - self.created_count
                                    else:
                                        remain = 0
                                job_decremented = True
                                self.window.after(0, self.status_var.set, f"Đã tạo {self.created_count}/{self.total_to_create} tài khoản (còn {remain})")
                            try:
                                page.on("close", _on_page_close)
                            except Exception:
                                pass
                            try:
                                await page.set_default_timeout(60000)
                                await page.set_default_navigation_timeout(90000)
                            except Exception:
                                pass

                            created_success = False  # Reset cho mỗi lần tạo tài khoản
                            try:
                                creator = HotmailAccountCreator()
                                domain = domain_choice if domain_choice in ("hotmail", "outlook") else random.choice(["hotmail", "outlook"]) 
                                account = await creator.create_account(page, email_prefix="myuser", domain=domain, password=fixed_pwd)
                                just_finished = False
                                attempt_email = creator.last_full_email or "(unknown)"
                                attempt_password = creator.last_password or "-"
                                if account and self.running:
                                    self.window.after(0, self.add_account_to_table, account["email"], account["password"], "SUCCESS")
                                    # Chỉ tăng bộ đếm khi thành công
                                    with lock:
                                        self.created_count += 1
                                        done = self.created_count
                                        if self.created_count >= self.total_to_create:
                                            self.running = False
                                            just_finished = True
                                        created_success = True
                                    self.window.after(0, self.status_var.set, f"Đã tạo {done}/{self.total_to_create} tài khoản")
                                    if just_finished:
                                        print("✅ ĐÃ HOÀN THÀNH TẤT CẢ TÀI KHOẢN")
                                else:
                                    if self.running:
                                        failure_text = f"Tạo tài khoản #{job_idx} thất bại, dừng toàn bộ."
                                        self.window.after(0, self.add_account_to_table, attempt_email, attempt_password, "FAILED")
                                        self._abort_creation(failure_text)
                                        job_decremented = True
                                    break
                            except TargetClosedError as e:
                                # Người dùng đóng cửa sổ: giảm mục tiêu tổng nếu còn dư
                                with lock:
                                    if self.total_to_create > self.created_count:
                                        self.total_to_create -= 1
                                        remain = self.total_to_create - self.created_count
                                    else:
                                        remain = 0
                                job_decremented = True
                                self.window.after(0, self.status_var.set, f"Đã tạo {self.created_count}/{self.total_to_create} tài khoản (còn {remain})")
                                # Không raise để finally đóng tài nguyên và worker lặp tiếp
                                break  # Thoát vòng lặp khi đóng cửa sổ
                            except Exception as e:
                                msg = str(e).lower()
                                closed_signals = [
                                    "target page, context or browser has been closed",
                                    "browser has been closed",
                                    "context has been closed",
                                    "target closed",
                                ]
                                if any(sig in msg for sig in closed_signals):
                                    # Xem như người dùng/tự động đóng cửa sổ ⇒ giảm mục tiêu
                                    with lock:
                                        if self.total_to_create > self.created_count:
                                            self.total_to_create -= 1
                                            remain = self.total_to_create - self.created_count
                                        else:
                                            remain = 0
                                    job_decremented = True
                                    self.window.after(0, self.status_var.set, f"Đã tạo {self.created_count}/{self.total_to_create} tài khoản (còn {remain})")
                                    break  # Thoát vòng lặp khi đóng cửa sổ
                                else:
                                    print(f"⚠️ Lỗi trong worker (job {job_idx}): {e}")
                                    if self.running:
                                        self.window.after(0, self.add_account_to_table, attempt_email, attempt_password, "FAILED")
                                        self._abort_creation(f"Lỗi job {job_idx}: {e}")
                                        job_decremented = True
                                    break  # Thoát nếu lỗi khác

                            if self.running:
                                pause = random.uniform(20, 40)
                                print(f"⏳ Nghỉ {pause:.1f}s trước lượt tiếp theo để giảm nghi ngờ bot...")
                                await asyncio.sleep(pause)
                    finally:
                        try:
                            if browser:
                                await browser.close()
                        except Exception:
                            pass
                        try:
                            if bot:
                                await bot.close()
                        except Exception:
                            pass
                        # Nếu job chưa thành công và chưa trừ bởi các handler, trừ mục tiêu còn lại
                        if not created_success and not job_decremented:
                            with lock:
                                if self.total_to_create > self.created_count:
                                    self.total_to_create -= 1
                                    remain = self.total_to_create - self.created_count
                                else:
                                    remain = 0
                            self.window.after(0, self.status_var.set, f"Đã tạo {self.created_count}/{self.total_to_create} tài khoản (còn {remain})")

                asyncio.run(run_one())

            layout_columns = max(3, concurrency)
            self.threads = []
            for i in range(concurrency):
                if not self.running:
                    break
                t = threading.Thread(target=worker, args=(fast_mode_val, chosen_domain, fixed_pwd_value, layout_columns, i), daemon=True)
                self.threads.append(t)
                t.start()
                # Giảm delay để tất cả cửa sổ khởi động gần như cùng lúc
                time.sleep(0.3)

            print(f"Đã bắt đầu tạo {total} tài khoản với tối đa {concurrency} cửa sổ...")
        except ValueError:
            print("Vui lòng nhập số hợp lệ")

    def run(self):
        self.window.mainloop()

    # ====== TÍNH NĂNG NUÔI ======
    def load_warmup_accounts(self):
        if self.warmup_running:
            self.warmup_status_var.set("Đang nuôi, vui lòng dừng trước khi tải lại")
            return
        raw_limit = (self.warmup_limit_entry.get() or "").strip()
        status_filter = (self.warmup_status_filter.get() or "created").lower()

        if status_filter == "all":
            limit = None
        else:
            try:
                limit = int(raw_limit)
                if limit <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                limit = 3
                self.warmup_limit_entry.delete(0, tk.END)
                self.warmup_limit_entry.insert(0, "3")

        display_filter = status_filter if status_filter else "created"
        accounts = fetch_pending_accounts(limit=limit, status_filter=display_filter)
        self.warmup_accounts = accounts
        self.warmup_email_map = {acc["email"]: acc for acc in accounts}
        for item in self.warmup_tree.get_children():
            self.warmup_tree.delete(item)
        for idx, acc in enumerate(accounts, 1):
            last = acc.get("last_activity_at") or "-"
            status = acc.get("status", "created")
            self.warmup_tree.insert("", "end", iid=acc["email"], values=(idx, acc["email"], status, last))
        if accounts:
            self.warmup_status_var.set(f"Đã nạp {len(accounts)} tài khoản (lọc {display_filter})")
        else:
            self.warmup_status_var.set(f"Không tìm thấy tài khoản status={display_filter}")

    def start_warmup(self):
        if self.warmup_running:
            self.warmup_status_var.set("Đang nuôi rồi")
            return
        mode = self.warmup_mode.get()
        accounts: list[dict] = []
        if mode == "manual":
            selected = self.warmup_tree.selection()
            if not selected:
                self.warmup_status_var.set("Hãy chọn ít nhất 1 tài khoản trong bảng")
                return
            for iid in selected:
                acc = self.warmup_email_map.get(iid)
                if acc:
                    accounts.append(acc)
        else:
            if not self.warmup_accounts:
                self.load_warmup_accounts()
            accounts = list(self.warmup_accounts)

        if not accounts:
            self.warmup_status_var.set("Không có tài khoản để nuôi")
            return

        try:
            requested_conc = int(self.warmup_concurrency_var.get())
        except (TypeError, ValueError):
            requested_conc = 1
        concurrency = max(1, min(3, requested_conc, len(accounts)))

        self.warmup_queue = queue.Queue()
        for acc in accounts:
            self.warmup_queue.put(acc)

        self.warmup_total = len(accounts)
        self.warmup_completed = 0
        self.warmup_active_workers = concurrency
        self.warmup_running = True
        self.warmup_worker_threads = []
        self.warmup_email_ring = fetch_all_emails(status_filter="all")
        self.warmup_status_var.set(f"Đang nuôi {self.warmup_total} tài khoản (tối đa {concurrency} cửa sổ)...")

        for i in range(concurrency):
            t = threading.Thread(
                target=self._warmup_worker,
                args=(self.warmup_queue, i, concurrency),
                daemon=True,
            )
            self.warmup_worker_threads.append(t)
            t.start()

    def stop_warmup(self):
        if not self.warmup_running:
            self.warmup_status_var.set("Không có phiên nuôi đang chạy")
            return
        self.warmup_running = False
        if self.warmup_queue:
            try:
                while not self.warmup_queue.empty():
                    self.warmup_queue.get_nowait()
            except queue.Empty:
                pass
        self.warmup_status_var.set("Đang dừng warm-up...")

    def _warmup_worker(self, work_queue: queue.Queue, worker_index: int, columns_count: int):
        async def runner():
            window_conf = self._calc_window_conf(columns_count, worker_index)
            while self.warmup_running:
                try:
                    account = work_queue.get_nowait()
                except queue.Empty:
                    break
                email = account["email"]
                target_email = self._pick_warmup_recipient(email)
                self.window.after(0, self._update_warmup_row, email, "Đang đăng nhập...", "...")
                success = False
                note = ""
                try:
                    success = await warmup_account(
                        account,
                        proxy=account.get("proxy"),
                        window_conf=window_conf,
                        target_email=target_email,
                    )
                except Exception as exc:
                    note = str(exc)
                    success = False
                status_text = "WARMED" if success else "FAILED"
                last_activity = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if success else "-"
                self.window.after(0, self._update_warmup_row, email, status_text, last_activity)
                message = f"{email} -> {status_text}"
                if note:
                    message += f" ({note})"
                with self.warmup_lock:
                    self.warmup_completed += 1
                    done = self.warmup_completed
                    total = self.warmup_total
                self.window.after(0, self.warmup_status_var.set, f"{done}/{total}: {message}")
                if not self.warmup_running:
                    break
                if not work_queue.empty():
                    await asyncio.sleep(random.uniform(8, 15))

            with self.warmup_lock:
                self.warmup_active_workers -= 1
                last_worker = self.warmup_active_workers <= 0

            if last_worker:
                self.warmup_running = False
                self.window.after(0, self.warmup_status_var.set, "Đã hoàn tất hoặc dừng nuôi")

        asyncio.run(runner())

    def _pick_warmup_recipient(self, sender_email: str) -> str:
        ring = [email for email in self.warmup_email_ring if email]
        if not ring:
            return sender_email
        if len(ring) == 1:
            return ring[0]
        try:
            idx = ring.index(sender_email)
        except ValueError:
            return ring[0]
        return ring[(idx + 1) % len(ring)]

    def _update_warmup_row(self, email: str, status_text: str, last_activity: str):
        if email not in self.warmup_tree.get_children():
            return
        current = list(self.warmup_tree.item(email, "values"))
        if not current:
            return
        current[2] = status_text
        current[3] = last_activity
        self.warmup_tree.item(email, values=current)

def main():
    app = MultiHotmailGUI()
    app.run()

if __name__ == "__main__":
    main()
