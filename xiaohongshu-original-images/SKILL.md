---
name: xiaohongshu-original-images
description: Extract original Xiaohongshu (小红书) note images from a share link, with no-watermark priority and minimal browser round-trips. Use when the user sends a Xiaohongshu share URL and wants the original images saved, downloaded, or sent back; especially when normal saving from phone/web produces blurry, compressed, or watermarked images. Trigger on natural requests like “把这个小红书链接里的原图发我”, “帮我下载这个小红书笔记的原图”, “这个小红书链接里的图片保存原图”, or similar wording without requiring the user to mention the skill name.
---

# Xiaohongshu Original Images

Extract **original / no-watermark-priority** images from a Xiaohongshu share link.

## User-facing behavior

When this skill is used, start with one short line before running:

- `现在在用 xiaohongshu-original-images skill 下载原图。`

Do not add extra explanation unless the user asks.

## Core rule

Prefer this data flow:

1. **One browser open** to the final note page
2. **One browser evaluate** that returns both:
   - note request params: `source_note_id`, `xsec_token`, `xsec_source`
   - SSR / initial-state image objects
   - `raw_key` values normalized from SSR preview URLs
   - signed feed API result (best case)
3. If feed returns true original image URLs, download those or normalize them back to `raw_key`
4. If feed is unavailable, treat SSR / initial-state URLs as **preview fallback**, not as confirmed originals

Do **not** bounce between multiple browser snapshots / evaluates if one evaluate can return everything.

## Fastest stable route

### 1. Open the share link once

Use browser to open the Xiaohongshu share URL.
If the short link redirects, stay on the final `/explore/<note_id>` page.

### 2. Run one evaluate that does all extraction work

In the same evaluate call:

- read the current URL
- extract `source_note_id`, `xsec_token`, `xsec_source`
- read SSR / initial state image objects if present
- convert SSR preview URLs to `raw_key`
- call the page webpack API wrapper for `/api/sns/web/v1/feed`
- return both the feed result and the fallback SSR data

Use this pattern:

```js
async () => {
  const href = location.href;
  const u = new URL(href);
  const source_note_id = (u.pathname.match(/\/explore\/([^/?#]+)/) || [])[1] || null;
  const xsec_token = u.searchParams.get('xsec_token');
  const xsec_source = u.searchParams.get('xsec_source') || 'pc_note';

  const extractRawKey = (value) => {
    if (!value) return null;
    try {
      const p = new URL(value, location.origin);
      let key = decodeURIComponent((p.pathname || '').split('/').filter(Boolean).pop() || '');
      if (key.includes('!')) key = key.split('!', 1)[0];
      if (key.includes('?')) key = key.split('?', 1)[0];
      return key || null;
    } catch {
      return null;
    }
  };

  const ssrStrings = [];
  const pushIfImage = (s) => {
    if (typeof s === 'string' && /xhscdn\.com|xhsci\.com|imageView2|!nd_/i.test(s)) ssrStrings.push(s);
  };

  const scripts = [...document.querySelectorAll('script')];
  for (const script of scripts) {
    const txt = script.textContent || '';
    const matches = txt.match(/https?:\\/\\/[^"'\\s]+/g) || [];
    matches.forEach(pushIfImage);
  }

  const ssrPreviewUrls = [...new Set(ssrStrings)];
  const ssrRawKeys = [...new Set(ssrPreviewUrls.map(extractRawKey).filter(Boolean))];

  let feed = null;
  try {
    const chunk = window.webpackChunkxhs_pc_web;
    let req;
    chunk.push([[Symbol('x')], {}, function(__webpack_require__){ req = __webpack_require__; }]);
    const api = req(40122);
    const r = await api.an({ source_note_id, xsec_token, xsec_source });
    feed = r?.data || r;
  } catch (e) {
    feed = e?.data || e?.response?.data || { ok: false, msg: String(e) };
  }

  const feedUrls = (((feed || {}).items || [])[0]?.noteCard?.imageList || [])
    .map(x => x?.url)
    .filter(Boolean);
  const feedRawKeys = [...new Set(feedUrls.map(extractRawKey).filter(Boolean))];

  return {
    href,
    source_note_id,
    xsec_token,
    xsec_source,
    ssrPreviewUrls,
    ssrRawKeys,
    feed,
    feedUrls,
    feedRawKeys,
  };
}
```

### 3. Success classification matters more than fallback depth

Priority:

1. `feedUrls` that are clearly **not** preview URLs
2. `feedRawKeys`
3. `ssrRawKeys` only as a probing fallback
4. `window.__INITIAL_STATE__` / SSR `urlDefault` only as **preview_only**

Do not return SSR preview URLs as "originals". If only SSR preview URLs are available, label the result as `preview_only`.

## URL / key rules

Read `references/url-patterns.md` if you need the exact normalization rules.

Short version:

- **Bad / preview / watermark-risk**:
  - host contains `sns-webpic`
  - URL contains `WB_PRV`, `WB_DFT`, `!nd_prv`, `!nd_dft`, `imageView2`
- **Best internal representation**:
  - `raw_key`
- **Safe downloadable original form**:
  - `https://<original-cdn-host>/notes_pre_post/<raw_key>`
  - no query, no `!nd_*`, no preview transform suffix

### Success statuses

The skill must distinguish:

- `original_success`
  - final URL is **not** `sns-webpic`
  - final URL does **not** contain `!nd_*`, `WB_PRV`, `WB_DFT`, or `imageView2`
- `preview_only`
  - only `urlDefault`, `urlPre`, `sns-webpic`, or other preview URLs are available
- `failed`
  - no usable image URL could be downloaded

### Raw key derivation rule

For any SSR preview URL:

1. take the last path segment
2. strip everything after `!`
3. strip everything after `?`
4. the remainder is the `raw_key`

## Download workflow

For a share link or pasted Xiaohongshu share text, use the end-to-end extractor first:

```bash
python scripts/xhs_extract_note_images.py "<share text or URL>" --out-dir tmp/xhs
```

It will:

- resolve the short link
- parse the note `window.__INITIAL_STATE__`
- extract `imageList`
- derive `raw_key` from each preview URL
- try `https://sns-img-*.xhscdn.com/notes_pre_post/<raw_key>` before preview URLs
- prefer `WB_DFT` / `urlDefault` over thumbnails
- download all note images
- write `manifest.json` with `original_success`, `preview_only`, or `failed`

Use the lower-level bundled script when you already have raw keys or specific image URLs:

- classify each input as preview URL / raw URL / raw key
- normalize preview URLs into `raw_key`
- probe candidate original CDN hosts
- download the first working candidate URL
- report whether the downloaded result is `original_success` or `preview_only`

### Probe only

```bash
python scripts/xhs_download_images.py --probe-only --url "<preview-or-raw-url>"
```

### Download from raw keys or preview URLs

```bash
python scripts/xhs_download_images.py --out-dir tmp/xhs --key "<raw_key_1>" --key "<raw_key_2>"
```

or

```bash
python scripts/xhs_download_images.py --out-dir tmp/xhs --url "<preview_url>"
```

## Verification

Before sending files back, verify:

- file exists
- content type starts with `image/`
- chosen URL is not a preview URL with `sns-webpic` / `!nd_*` / `imageView2` if you plan to call it original
- if chosen URL is preview-only, say so explicitly

## Recovery rules

- If feed API returns usable original URLs, stop there; do not spend extra browser round-trips.
- If feed API fails but SSR preview URLs exist, derive `raw_key` from SSR and use the script fallback, but treat any `sns-webpic` / `!nd_*` result as `preview_only`.
- If the page redirects to login, reopen the note page fresh and rerun the single evaluate.
- If only preview URLs are available after retry, explain that the page signing chain blocked extraction of the original feed payload.

## Output rule

If the user asked for the images, send the downloaded files directly and keep the reply short.

## Bundled files

- `scripts/xhs_extract_note_images.py`: end-to-end share URL resolver, note parser, and downloader
- `scripts/xhs_download_images.py`: classify input, extract raw key, probe candidate original CDN URLs, and download images
- `references/url-patterns.md`: exact rules for distinguishing preview URL / raw URL / raw key and avoiding watermark-prone forms
