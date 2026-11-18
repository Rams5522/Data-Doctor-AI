import requests

url = "http://127.0.0.1:8002/api/quality/79/detect?version_id=80"
response = requests.post(url, json={})
print(f"Status: {response.status_code}")
print(response.json())