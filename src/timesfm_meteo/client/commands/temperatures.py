from __future__ import annotations

import json
import sys

from timesfm_meteo.client.http import handle_response_error, make_client


def cmd_temperatures_get(args) -> int:
    client = make_client()
    try:
        resp = client.get(
            "/temperatures",
            params={
                "latitude": args.latitude,
                "longitude": args.longitude,
                "start_date": args.start_date,
                "end_date": args.end_date,
            },
        )
    except Exception as exc:
        print(f"Network error contacting {client.base_url}: {exc}", file=sys.stderr)
        return 1
    handle_response_error(resp, "temperatures")
    print(json.dumps(resp.json(), indent=2))
    return 0
