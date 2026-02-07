
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('NEWS_API_KEY')
print(f"NEWS_API_KEY present: {bool(api_key)}")
if api_key:
    print(f"Key starts with: {api_key[:4]}..." if len(api_key) > 4 else "Key is short")
    if 'your_' in api_key:
        print("Key contains 'your_', likely a placeholder.")

url = "https://newsapi.org/v2/everything"
params = {
    'q': 'shortage',
    'apiKey': api_key,
    'pageSize': 1
}

try:
    print("Making request to NewsAPI...")
    resp = requests.get(url, params=params, timeout=10)
    print(f"Status Code: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Total Results: {data.get('totalResults')}")
        if data.get('articles'):
            print("First article title:", data['articles'][0].get('title'))
    else:
        print("Error response:", resp.text)
except Exception as e:
    print(f"Exception: {e}")
