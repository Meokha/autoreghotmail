from __future__ import annotations

from pathlib import Path

from db import upsert_account

TXT_PATH = Path(__file__).with_name("hotmail_accounts.txt")


def parse_accounts(txt_path: Path):
    if not txt_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file {txt_path}")

    accounts = []
    current = {}

    with txt_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("Email:"):
                current.setdefault("created_time", "")
                current["email"] = line.split(":", 1)[1].strip()
            elif line.startswith("Password:"):
                current["password"] = line.split(":", 1)[1].strip()
            elif line.startswith("Name:"):
                full_name = line.split(":", 1)[1].strip()
                parts = full_name.split()
                current["firstname"] = parts[0]
                current["lastname"] = " ".join(parts[1:]) if len(parts) > 1 else ""
            elif line.startswith("Birth:"):
                current["birthdate"] = line.split(":", 1)[1].strip()
            elif line.startswith("Created:"):
                current["created_time"] = line.split(":", 1)[1].strip()
                if {"email", "password", "firstname", "lastname", "birthdate", "created_time"} <= current.keys():
                    accounts.append(current.copy())
                current = {}
    return accounts


def main():
    accounts = parse_accounts(TXT_PATH)
    if not accounts:
        print("Không tìm thấy tài khoản nào trong TXT.")
        return

    for acc in accounts:
        upsert_account(acc)
        print(f"✓ Đã import {acc['email']} vào hotmail_accounts.db")

    print(f"Hoàn tất: {len(accounts)} tài khoản đã được thêm vào DB.")


if __name__ == "__main__":
    main()
