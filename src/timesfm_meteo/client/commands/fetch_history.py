from __future__ import annotations

import json
import sys
import time

from timesfm_meteo.client.http import handle_response_error, make_client


def _poll_job(client, job_id: str, timeout: float) -> int:
    deadline = time.monotonic() + timeout
    interval = 1.0
    while True:
        try:
            resp = client.get(f"/jobs/{job_id}")
        except Exception as exc:
            print(f"Network error contacting {client.base_url}: {exc}", file=sys.stderr)
            return 1
        handle_response_error(resp, f"job {job_id}")
        data = resp.json()
        status = data.get("status")
        if status == "done":
            print(json.dumps(data, indent=2))
            return 0
        if status == "failed":
            print(f"Error: job {job_id} failed: {data.get('error')}", file=sys.stderr)
            return 1
        if time.monotonic() >= deadline:
            print(f"Error: timed out waiting for job {job_id} (status={status})", file=sys.stderr)
            return 1
        time.sleep(min(interval, deadline - time.monotonic()))
        interval = min(interval * 1.5, 5.0)


def cmd_fetch_history_run(args) -> int:
    client = make_client(timeout=getattr(args, "timeout", 30))
    body: dict = {"latitude": args.latitude, "longitude": args.longitude}
    if args.years is not None:
        body["years"] = args.years
    if args.start_date is not None:
        body["start_date"] = args.start_date
    if args.end_date is not None:
        body["end_date"] = args.end_date

    try:
        resp = client.post("/fetch-history", json=body)
    except Exception as exc:
        print(f"Network error contacting {client.base_url}: {exc}", file=sys.stderr)
        return 1
    handle_response_error(resp, "fetch-history")
    job_id = resp.json()["job_id"]

    if getattr(args, "no_wait", False):
        print(json.dumps(resp.json(), indent=2))
        return 0

    wait_timeout = getattr(args, "timeout", 120)
    return _poll_job(client, job_id, wait_timeout)
