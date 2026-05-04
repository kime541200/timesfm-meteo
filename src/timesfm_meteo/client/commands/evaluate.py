from __future__ import annotations

import json
import sys

from timesfm_meteo.client.http import handle_response_error, make_client


def cmd_evaluate_get(args) -> int:
    client = make_client()
    params = {
        "latitude": args.latitude,
        "longitude": args.longitude,
        "start_date_from": args.start_date_from,
        "start_date_to": args.start_date_to,
    }
    if args.horizon_step is not None:
        params["horizon_step"] = args.horizon_step
    try:
        resp = client.get("/evaluate", params=params)
    except Exception as exc:
        print(f"Network error contacting {client.base_url}: {exc}", file=sys.stderr)
        return 1
    handle_response_error(resp, "evaluation report")
    print(json.dumps(resp.json(), indent=2))
    return 0
