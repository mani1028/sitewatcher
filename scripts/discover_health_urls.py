#!/usr/bin/env python3
"""Discover and set health_url for all SiteWatch websites."""
from __future__ import annotations

import concurrent.futures
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlparse

PATHS = [
    "/api/v1/health",
    "/api/health",
    "/health",
    "/api/healthz",
    "/healthz",
    "/api/status",
    "/status",
    "/actuator/health",
    "/ready",
    "/live",
]


def psql(sql: str) -> str:
    return subprocess.check_output(
        [
            "docker",
            "exec",
            "sitewatch-postgres-1",
            "psql",
            "-U",
            "sitewatch",
            "-d",
            "sitewatch",
            "-t",
            "-A",
            "-F",
            "|",
            "-c",
            sql,
        ],
        text=True,
    )


def probe(url: str, timeout: float = 5.0):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SiteWatch-Discover/1.0",
            "Accept": "application/json, text/plain, */*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.headers.get("Content-Type", ""), resp.read(500)
    except urllib.error.HTTPError as e:
        body = e.read(200) if e.fp else b""
        ctype = e.headers.get("Content-Type", "") if e.headers else ""
        return e.code, ctype, body
    except Exception as e:  # noqa: BLE001
        return None, "", str(e).encode()[:80]


def accept(code, ctype, body) -> bool:
    if code != 200:
        return False
    text = body.decode("utf-8", "ignore") if isinstance(body, (bytes, bytearray)) else str(body)
    is_json = "json" in (ctype or "").lower() or text.strip()[:1] in "{["
    is_html = "text/html" in (ctype or "").lower() or "<html" in text.lower()[:200]
    if is_html and not is_json:
        return False
    if is_json:
        return True
    if len(text) < 400 and any(
        k in text.lower() for k in ("ok", "up", "healthy", "status", "pong", "true", "alive")
    ):
        return True
    return (not is_html) and len(text) < 250


def bases_for(url: str) -> list[str]:
    raw = url.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    p = urlparse(raw)
    host = p.hostname or ""
    scheme = p.scheme or "https"
    out = [f"{scheme}://{host}"]
    if host and not host.startswith("api."):
        out.append(f"{scheme}://api.{host}")
    # portal.x.com -> try api.x.com and x.com
    if host.startswith("portal."):
        root = host[len("portal.") :]
        out.append(f"{scheme}://api.{root}")
        out.append(f"{scheme}://{root}")
    if host.startswith("admin.") or host.startswith("admin-"):
        root = host.split(".", 1)[-1] if host.startswith("admin.") else host.split("-", 1)[-1]
        # weak guess; still useful for some stacks
        out.append(f"{scheme}://api.{root}" if "." in root else f"{scheme}://{host}")
    # unique
    seen: set[str] = set()
    ordered: list[str] = []
    for b in out:
        if b not in seen:
            seen.add(b)
            ordered.append(b)
    return ordered


def discover(row: str):
    id_s, name, url, existing = row.split("|", 3)
    site_id = int(id_s)
    if existing.strip():
        return site_id, name, existing.strip(), "keep"
    candidates: list[str] = []
    u = url.strip().rstrip("/")
    host = (urlparse(u if "://" in u else "https://" + u).hostname or "").lower()
    if host.startswith("api.") or host.startswith("filemanager"):
        candidates.append(u)
    for base in bases_for(url):
        for path in PATHS:
            candidates.append(base.rstrip("/") + path)
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    for cand in ordered:
        code, ctype, body = probe(cand)
        if accept(code, ctype, body):
            snip = (
                body.decode("utf-8", "ignore")
                if isinstance(body, (bytes, bytearray))
                else str(body)
            )[:70].replace("\n", " ")
            return site_id, name, cand, f"found:{snip}"
    return site_id, name, None, "none"


def main() -> None:
    rows = [
        r
        for r in psql(
            "SELECT id, name, url, coalesce(health_url, '') FROM websites ORDER BY id;"
        )
        .strip()
        .splitlines()
        if r.strip()
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        results = list(ex.map(discover, rows))

    updates = [(i, h) for i, _n, h, _s in results if h]
    print(f"sites={len(results)} with_health={len(updates)}")
    for i, n, h, s in results:
        print(f"{i}|{n}|{h or '-'}|{s}")

    if updates:
        values = ", ".join(f"({i}, '{h.replace(chr(39), chr(39)+chr(39))}')" for i, h in updates)
        sql = (
            "UPDATE websites w SET health_url = v.health_url, next_check_at = NOW() "
            f"FROM (VALUES {values}) AS v(id, health_url) WHERE w.id = v.id;"
        )
        subprocess.check_call(
            [
                "docker",
                "exec",
                "sitewatch-postgres-1",
                "psql",
                "-U",
                "sitewatch",
                "-d",
                "sitewatch",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                sql,
            ]
        )
    summary = psql(
        "SELECT count(*) FILTER (WHERE health_url IS NOT NULL AND btrim(health_url) <> ''), count(*) FROM websites;"
    )
    print("SUMMARY", summary.strip())


if __name__ == "__main__":
    main()
