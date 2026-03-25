# xiaohongshu-original-images Skill Repository

This repository stores the `xiaohongshu-original-images` AgentSkill so it can be tracked, audited, and deployed to other OpenClaw environments or published to GitHub. The skill is designed to extract no-watermark original photos from Xiaohongshu (小红书) note share links with a single browser round-trip and controlled download logic.

## Repository Contents

- `xiaohongshu-original-images/SKILL.md` — Skill definition plus procedural instructions for using the skill.
- `xiaohongshu-original-images/scripts/xhs_download_images.py` — Python helper that classifies URLs/raw keys, probes CDN hosts, and downloads the best original images.
- `xiaohongshu-original-images/references/url-patterns.md` — Detailed rules for differentiating preview URLs from raw keys and avoiding watermark-prone transformations.

## Usage

1. **Open the note in a browser** (the skill expects you to load the share link once and stay on `/explore/<note_id>`).
2. **Run the evaluate script inside the browser** to collect `source_note_id`, `xsec_token`, and the SSR/ feed data. Follow the snippet inside `SKILL.md`.
3. **Feed the extracted `raw_key`/URL data to `scripts/xhs_download_images.py`** with the `--out-dir` where you want the files stored.
4. **Verify** downloaded files for `image/` MIME type and sensible resolution before delivering back to the requester.

Example download command:
```bash
python skills/xiaohongshu-original-images/scripts/xhs_download_images.py \
  --out-dir /tmp/xhs \
  --key <raw_key_1> \
  --key <raw_key_2>
```

## GitHub Deployment

1. Initialize a new GitHub repository (via `github.com/new` or CLI).
2. From this workspace:
   ```bash
   cd repo
   git init
   git add -A
   git commit -m "Add Xiaohongshu original-images skill"
   git branch -M main
   git remote add origin <your-github-remote>
   git push -u origin main
   ```
3. Add a release or tag if you want versioned references.

You can also automate packaging with `scripts/package_skill.py` inside the skill directory if you plan to distribute this as a `.skill` file.

Let me know when you want me to push this to your GitHub account or to create a remote for you—just give me the repo name or URL. All further automation (like CI or issues) can reference this repository directly.