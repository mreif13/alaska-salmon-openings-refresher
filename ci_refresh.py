#!/usr/bin/env python3
"""Alaska Salmon Openings - cloud refresher bootstrap.

Picks the newest engine it can see without spending the site's bandwidth, then
hands over to that engine's engine/cloud.py, which does everything else.

Where an engine can come from:
  - app-src.zip in this repo (a whole engine: code and seeds);
  - engine-code-*.zip in this repo (the CODE of an engine; its seeds - the fixed
    chart geometry - are taken from the site's own app-src.zip, which is
    downloaded once and kept in the state folder);
  - the copy kept in the state folder from an earlier run;
  - the site's app-src.zip, downloaded only when the site's tiny engine.txt says
    it is newer (the desktop app and the refresher publish their engine there).
"""
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

SITE = os.environ.get("AFO_SITE_URL", "https://alaska-salmon-openings.netlify.app").rstrip("/")
HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIRS = ("engine/", "pipeline/", "tests/")


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def zip_version(b):
    try:
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            m = re.search(r'^VERSION\s*=\s*"([^"]+)"', z.read("app.py").decode("utf-8", "replace"), re.M)
            return m.group(1) if m else ""
    except Exception:
        return ""


def has_seeds(b):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        return any(n.startswith("seeds/SE_Openings.html") for n in z.namelist())


def get(url, limit=None):
    req = urllib.request.Request(url, headers={"User-Agent": "AlaskaFisheryOpenings-refresher"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read(limit) if limit else r.read()


def combine(code, base):
    """An engine's code over another engine's seeds: every code file from `code`,
    every seed (and anything else outside the code folders) from `base`."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(code)) as c, zipfile.ZipFile(io.BytesIO(base)) as s, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        names = set(c.namelist())
        for n in sorted(names):
            z.writestr(n, c.read(n))
        for n in sorted(s.namelist()):
            if n in names or n == "app.py" or n.startswith(CODE_DIRS):
                continue
            z.writestr(n, s.read(n))
    return out.getvalue()


def main():
    args = sys.argv[1:] or ["--state", "state"]
    state = args[args.index("--state") + 1] if "--state" in args else "state"
    cache_dir = os.path.join(state, "engine")
    cache = os.path.join(cache_dir, "app-src.zip")
    base_cache = os.path.join(cache_dir, "seed-base.zip")
    downloaded = False

    cands = []
    for p in [os.path.join(HERE, "app-src.zip"), cache]:
        if os.path.exists(p):
            b = open(p, "rb").read()
            if has_seeds(b):
                cands.append((vtuple(zip_version(b)), p, b))

    # an engine's code alone: its seeds come from the site's published engine
    for p in sorted(glob.glob(os.path.join(HERE, "engine-code-*.zip"))):
        code = open(p, "rb").read()
        v = vtuple(zip_version(code))
        if cands and max(c[0] for c in cands) >= v:
            continue
        base = open(base_cache, "rb").read() if os.path.exists(base_cache) else None
        if base is None:
            try:
                base = get(SITE + "/app-src.zip")
                if not has_seeds(base):
                    base = None
                else:
                    os.makedirs(cache_dir, exist_ok=True)
                    open(base_cache, "wb").write(base)
                    downloaded = True
                    print(f"[boot] took the chart's seeds from the site's engine ({zip_version(base)}), once")
            except Exception as e:
                print(f"[boot] could not read the site's engine for its seeds: {e}")
        if base is not None:
            b = combine(code, base)
            os.makedirs(cache_dir, exist_ok=True)
            open(cache, "wb").write(b)
            downloaded = True
            cands.append((v, cache, b))
            print(f"[boot] engine {'.'.join(map(str, v))}: code from {os.path.basename(p)}, seeds from the site")

    best = max(c[0] for c in cands) if cands else (0,)
    try:
        site_v = get(SITE + "/engine.txt", 64).decode("ascii", "replace").strip()
    except Exception:
        site_v = ""
    if site_v and vtuple(site_v) > best:
        b = get(SITE + "/app-src.zip")
        if vtuple(zip_version(b)) > best and has_seeds(b):
            os.makedirs(cache_dir, exist_ok=True)
            open(cache, "wb").write(b)
            cands.append((vtuple(zip_version(b)), cache, b))
            downloaded = True
            print(f"[boot] the site carries a newer engine ({site_v}); kept it")

    usable = []
    for v, p, b in sorted(cands, key=lambda x: x[0], reverse=True):
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            if "engine/cloud.py" in z.namelist():
                usable.append((v, p, b))
    if not usable:
        print("[boot] no engine with engine/cloud.py is available (put engine-code-3.1.0.zip or app-src.zip in the repo)")
        return 1
    v, p, b = usable[0]
    app = os.path.join(HERE, "app")
    if os.path.isdir(app):
        shutil.rmtree(app)
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        z.extractall(app)
    print(f"[boot] engine {'.'.join(map(str, v))} from {os.path.relpath(p, HERE)}")
    env = dict(os.environ)
    if downloaded:
        env["AFO_ENGINE_CACHED"] = "1"        # keep it even if this run goes no further
    rc = subprocess.call([sys.executable, os.path.join(app, "engine", "cloud.py")] + args, env=env)
    # ADF&G unreachable (2) is weather, not a fault: the next run tries again.
    # A red ship gate (3), a chart that would not deploy (4) or a crash fails
    # the run, and GitHub emails the owner.
    return 0 if rc in (0, 2) else rc


if __name__ == "__main__":
    sys.exit(main())
