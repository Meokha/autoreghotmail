import requests

api_key = "98a8b2d37b764fd5a30ca208eb488034276519"  # API key của bạn
url = "https://api.ez-captcha.com/createTask"

data = {
    "clientKey": api_key,
    "task": {
        "type": "CloudFlareTurnstileTaskProxyless",
        "websiteURL": "https://example.com",
        "websiteKey": "0x4AAAAAAA_test_key"
    }
}

try:
    response = requests.post(url, json=data, timeout=10)
    print("Response:", response.json())
except Exception as e:
    print("Error:", e)
