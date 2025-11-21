"""Script warm-up tài khoản Hotmail sau khi đã lưu vào SQLite."""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime
from typing import Optional

import botright

from db import fetch_pending_accounts, update_warmup_status

WARMUP_ACTIONS = ["open_inbox", "mark_read", "send_test"]  # add_contact tạm dừng sử dụng


async def _human_type(page, text: str, *, delay_range: tuple[float, float] = (0.05, 0.12)):
    for ch in text:
        await page.keyboard.type(ch)
        await asyncio.sleep(random.uniform(*delay_range))


async def _fill_recipient(page, target: str) -> bool:
    recipient_selectors = [
        "div[aria-label='To'] div[contenteditable='true']",
        "div[aria-label='To']",
        "div[role='presentation'][aria-label='To']",
        "input[aria-label='To']",
        "div[aria-label='Email or phone number']",
        "input[aria-label='Email or phone number']",
    ]
    for sel in recipient_selectors:
        try:
            field = await page.wait_for_selector(sel, timeout=6000)
            await field.click()
            try:
                await field.fill("")
            except Exception:
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Delete")
            await _human_type(page, target)
            await page.keyboard.press("Enter")
            return True
        except Exception:
            continue
    return False


async def _fill_first_selector(page, selectors: list[str], value: str, *, timeout: int = 8000, human: bool = False) -> bool:
    for selector in selectors:
        try:
            field = await page.wait_for_selector(selector, timeout=timeout)
            await field.click()
            try:
                await field.fill("")
            except Exception:
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Delete")
            if human:
                await _human_type(page, value)
            else:
                await field.type(value)
            return True
        except Exception:
            continue
    return False


async def _send_test_mail(page, *, sender: str, target: str) -> bool:
    try:
        await page.goto("https://outlook.live.com/mail/0/", wait_until="domcontentloaded", timeout=60000)
        new_mail_btn = await page.wait_for_selector("button[aria-label='New mail']", timeout=15000)
        await new_mail_btn.click()
        await asyncio.sleep(2)

        if not await _fill_recipient(page, target):
            raise RuntimeError("Không tìm thấy ô To trong cửa sổ compose")

        subject_selectors = [
            "input[aria-label='Add a subject']",
            "input[aria-label='Subject']",
        ]
        subject = None
        for sel in subject_selectors:
            try:
                subject = await page.wait_for_selector(sel, timeout=8000)
                break
            except Exception:
                continue
        if not subject:
            raise RuntimeError("Không tìm thấy ô Subject")
        subject_text = random.choice([
            "Hello from warmup",
            "Testing mail",
            "Ping from bot",
            "Greetings",
        ])
        await subject.click()
        await asyncio.sleep(0.2)
        await _human_type(page, subject_text, delay_range=(0.04, 0.1))
        body = await page.wait_for_selector("div[aria-label='Message body']", timeout=15000)
        body_text = random.choice([
            "Just keeping the inbox active",
            "Automated warmup message, please ignore",
            "Sending random content for warmup",
            "Hope you're having a good day!",
        ])
        await body.focus()
        await asyncio.sleep(0.2)
        await _human_type(page, body_text + "\nSent from " + sender, delay_range=(0.03, 0.09))
        send_selectors = [
            "button[title='Send']",
            "button[aria-label='Send']",
            "button[id^='splitButton'][title*='Send']",
            "button[data-icon-name='Send']",
        ]
        send_btn = None
        for sel in send_selectors:
            try:
                send_btn = await page.wait_for_selector(sel, timeout=8000)
                break
            except Exception:
                continue
        if not send_btn:
            raise RuntimeError("Không tìm thấy nút Send")
        await send_btn.click()
        await asyncio.sleep(3)
        try:
            await page.wait_for_selector("div[role='status']:has-text('Sent')", timeout=5000)
        except Exception:
            pass
        await asyncio.sleep(3)
        return True
    except Exception as exc:
        print(f"[Warmup] Lỗi gửi mail test: {exc}")
        return False


async def _mark_first_mail(page) -> bool:
    try:
        folders_to_try = ["Junk Email", "Inbox"]
        mail_selectors = [
            "div[role='option'][aria-label*='Unread']",
            "div[role='option']",
            "div[role='listitem']",
            "div[data-selection-index]",
        ]
        mark_button_selectors = [
            "button[aria-label='Mark as read']",
            "button[title='Mark as read']",
            "button.ms-Button:has-text('Mark as read')",
            "button.ms-Button--icon[aria-label='Mark as read']",
            "div[role='group'] button[title='Mark as read']",
        ]

        # Thử click tab Focused/Other để chắc chắn có conversation hiển thị
        tab_selectors = [
            "button[role='tab'][name='Focused']",
            "button[role='tab'][name='Other']",
        ]
        for sel in tab_selectors:
            try:
                tab = await page.query_selector(sel)
                if tab:
                    await tab.click()
                    await asyncio.sleep(0.8)
            except Exception:
                continue

        for folder in folders_to_try:
            if not await _select_folder(page, folder):
                continue
            mail_row = None
            for sel in mail_selectors:
                try:
                    mail_row = await page.wait_for_selector(sel, timeout=15000)
                    if mail_row:
                        break
                except Exception:
                    continue
            if not mail_row:
                continue
            try:
                await mail_row.scroll_into_view_if_needed()
            except Exception:
                pass
            await mail_row.click()
            await asyncio.sleep(1.2)

            # Nếu có nút Mark as read ngay trên dòng thì click trực tiếp
            try:
                row_mark_btn = await mail_row.query_selector("button[aria-label='Mark as read'], button[title='Mark as read']")
            except Exception:
                row_mark_btn = None
            if row_mark_btn:
                try:
                    await row_mark_btn.click()
                    await asyncio.sleep(1.0)
                    return True
                except Exception:
                    pass

            clicked = await _click_first_selector(page, mark_button_selectors, timeout=4000)
            if not clicked:
                # Phím tắt chuẩn của Outlook Web là Ctrl+Q, fallback Shift+Q
                for shortcut in ["Control+Q", "Shift+Q"]:
                    try:
                        await page.keyboard.press(shortcut)
                        clicked = True
                        break
                    except Exception:
                        continue
            await asyncio.sleep(1.5)
            return clicked
        return False
    except Exception as exc:
        print(f"[Warmup] Lỗi mark read: {exc}")
        return False


# async def _add_contact(page, display_name: str, email: str) -> bool:
#     try:
#         await page.goto("https://outlook.live.com/people/0/", wait_until="domcontentloaded", timeout=60000)
#         await asyncio.sleep(2)
#         add_btn = await page.wait_for_selector("button[aria-label='New contact']", timeout=20000)
#         await add_btn.click()
#         await asyncio.sleep(2)
#         name_input = await page.wait_for_selector("input[aria-label='First name']", timeout=15000)
#         await name_input.fill(display_name)
#         email_input = await page.wait_for_selector("input[aria-label='Email']", timeout=15000)
#         await email_input.fill(email)
#         save_btn = await page.wait_for_selector("button[aria-label='Create']", timeout=15000)
#         await save_btn.click()
#         await asyncio.sleep(3)
#         return True
#     except Exception as exc:
#         print(f"[Warmup] Lỗi thêm contact: {exc}")
#         return False


async def _select_folder(page, folder_name: str) -> bool:
    await _ensure_nav_open(page)
    folder_lower = folder_name.lower()
    selectors = [
        f"div[data-folder-name='{folder_lower}']",
        f"button[title='{folder_name}']",
        f"button:has-text('{folder_name}')",
        f"div[role='treeitem']:has-text('{folder_name}')",
        f"span[title='{folder_name}']",
    ]
    for sel in selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=6000)
            if el:
                try:
                    await el.scroll_into_view_if_needed()
                except Exception:
                    pass
                await el.click()
                await asyncio.sleep(2)
                return True
        except Exception:
            continue
    return False


async def _ensure_nav_open(page) -> None:
    try:
        toggle = await page.query_selector("button[aria-label='Show navigation pane']")
        if toggle:
            await toggle.click()
            await asyncio.sleep(1.5)
    except Exception:
        pass


async def _click_first_selector(page, selectors: list[str], *, timeout: int = 6000) -> bool:
    for selector in selectors:
        try:
            btn = await page.wait_for_selector(selector, timeout=timeout)
            await btn.click()
            return True
        except Exception:
            continue
    return False


async def warmup_account(
    account: dict,
    *,
    proxy: Optional[str] = None,
    window_conf: Optional[dict] = None,
    target_email: Optional[str] = None,
) -> bool:
    bot = None
    browser = None
    page = None
    email = account["email"]
    try:
        bot = await botright.Botright(headless=False, block_images=True)
        browser_kwargs = window_conf or {}
        browser = await bot.new_browser(proxy=proxy, **browser_kwargs)
        page = await browser.new_page()

        print(f"[Warmup] Đăng nhập {email}...")
        await page.goto("https://login.live.com/", wait_until="domcontentloaded", timeout=60000)
        username_ok = await _fill_first_selector(
            page,
            [
                "input[name='loginfmt']",
                "input#usernameEntry",
                "input[type='email']",
            ],
            email,
        )
        if not username_ok:
            raise RuntimeError("Không tìm thấy ô nhập Email/phone trên trang đăng nhập")
        await _click_first_selector(page, ["input[type='submit']", "button[type='submit']", "button[data-reportingid='LoginSubmit']"])
        await page.wait_for_timeout(2000)

        pwd_ok = await _fill_first_selector(
            page,
            [
                "input[name='passwd']",
                "input#passwordInput",
                "input[type='password']",
            ],
            account["password"],
        )
        if not pwd_ok:
            raise RuntimeError("Không tìm thấy ô nhập mật khẩu")
        await _click_first_selector(page, ["input[type='submit']", "button[type='submit']", "button[data-reportingid='LoginSubmit']"])
        await asyncio.sleep(5)

        # Stay signed in prompt
        try:
            stay_btn = await page.wait_for_selector("input#idBtn_Back", timeout=5000)
            await stay_btn.click()
        except Exception:
            pass

        await page.goto("https://outlook.live.com/mail/0/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(3, 6))

        results = []
        results.append(("open_inbox", True))
        mark_success = await _mark_first_mail(page)
        if not mark_success:
            await asyncio.sleep(3)
            mark_success = await _mark_first_mail(page)
        results.append(("mark_read", mark_success))
        recipient = target_email or email
        if mark_success:
            await asyncio.sleep(random.uniform(2, 4))
        else:
            print("[Warmup] Không đánh dấu được thư nào, vẫn tiếp tục gửi mail")
        send_success = await _send_test_mail(page, sender=email, target=recipient)
        results.append(("send_test", send_success))
        print("[Warmup] Bỏ qua bước add_contact theo yêu cầu")

        success = all(flag for _, flag in results)
        status = "warmed" if success else "warmup_failed"
        note = ", ".join(f"{name}:{'ok' if ok else 'fail'}" for name, ok in results)
        update_warmup_status(
            email,
            status=status,
            proxy=proxy,
            note=note,
            last_activity_at=datetime.utcnow().isoformat(),
        )
        print(f"[Warmup] Hoàn tất {email}: {note}")
        return success
    except Exception as exc:
        print(f"[Warmup] Lỗi với {email}: {exc}")
        update_warmup_status(email, status="warmup_failed", note=str(exc))
        return False
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if bot:
            try:
                await bot.close()
            except Exception:
                pass


async def main():
    pending = fetch_pending_accounts(limit=3)
    if not pending:
        print("[Warmup] Không có tài khoản nào cần warm-up.")
        return

    for acc in pending:
        proxy = acc.get("proxy")
        await warmup_account(acc, proxy=proxy)
        await asyncio.sleep(random.uniform(10, 25))


if __name__ == "__main__":
    asyncio.run(main())
