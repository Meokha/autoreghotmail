# botright/chrome_fingerprints/__init__.py
import asyncio
import random


class AsyncFingerprintGenerator:
    """Fake Chrome Fingerprint Generator for Botright (realistic presets)"""

    def __init__(self) -> None:
        # Một số cấu hình trình duyệt phổ biến, gần với user thật
        self._profiles = [
            {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                "platform": "Win32",
                "language": "en-US,en;q=0.9",
                "timezone": "Asia/Ho_Chi_Minh",
            },
            {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "platform": "Win32",
                "language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "timezone": "Asia/Ho_Chi_Minh",
            },
            {
                "user_agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/118.0.0.0 Safari/537.36"
                ),
                "platform": "Linux x86_64",
                "language": "en-US,en;q=0.9",
                "timezone": "UTC",
            },
            {
                "user_agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Safari/605.1.15"
                ),
                "platform": "MacIntel",
                "language": "en-US,en;q=0.9",
                "timezone": "America/Los_Angeles",
            },
        ]

    async def generate(self, *args, **kwargs):
        # Chọn một cấu hình browser "giống thật" làm base
        profile = random.choice(self._profiles)

        # Mô phỏng thêm một số thông số phần cứng/trình duyệt
        screen_width = random.choice([1366, 1440, 1536, 1600, 1920])
        screen_height = random.choice([768, 900, 960, 1080])
        device_memory = random.choice([4, 8, 16])  # GB
        hardware_concurrency = random.choice([4, 8, 12])

        return {
            "user_agent": profile["user_agent"],
            "platform": profile["platform"],
            "canvas": "fake_canvas_data_" + str(random.randint(1000, 9999)),
            "webgl": "fake_webgl_data_" + str(random.randint(1000, 9999)),
            "fonts": ["Arial", "Verdana", "Tahoma", "Times New Roman"],
            "timezone": profile["timezone"],
            "language": profile["language"],
            "screen_size": f"{screen_width}x{screen_height}",
            "device_memory": device_memory,
            "hardware_concurrency": hardware_concurrency,
        }

# Nếu Botright gọi đồng bộ
def generate_fingerprint():
    return asyncio.get_event_loop().run_until_complete(
        AsyncFingerprintGenerator().generate()
    )

__all__ = ["AsyncFingerprintGenerator", "generate_fingerprint"]
