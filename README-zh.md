# easyVmaf

基于 FFmpeg 和 FFprobe 的 Python 工具，用于处理 VMAF 所需的视频预处理：

- 去隔行
- 上变换 / 下变换
- 逐帧同步
- 帧率适配

关于**工作原理**的详细说明，请参阅[此处](https://ottverse.com/vmaf-easyvmaf/)。

## 环境要求

- Linux / macOS / Windows
- Python >= 3.8
- FFmpeg >= 5.0，编译时需启用 `--enable-libvmaf`（需要内置模型）
- Python 依赖包：[`ffmpeg-progress-yield`](https://github.com/slhck/ffmpeg-progress-yield)

GPU 加速 VMAF 额外要求：

- 支持 CUDA 的 NVIDIA GPU
- FFmpeg 编译时需启用 `--enable-nonfree --enable-ffnvcodec --enable-libvmaf`
- libvmaf 编译时需启用 `-Denable_cuda=true -Denable_float=true`
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)（Docker GPU 模式需要）

## 安装

```bash
pip install easyvmaf
```

或从源码安装：

```bash
git clone https://github.com/gdavila/easyVmaf.git
cd easyVmaf
pip install -e .
```

FFmpeg 必须在 `PATH` 中，或通过环境变量指定：

```bash
# Linux / macOS
FFMPEG=/path/to/ffmpeg FFPROBE=/path/to/ffprobe easyvmaf ...

# Windows (PowerShell)
$env:FFMPEG="C:\path\to\ffmpeg.exe"; $env:FFPROBE="C:\path\to\ffprobe.exe"; easyvmaf ...
```

## 使用方法

```
easyvmaf -d <distorted> -r <reference> [options]
```

### 必需参数

| 参数 | 说明 |
|------|------|
| `-d D` | 失真视频路径（支持 glob 模式进行批量处理） |
| `-r R` | 参考视频路径 |

### 可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-sw SW` | `0` | 同步窗口大小（秒）。启用在失真视频首帧与参考视频子样本之间自动搜索同步偏移。`0` 表示禁用同步。 |
| `-ss SS` | `0` | 同步起始时间：参考视频中同步窗口开始的偏移位置。 |
| `-fps FPS` | `0` | 强制帧率转换。设置后禁用自动去隔行。 |
| `-subsample N` | `1` | 帧子采样因子，用于加速计算。 |
| `-reverse` | 关闭 | 反转同步方向：用参考视频首帧去匹配失真视频，而非默认的反向匹配。 |
| `-model MODEL` | `HD` | VMAF 模型。可选值：`HD`、`4K`。 |
| `-threads N` | `0` | 线程数（0 = 自动）。 |
| `-output_fmt FMT` | `json` | 逐帧 VMAF 输出文件格式：`json`、`xml` 或 `csv`。 |
| `-verbose` | 关闭 | 启用详细日志级别。 |
| `-progress` | 关闭 | VMAF 计算过程中显示 FFmpeg 进度。 |
| `-endsync` | 关闭 | 较短视频结束时停止。 |
| `-cambi_heatmap` | 关闭 | 计算并保存 CAMBI 条带检测热力图。 |
| `-sync_only` | 关闭 | 仅测量同步偏移 — 跳过 VMAF 计算。 |
| `-json` | 关闭 | 以 JSON 格式将最终结果输出到 stdout。兼容 `-sync_only` 和完整 VMAF 运行。批量模式下每行一个 JSON 对象（NDJSON）。 |
| `-gpu` | 关闭 | 使用 GPU 加速 VMAF（通过 `libvmaf_cuda`）。需要支持 CUDA 的 FFmpeg 构建版本（参见 [Docker: CUDA](#cuda-gpu-构建)）。 |

## 示例

### 基础 VMAF（不同步）

```bash
easyvmaf -d distorted.mp4 -r reference.mp4
```

### 自动同步

```bash
# 从参考视频开头搜索 2 秒同步窗口
easyvmaf -d distorted.mp4 -r reference.mp4 -sw 2

# 从参考视频第 6 秒开始搜索 3 秒同步窗口，反向匹配
easyvmaf -d distorted.mp4 -r reference.mp4 -sw 3 -ss 6 -reverse
```

### 仅测量同步

```bash
# 人类可读输出
easyvmaf -d distorted.mp4 -r reference.mp4 -sw 2 -sync_only

# 结构化 JSON 输出
easyvmaf -d distorted.mp4 -r reference.mp4 -sw 2 -sync_only -json
```

### 结构化 JSON 输出

`-json` 参数将单个 JSON 对象输出到 stdout（批量模式下每行一个对象）：

```bash
easyvmaf -d distorted.mp4 -r reference.mp4 -sw 2 -json
```

```json
{
  "distorted": "distorted.mp4",
  "reference": "reference.mp4",
  "sync": { "offset": 0.7007, "psnr": 48.863779 },
  "vmaf": {
    "model": "HD",
    "vmaf_hd": 89.123456,
    "vmaf_hd_neg": 88.654321,
    "vmaf_hd_phone": 91.234567,
    "output_file": "distorted_vmaf.json"
  }
}
```

### 批量处理

```bash
# Glob 模式 — 每个文件一个结果
easyvmaf -d "folder/*.mp4" -r reference.mp4 -json
```

### 4K 模型

```bash
easyvmaf -d distorted_4k.mp4 -r reference_4k.mp4 -model 4K
```

### GPU 加速 VMAF

需要 CUDA 版本的 FFmpeg/libvmaf（参见下方 Docker 章节）：

```bash
easyvmaf -d distorted.mp4 -r reference.mp4 -gpu
```

无论是否设置 `-gpu`，同步计算始终在 CPU 上运行。GPU 仅用于最终的 VMAF 评分步骤。

---

## Docker

### CPU 构建

```bash
docker build -t easyvmaf .
```

### CUDA / GPU 构建

```bash
docker build -f Dockerfile.cuda -t easyvmaf:cuda .
```

> **注意：** CUDA 镜像链接了 `--enable-nonfree` 组件（nvcc/CUDA）的 FFmpeg。受许可限制，不能重新分发 — 仅限本地构建和使用。

### 构建参数

两个 Dockerfile 都接受以下构建时参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FFMPEG_version` | `8.1` | FFmpeg 发布标签 |
| `VMAF_version` | `3.0.0` | libvmaf 发布标签 |
| `EASYVMAF_VERSION` | `2.1.0` | easyVmaf 版本标签 |
| `DAV1D_version` | `1.4.3` | dav1d 发布版本（仅 CUDA 镜像 — 从源码编译） |

```bash
# 自定义版本
docker build --build-arg FFMPEG_version=8.1 --build-arg VMAF_version=3.0.0 -t easyvmaf .
```

### Docker 运行

```bash
# CPU
docker run --rm -v /path/to/videos:/videos \
  easyvmaf -d /videos/distorted.mp4 -r /videos/reference.mp4

# 带同步
docker run --rm -v /path/to/videos:/videos \
  easyvmaf -d /videos/distorted.mp4 -r /videos/reference.mp4 -sw 2

# JSON 输出
docker run --rm -v /path/to/videos:/videos \
  easyvmaf -d /videos/distorted.mp4 -r /videos/reference.mp4 -json

# GPU（需要 NVIDIA Container Toolkit）
docker run --rm --gpus all -v /path/to/videos:/videos \
  easyvmaf:cuda -d /videos/distorted.mp4 -r /videos/reference.mp4 -gpu
```

### Docker Compose

项目包含预配置的 `docker-compose.yml`，提供 `easyvmaf`（CPU）和 `easyvmaf-cuda`（GPU）服务：

```bash
# CPU 服务
VIDEO_DIR=/path/to/videos docker compose run easyvmaf \
  -d /videos/distorted.mp4 -r /videos/reference.mp4

# GPU 服务
VIDEO_DIR=/path/to/videos docker compose run easyvmaf-cuda \
  -d /videos/distorted.mp4 -r /videos/reference.mp4 -gpu
```

`VIDEO_DIR` 未设置时默认为 `./video_samples`。

---

## 同步示例说明

### 参考视频相对失真视频有延迟

![](readme/easyVmaf1.svg)

`reference.ts` 比 `distorted-A.ts` 晚 0.7 秒开始。使用 `-sw` 自动搜索偏移量：

```bash
easyvmaf -d distorted-A.ts -r reference.ts -sw 2
```

同步窗口 `sw=2` 表示 easyVmaf 在 `reference.ts` 的前 2 秒内搜索与 `distorted-A.ts` 首帧 PSNR 最佳匹配的位置。

### 失真视频相对参考视频有延迟

![](readme/easyVmaf2.svg)

`distorted-B.ts` 比 `reference.ts` 晚 8.3 秒开始。使用 `-reverse` 反转同步方向：

```bash
easyvmaf -d distorted-B.ts -r reference.ts -sw 3 -ss 6 -reverse
```

`-ss 6` 从 `reference.ts` 的第 6 秒开始同步搜索；`-reverse` 让参考视频首帧去匹配失真视频流。
