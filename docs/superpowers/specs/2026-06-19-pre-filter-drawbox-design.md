# Design Spec: `--pre-filter` for Region Masking

**Date**: 2026-06-19
**Status**: approved

## Purpose

Allow users to pass an arbitrary FFmpeg filter string (typically `drawbox`) that is
applied to **both** the distorted and reference video streams before VMAF
computation.  The primary use-case is masking logos, subtitles, watermarks, or
other fixed-overlay regions that would unfairly penalise the VMAF score.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Target streams | Both main and ref | Keep compared content identical; prevents asymmetric mask from skewing comparison |
| Parameter form | Raw FFmpeg `drawbox` filter text | Full power of drawbox: multiple regions, time ranges (`enable=`), alpha transparency |
| Position in filter chain | After scale, before deinterlace/fps | User specifies coordinates in model-resolution space (HD: 1920×1080, 4K: 3840×2160) |
| Sync phase | Not applied | PSNR-based offset search runs on independent `FFmpegQos` instances without pre-filter |
| CLI flag | `--pre-filter` | Generic name allows future extension to other pre-processing filters (`delogo`, `crop`, etc.) |

## Filter Chain Position

```
原始帧 → scale(模型分辨率) → [--pre-filter] → deinterlace/fps → trim(同步) → VMAF
                                  ↑
                          drawbox 插在这里
```

Example full chain (HD model, GPU mode, `--pre-filter "drawbox=x=0:y=0:w=200:h=80:color=black:t=fill"`):

```
main: [0:v]scale=1920:1080:flags=bicubic[input0_0]
      [input0_0]drawbox=x=0:y=0:w=200:h=80:color=black:t=fill[input0_1]
      [input0_1]fps=fps=30[input0_2]
      [input0_2]trim=start=0:duration=10,setpts=PTS-STARTPTS[input0_3]
      [input0_3]format=yuv420p[...] → setparams=... → hwupload_cuda[input0_4]

ref:  [1:v]scale=1920:1080:flags=bicubic[input1_0]
      [input1_0]drawbox=x=0:y=0:w=200:h=80:color=black:t=fill[input1_1]
      [input1_1]fps=fps=30[input1_2]
      ...
```

## Implementation

### Layer 1 — `easyvmaf/ffmpeg.py`

New method on `inputFFmpeg`:

```python
def setPreFilter(self, filter_string):
    """Insert an arbitrary filter after the current chain position."""
    inputID, outputID = self._newInOutForFilter()
    preFilter = f'[{inputID}]{filter_string}[{outputID}]'
    self._setFilter(preFilter)
    self._updateOutputId(outputID)
```

Follows the established pattern of `setScaleFilter`, `setFpsFilter`, etc.

### Layer 2 — `easyvmaf/vmaf.py`

**Constructor**: new keyword argument `pre_filter: Optional[str] = None`,
stored as `self.pre_filter`.

**`getVmaf()`**: after `_autoScale()` and before `_autoDeinterlace()` / `_forceFps()`:

```python
if self.pre_filter:
    self.ffmpegQos.main.setPreFilter(self.pre_filter)
    self.ffmpegQos.ref.setPreFilter(self.pre_filter)
```

**`_computePsnrAtOffset()`**: unchanged — sync phase is not affected.

### Layer 3 — `easyvmaf/cli.py`

New argument:

```python
parser.add_argument(
    '--pre-filter', dest='pre_filter', type=str, default=None,
    help='FFmpeg filter string applied to both videos after scaling. '
         'Use drawbox to cover logos, subtitles, watermarks. '
         'Example: --pre-filter "drawbox=x=0:y=0:w=200:h=80:color=black:t=fill"'
)
```

Pass to `vmaf()` constructor: `pre_filter=cmdParser.pre_filter`.

## Verification

1. Unit: `setPreFilter()` appends correct filter to `filtersList` and updates `lastOutputID`
2. Integration: run with `--pre-filter "drawbox=x=0:y=0:w=100:h=100:color=black:t=fill"`,
   inspect FFmpeg debug log to confirm drawbox appears in both main and ref chains
3. Regression: run without `--pre-filter` — output unchanged
4. Edge cases:
   - Multiple drawbox filters separated by commas
   - Time-limited drawbox with `enable='between(t,0,10)'`
   - Alpha transparency: `color=0xff4444@0.6`
   - GPU mode: `hwupload_cuda` still inserted after all CPU filters
   - `--sync-only` mode: pre-filter is irrelevant (no VMAF run), flag is silently ignored
