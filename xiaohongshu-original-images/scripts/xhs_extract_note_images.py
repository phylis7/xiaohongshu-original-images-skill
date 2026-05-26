import argparse
import html
import json
import os
import re
import struct
from io import BytesIO
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import requests


PREVIEW_MARKERS = (
    "!nd_",
    "WB_PRV",
    "WB_DFT",
    "imageView2",
    "watermark",
    "sns-webpic",
)
ORIGINAL_HOSTS = (
    "https://sns-img-qc.xhscdn.com",
    "https://sns-img-bd.xhscdn.com",
    "https://sns-img-hw.xhscdn.com",
    "https://sns-img-qn.xhscdn.com",
    "https://ci.xiaohongshu.com",
)


def extract_share_url(text: str) -> str:
    match = re.search(r"https?://[^\s]+", text)
    if not match:
        raise ValueError("no URL found in input")
    return match.group(0).rstrip("。.,，")


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            ),
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


def final_note_page(session: requests.Session, share_url: str) -> Tuple[str, str]:
    response = session.get(share_url, allow_redirects=True, timeout=30)
    response.raise_for_status()
    return response.url, response.text


def parse_initial_state(html_text: str) -> Dict:
    match = re.search(r"window\.__INITIAL_STATE__=(\{.*?\})</script>", html_text, re.S)
    if not match:
        raise ValueError("window.__INITIAL_STATE__ not found")

    raw = html.unescape(match.group(1)).replace(":undefined", ":null")
    return json.loads(raw)


def note_id_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    match = re.search(r"/(?:explore|discovery/item)/([^/?#]+)", parsed.path)
    return match.group(1) if match else None


def note_from_state(state: Dict, note_id: Optional[str]) -> Dict:
    detail_map = state.get("note", {}).get("noteDetailMap", {})
    if note_id and note_id in detail_map:
        return detail_map[note_id].get("note", {})
    if detail_map:
        return next(iter(detail_map.values())).get("note", {})
    raise ValueError("note detail not found in initial state")


def classify_url(url: str) -> str:
    lower = url.lower()
    if any(marker.lower() in lower for marker in PREVIEW_MARKERS):
        return "preview_url"
    if "xhscdn.com" in lower or "xhsci.com" in lower:
        return "original_url"
    return "unknown_url"


def extract_raw_key(url: str) -> Optional[str]:
    if not url:
        return None
    path = unquote(urlparse(url).path or "").strip("/")
    if not path:
        return None
    key = path.split("/")[-1]
    if "!" in key:
        key = key.split("!", 1)[0]
    if "?" in key:
        key = key.split("?", 1)[0]
    return key or None


def image_candidates(image: Dict) -> List[str]:
    urls: List[str] = []
    raw_keys = []

    for item in image.get("infoList", []) or []:
        if item.get("imageScene") == "WB_DFT" and item.get("url"):
            urls.append(item["url"])
    if image.get("urlDefault"):
        urls.append(image["urlDefault"])
    for item in image.get("infoList", []) or []:
        if item.get("url"):
            urls.append(item["url"])
    if image.get("urlPre"):
        urls.append(image["urlPre"])

    for url in urls:
        raw_key = extract_raw_key(url)
        if raw_key and raw_key not in raw_keys:
            raw_keys.append(raw_key)

    original_urls = []
    for raw_key in raw_keys:
        for host in ORIGINAL_HOSTS:
            original_urls.append(f"{host}/notes_pre_post/{raw_key}")

    seen = set()
    ordered = []
    for url in [*original_urls, *urls]:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def sniff_size(content: bytes, content_type: str) -> Optional[Tuple[int, int]]:
    if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
        width, height = struct.unpack(">II", content[16:24])
        return width, height

    if content.startswith(b"\xff\xd8"):
        stream = BytesIO(content)
        stream.read(2)
        while True:
            marker_prefix = stream.read(1)
            if not marker_prefix:
                break
            if marker_prefix != b"\xff":
                continue
            marker = stream.read(1)
            while marker == b"\xff":
                marker = stream.read(1)
            if marker in {
                b"\xc0",
                b"\xc1",
                b"\xc2",
                b"\xc3",
                b"\xc5",
                b"\xc6",
                b"\xc7",
                b"\xc9",
                b"\xca",
                b"\xcb",
                b"\xcd",
                b"\xce",
                b"\xcf",
            }:
                block = stream.read(7)
                if len(block) >= 5:
                    height, width = struct.unpack(">HH", block[1:5])
                    return width, height
                break
            size_bytes = stream.read(2)
            if len(size_bytes) != 2:
                break
            block_size = struct.unpack(">H", size_bytes)[0]
            stream.seek(max(block_size - 2, 0), os.SEEK_CUR)

    if content.startswith(b"RIFF") and content[8:12] == b"WEBP" and len(content) >= 30:
        if content[12:16] == b"VP8X":
            width = 1 + int.from_bytes(content[24:27], "little")
            height = 1 + int.from_bytes(content[27:30], "little")
            return width, height
    return None


def download_first_working(
    session: requests.Session,
    candidates: Iterable[str],
    out_dir: str,
    index: int,
) -> Dict:
    failures = []
    for url in candidates:
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if not content_type.startswith("image/"):
                failures.append({"url": url, "reason": f"not image: {content_type}"})
                continue

            ext = ".png" if "png" in content_type else ".jpg" if "jpeg" in content_type or "jpg" in content_type else ".webp"
            path = os.path.join(out_dir, f"{index:02d}{ext}")
            with open(path, "wb") as f:
                f.write(response.content)

            return {
                "downloaded": True,
                "path": path,
                "url": url,
                "status": "original_success" if classify_url(url) == "original_url" else "preview_only",
                "url_kind": classify_url(url),
                "content_type": content_type,
                "bytes": len(response.content),
                "size": sniff_size(response.content, content_type),
            }
        except Exception as exc:
            failures.append({"url": url, "reason": str(exc)})

    return {"downloaded": False, "status": "failed", "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and download Xiaohongshu note images from a share URL.")
    parser.add_argument("input", help="Xiaohongshu share text or URL")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    session = make_session()
    share_url = extract_share_url(args.input)
    final_url, page_html = final_note_page(session, share_url)
    state = parse_initial_state(page_html)
    note_id = note_id_from_url(final_url)
    note = note_from_state(state, note_id)
    images = note.get("imageList") or []

    if not images:
        raise SystemExit("no note images found")

    os.makedirs(args.out_dir, exist_ok=True)
    results = []
    for index, image in enumerate(images, 1):
        candidates = image_candidates(image)
        result = download_first_working(session, candidates, args.out_dir, index)
        result.update(
            {
                "index": index,
                "expected_size": [image.get("width"), image.get("height")],
                "raw_key": extract_raw_key(candidates[0]) if candidates else None,
                "candidate_count": len(candidates),
            }
        )
        print(json.dumps(result, ensure_ascii=False))
        results.append(result)

    manifest = {
        "input_url": share_url,
        "final_url": final_url,
        "note_id": note_id,
        "title": note.get("title") or "",
        "status": (
            "original_success"
            if any(r.get("status") == "original_success" for r in results)
            else "preview_only"
            if any(r.get("status") == "preview_only" for r in results)
            else "failed"
        ),
        "images": results,
    }
    manifest_path = os.path.join(args.out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(json.dumps({"manifest": manifest_path, "status": manifest["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
