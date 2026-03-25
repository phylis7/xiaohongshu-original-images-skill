# xiaohongshu-original-images

这是一个用于 **提取和下载小红书（Xiaohongshu）笔记原图** 的 OpenClaw Skill。

它的目标不是保存网页预览图，而是尽量拿到：

- **原图**
- **无水印优先**
- **更少浏览器往返**
- **更稳定的下载流程**

适合下面这类需求：

- “帮我把这个小红书链接里的原图下载下来”
- “这个小红书笔记的图片发我原图”
- “不要压缩图，不要模糊图，直接提取原图”

---

## 功能说明

这个 Skill 会优先通过页面里的笔记数据提取图片原始标识，再组合为可下载的原图地址。

核心能力包括：

- 从小红书分享链接进入最终笔记页
- 提取 `source_note_id`、`xsec_token`、`xsec_source`
- 优先从 feed 数据中拿图片原始信息
- 失败时回退到 SSR 预览图并反推出 `raw_key`
- 用脚本自动探测可用原图 CDN 并下载
- 避免直接使用带压缩/预览参数的链接

---

## 仓库结构

```text
xiaohongshu-original-images/
├─ SKILL.md
├─ references/
│  └─ url-patterns.md
└─ scripts/
   └─ xhs_download_images.py
```

### 文件作用

- `SKILL.md`
  - Skill 主说明文件
  - 定义了触发场景、执行流程、浏览器提取逻辑、回退策略

- `references/url-patterns.md`
  - 说明什么是预览图 URL、什么是原图 URL、什么是 `raw_key`
  - 用于避免下载到带水印或被压缩的图片

- `scripts/xhs_download_images.py`
  - 下载脚本
  - 负责识别输入、探测 CDN、下载图片到本地目录

---

## 如何使用

### 方式一：在 OpenClaw 里作为 Skill 使用

当用户给出一个小红书链接，并表达“下载原图 / 保存原图 / 发原图”之类意图时，这个 Skill 会被触发。

典型说法例如：

- 把这个小红书链接里的原图发我
- 帮我下载这个小红书笔记的原图
- 这个小红书链接里的图片保存原图

Skill 的执行思路是：

1. 打开小红书分享链接
2. 跳转到最终笔记页 `/explore/<note_id>`
3. 在页面里一次性提取：
   - 笔记参数
   - SSR 图片信息
   - feed 返回结果
4. 优先使用 feed 中的原图信息
5. 如果 feed 不可用，则从 SSR 预览图反推 `raw_key`
6. 调用 Python 脚本下载原图

---

### 方式二：直接使用下载脚本

你也可以不用整套 Skill，只直接调用脚本。

#### 1）根据 URL 探测

```bash
python scripts/xhs_download_images.py --probe-only --url "<图片链接或预览链接>"
```

这个模式适合先验证某个链接能不能还原成原图地址。

#### 2）按 raw_key 下载

```bash
python scripts/xhs_download_images.py --out-dir tmp/xhs --key "<raw_key_1>" --key "<raw_key_2>"
```

#### 3）按 URL 直接下载

```bash
python scripts/xhs_download_images.py --out-dir tmp/xhs --url "<preview_or_raw_url>"
```

---

## 推荐使用流程

推荐按照下面顺序使用，稳定性最好：

1. 用浏览器打开小红书分享链接
2. 进入最终笔记页
3. 从页面中提取：
   - `source_note_id`
   - `xsec_token`
   - `xsec_source`
   - `feedRawKeys` / `ssrRawKeys`
4. 优先使用 `feedRawKeys`
5. 再调用 `xhs_download_images.py` 下载到本地

---

## 结果校验

下载完成后，建议至少检查以下几点：

- 文件是否真实存在
- MIME 类型是否为 `image/*`
- 分辨率是否合理，不是很小的缩略图
- 下载链接是否包含以下预览特征：
  - `sns-webpic`
  - `imageView2`
  - `!nd_prv`
  - `!nd_dft`
  - `WB_PRV`
  - `WB_DFT`

如果有这些特征，通常说明拿到的是预览图，不是理想原图。

---

## 适用场景

适合：

- 小红书分享链接原图提取
- 无水印优先下载
- 批量保存笔记图片
- 给用户返回更清晰的原始图片

不适合：

- 抓取视频
- 抓取登录后强权限内容
- 长期高频批量爬取
- 绕过平台风控的重型抓取任务

---

## 注意事项

- 小红书页面结构和接口签名可能变化
- 如果 feed 接口失效，Skill 会退回 SSR 路线
- 如果页面要求登录，需重新进入可访问页面后再提取
- 本 Skill 目标是提高原图获取成功率，不保证平台所有笔记都可稳定提取

---

## 总结

这个 Skill 的定位很明确：

> **尽量稳定、尽量少绕路地把小红书笔记图片提取成原图并下载下来。**

如果你在 OpenClaw 里经常处理“小红书原图下载”这类任务，这个 Skill 就是专门为这个场景准备的。