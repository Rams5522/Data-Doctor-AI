import requests

def test_backend():
    try:
        response = requests.get('http://127.0.0.1:8000/api/health')
        print(f"Health check status: {response.status_code}")
        print(f"Response: {response.json()}")

        # Test a few API endpoints
        endpoints = [
            '/api/datasets/',
            '/api/profiling/',
            '/api/quality/',
            '/api/repair/'
        ]

        for endpoint in endpoints:
            try:
                resp = requests.get(f'http://127.0.0.1:8000{endpoint}')
                print(f"{endpoint}: {resp.status_code}")
            except Exception as e:
                print(f"{endpoint}: Error - {e}")

    except Exception as e:
        print(f"Error connecting to backend: {e}")

if __name__ == "__main__":
    test_backend()