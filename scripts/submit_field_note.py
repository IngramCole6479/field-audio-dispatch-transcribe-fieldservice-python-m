import argparse
import json

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_path")
    parser.add_argument("--service", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    payload = {
        "work_order_id": "WO-1042",
        "technician_id": "tech-17",
        "customer_name": "North Street Market",
        "audio_path": args.audio_path,
        "audio_content_type": "audio/wav",
        "photos": [
            {"object_key": "WO-1042/panel.jpg", "caption": "Burn mark by main relay"}
        ],
    }
    response = httpx.request(
        method="POST",
        url=f"{args.service}/work-orders/transcribe",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
