import requests
import os

def test_upload():
    url = "http://127.0.0.1:8000/api/datasets/upload"

    # Use one of the existing sample files
    file_path = "storage/uploads/1_f9da8716-c880-4e0b-95dc-7f639c806e34.csv"

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'text/csv')}
        data = {
            'name': 'Test Employee Data',
            'description': 'Sample employee dataset for testing'
        }

        try:
            response = requests.post(url, files=files, data=data)
            print(f"Upload status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_upload()