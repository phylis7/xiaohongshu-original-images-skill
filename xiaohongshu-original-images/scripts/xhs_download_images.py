import argparse
import json
import os
from io import BytesIO
from typing import Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import requests
from PIL import Image


DEFAULT_HOSTS = [
    'https://sns-img-bd.xhscdn.com',
    'https://sns-img-hw.xhscdn.com',
    'https://sns-na-i1.xhscdn.com',
    'https://sns-na-i2.xhscdn.com',
]
PREVIEW_MARKERS = (
    '!nd_',
    'WB_PRV',
    'WB_DFT',
    'imageView2',
    'watermark',
    'sns-webpic',
)


def classify_input(value: str) -> str:
    lower = value.lower()
    if lower.startswith('http://') or lower.startswith('https://'):
        if any(marker.lower() in lower for marker in PREVIEW_MARKERS):
            return 'preview_url'
        if 'xhscdn.com' in lower:
            return 'raw_url'
        return 'url'
    return 'raw_key'



def extract_raw_key(value: str) -> str:
    kind = classify_input(value)
    if kind == 'raw_key':
        return value.strip()

    parsed = urlparse(value)
    path = unquote(parsed.path or '').strip('/')
    if not path:
        raise ValueError(f'cannot extract raw key from: {value}')

    key = path.split('/')[-1]
    if '!' in key:
        key = key.split('!', 1)[0]
    if '?' in key:
        key = key.split('?', 1)[0]
    return key



def build_candidate_urls(raw_key: str, hosts: Iterable[str]) -> List[str]:
    key = raw_key.lstrip('/')
    return [f"{host.rstrip('/')}/{key}" for host in hosts]



def probe(session: requests.Session, url: str, timeout: int = 20) -> Tuple[bool, Optional[dict]]:
    try:
        r = session.get(url, timeout=timeout, stream=True)
        r.raise_for_status()
        content_type = (r.headers.get('content-type') or '').lower()
        body = r.raw.read(512 * 1024, decode_content=True)
        info = {
            'url': url,
            'status': r.status_code,
            'content_type': content_type,
            'bytes_sampled': len(body),
            'size': None,
        }
        if content_type.startswith('image/'):
            try:
                img = Image.open(BytesIO(body))
                info['size'] = img.size
            except Exception:
                info['size'] = None
        return True, info
    except Exception as e:
        return False, {'url': url, 'error': str(e)}



def download(session: requests.Session, url: str, out_dir: str, index: int):
    r = session.get(url, timeout=30)
    r.raise_for_status()

    content_type = (r.headers.get('content-type') or '').lower()
    ext = '.png' if 'png' in content_type else '.jpg' if 'jpeg' in content_type or 'jpg' in content_type else '.bin'
    path = os.path.join(out_dir, f'original_{index}{ext}')

    with open(path, 'wb') as f:
        f.write(r.content)

    info = {'path': path, 'content_type': content_type, 'bytes': len(r.content), 'size': None, 'url': url}
    if content_type.startswith('image/'):
        img = Image.open(BytesIO(r.content))
        info['size'] = img.size
    return info



def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.xiaohongshu.com/'
    })
    return session



def main():
    parser = argparse.ArgumentParser(description='Normalize Xiaohongshu preview URLs to raw keys, probe candidates, and download original images.')
    parser.add_argument('--out-dir')
    parser.add_argument('--url', action='append', default=[], help='Image URL. Can be preview URL or raw CDN URL.')
    parser.add_argument('--key', action='append', default=[], help='Raw CDN key without host.')
    parser.add_argument('--host', action='append', default=[], help='Candidate raw host. Can be passed multiple times.')
    parser.add_argument('--probe-only', action='store_true', help='Only classify / normalize / probe candidate URLs, do not download.')
    args = parser.parse_args()

    if not args.url and not args.key:
        parser.error('at least one of --url or --key is required')

    hosts = args.host or DEFAULT_HOSTS
    session = make_session()

    raw_keys: List[str] = []
    seen = set()
    for value in [*args.url, *args.key]:
        raw_key = extract_raw_key(value)
        if raw_key not in seen:
            seen.add(raw_key)
            raw_keys.append(raw_key)
        print(json.dumps({
            'input': value,
            'kind': classify_input(value),
            'raw_key': raw_key,
            'candidate_urls': build_candidate_urls(raw_key, hosts),
        }, ensure_ascii=False))

    if args.probe_only:
        for raw_key in raw_keys:
            for url in build_candidate_urls(raw_key, hosts):
                ok, info = probe(session, url)
                print(json.dumps({'probe_ok': ok, **info}, ensure_ascii=False))
        return

    if not args.out_dir:
        parser.error('--out-dir is required unless --probe-only is set')

    os.makedirs(args.out_dir, exist_ok=True)

    download_index = 1
    for raw_key in raw_keys:
        selected_url = None
        for url in build_candidate_urls(raw_key, hosts):
            ok, info = probe(session, url)
            print(json.dumps({'probe_ok': ok, **info}, ensure_ascii=False))
            if ok and (info.get('content_type') or '').startswith('image/'):
                selected_url = url
                break

        if not selected_url:
            print(json.dumps({'raw_key': raw_key, 'downloaded': False, 'reason': 'no_working_candidate_url'}, ensure_ascii=False))
            continue

        info = download(session, selected_url, args.out_dir, download_index)
        print(json.dumps({'downloaded': True, **info}, ensure_ascii=False))
        download_index += 1


if __name__ == '__main__':
    main()
