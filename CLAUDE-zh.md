# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码仓库中工作时提供指导。

## 项目概述

easyVmaf 是一个 Python CLI 工具，封装了 FFmpeg 和 FFprobe 来计算 VMAF 视频质量评分。
它处理 VMAF 所需的预处理工作：去隔行、缩放、帧率归一化，以及参考视频流与失真视频流之间的帧精确时间同步。

## 环境配置

```bash
pip install -e .          # 从源码安装（可编辑模式）
# 或发布到 PyPI 后：
pip install easyvmaf
```

FFmpeg >= 5.0（编译时启用 `--enable-libvmaf`）必须在 PATH 中，或通过环境变量指定：

```bash
FFMPEG=/path/to/ffmpeg FFPROBE=/path/to/ffprobe python3 -m easyvmaf ...
```

## 运行工具

```bash
# 已安装的 CLI 命令
easyvmaf -d distorted.mp4 -r reference.mp4
easyvmaf -d distorted.mp4 -r reference.mp4 -sw 2      # 带同步窗口
easyvmaf -d distorted.mp4 -r reference.mp4 --gpu      # GPU 加速（CUDA）
easyvmaf -d distorted.mp4 -r reference.mp4 -json      # 结构化 JSON 输出
easyvmaf -d "folder/*.mp4" -r reference.mp4           # 批量处理

# 模块调用（无需安装）
python3 -m easyvmaf -d distorted.mp4 -r reference.mp4
```

## Docker

```bash
# CPU 构建
docker build -t easyvmaf .
docker run --rm -v $(pwd)/video_samples:/videos easyvmaf \
  -d /videos/distorted.mp4 -r /videos/reference.mp4

# GPU 构建（需要 CUDA 12.3，主机上的 nvidia-container-toolkit）
docker build -f Dockerfile.cuda -t easyvmaf:cuda .
docker run --rm --gpus all -v $(pwd)/video_samples:/videos easyvmaf:cuda \
  -d /videos/distorted.mp4 -r /videos/reference.mp4 --gpu

# docker-compose
docker compose build
docker compose run easyvmaf -d /videos/dist.mp4 -r /videos/ref.mp4
```

---

## 三层架构

每层只能与其直接下层通信。

```
easyvmaf/cli.py     ← 第 3 层：仅 CLI（argparse、glob、JSON 输出、打印结果）
easyvmaf/vmaf.py    ← 第 2 层：VMAF 逻辑（缩放、去隔行、同步、评分）
easyvmaf/ffmpeg.py  ← 第 1 层：FFmpeg/FFprobe 子进程封装
easyvmaf/config.py  ← 二进制路径解析（通过 shutil.which 查找 ffmpeg、ffprobe）
```

辅助入口点：
- `easyvmaf/__init__.py` — 公共 API 接口
- `easyvmaf/__main__.py` — 启用 `python3 -m easyvmaf` 调用方式

### 第 1 层 — easyvmaf/ffmpeg.py
FFmpeg 和 ffprobe 二进制文件的轻量子进程封装。
- `FFprobe`：运行 ffprobe，以字典形式返回流/帧/包/格式信息
- `FFmpegQos`：构建并运行 FFmpeg 滤镜图，用于 PSNR 和 VMAF 计算
- `inputFFmpeg`：管理每个输入的滤镜链（scale、trim、fps、deinterlace、hwupload_cuda）
- `check_ffmpeg()`：探测 FFmpeg 版本、内置模型可用性和 `libvmaf_cuda` 支持
- `VMAF_MODELS`：定义 HD 和 4K 模型配置的结构化字典
- `_build_model_string()`：构建 libvmaf 的 `model=` 参数字符串

此层不得包含任何 VMAF 业务逻辑或面向用户的 print 语句。

### 第 2 层 — easyvmaf/vmaf.py
VMAF 计算编排。
- `video`：通过 FFprobe 解析流元数据（懒加载），检测隔行扫描
- `vmaf`：自动缩放、自动去隔行、并行同步偏移搜索、最终 VMAF 评分
- `UnsupportedFramerateError`：当没有去隔行滤镜覆盖该帧率组合时抛出
- `FeatureConfig`：用于构建 libvmaf `feature=` 参数字符串的数据类

此层不得包含 CLI 参数解析或结果格式化。

### 第 3 层 — easyvmaf/cli.py
仅限 CLI 入口点。Argparse、glob 模式展开用于批量处理、读取 VMAF 输出文件（json/xml/csv）、打印或输出结构化 JSON 结果。
- `-json` 参数：向 stdout 输出 NDJSON（批量模式下每个文件一个对象）；日志输出到 stderr
- `_build_result()`：构建用于 JSON 输出和人类可读显示的结果字典
- `check_ffmpeg()` 在启动时调用，进行版本/模型/CUDA 验证

此层不得直接包含 FFmpeg 滤镜逻辑或 VMAF 计算。

---

## FFprobe 调用映射 — 关键参考

在修改 easyvmaf/vmaf.py 或 easyvmaf/ffmpeg.py 之前，必须理解此映射。

| 数据               | 方法              | vmaf.py 中的消费者                            | 开销  |
|--------------------|-------------------|-----------------------------------------------|-------|
| `streamInfo`       | `getStreamInfo()` | `_autoScale`（width, height）                 | 低    |
|                    |                   | `_autoDeinterlace`（r_frame_rate）            |       |
|                    |                   | `_deinterlaceFrame/Field`（r_frame_rate）     |       |
|                    |                   | `syncOffset`（r_frame_rate, width, height）   |       |
|                    |                   | `getVmaf`（r_frame_rate, width, height,       |       |
|                    |                   |   cambi feature string）                      |       |
|                    |                   | `getDuration`（主要：duration, start_time）   |       |
| `formatInfo`       | `getFormatInfo()` | `getDuration` 仅回退使用（KeyError 路径）     | 低    |
| `framesInfo` /     | `getFramesInfo()` | `_autoDeinterlace` 仅通过 `self.interlaced`   | 高    |
| `interlaced`       |                   | 当 `manual_fps != 0` 时完全跳过               |       |
|                    |                   | 当使用 `--sync_only` 时完全跳过               |       |

`getFramesInfo()` 使用 `-read_intervals %+5` — 每个输入解码 5 秒帧数据来采样隔行状态。此参数标志不得更改。

**懒加载**：`video` 类上的 `interlaced` 和 `formatInfo` 是懒属性 — 仅在首次访问时触发 FFprobe 并缓存结果。`streamInfo` 是即时加载的（在 `__init__` 中获取）。

---

## 关键行为约定

### 同步循环（syncOffset）
- 通过 `ThreadPoolExecutor` **并行**运行同步窗口中每个帧偏移的 PSNR 计算
- 每个 worker 创建自己的 `FFmpegQos` 实例，`gpu_mode=False` — 即使设置了 `--gpu`，同步也始终仅使用 CPU
- 当设置 `--reverse` 时，`ffmpegQos.invertSrcs()` 交换 main/ref
- 反转后，必须再次调用 `invertSrcs()` 恢复原始顺序
- 每个 worker 的 QoS 实例都会调用 `clearFilters()`

### 滤镜应用顺序（始终按此顺序）
1. `clearFilters()` — 重置状态（同时重置 `_hwupload_done`）
2. `_autoScale()` — 缩放到模型分辨率（CPU `scale` 滤镜；如果未先调用 `clearFilters()` 会发出警告）
3. `_autoDeinterlace()` 或 `_forceFps()` — 归一化帧率（互斥）
4. `setOffset()` — 应用同步的 trim 滤镜
5. `getVmaf()` — 如果 `gpu=True`，自动在两条链上插入 `hwupload_cuda` 作为 `libvmaf_cuda` 之前的最后一步 CPU→GPU 转换

### GPU 滤镜管道
当使用 `--gpu` 时，`getVmaf()` 在所有 CPU 滤镜追加**之后**，对 `main` 和 `ref` 输入调用 `_insertHwupload()`：
```
[scale (CPU)] → [fps (CPU)] → [trim (CPU)] → [format=yuv420p] → [setparams=colorspace=unknown:range=unknown] → [hwupload_cuda] → [libvmaf_cuda]
```
`format=yuv420p` 归一化像素格式，但**不会**去除色彩空间元数据。
`setparams=colorspace=unknown:range=unknown` 重置 csp/range 标签，使两个输入向 `libvmaf_cuda` 呈现相同的属性。如果没有这一步，标记为 `bt709/tv` 的输入会导致 `libvmaf_cuda` 自动插入 CPU `auto_scale` 进行颜色归一化，而 `auto_scale` 无法接收 CUDA 帧，从而导致崩溃。
`_insertHwupload()` 是幂等的 — `_hwupload_done` 标志防止重复插入。
`clearFilters()` 重置此标志，使序列可重复执行。

### 时长计算
`getDuration()` 首先尝试 `streamInfo['duration']`。遇到 KeyError 时（常见于 MKV 和某些 TS 流）回退到 `formatInfo['duration']`。两个值都减去 `start_time` 并应用 `math.floor` 精确到毫秒。
时长传递给 `setOffset()` 用于计算 trim 长度。

### VMAF 模型
```python
VMAF_MODELS = {
    'HD': [                                                       # 默认
        ('vmaf_v0.6.1',     'vmaf_hd',       {}),
        ('vmaf_v0.6.1neg',  'vmaf_hd_neg',   {}),
        ('vmaf_v0.6.1',     'vmaf_hd_phone', {'enable_transform': 'true'}),
    ],
    '4K': [
        ('vmaf_4k_v0.6.1',  'vmaf_4k',       {}),
    ],
}
```
- HD 模型：单次 FFmpeg 运行计算 vmaf_hd、vmaf_hd_neg、vmaf_hd_phone
- 4K 模型：仅计算 vmaf_4k
- 使用内置模型（需要 FFmpeg >= 5.0 — 模型随 FFmpeg 构建捆绑）
- `_build_model_string()` 生成以管道/冒号分隔的 `model=` 参数

### Feature 字符串
vmaf.py 中的 `_build_feature_string()` 始终包含 PSNR；仅在传递 `--cambi_heatmap` 时添加 CAMBI。通过 `FeatureConfig` 数据类构建 — 新 feature 应添加到那里，而不是直接编辑字符串。

### 输出格式
VMAF 结果写入文件：json（默认）、xml、csv。
文件路径：与失真输入相同的目录，相同基础名 + `_vmaf.{ext}`

stdout 的 JSON 输出（`-json` 参数）：NDJSON，每个文件一个对象。
格式：`{ distorted, reference, sync: { offset, psnr }, vmaf: { model, scores…, output_file } }`

---

## 编码规则

- **subprocess**：始终使用 `shell=False` 和参数列表。禁止使用 `shell=True`。
- **滤镜字符串**：Python 源码中 `\\\\:` 对于 libvmaf 模型和 feature 参数字符串是必需的。在 Python 源码中 `\\\\` 变为两字符字面量 `\\`，FFmpeg 滤镜图解析器需要它来将选项值中的 `:` 作为字面量处理。不得更改这些分隔符。
- **禁止静默失败**：如果去隔行/帧率组合不受支持，应抛出 `UnsupportedFramerateError`，而不是打印后继续。
- **第 1 层和第 2 层禁止使用 print()**：使用 `logging` 模块和 `%s` 风格的格式化参数。`print()` 仅属于第 3 层（CLI）。
- **日志输出目标**：`basicConfig(stream=sys.stderr)` — 保持 stdout 清洁以供 `-json` 输出使用。
- **Python >= 3.8**。在适当位置使用 `functools.cached_property` 或懒 `@property`。
- **ffmpeg.py 中的公共方法签名**：未经明确指示不得更改。

## 未经明确指示不得更改的内容

- FFprobe `getFramesInfo` 命令中的 `-read_intervals %+5` 参数标志
- `getDuration()` 回退链（streamInfo → formatInfo KeyError 回退）
- `syncOffset()` 基于 PSNR 的同步算法逻辑
- libvmaf 滤镜参数名称：`n_subsample`、`n_threads`、`log_fmt`、`log_path`、`shortest`、`feature`
- `_build_model_string()` 和 feature 字符串中的 `\\\\:` 分隔符 — FFmpeg 滤镜图解析器语法
- 同步处理中的 `invertSrcs()` / `invertedSrc` 标志逻辑
- `ffmpeg.py` 中的任何公共方法名称
- `_insertHwupload()` 中的 `_hwupload_done` 守卫和 `clearFilters()` 中的重置

---

## 运行环境

- Linux / macOS（当前）
- Python >= 3.8
- FFmpeg >= 5.0，编译时启用 `--enable-libvmaf`（需要内置模型）
- GPU：FFmpeg 编译时启用 `--enable-libvmaf --enable-ffnvcodec --enable-cuda-nvcc --enable-nonfree`，libvmaf 3.0.0 编译时启用 `-Denable_cuda=true`；CUDA 12.3+ 且主机上安装 nvidia-container-toolkit
- 依赖：`ffmpeg-progress-yield >= 0.7.0`（pip）

### Docker 镜像版本（固定）
| 组件       | 版本    |
|------------|---------|
| FFmpeg     | 8.1     |
| libvmaf    | 3.0.0   |
| dav1d      | 1.4.3   |
| Python     | 3.12    |
| CUDA 基础镜像 | 12.3.2  |
