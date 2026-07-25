---
name: "xiaohongshu-original-images"
description: "Make Xiaohongshu image delivery strictly original-only; never send preview images."
---

# Xiaohongshu Original Images

Download **confirmed original images only** from a Xiaohongshu share link.

## User-facing start

Before running, say exactly:

`现在在用 xiaohongshu-original-images skill 下载原图。`

## Non-negotiable delivery rule

- Never send `preview_only` images, thumbnails, `sns-webpic` URLs, or URLs containing `!nd_*`, `WB_PRV`, `WB_DFT`, or `imageView2`.
- Send an image only when its result is `original_success`.
- Every image in the note must be `original_success` before delivery. If any image fails, do not substitute a preview; state which images failed.
- When sending through Feishu, send each original as a **file attachment**, one message per file, to avoid image-message recompression.

## Workflow

1. Resolve the share URL and parse the note initial state:

```bash
python scripts/xhs_extract_note_images.py "<share text or URL>" --out-dir tmp/xhs/<note>
```

2. Inspect `manifest.json`.
3. If every image is `original_success`, verify files and send them as separate file attachments.
4. If any result is `preview_only`, take every `raw_key` from the manifest and run the lower-level downloader:

```bash
python scripts/xhs_download_images.py --out-dir tmp/xhs/<note>/originals --key "<raw_key_1>" --key "<raw_key_2>"
```

5. The lower-level downloader must probe both URL shapes on each raw CDN host:
   - `https://<host>/<raw_key>`
   - `https://<host>/notes_pre_post/<raw_key>`
6. Prefer direct raw-key paths first because current Xiaohongshu assets may return 404 on `/notes_pre_post/` while the direct path returns the full original.
7. Deliver only results explicitly reported as `original_success`.

## Original verification

Before delivery, verify all of the following:

- file exists and is non-empty
- content type starts with `image/`
- final URL host is an original CDN, not `sns-webpic`
- final URL has no `!nd_*`, `WB_PRV`, `WB_DFT`, `imageView2`, resize, transform, or watermark suffix
- downloader status is `original_success`
- preserve the downloaded bytes during delivery; use file attachments rather than compressed image messages

## Failure behavior

If confirmed originals cannot be downloaded:

- do not send previews
- do not describe previews as originals
- briefly say original extraction failed because the signed/original CDN chain was unavailable
- retain raw keys and diagnostic results for a later retry

## URL normalization

For a preview URL, derive `raw_key` by taking the last path segment, then stripping everything after `!` and `?`. Use the raw key only for probing; never deliver the preview URL itself.

Read `references/url-patterns.md` when exact classification rules are needed.
