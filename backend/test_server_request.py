import urllib.request
import json
import sys

def run_test():
    url = "http://127.0.0.1:8000/api/google/sheets/create-custom"
    data = json.dumps({"columns": ["Name", "Phone", "Status", "Notes"]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        print("Sending request to server at 127.0.0.1:8000...")
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            print("Response Status:", response.status)
            print("Response Body:", res_body)
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    run_test()
