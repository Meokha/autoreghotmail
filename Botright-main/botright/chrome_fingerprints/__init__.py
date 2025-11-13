# botright/chrome_fingerprints/__init__.py
import asyncio
import random

class AsyncFingerprintGenerator:
    """Fake Chrome Fingerprint Generator for Botright"""

    async def generate(self, *args, **kwargs):
        # mô phỏng fingerprint cơ bản (Botright chỉ cần dữ liệu này)
        return {
            "user_agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Mozilla/5.0 (X11; Linux x86_64)",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            ]),
            "platform": random.choice(["Win32", "Linux x86_64", "MacIntel"]),
            "canvas": "fake_canvas_data_" + str(random.randint(1000, 9999)),
            "webgl": "fake_webgl_data_" + str(random.randint(1000, 9999)),
            "fonts": ["Arial", "Verdana", "Tahoma"],
            "timezone": "UTC+7",
            "language": "en-US",
        }

# Nếu Botright gọi đồng bộ
def generate_fingerprint():
    return asyncio.get_event_loop().run_until_complete(
        AsyncFingerprintGenerator().generate()
    )

__all__ = ["AsyncFingerprintGenerator", "generate_fingerprint"]
