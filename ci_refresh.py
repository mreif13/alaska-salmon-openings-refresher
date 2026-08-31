#!/usr/bin/env python3
"""CLOUD REFRESH — the Alaska Fishery Openings engine on GitHub's scheduler,
so the public phone page updates even with the desktop computer off
(ledger #83).

SELF-UPDATING: the engine itself (app-src.zip) is fetched from the live site
at every run — the desktop app publishes it beside the page, so whatever
engine version the app last shipped is exactly what runs here. This repo
holds only this script and the workflow; there is nothing in it to keep
current by hand.

Flow per run:
  1. download app-src.zip from the live site (published by the desktop app)
  2. unpack; seed a fresh data dir exactly like the app's own boot
  3. fetch ADF&G's announcement listing; ingest anything new
  4. rebuild the page; the doctor validates it
  5. artifact gates: partial floor, feature floor, CLOCK gate — any failure
     publishes NOTHING and turns the run red
  6. deploy index.html + the same app-src.zip back to Netlify
     (env: NETLIFY_AUTH_TOKEN secret, NETLIFY_SITE_NAME)
"""
import json, os, sys, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
SITE = os.environ.get("SITE_URL", "https://alaska-salmon-openings.netlify.app").rstrip("/")


def log(*a):
    print(*a, flush=True)


def main():
    # 1. the engine, from the site the desktop app publishes
    src_zip = os.path.join(HERE, "app-src.zip")
    url = SITE + "/app-src.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AFO-cloud-refresh"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        open(src_zip, "wb").write(data)
        log(f"engine downloaded: {len(data)//1024} KB from {url}")
    except Exception as e:
        log(f"FATAL: could not download {url} ({e}).")
        log("Fix: on the desktop computer, open the app -> Auto-publish settings")
        log("-> Publish now (the app publishes the engine beside the page).")
        return 1
    import shutil
    if os.path.isdir(SRC):
        shutil.rmtree(SRC)
    with zipfile.ZipFile(src_zip) as z:
        z.extractall(SRC)
    for sub in ("engine", "pipeline", "tests", "."):
        p = os.path.join(SRC, sub)
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(SRC)
    os.makedirs("data", exist_ok=True)

    # 2–4. the app's own boot + refresh, publishing disabled during the cycle
    json.dump({"enabled": False}, open(os.path.join("data", "publish.json"), "w"))
    import app                                     # noqa: E402
    app._seed()
    res = app.refresh(force_rebuild=True)
    log("refresh:", {k: res.get(k) for k in ("ok", "new", "ingested", "rebuilt", "as_of")})
    page = os.path.join("data", "SE_Openings.html")
    if not os.path.exists(page):
        log("FATAL: no page produced")
        return 1

    # 5. artifact gates — what the public sees must pass, or nothing ships
    import test_all                                 # noqa: E402
    gates = [test_all.partial_floor_gate(), test_all.feature_floor_gate(),
             test_all.stale_status_gate()]
    for g in gates:
        log(("PASS " if g["ok"] else "FAIL ") + g["name"] + " — " + g["detail"])
    if any(not g["ok"] for g in gates):
        log("GATE FAILURES — NOT PUBLISHING")
        return 1

    # 6. publish page + the same engine bundle (a deploy replaces the site)
    token = os.environ.get("NETLIFY_AUTH_TOKEN", "").strip()
    site = os.environ.get("NETLIFY_SITE_NAME", "alaska-salmon-openings").strip()
    if not token:
        log("NETLIFY_AUTH_TOKEN not set — dry run complete, no publish")
        return 0
    import publisher                                # noqa: E402
    site_id, name, url2 = publisher.resolve_site(token, site)
    out = publisher.publish(page, token, site_id, include_src=True, src_bytes=data)
    log(f"published to {out.get('url')} (deploy {out.get('deploy_id')}, {out.get('state')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
