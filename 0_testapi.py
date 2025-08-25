import requests

url = "http://127.0.0.1:8000/users"
params = {"last_name": "asdfadfa"}
headers = {"accept": "application/json"}

resp = requests.get(url, params=params, headers=headers, timeout=10)
resp.raise_for_status()  # 非 2xx 会抛异常，便于排错
print(resp.json())