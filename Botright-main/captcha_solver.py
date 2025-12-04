"""Script warm-up tài khoản Hotmail sau khi đã lưu vào SQLite."""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime
from typing import Optional
import re

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


def _scale_timeout(value: int, fast: bool) -> int:
    if fast:
        return max(1000, int(value * 0.5))
    return int(value)


async def _send_test_mail(page, *, sender: str, target: str, fast: bool = False) -> bool:
    try:
        await page.goto("https://outlook.live.com/mail/0/", wait_until="domcontentloaded", timeout=_scale_timeout(60000, fast))
        # Try multiple possible compose/selectors to handle UI variations
        compose_selectors = [
            "button[aria-label='New mail']",
            "button[aria-label='New message']",
            "button[title='New message']",
            "button[data-icon-name='Mail']",
            "[data-automation-id='NewMessageButton']",
            "button[aria-label*='New']",
        ]
        new_mail_btn = None
        for sel in compose_selectors:
            try:
                new_mail_btn = await page.wait_for_selector(sel, timeout=_scale_timeout(2500, fast))
                if new_mail_btn:
                    await new_mail_btn.click()
                    break
            except Exception:
                new_mail_btn = None
                continue
        # if no compose button found, try keyboard shortcut 'N' (Outlook sometimes supports it)
        if not new_mail_btn:
            try:
                await page.keyboard.press('n')
            except Exception:
                pass
        await asyncio.sleep(1 if fast else 2)

        if not await _fill_recipient(page, target):
            raise RuntimeError("Không tìm thấy ô To trong cửa sổ compose")

        subject_selectors = [
            "input[aria-label='Add a subject']",
            "input[aria-label='Subject']",
            "input[placeholder*='Subject']",
            "input[name='Subject']",
        ]
        subject = None
        for sel in subject_selectors:
            try:
                subject = await page.wait_for_selector(sel, timeout=_scale_timeout(8000, fast))
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
        # find the message body area
        body_selectors = ["div[aria-label='Message body']", "div[role='document']", "div[aria-label*='Message body']", "div[contenteditable='true'][aria-label*='Message body']"]
        body = None
        for sel in body_selectors:
            try:
                body = await page.wait_for_selector(sel, timeout=_scale_timeout(2500, fast))
                if body:
                    break
            except Exception:
                continue
        if not body:
            raise RuntimeError("Không tìm thấy ô nhập nội dung thư (body)")
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
            "button[role='button'][name='Send']",
        ]
        send_btn = None
        for sel in send_selectors:
            try:
                send_btn = await page.wait_for_selector(sel, timeout=_scale_timeout(2500, fast))
                if send_btn:
                    await send_btn.click()
                    break
            except Exception:
                send_btn = None
                continue

        # If no send button found/clicked, try keyboard shortcut Ctrl+Enter as fallback
        if not send_btn:
            try:
                await page.keyboard.down('Control')
                await page.keyboard.press('Enter')
                await page.keyboard.up('Control')
            except Exception:
                try:
                    # Try Ctrl+M (some layouts) or just press Enter in body
                    await page.keyboard.press('Enter')
                except Exception:
                    raise RuntimeError("Không tìm thấy nút Send và không thể gửi bằng phím tắt")

        await asyncio.sleep(1 if fast else 3)
        try:
            await page.wait_for_selector("div[role='status']:has-text('Sent')", timeout=_scale_timeout(4000, fast))
        except Exception:
            # Some layouts don't show a 'Sent' toast consistently; continue and treat as success if no exception
            pass
        await asyncio.sleep(1 if fast else 2)
        return True
    except Exception as exc:
        print(f"[Warmup] Lỗi gửi mail test: {exc}")
        return False


async def _mark_first_mail(page, fast: bool = False) -> bool:
    try:
        # Only inspect Inbox for marking/read actions; ignore Junk to avoid false positives
        folders_to_try = ["Inbox"]
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
                    await asyncio.sleep(0.5 if fast else 0.8)
            except Exception:
                continue

        for folder in folders_to_try:
            if not await _select_folder(page, folder):
                continue
            # Quick check for empty-folder indicators (avoid long waits when inbox/junk is empty)
            try:
                await asyncio.sleep(0.3 if fast else 0.5)
                empty_texts = [
                    "Nothing in Junk",
                    "Nothing in",
                    "No messages",
                    "Looks empty",
                    "No messages to show",
                ]
                empty_found = False
                for txt in empty_texts:
                    try:
                        el = await page.wait_for_selector(f"text=\"{txt}\"", timeout=_scale_timeout(900, fast))
                        if el:
                            empty_found = True
                            break
                    except Exception:
                        continue
                if empty_found:
                    # skip to next folder quickly
                    continue
            except Exception:
                pass

            mail_row = None
            for sel in mail_selectors:
                try:
                    mail_row = await page.wait_for_selector(sel, timeout=_scale_timeout(3000, fast))
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
            await asyncio.sleep(0.6 if fast else 1.2)

            # Nếu có nút Mark as read ngay trên dòng thì click trực tiếp
            try:
                row_mark_btn = await mail_row.query_selector("button[aria-label='Mark as read'], button[title='Mark as read']")
            except Exception:
                row_mark_btn = None
            if row_mark_btn:
                try:
                    await row_mark_btn.click()
                    await asyncio.sleep(0.6 if fast else 1.0)
                    return True
                except Exception:
                    pass

            clicked = await _click_first_selector(page, mark_button_selectors, timeout=_scale_timeout(4000, fast), fast=fast)
            if not clicked:
                # Phím tắt chuẩn của Outlook Web là Ctrl+Q, fallback Shift+Q
                for shortcut in ["Control+Q", "Shift+Q"]:
                    try:
                        await page.keyboard.press(shortcut)
                        clicked = True
                        break
                    except Exception:
                        continue
            await asyncio.sleep(0.8 if fast else 1.5)
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


async def _click_first_selector(page, selectors: list[str], *, timeout: int = 6000, fast: bool = False) -> bool:
    for selector in selectors:
        try:
            btn = await page.wait_for_selector(selector, timeout=_scale_timeout(timeout, fast))
            await btn.click()
            return True
        except Exception:
            continue
    return False


async def _extract_otps_from_text(text: str) -> list[str]:
    if not text:
        return []
    matches = re.findall(r"\b(\d{4,8})\b", text)
    seen = set()
    out = []
    for m in matches:
        if m not in seen:
            out.append(m)
            seen.add(m)
    return out


async def _scan_inbox_for_otps(page, max_messages: int = 6, fast: bool = False) -> list[str]:
    otps = []
    try:
        await page.goto("https://outlook.live.com/mail/0/", wait_until="domcontentloaded", timeout=_scale_timeout(60000, fast))
        await asyncio.sleep(0.8 if fast else 1.5)
        await _select_folder(page, "Inbox")
        await asyncio.sleep(0.6 if fast else 1.0)

        list_selectors = [
            "div[role='option']",
            "div[role='listitem']",
            "div[data-selection-index]",
            "div[aria-label*='Unread']",
        ]
        rows = []
        for sel in list_selectors:
            try:
                found = await page.query_selector_all(sel)
                if found and len(found) > 0:
                    rows = found
                    break
            except Exception:
                continue

        if not rows:
            return []

        # Prefer only the newest message(s); stop after first OTP found or after checking the first message
        for row in rows[:1]:
            try:
                await row.scroll_into_view_if_needed()
                await row.click()
                await asyncio.sleep(0.5 if fast else 0.8)
                content_selectors = [
                    "div[aria-label='Message body']",
                    "div[role='document']",
                    "div[aria-label*='Message body']",
                ]
                message_text = None
                for sel in content_selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            message_text = await el.inner_text()
                            if message_text and len(message_text) > 10:
                                break
                    except Exception:
                        continue
                if message_text:
                    found = await _extract_otps_from_text(message_text)
                    for code in found:
                        if code not in otps:
                            otps.append(code)
                            print(f"[Warmup][OTP] Found OTP: {code}")
                    # stop after first message's OTPs to avoid junk folder noise
                    if otps:
                        return otps
                await asyncio.sleep(0.2 if fast else 0.4)
            except Exception:
                continue
    except Exception as exc:
        print(f"[Warmup] OTP scan failed: {exc}")
    return otps


async def warmup_account(
    account: dict,
    *,
    proxy: Optional[str] = None,
    window_conf: Optional[dict] = None,
    target_email: Optional[str] = None,
    fast: bool = False,
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

        await page.goto("https://outlook.live.com/mail/0/", wait_until="domcontentloaded", timeout=_scale_timeout(60000, fast))
        await asyncio.sleep(random.uniform(1, 2) if fast else random.uniform(3, 6))

        # scan inbox before actions for OTPs
        otps_before = await _scan_inbox_for_otps(page, max_messages=6, fast=fast)
        # If OTPs already present, stop further warmup steps and proceed
        if otps_before:
            seen = []
            s = set()
            for c in otps_before:
                if c not in s:
                    s.add(c)
                    seen.append(c)
            note = "; OTPs: " + ",".join(seen)
            update_warmup_status(
                email,
                status="warmed",
                proxy=proxy,
                note=note,
                last_activity_at=datetime.utcnow().isoformat(),
            )
            print(f"[Warmup] OTP(s) already present for {email}: {seen}")
            return True, seen

        results = []
        results.append(("open_inbox", True))
        mark_success = await _mark_first_mail(page, fast=fast)
        if not mark_success:
            await asyncio.sleep(1 if fast else 3)
            mark_success = await _mark_first_mail(page, fast=fast)

        # After attempting to mark/read, scan again for OTPs and stop early if found
        otps_after_mark = await _scan_inbox_for_otps(page, max_messages=2, fast=fast)
        if otps_after_mark:
            seen = []
            s = set()
            for c in otps_after_mark:
                if c not in s:
                    s.add(c)
                    seen.append(c)
            note = ", ".join(f"open_inbox:ok, mark_read:{'ok' if mark_success else 'fail'}") + "; OTPs: " + ",".join(seen)
            status = "warmed"
            update_warmup_status(
                email,
                status=status,
                proxy=proxy,
                note=note,
                last_activity_at=datetime.utcnow().isoformat(),
            )
            print(f"[Warmup] Found OTP(s) after mark for {email}: {seen}")
            return True, seen
        results.append(("mark_read", mark_success))
        recipient = target_email or email
        if mark_success:
            await asyncio.sleep(random.uniform(1, 2) if fast else random.uniform(2, 4))
        else:
            print("[Warmup] Không đánh dấu được thư nào, vẫn tiếp tục gửi mail")
        send_success = await _send_test_mail(page, sender=email, target=recipient, fast=fast)
        results.append(("send_test", send_success))
        print("[Warmup] Bỏ qua bước add_contact theo yêu cầu")

        # scan after actions for any new OTPs
        otps_after = await _scan_inbox_for_otps(page, max_messages=6, fast=fast)

        success = all(flag for _, flag in results)
        status = "warmed" if success else "warmup_failed"
        note = ", ".join(f"{name}:{'ok' if ok else 'fail'}" for name, ok in results)

        # include discovered OTPs (deduped) in note and DB
        otp_found = []
        try:
            if otps_before:
                otp_found.extend(otps_before)
            if otps_after:
                otp_found.extend(otps_after)
            seen = set()
            ordered = []
            for c in otp_found:
                if c not in seen:
                    seen.add(c)
                    ordered.append(c)
            if ordered:
                note = note + "; OTPs: " + ",".join(ordered)
        except Exception:
            ordered = []

        update_warmup_status(
            email,
            status=status,
            proxy=proxy,
            note=note,
            last_activity_at=datetime.utcnow().isoformat(),
        )
        print(f"[Warmup] Hoàn tất {email}: {note}")
        return success, ordered
    except Exception as exc:
        print(f"[Warmup] Lỗi với {email}: {exc}")
        update_warmup_status(email, status="warmup_failed", note=str(exc))
        return False, []
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
        ok, otps = await warmup_account(acc, proxy=proxy)
        if otps:
            print(f"[Warmup] OTPs for {acc.get('email')}: {otps}")
        await asyncio.sleep(random.uniform(10, 25))


if __name__ == "__main__":
    asyncio.run(main())
