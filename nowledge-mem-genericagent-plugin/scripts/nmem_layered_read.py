#!/usr/bin/env python3
"""Layered nmem reader for GenericAgent.

Protocol goals:
1. Keep GenericAgent's active context small.
2. Never rely on one huge nmem dump.
3. Use index/search for discovery, page for bounded reading, export for large offline inspection.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_PAGE_CHARS = 12000
DEFAULT_CONTENT_LIMIT = 6000


def run_nmem(args):
    cmd = ["nmem", "-j"] + args
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise SystemExit(f"nmem failed ({p.returncode}): {' '.join(cmd)}\nSTDERR:\n{p.stderr}\nSTDOUT:\n{p.stdout}")
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"nmem returned non-JSON: {exc}\n{p.stdout[:2000]}")


def compact(s, n=240):
    s = (s or "").replace("\r", "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def cmd_index(a):
    args = ["t", "list", "-n", str(a.limit), "--offset", str(a.offset)]
    if a.space: args += ["--space", a.space]
    if a.source: args += ["--source", a.source]
    data = run_nmem(args)
    out = {
        "protocol": "nmem-layered-v1/index",
        "rule": "Use ids from this lightweight index; do not load full threads until needed.",
        "threads": data.get("threads", []),
        "total": data.get("total"),
        "offset": data.get("offset"),
        "limit": data.get("limit"),
        "has_more": data.get("has_more"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_search(a):
    args = ["t", "search", a.query, "-n", str(a.limit)]
    if a.space: args += ["--space", a.space]
    if a.source: args += ["--source", a.source]
    data = run_nmem(args)
    print(json.dumps({
        "protocol": "nmem-layered-v1/search",
        "rule": "Treat results as candidates/snippets only. Use page/export for exact evidence.",
        "query": a.query,
        "result": data,
    }, ensure_ascii=False, indent=2))


def render_messages(thread):
    parts = []
    for m in thread.get("messages", []):
        idx = m.get("index")
        role = m.get("role", "?")
        content = m.get("content", "") or ""
        parts.append(f"[{idx}] {role}\n{content}\n")
    return "\n".join(parts)


def cmd_page(a):
    # content-limit=0 means nmem currently returns full message content.
    cl = str(a.content_limit)
    args = ["t", "show", a.id, "--offset", str(a.offset), "-n", str(a.messages), "--content-limit", cl]
    if a.space: args += ["--space", a.space]
    thread = run_nmem(args)
    body = render_messages(thread)
    truncated_by_page = False
    if a.max_chars and len(body) > a.max_chars:
        body = body[:a.max_chars] + f"\n\n[page clipped by nmem_layered_read.py --max-chars={a.max_chars}; rerun with larger max or smaller -n]\n"
        truncated_by_page = True
    out = {
        "protocol": "nmem-layered-v1/page",
        "id": thread.get("id"),
        "title": thread.get("title"),
        "source": thread.get("source"),
        "total_messages": thread.get("total_messages"),
        "offset": a.offset,
        "message_count": thread.get("message_count"),
        "next_offset": a.offset + int(thread.get("message_count") or 0),
        "has_more": (a.offset + int(thread.get("message_count") or 0)) < int(thread.get("total_messages") or 0),
        "content_limit_per_message": a.content_limit,
        "max_chars": a.max_chars,
        "truncated_by_page": truncated_by_page,
        "body": body,
    }
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: out[k] for k in out if k != "body"} | {"saved_to": a.out, "body_chars": len(body)}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_export(a):
    offset = a.offset
    all_msgs = []
    meta = None
    while True:
        args = ["t", "show", a.id, "--offset", str(offset), "-n", str(a.batch), "--content-limit", "0"]
        if a.space: args += ["--space", a.space]
        thread = run_nmem(args)
        if meta is None: meta = {k: thread.get(k) for k in ["id", "title", "source", "created_at", "space_id", "total_messages"]}
        msgs = thread.get("messages", [])
        if not msgs: break
        all_msgs.extend(msgs)
        offset += len(msgs)
        if offset >= int(thread.get("total_messages") or 0): break
    out = {"protocol": "nmem-layered-v1/export", **(meta or {"id": a.id}), "messages": all_msgs}
    outpath = Path(a.out or f"nmem_thread_{a.id}.json")
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved_to": str(outpath), "messages": len(all_msgs), "chars": outpath.stat().st_size}, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Layered nmem reader for small-context GenericAgent")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("index", help="lightweight thread index")
    pi.add_argument("-n", "--limit", type=int, default=10); pi.add_argument("--offset", type=int, default=0); pi.add_argument("--source"); pi.add_argument("--space"); pi.set_defaults(func=cmd_index)
    ps = sub.add_parser("search", help="candidate search/snippets")
    ps.add_argument("query"); ps.add_argument("-n", "--limit", type=int, default=10); ps.add_argument("--source"); ps.add_argument("--space"); ps.set_defaults(func=cmd_search)
    pp = sub.add_parser("page", help="bounded exact page from one thread")
    pp.add_argument("id"); pp.add_argument("--offset", type=int, default=0); pp.add_argument("-n", "--messages", type=int, default=4); pp.add_argument("--content-limit", type=int, default=0, help="per-message nmem limit; 0 means full per nmem CLI"); pp.add_argument("--max-chars", type=int, default=DEFAULT_PAGE_CHARS); pp.add_argument("--space"); pp.add_argument("--out"); pp.set_defaults(func=cmd_page)
    pe = sub.add_parser("export", help="export full thread to file, never inject directly")
    pe.add_argument("id"); pe.add_argument("--offset", type=int, default=0); pe.add_argument("--batch", type=int, default=50); pe.add_argument("--space"); pe.add_argument("--out"); pe.set_defaults(func=cmd_export)
    a = p.parse_args()
    a.func(a)

if __name__ == "__main__":
    main()
