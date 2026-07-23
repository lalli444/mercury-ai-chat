import requests

API_KEY = "sk_79dc744ad9f7b341931bcf2d7034ace6"

url = "https://api.inceptionlabs.ai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": "mercury-2",
    "messages": [
        {
            "role": "user",
            "content": "Tell me a short story."
        }
    ],
    "stream": True
}

import json

response = requests.post(
    url,
    headers=headers,
    json=data,
    stream=True
)

if response.status_code != 200:
    print(response.status_code)
    print(response.text)
    exit()

print("Mercury: ", end="", flush=True)

for line in response.iter_lines(decode_unicode=True):
    if not line:
        continue

    if line.startswith("data: "):
        text = line[6:]

        if text == "[DONE]":
            break

        try:
            event = json.loads(text)

            token = (
                event["choices"][0]
                .get("delta", {})
                .get("content", "")
            )

            print(token, end="", flush=True)

        except Exception:
            pass

print()