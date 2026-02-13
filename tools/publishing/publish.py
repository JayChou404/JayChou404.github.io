#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

GENERATED_BY = "publish.py"
ASSET_MARKER_FILE = ".generated_by_publish_py"

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")

SENSITIVE_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("password_assignment", re.compile(r"(?i)\bpassword\b\s*[:=]\s*\S+")),
    ("token_assignment", re.compile(r"(?i)\btoken\b\s*[:=]\s*\S+")),
    ("cookie_assignment", re.compile(r"(?i)\bcookie\b\s*[:=]\s*\S+")),
    ("ssh_private", re.compile(r"(?i)id_rsa")),
]


@dataclass
class Note:
    source_path: Path
    frontmatter: Dict[str, object]
    body: str
    title: str
    slug: str
    date_raw: str
    date_prefix: str
    post_id: str
    output_post_path: Path
    assets_dir: Path


def parse_frontmatter(text: str) -> Tuple[Dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text

    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text

    raw = text[4:end]
    body = text[end + 5 :]
    fm: Dict[str, object] = {}
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.lower() in {"true", "false"}:
            fm[key] = value.lower() == "true"
        elif value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip('"\'') for v in value[1:-1].split(",") if v.strip()]
            fm[key] = items
        else:
            fm[key] = value.strip('"\'')
    return fm, body


def parse_date_prefix(value: str) -> Optional[str]:
    value = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    try:
        normal = value.replace("T", " ")
        normal = re.sub(r"\s+[+-]\d{2}:?\d{2}$", "", normal)
        normal = normal.split("+")[0].split("Z")[0].strip()
        dt = datetime.fromisoformat(normal)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff\-\s]", "", value).strip().lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def load_notes(vault_posts_dir: Path, site_dir: Path) -> Tuple[List[Note], List[str]]:
    errors: List[str] = []
    notes: List[Note] = []

    for source in sorted(vault_posts_dir.rglob("*.md")):
        text = source.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)

        if not fm.get("publish", False):
            continue
        if fm.get("private", False) or fm.get("sensitive", False):
            continue

        title = str(fm.get("title", "")).strip()
        date_raw = str(fm.get("date", "")).strip()
        slug = str(fm.get("slug", "")).strip() or slugify(title)

        if not title:
            errors.append(f"{source}: missing front matter title")
            continue
        if not date_raw:
            errors.append(f"{source}: missing front matter date")
            continue
        date_prefix = parse_date_prefix(date_raw)
        if not date_prefix:
            errors.append(f"{source}: invalid date format `{date_raw}`")
            continue
        if not slug:
            errors.append(f"{source}: missing or invalid slug")
            continue

        post_id = f"{date_prefix}-{slug}"
        output_post_path = site_dir / "posts" / f"{post_id}.md"
        assets_dir = site_dir / "assets" / slug
        notes.append(
            Note(
                source_path=source,
                frontmatter=fm,
                body=body,
                title=title,
                slug=slug,
                date_raw=date_raw,
                date_prefix=date_prefix,
                post_id=post_id,
                output_post_path=output_post_path,
                assets_dir=assets_dir,
            )
        )

    seen_post_ids: Dict[str, Path] = {}
    seen_slugs: Dict[str, Path] = {}
    for note in notes:
        if note.post_id in seen_post_ids:
            errors.append(f"post_id conflict: {note.source_path} conflicts with {seen_post_ids[note.post_id]}")
        seen_post_ids[note.post_id] = note.source_path
        if note.slug in seen_slugs:
            errors.append(f"slug conflict: {note.source_path} conflicts with {seen_slugs[note.slug]}")
        seen_slugs[note.slug] = note.source_path

    return notes, errors


def resolve_asset(note: Note, ref: str, vault_dir: Path) -> Optional[Path]:
    ref_name = ref.split("|")[0].strip()
    candidates = [
        note.source_path.parent / ref_name,
        vault_dir / "attachments" / ref_name,
        vault_dir / ref_name,
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def convert_content(note: Note, title_map: Dict[str, Note], vault_dir: Path, errors: List[str]) -> Tuple[str, List[Tuple[Path, Path]]]:
    copy_plan: List[Tuple[Path, Path]] = []
    body = note.body

    def replace_embed(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        asset = resolve_asset(note, raw, vault_dir)
        if not asset:
            errors.append(f"{note.source_path}: missing embed asset `{raw}`")
            return match.group(0)
        note.assets_dir.mkdir(parents=True, exist_ok=True)
        dest = note.assets_dir / asset.name
        copy_plan.append((asset, dest))
        alt = asset.stem
        return f"![{alt}](/assets/img/posts/{note.slug}/{asset.name})"

    body = EMBED_RE.sub(replace_embed, body)

    def replace_wikilink(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        if raw.startswith("http"):
            return match.group(0)

        if "|" in raw:
            target, alias = raw.split("|", 1)
            alias = alias.strip()
        else:
            target, alias = raw, raw
        target = target.strip()

        anchor = ""
        if "#" in target:
            target, section = target.split("#", 1)
            anchor = f"#{section.strip()}"

        linked = title_map.get(target)
        if not linked:
            errors.append(f"{note.source_path}: unresolved wikilink `[[{raw}]]`")
            return f"[{alias}]"

        return f"[{alias}]({{% post_url {linked.post_id} %}}{anchor})"

    body = WIKILINK_RE.sub(replace_wikilink, body)
    return body, copy_plan


def render_frontmatter(note: Note) -> str:
    inherit_keys = ["categories", "tags", "description", "image", "toc", "comments", "pin"]
    lines = [
        "---",
        "layout: post",
        f'title: "{note.title}"',
        f"date: {note.date_raw}",
        f"slug: {note.slug}",
        f"generated_by: {GENERATED_BY}",
        f"source_path: {note.source_path.as_posix()}",
    ]
    for key in inherit_keys:
        if key in note.frontmatter:
            value = note.frontmatter[key]
            if isinstance(value, list):
                lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
            elif isinstance(value, bool):
                lines.append(f"{key}: {'true' if value else 'false'}")
            else:
                lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def cmd_export(args: argparse.Namespace) -> int:
    vault_dir = Path(args.vault_dir)
    site_dir = Path(args.site_dir)
    posts_dir = vault_dir / "20-Posts"

    notes, errors = load_notes(posts_dir, site_dir)
    if errors:
        print("Export failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    title_map = {note.title: note for note in notes}

    site_posts = site_dir / "posts"
    site_assets = site_dir / "assets"
    shutil.rmtree(site_posts, ignore_errors=True)
    shutil.rmtree(site_assets, ignore_errors=True)
    site_posts.mkdir(parents=True, exist_ok=True)
    site_assets.mkdir(parents=True, exist_ok=True)

    index = {}
    export_errors: List[str] = []

    for note in sorted(notes, key=lambda n: n.post_id):
        converted_body, copy_plan = convert_content(note, title_map, vault_dir, export_errors)
        front = render_frontmatter(note)
        write_if_changed(note.output_post_path, front + converted_body.strip() + "\n")

        if copy_plan:
            note.assets_dir.mkdir(parents=True, exist_ok=True)
            (note.assets_dir / ASSET_MARKER_FILE).write_text(GENERATED_BY, encoding="utf-8")
            for src, dst in sorted(copy_plan, key=lambda x: x[0].as_posix()):
                if not dst.exists() or src.read_bytes() != dst.read_bytes():
                    shutil.copy2(src, dst)

        index[note.title] = {
            "title": note.title,
            "source_path": note.source_path.as_posix(),
            "post_id": note.post_id,
            "output_post_path": note.output_post_path.as_posix(),
            "assets_dir": note.assets_dir.as_posix(),
        }

    if export_errors:
        print("Export failed:")
        for err in export_errors:
            print(f"- {err}")
        return 1

    index_path = site_dir / ".index.json"
    write_if_changed(index_path, json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(f"Exported {len(notes)} post(s) into {site_dir}")
    return 0


def read_index(site_dir: Path) -> Dict[str, dict]:
    index_path = site_dir / ".index.json"
    if not index_path.exists():
        return {}
    return json.loads(index_path.read_text(encoding="utf-8"))


def is_generated_post(path: Path) -> bool:
    if not path.exists():
        return False
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm.get("generated_by") == GENERATED_BY


def cmd_sync(args: argparse.Namespace) -> int:
    site_dir = Path(args.site_dir)
    posts_dir = Path(args.posts_dir)
    assets_dir = Path(args.assets_dir)

    source_posts = site_dir / "posts"
    source_assets = site_dir / "assets"

    if not source_posts.exists():
        print(f"sync failed: missing source posts dir {source_posts}")
        return 1

    index = read_index(site_dir)
    managed_posts = {Path(data["output_post_path"]).name for data in index.values()}
    for post_file in sorted(posts_dir.glob("*.md")):
        if is_generated_post(post_file) and post_file.name not in managed_posts:
            post_file.unlink()

    for src in sorted(source_posts.glob("*.md")):
        if not is_generated_post(src):
            continue
        dst = posts_dir / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or src.read_text(encoding="utf-8") != dst.read_text(encoding="utf-8"):
            shutil.copy2(src, dst)

    managed_asset_slugs = {Path(data["assets_dir"]).name for data in index.values()}
    assets_dir.mkdir(parents=True, exist_ok=True)

    for child in sorted(assets_dir.iterdir()):
        if not child.is_dir():
            continue
        marker = child / ASSET_MARKER_FILE
        if marker.exists() and child.name not in managed_asset_slugs:
            shutil.rmtree(child)

    if source_assets.exists():
        for src_dir in sorted(source_assets.iterdir()):
            if not src_dir.is_dir():
                continue
            dst_dir = assets_dir / src_dir.name
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)

    print("Sync completed")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    vault_dir = Path(args.vault_dir)
    posts_dir = vault_dir / "20-Posts"

    notes, errors = load_notes(posts_dir, Path(args.site_dir))
    title_map = {note.title: note for note in notes}

    for note in notes:
        convert_content(note, title_map, vault_dir, errors)
        raw = note.source_path.read_text(encoding="utf-8")
        for name, pattern in SENSITIVE_PATTERNS:
            if pattern.search(raw):
                errors.append(f"{note.source_path}: sensitive pattern matched `{name}`")

    if errors:
        print("Validation failed:")
        for err in sorted(errors):
            print(f"- {err}")
        return 1

    print(f"Validation passed for {len(notes)} post(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Obsidian -> Jekyll publishing pipeline")
    parser.add_argument("--vault-dir", default="vault", help="Path to vault root")
    parser.add_argument("--site-dir", default="site-content", help="Path to site-content root")
    parser.add_argument("--posts-dir", default="_posts", help="Path to Jekyll posts directory")
    parser.add_argument("--assets-dir", default="assets/img/posts", help="Path to Jekyll assets directory")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export", help="Export publishable notes into site-content")
    sub.add_parser("sync", help="Sync exported content into _posts/assets")
    sub.add_parser("validate", help="Validate publishable notes")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "export":
        return cmd_export(args)
    if args.command == "sync":
        return cmd_sync(args)
    if args.command == "validate":
        return cmd_validate(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
