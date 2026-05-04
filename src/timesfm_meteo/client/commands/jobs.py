from __future__ import annotations

import json
import sys

from timesfm_meteo.client.http import handle_response_error, make_client


def cmd_jobs_get(args) -> int:
    client = make_client()
    try:
        resp = client.get(f"/jobs/{args.job_id}")
    except Exception as exc:
        print(f"Network error contacting {client.base_url}: {exc}", file=sys.stderr)
        return 1
    handle_response_error(resp, f"job {args.job_id}")
    print(json.dumps(resp.json(), indent=2))
    return 0
