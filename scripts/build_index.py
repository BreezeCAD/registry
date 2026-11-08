#!/usr/bin/env python3
"""Собирает index.json каталога модулей и библиотек BreezeCAD.

Откуда берутся паспорта (breezecad.json):
  1. репозитории организации BreezeCAD с темой breezecad-module или breezecad-library;
  2. внешние репозитории из external.json (добавляются через PR);
  3. папка entries/ — паспорта того, что живёт не в своём репозитории
     (языковые пакеты, встроенные пакеты изделий и т. п.).
Паспорт из репозитория важнее паспорта из entries/ с тем же id.

Каждый паспорт проверяется по schema/breezecad.schema.json, файлы выпуска
находятся через GitHub API. Ошибки одного паспорта не ломают каталог: он
попадает в "errors", остальные — в "items".

  python3 scripts/build_index.py            # собрать index.json
  python3 scripts/build_index.py --check    # только проверить entries/ и external.json (для PR)

Нужен пакет jsonschema. Токен — переменная GITHUB_TOKEN (в Actions есть всегда).
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import fnmatch
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    sys.exit("Нужен пакет jsonschema: pip install jsonschema")

ROOT = Path(__file__).resolve().parent.parent
ORG = os.environ.get("BZ_ORG", "BreezeCAD")
TOPICS = {"breezecad-module": "module", "breezecad-library": "library"}
API = "https://api.github.com"


# ---------------------------------------------------------------- GitHub API
def gh(path: str):
    """GET к API GitHub; None, если 404."""
    req = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "breezecad-registry",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise RuntimeError(f"GitHub API {path}: HTTP {e.code}") from e


def org_repos() -> list[dict]:
    repos, page = [], 1
    while True:
        batch = gh(f"/orgs/{ORG}/repos?type=public&per_page=100&page={page}") or []
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


def read_passport(repo: str, path: str = "breezecad.json") -> dict | None:
    data = gh(f"/repos/{repo}/contents/{path}")
    if not data or "content" not in data:
        return None
    return json.loads(base64.b64decode(data["content"]).decode("utf-8"))


# ---------------------------------------------------------------- files
PLATFORM_HINTS = [
    ("windows", re.compile(r"windows|win(32|64)|\.exe$", re.I)),
    ("macos", re.compile(r"macos|darwin|osx|\.dmg$", re.I)),
    ("android", re.compile(r"android|\.apk$", re.I)),
    ("ios", re.compile(r"\bios\b|\.ipa$", re.I)),
    ("linux", re.compile(r"linux", re.I)),
]


def platform_of(name: str) -> str:
    for plat, rx in PLATFORM_HINTS:
        if rx.search(name):
            return plat
    return "any"


def resolve_files(p: dict, home_repo: str | None) -> tuple[str, str | None, list[dict]]:
    """→ (версия, дата выпуска, файлы)."""
    d = p["download"]
    if "urls" in d:
        files = [{
            "name": u.get("name") or u["url"].rstrip("/").rsplit("/", 1)[-1],
            "url": u["url"],
            "size": None,
            "platform": u.get("platform") or platform_of(u["url"]),
        } for u in d["urls"]]
        return d.get("version", ""), None, files

    repo = d.get("repo") or home_repo
    if not repo:
        raise ValueError("download.repo обязателен для паспорта из entries/")
    tag = d["release"]
    rel = gh(f"/repos/{repo}/releases/latest" if tag == "latest" else f"/repos/{repo}/releases/tags/{tag}")
    if not rel:
        raise ValueError(f"нет выпуска «{tag}» в {repo}")
    files = []
    for a in rel.get("assets", []):
        if any(fnmatch.fnmatchcase(a["name"], pat) for pat in d["assets"]):
            files.append({
                "name": a["name"],
                "url": a["browser_download_url"],
                "size": a["size"],
                "platform": platform_of(a["name"]),
            })
    if not files:
        raise ValueError(f"в выпуске {repo}@{rel['tag_name']} нет файлов по шаблонам {d['assets']}")
    version = re.sub(r"^v(?=\d)", "", rel["tag_name"])
    if not re.match(r"\d", version):  # тег вроде «modules» — версию берём из имени файла
        m = re.search(r"\d+\.\d+(?:\.\d+)*", files[0]["name"]) if files else None
        version = m.group(0) if m else version
    return version, (rel.get("published_at") or "")[:10], sorted(files, key=lambda f: f["name"])


# ---------------------------------------------------------------- build
def load_schema() -> jsonschema.Validator:
    schema = json.loads((ROOT / "schema" / "breezecad.schema.json").read_text("utf-8"))
    cls = jsonschema.validators.validator_for(schema)
    return cls(schema, format_checker=cls.FORMAT_CHECKER)


def problems(validator, p: dict) -> list[str]:
    out = []
    for e in sorted(validator.iter_errors(p), key=lambda e: list(e.path)):
        where = "/".join(str(x) for x in e.path) or "(корень)"
        out.append(f"{where}: {e.message}")
    return out


def collect(validator, offline: bool) -> tuple[list[tuple[str, str | None, dict]], list[dict]]:
    """→ ([(источник, репозиторий или None, паспорт)], ошибки)."""
    found, errors = [], []
    local = []
    for f in sorted((ROOT / "entries").glob("*.json")):
        try:
            local.append((f"entries/{f.name}", None, json.loads(f.read_text("utf-8"))))
        except json.JSONDecodeError as e:
            errors.append({"source": f"entries/{f.name}", "message": f"не JSON: {e}"})

    if offline:
        return local, errors

    repos: list[tuple[str, str | None]] = []
    for r in org_repos():
        if r.get("archived") or r.get("private"):
            continue
        kinds = [TOPICS[t] for t in r.get("topics", []) if t in TOPICS]
        if kinds:
            repos.append((r["full_name"], kinds[0]))
    ext = json.loads((ROOT / "external.json").read_text("utf-8"))
    for e in ext.get("repos", []):
        repos.append((e["repo"] if isinstance(e, dict) else e, None))

    for full, topic_type in repos:
        try:
            p = read_passport(full)
        except Exception as e:  # noqa: BLE001
            errors.append({"source": full, "message": str(e)})
            continue
        if p is None:
            errors.append({"source": full, "message": "нет breezecad.json в корне"})
            continue
        if topic_type and p.get("type") != topic_type:
            errors.append({"source": full, "message": f"тема репозитория — {topic_type}, а в паспорте type = {p.get('type')}"})
        found.append((full, full, p))
    return found + local, errors  # репозитории первыми: они важнее entries/


def build(offline: bool = False) -> dict:
    validator = load_schema()
    found, errors = collect(validator, offline)

    by_id: dict[str, dict] = {}
    for source, repo, p in found:
        bad = problems(validator, p)
        if bad:
            errors.append({"source": source, "message": "; ".join(bad)})
            continue
        prev = by_id.get(p["id"])
        if prev:
            if repo is None:
                continue  # паспорт из репозитория важнее записи в entries/
            errors.append({"source": source, "message": f"id «{p['id']}» уже занят ({prev['source']['name']})"})
            continue
        try:
            version, published, files = resolve_files(p, repo)
        except Exception as e:  # noqa: BLE001
            errors.append({"source": source, "message": str(e)})
            continue
        item = {k: v for k, v in p.items() if k not in ("$schema", "schemaVersion", "download")}
        item.setdefault("tags", [])
        item.setdefault("bundled", False)
        item.update({
            "version": version,
            "published": published,
            "files": files,
            "source": {
                "name": source,
                "repo": repo,
                "url": f"https://github.com/{repo}" if repo else f"https://github.com/{ORG}/registry/blob/main/{source}",
            },
        })
        by_id[p["id"]] = item

    items = sorted(by_id.values(), key=lambda i: (i["type"], i["name"]["ru"].lower()))
    return {
        "schemaVersion": 1,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": items,
        "errors": errors,
    }


def same_content(a: dict, b: dict) -> bool:
    strip = lambda d: {k: v for k, v in d.items() if k != "generated"}  # noqa: E731
    return strip(a) == strip(b)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="проверить entries/ и external.json без сети, код 1 при ошибках")
    ap.add_argument("--offline", action="store_true", help="не ходить в сеть за репозиториями организации")
    ap.add_argument("-o", "--output", default=str(ROOT / "index.json"))
    args = ap.parse_args()

    if args.check:
        validator = load_schema()
        bad = 0
        for f in sorted((ROOT / "entries").glob("*.json")):
            for msg in problems(validator, json.loads(f.read_text("utf-8"))):
                print(f"::error file=entries/{f.name}::{msg}")
                bad += 1
        ext = json.loads((ROOT / "external.json").read_text("utf-8"))
        for e in ext.get("repos", []):
            repo = e["repo"] if isinstance(e, dict) else e
            if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repo):
                print(f"::error file=external.json::неверное имя репозитория: {repo}")
                bad += 1
        print("Ошибок нет." if not bad else f"Ошибок: {bad}")
        return 1 if bad else 0

    index = build(offline=args.offline)
    out = Path(args.output)
    old = json.loads(out.read_text("utf-8")) if out.exists() else None
    for e in index["errors"]:
        print(f"::warning title={e['source']}::{e['message']}")
    print(f"В каталоге: {len(index['items'])}; ошибок: {len(index['errors'])}")
    if old and same_content(old, index):
        print("Каталог не изменился.")
        return 0
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"Записан {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
