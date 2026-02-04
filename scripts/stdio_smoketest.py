import json
import os
import select
import subprocess
import sys
import time


DEFAULT_PROTOCOL = "2025-11-25"


def _read_line(proc: subprocess.Popen, timeout: float) -> str:
    fd = proc.stdout.fileno()
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        raise TimeoutError("Timed out waiting for server response.")
    line = proc.stdout.readline()
    if not line:
        raise EOFError("Server closed stdout unexpectedly.")
    return line


def _read_json(proc: subprocess.Popen, timeout: float) -> dict:
    start = time.time()
    while True:
        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for JSON message.")
        line = _read_line(proc, remaining).strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            print(f"Non-JSON output from server: {line}", file=sys.stderr)


def _send(proc: subprocess.Popen, payload: dict) -> None:
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()


def _initialize(proc: subprocess.Popen, protocol_version: str) -> dict:
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": "stdio-smoketest",
                    "version": "0.1.0",
                },
            },
        },
    )
    return _read_json(proc, timeout=5)


def main() -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    server_path = os.path.join(repo_root, "postgres-connect.py")
    proc = subprocess.Popen(
        [sys.executable, server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        bufsize=1,
    )

    try:
        response = _initialize(proc, DEFAULT_PROTOCOL)
        if "error" in response:
            data = response.get("error", {}).get("data", {})
            supported = data.get("supported") or []
            if supported:
                print(
                    f"Retrying with server-supported protocol {supported[0]}",
                    file=sys.stderr,
                )
                response = _initialize(proc, supported[0])
            else:
                print(json.dumps(response, indent=2), file=sys.stderr)
                return 1

        print("Initialize response:")
        print(json.dumps(response, indent=2))

        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools_response = _read_json(proc, timeout=5)
        print("Tools list response:")
        print(json.dumps(tools_response, indent=2))

        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "query_data_read",
                    "arguments": {"sql_query": "select 1 as ok"},
                },
            },
        )
        call_response = _read_json(proc, timeout=5)
        print("Tool call response:")
        print(json.dumps(call_response, indent=2))
        return 0
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
