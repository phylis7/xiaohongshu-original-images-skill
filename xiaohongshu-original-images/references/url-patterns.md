# Xiaohongshu 图片 URL / Key 规则

## 结论

优先拿 **raw key**，其次才拿 **raw CDN URL**；不要把 SSR 里的完整预览 URL 当最终结果。

最稳妥的输出形态是：

- **无水印优先形态**：`raw key`
  - 例：`1040g2sg31ivgho1g12405o6bdr3k8g1d9m9h4n0`
- **可直接下载的原图 URL**：`https://sns-na-i1.xhscdn.com/<raw_key>` 这类 **无任何图片处理后缀** 的 CDN URL
- **高风险预览 / 水印形态**：带 `sns-webpic`、`WB_PRV`、`WB_DFT`、`!nd_prv...`、`!nd_dft...`、`imageView2` 的完整 URL

## 从 SSR 预览 URL 直接推 raw key

### 规则

对 SSR / HTML / script 里看到的预览 URL，先只做一件事：

1. 取 URL path 最后一个片段
2. 去掉 `!` 后面的全部处理后缀
3. 去掉 `?` 后面的全部 query
4. 剩下的就是 `raw key`

### 示例 1：`sns-webpic` + query 参数

输入：

```text
https://sns-webpic-qc.xhscdn.com/1040g2sg31ivgho1g12405o6bdr3k8g1d9m9h4n0?imageView2/2/w/1080/format/jpg
```

输出：

```text
1040g2sg31ivgho1g12405o6bdr3k8g1d9m9h4n0
```

### 示例 2：`!nd_prv` / `!nd_dft` 后缀

输入：

```text
https://ci.xiaohongshu.com/1040g2sg31ivgho1g12405o6bdr3k8g1d9m9h4n0!nd_prv_wgth_jpg_1080
```

输出：

```text
1040g2sg31ivgho1g12405o6bdr3k8g1d9m9h4n0
```

## 形态区分

### A. 预览 / 水印风险 URL（不要直接回传）

满足任一条件都视为预览：

- host 含 `sns-webpic`
- URL 含 `WB_PRV` 或 `WB_DFT`
- URL 含 `!nd_`
- URL 含 `imageView2`
- URL 明显带缩放、格式转换、水印参数

这类 URL 常见问题：

- 分辨率被限制
- 可能带水印
- 同一 key 被套了 web preview 处理链

### B. raw key（优先保留）

raw key 是**不带 host、不带 query、不带 `!nd_*` 后缀**的裸资源标识。

这是最适合在 skill 内部传递和缓存的形态，因为：

- 不绑定某个具体 CDN host
- 不会把 preview 处理参数一起带过去
- 后续可用 feed API 返回的原始 URL 或候选 host 再拼接

### C. 原图 raw CDN URL（可下载）

形态：

```text
https://<original-cdn-host>/<raw_key>
```

关键要求：

- host 是原图 CDN，而不是 `sns-webpic`
- URL 末尾只有 raw key
- 不带 `!nd_prv...` / `!nd_dft...` / `imageView2`

## 推荐策略

1. **一次 browser evaluate 同时拿齐**：`source_note_id`、`xsec_token`、`xsec_source`、SSR 里的预览图 URL、由预览图 URL 提出来的 `raw key`
2. **优先调用页面内 feed API**，直接拿 `items[0].noteCard.imageList[].url`
3. **把 feed 返回 URL 再归一化成 `raw key` 保存**
4. 回传给下载脚本时，优先传 `raw key`，不要传 preview URL
5. 只有在 feed API 不稳定时，才用 SSR 提出来的 raw key 做候选 host 探测

## 为什么 raw key 更安全

因为“带水印版本”通常是 **完整 URL + 图片处理链**，而不是 key 本身。

换句话说：

- **问题往往出在 URL 形态**，不是资源 key 形态
- 同一个资源，只要把 `!nd_*` / `imageView2` 这类处理链带上，就可能又回到预览 / 水印链路

所以在 skill 内部流转时，应优先保存：

- `raw key`
- 或不带任何处理后缀的原图 URL

而不是保存 SSR 里的完整预览 URL。
