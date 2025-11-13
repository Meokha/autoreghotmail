import tkinter as tk
from tkinter import ttk
import threading
import random
import time
import asyncio

import botright
import hcaptcha_challenger as solver
from hotmail_auto_simple import HotmailAccountCreator
from playwright._impl._errors import TargetClosedError


class MultiHotmailGUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Auto hotmail registration")
        self.window.geometry("640x460")
        self.running = False
        self.threads = []
        self.account_list = []
        # Lấy kích thước màn hình để tính layout cửa sổ trình duyệt
        # Gọi update_idletasks để Tk có thể trả về đúng thông số màn hình
        self.window.update_idletasks()
        self.screen_w = self.window.winfo_screenwidth()
        self.screen_h = self.window.winfo_screenheight()
        self.create_widgets()

    def create_widgets(self):
        top = ttk.Frame(self.window)
        top.pack(fill="x", pady=10, padx=10)

        label = ttk.Label(top, text="Số tài khoản cần tạo:")
        label.pack(side="left")

        self.num_accounts = ttk.Entry(top, width=8)
        self.num_accounts.pack(side="left", padx=8)
        self.num_accounts.insert(0, "3")

        self.fast_mode = tk.BooleanVar()
        fast_check = ttk.Checkbutton(top, text="Fast Mode (Tối ưu tốc độ)", variable=self.fast_mode)
        fast_check.pack(side="left", padx=8)

        domain_frame = ttk.Frame(self.window)
        domain_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(domain_frame, text="Domain:").pack(side="left")
        self.domain_choice = ttk.Combobox(domain_frame, values=["random", "hotmail", "outlook"], state="readonly", width=10)
        self.domain_choice.set("random")
        self.domain_choice.pack(side="left", padx=8)

        # Password options
        pwd_frame = ttk.Frame(self.window)
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

        button_frame = ttk.Frame(self.window)
        button_frame.pack(pady=8)

        start_button = ttk.Button(button_frame, text="Bắt đầu", command=self.start_creation)
        start_button.pack(side="left", padx=5)

        stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_creation)
        stop_button.pack(side="left", padx=5)

        delete_button = ttk.Button(button_frame, text="Delete", command=self.delete_selected)
        delete_button.pack(side="left", padx=5)

        self.tree = ttk.Treeview(self.window, columns=("stt", "email", "password"), show="headings", height=12)
        self.tree.heading("stt", text="STT")
        self.tree.heading("email", text="Email")
        self.tree.heading("password", text="Password")
        self.tree.column("stt", width=60, anchor="center")
        self.tree.column("email", width=260, anchor="w")
        self.tree.column("password", width=220, anchor="w")
        self.tree.pack(pady=10, fill="both", expand=True, padx=10)

        status_frame = ttk.Frame(self.window)
        status_frame.pack(fill="x", padx=10, pady=5)
        self.status_var = tk.StringVar(value="Sẵn sàng")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left")

    def add_account_to_table(self, email, password):
        stt = len(self.account_list) + 1
        self.account_list.append((email, password))
        self.tree.insert("", "end", values=(stt, email, password))
        self.status_var.set(f"Đã tạo {stt} tài khoản")

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
                self.account_list = [(e, p) for e, p in self.account_list if e != email]
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
        return random.choice(["hotmail", "outlook"])  # random

    def start_creation(self):
        try:
            if self.running:
                print("⚠️ Đang trong quá trình tạo tài khoản!")
                return
            total = int(self.num_accounts.get())
            if total <= 0:
                print("Số tài khoản phải lớn hơn 0")
                return
            # Giới hạn tối đa 3 cửa sổ chạy song song
            concurrency = 3 if total >= 3 else total

            self.running = True
            self.status_var.set(f"Đang tạo {total} tài khoản (tối đa {concurrency} cửa sổ song song)...")
            print("🔥 HOTMAIL AUTO CREATOR - GUI VERSION")
            print("=" * 60)
            print(f"Bắt đầu tạo {total} tài khoản Hotmail...")
            print("=" * 60)

            fast_mode_val = self.fast_mode.get()
            chosen_domain = self._resolve_domain()
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

            def worker(fast_mode: bool, domain_choice: str, fixed_pwd: str | None, index: int):
                async def run_one():
                    while self.running:
                        # Tiếp tục cho đến khi đạt đủ số tài khoản tạo thành công
                        with lock:
                            if self.created_count >= self.total_to_create:
                                break
                            job_idx = self.created_count + 1  # chỉ số hiển thị

                        bot = None
                        browser = None
                        try:
                            # Luôn hiển thị cửa sổ trong GUI để người dùng quan sát
                            bot = await botright.Botright(
                                headless=False,
                                block_images=fast_mode,
                            )
                            # Vị trí + kích thước cửa sổ theo kích thước màn hình (tối đa 3)
                            pad = 10
                            # Chia 2 cột x 2 hàng, dùng 3 ô đầu tiên
                            win_w = max(600, int((self.screen_w - 3 * pad) / 2))
                            win_h = max(400, int((self.screen_h - 3 * pad) / 2))
                            # Bảo đảm không tràn màn hình
                            win_w = min(win_w, self.screen_w - 2 * pad)
                            win_h = min(win_h, self.screen_h - 2 * pad)
                            positions = [
                                (pad, pad),
                                (pad + win_w + pad, pad),
                                (pad, pad + win_h + pad),
                            ]
                            x, y = positions[index % 3]
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

                            created_success = False
                            try:
                                creator = HotmailAccountCreator()
                                domain = domain_choice if domain_choice in ("hotmail", "outlook") else random.choice(["hotmail", "outlook"]) 
                                account = await creator.create_account(page, email_prefix="myuser", domain=domain, password=fixed_pwd)
                                just_finished = False
                                if account and self.running:
                                    self.window.after(0, self.add_account_to_table, account["email"], account["password"]) 
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
                                else:
                                    print(f"⚠️ Lỗi trong worker (job {job_idx+1}): {e}")
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

            self.threads = []
            for i in range(concurrency):
                if not self.running:
                    break
                t = threading.Thread(target=worker, args=(fast_mode_val, chosen_domain, fixed_pwd_value, i), daemon=True)
                self.threads.append(t)
                t.start()
                time.sleep(1)

            print(f"Đã bắt đầu tạo {total} tài khoản với tối đa {concurrency} cửa sổ...")
        except ValueError:
            print("Vui lòng nhập số hợp lệ")

    def run(self):
        self.window.mainloop()


def main():
    app = MultiHotmailGUI()
    app.run()


if __name__ == "__main__":
    main()
