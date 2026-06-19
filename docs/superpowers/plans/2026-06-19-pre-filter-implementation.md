# `--pre-filter` Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--pre-filter` CLI flag that inserts an arbitrary FFmpeg filter string (typically `drawbox`) into both main and ref filter chains after scaling, before deinterlace/fps.

**Architecture:** Three-layer change following existing patterns. `inputFFmpeg.setPreFilter()` at Layer 1 mirrors `setScaleFilter`/`setFpsFilter`. Layer 2 calls it from `getVmaf()` after `_autoScale()`. Layer 3 adds the CLI argument and passes it through.

**Tech Stack:** Python >=3.8, pytest (dev dependency, already declared in pyproject.toml)

---

### Task 1: Add `setPreFilter` method to `inputFFmpeg`

**Files:**
- Modify: `easyvmaf/ffmpeg.py` — `inputFFmpeg` class (after `setFpsFilter`, before `clearFilters`)

- [ ] **Step 1: Write the failing unit test**

```bash
mkdir tests
```

Create `tests/test_ffmpeg_filters.py`:

```python
"""Tests for inputFFmpeg filter chain construction."""
import pytest
from easyvmaf.ffmpeg import inputFFmpeg


class TestInputFFmpegPreFilter:
    """Tests for setPreFilter method."""

    def test_set_pre_filter_appends_to_filters_list(self):
        """setPreFilter should append filter with correct I/O labels."""
        inp = inputFFmpeg("test_video.mp4", input_id=0)

        inp.setPreFilter("drawbox=x=0:y=0:w=100:h=100:color=black:t=fill")

        assert len(inp.filtersList) == 1
        expected_filter = (
            "[0:v]drawbox=x=0:y=0:w=100:h=100:color=black:t=fill[input0_0]"
        )
        assert inp.filtersList[0] == expected_filter

    def test_set_pre_filter_updates_last_output_id(self):
        """setPreFilter should update lastOutputID after insertion."""
        inp = inputFFmpeg("test_video.mp4", input_id=0)

        assert inp.lastOutputID == "0:v"

        inp.setPreFilter("drawbox=x=0:y=0:w=100:h=100:color=black:t=fill")

        assert inp.lastOutputID == "input0_0"

    def test_set_pre_filter_chains_after_scale_filter(self):
        """setPreFilter should chain correctly after a prior filter."""
        inp = inputFFmpeg("test_video.mp4", input_id=0)

        inp.setScaleFilter(1920, 1080)
        inp.setPreFilter("drawbox=x=0:y=0:w=100:h=100:color=black:t=fill")

        assert len(inp.filtersList) == 2
        expected_pre = (
            "[input0_0]drawbox=x=0:y=0:w=100:h=100:color=black:t=fill[input0_1]"
        )
        assert inp.filtersList[1] == expected_pre
        assert inp.lastOutputID == "input0_1"

    def test_set_pre_filter_with_input_id_1(self):
        """setPreFilter should work for input_id=1 (ref stream)."""
        inp = inputFFmpeg("test_video.mp4", input_id=1)

        inp.setPreFilter("drawbox=x=0:y=0:w=100:h=100:color=black:t=fill")

        expected_filter = (
            "[1:v]drawbox=x=0:y=0:w=100:h=100:color=black:t=fill[input1_0]"
        )
        assert inp.filtersList[0] == expected_filter
        assert inp.lastOutputID == "input1_0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ffmpeg_filters.py -v`
Expected: FAIL with `AttributeError: 'inputFFmpeg' object has no attribute 'setPreFilter'`

- [ ] **Step 3: Implement `setPreFilter` in `easyvmaf/ffmpeg.py`**

Add after the `setFpsFilter` method (line 446) and before `clearFilters` (line 447):

```python
def setPreFilter(self, filter_string):
    """
    Insert an arbitrary FFmpeg filter after the current filter chain position.

    Args:
        filter_string: a complete FFmpeg filter descriptor, e.g.
            'drawbox=x=0:y=0:w=100:h=100:color=black:t=fill'

    The filter is appended to the chain with automatic I/O label wiring,
    following the same pattern as setScaleFilter and setFpsFilter.
    """
    inputID, outputID = self._newInOutForFilter()
    preFilter = f'[{inputID}]{filter_string}[{outputID}]'
    self._setFilter(preFilter)
    self._updateOutputId(outputID)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ffmpeg_filters.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add easyvmaf/ffmpeg.py tests/test_ffmpeg_filters.py
git commit -m "feat: add setPreFilter method to inputFFmpeg"
```

---

### Task 2: Add `pre_filter` support to `vmaf` class

**Files:**
- Modify: `easyvmaf/vmaf.py` — `vmaf.__init__()` and `getVmaf()`

- [ ] **Step 1: Write the unit test for `vmaf` pre_filter integration**

Add to `tests/test_ffmpeg_filters.py`:

```python
from unittest.mock import patch, MagicMock


class TestVmafPreFilter:
    """Tests for pre_filter integration in vmaf class."""

    @patch('easyvmaf.vmaf.video')
    @patch('easyvmaf.vmaf.FFmpegQos')
    def test_constructor_stores_pre_filter(self, mock_qos, mock_video):
        """vmaf constructor should store pre_filter when provided."""
        from easyvmaf.vmaf import vmaf

        mock_video_instance = MagicMock()
        mock_video_instance.streamInfo = {'width': 1920, 'height': 1080,
                                           'r_frame_rate': '30/1',
                                           'duration': 10, 'start_time': 0}
        mock_video.side_effect = [mock_video_instance, mock_video_instance]
        mock_video_instance.interlaced = False
        mock_video_instance.duration = 10

        v = vmaf("main.mp4", "ref.mp4", model="HD", output_fmt="json",
                 pre_filter="drawbox=x=0:y=0:w=100:h=100:color=black:t=fill")

        assert v.pre_filter == "drawbox=x=0:y=0:w=100:h=100:color=black:t=fill"

    @patch('easyvmaf.vmaf.video')
    @patch('easyvmaf.vmaf.FFmpegQos')
    def test_constructor_default_pre_filter_is_none(self, mock_qos, mock_video):
        """vmaf constructor should default pre_filter to None."""
        from easyvmaf.vmaf import vmaf

        mock_video_instance = MagicMock()
        mock_video_instance.streamInfo = {'width': 1920, 'height': 1080,
                                           'r_frame_rate': '30/1',
                                           'duration': 10, 'start_time': 0}
        mock_video.side_effect = [mock_video_instance, mock_video_instance]
        mock_video_instance.interlaced = False
        mock_video_instance.duration = 10

        v = vmaf("main.mp4", "ref.mp4", model="HD", output_fmt="json")

        assert v.pre_filter is None

    @patch('easyvmaf.vmaf.video')
    @patch('easyvmaf.vmaf.FFmpegQos')
    @patch('easyvmaf.vmaf.FFprobe')
    def test_get_vmaf_applies_pre_filter_to_both_streams(self, mock_ffprobe, mock_qos_class, mock_video):
        """getVmaf should call setPreFilter on both main and ref when pre_filter is set."""
        from easyvmaf.vmaf import vmaf

        # Setup mock video
        mock_video_instance = MagicMock()
        mock_video_instance.streamInfo = {'width': 1920, 'height': 1080,
                                           'r_frame_rate': '30/1',
                                           'duration': 10, 'start_time': 0}
        mock_video.side_effect = [mock_video_instance, mock_video_instance]
        mock_video_instance.interlaced = False
        mock_video_instance.duration = 10

        # Setup mock QoS
        mock_qos = MagicMock()
        mock_qos.vmafpath = "/tmp/test_vmaf.json"
        mock_qos.vmaf_cambi_heatmap_path = "/tmp/test_cambi_heatmap"
        mock_qos_class.return_value = mock_qos

        v = vmaf("main.mp4", "ref.mp4", model="HD", output_fmt="json",
                 pre_filter="drawbox=x=0:y=0:w=100:h=100:color=black:t=fill")

        v.getVmaf()

        mock_qos.main.setPreFilter.assert_called_once_with(
            "drawbox=x=0:y=0:w=100:h=100:color=black:t=fill"
        )
        mock_qos.ref.setPreFilter.assert_called_once_with(
            "drawbox=x=0:y=0:w=100:h=100:color=black:t=fill"
        )

    @patch('easyvmaf.vmaf.video')
    @patch('easyvmaf.vmaf.FFmpegQos')
    @patch('easyvmaf.vmaf.FFprobe')
    def test_get_vmaf_does_not_apply_pre_filter_when_none(self, mock_ffprobe, mock_qos_class, mock_video):
        """getVmaf should NOT call setPreFilter when pre_filter is None."""
        from easyvmaf.vmaf import vmaf

        mock_video_instance = MagicMock()
        mock_video_instance.streamInfo = {'width': 1920, 'height': 1080,
                                           'r_frame_rate': '30/1',
                                           'duration': 10, 'start_time': 0}
        mock_video.side_effect = [mock_video_instance, mock_video_instance]
        mock_video_instance.interlaced = False
        mock_video_instance.duration = 10

        mock_qos = MagicMock()
        mock_qos.vmafpath = "/tmp/test_vmaf.json"
        mock_qos.vmaf_cambi_heatmap_path = "/tmp/test_cambi_heatmap"
        mock_qos_class.return_value = mock_qos

        v = vmaf("main.mp4", "ref.mp4", model="HD", output_fmt="json")

        v.getVmaf()

        mock_qos.main.setPreFilter.assert_not_called()
        mock_qos.ref.setPreFilter.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ffmpeg_filters.py::TestVmafPreFilter -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'pre_filter'`

- [ ] **Step 3: Add `pre_filter` to `vmaf.__init__()`**

In `easyvmaf/vmaf.py`, modify the `vmaf.__init__` signature (line 179):

Change:
```python
def __init__(self, mainSrc, refSrc, output_fmt, model="HD", phone=False, loglevel="info", subsample=1, threads=0, print_progress=False, end_sync=False, manual_fps=0, cambi_heatmap=False, gpu_mode=False):
```

To:
```python
def __init__(self, mainSrc, refSrc, output_fmt, model="HD", phone=False, loglevel="info", subsample=1, threads=0, print_progress=False, end_sync=False, manual_fps=0, cambi_heatmap=False, gpu_mode=False, pre_filter=None):
```

Then add after `self._filters_applied = False` (line 199):
```python
self.pre_filter = pre_filter
```

- [ ] **Step 4: Apply pre_filter in `getVmaf()`**

In `easyvmaf/vmaf.py`, in the `getVmaf()` method, after the `_autoScale()` call (line 549) and before the `if self.manual_fps == 0:` block (line 551), insert:

```python
if self.pre_filter:
    self.ffmpegQos.main.setPreFilter(self.pre_filter)
    self.ffmpegQos.ref.setPreFilter(self.pre_filter)
```

The surrounding code after the change should read:

```python
self._autoScale()

if self.pre_filter:
    self.ffmpegQos.main.setPreFilter(self.pre_filter)
    self.ffmpegQos.ref.setPreFilter(self.pre_filter)

if self.manual_fps == 0:
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ffmpeg_filters.py -v`
Expected: 8 PASS (4 from Task 1 + 4 from Task 2)

- [ ] **Step 6: Commit**

```bash
git add easyvmaf/vmaf.py tests/test_ffmpeg_filters.py
git commit -m "feat: add pre_filter parameter to vmaf class"
```

---

### Task 3: Add `--pre-filter` CLI argument

**Files:**
- Modify: `easyvmaf/cli.py` — `get_args()` and `main()`

- [ ] **Step 1: Write the CLI parsing test**

Add to `tests/test_ffmpeg_filters.py`:

```python
class TestCliPreFilter:
    """Tests for --pre-filter CLI argument."""

    def test_pre_filter_argument_parses(self):
        """--pre-filter should be parsed as a string."""
        import sys
        from easyvmaf.cli import get_args

        test_args = [
            'easyvmaf',
            '-d', 'distorted.mp4',
            '-r', 'reference.mp4',
            '--pre-filter', 'drawbox=x=0:y=0:w=100:h=100:color=black:t=fill'
        ]
        sys.argv = test_args
        args = get_args()
        assert args.pre_filter == 'drawbox=x=0:y=0:w=100:h=100:color=black:t=fill'

    def test_pre_filter_defaults_to_none(self):
        """--pre-filter should default to None when not provided."""
        import sys
        from easyvmaf.cli import get_args

        test_args = ['easyvmaf', '-d', 'distorted.mp4', '-r', 'reference.mp4']
        sys.argv = test_args
        args = get_args()
        assert args.pre_filter is None

    def test_pre_filter_with_multiple_drawboxes(self):
        """--pre-filter should accept comma-separated drawbox chain."""
        import sys
        from easyvmaf.cli import get_args

        filter_str = (
            "drawbox=x=0:y=0:w=200:h=80:color=black:t=fill,"
            "drawbox=x=1500:y=1000:w=400:h=60:color=0xff4444@0.6:t=fill"
        )
        test_args = ['easyvmaf', '-d', 'd.mp4', '-r', 'r.mp4',
                     '--pre-filter', filter_str]
        sys.argv = test_args
        args = get_args()
        assert args.pre_filter == filter_str

    def test_pre_filter_with_enable_clause(self):
        """--pre-filter should accept drawbox with enable= time expression."""
        import sys
        from easyvmaf.cli import get_args

        filter_str = "drawbox=x=0:y=0:w=200:h=80:color=black@0.5:t=4:enable='between(t,0,10)'"
        test_args = ['easyvmaf', '-d', 'd.mp4', '-r', 'r.mp4',
                     '--pre-filter', filter_str]
        sys.argv = test_args
        args = get_args()
        assert args.pre_filter == filter_str
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ffmpeg_filters.py::TestCliPreFilter -v`
Expected: FAIL — `AttributeError: 'Namespace' object has no attribute 'pre_filter'`

- [ ] **Step 3: Add `--pre-filter` to argparse**

In `easyvmaf/cli.py`, add after the `--gpu` argument block (around line 146, before the `if len(sys.argv) == 1` line):

```python
parser.add_argument(
    '--pre-filter', dest='pre_filter', type=str, default=None,
    help='FFmpeg filter string applied to both distorted and reference '
         'videos after scaling, before deinterlace/fps. '
         'Use drawbox to cover logos, subtitles, or watermarks. '
         'Example: --pre-filter "drawbox=x=0:y=0:w=200:h=80:color=black:t=fill"'
)
```

- [ ] **Step 4: Pass `pre_filter` to `vmaf()` constructor**

In `easyvmaf/cli.py`, in the `main()` function, find the `vmaf(...)` call (around line 266). Add `pre_filter=cmdParser.pre_filter` to the keyword arguments.

The call changes from:
```python
myVmaf = vmaf(main, reference, loglevel=loglevel, subsample=n_subsample, model=model,
              output_fmt=output_fmt, threads=threads, print_progress=print_progress, end_sync=end_sync, manual_fps=fps, cambi_heatmap=cambi_heatmap, gpu_mode=gpu_mode)
```

To:
```python
myVmaf = vmaf(main, reference, loglevel=loglevel, subsample=n_subsample, model=model,
              output_fmt=output_fmt, threads=threads, print_progress=print_progress, end_sync=end_sync, manual_fps=fps, cambi_heatmap=cambi_heatmap, gpu_mode=gpu_mode, pre_filter=cmdParser.pre_filter)
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `pytest tests/test_ffmpeg_filters.py -v`
Expected: 12 PASS (4 + 4 + 4)

- [ ] **Step 6: Commit**

```bash
git add easyvmaf/cli.py tests/test_ffmpeg_filters.py
git commit -m "feat: add --pre-filter CLI argument for drawbox region masking"
```

---

### Task 4: Integration verification

- [ ] **Step 1: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: 12 PASS

- [ ] **Step 2: Smoke test with real FFmpeg (manual)**

```bash
easyvmaf -d distorted.mp4 -r reference.mp4 --pre-filter "drawbox=x=0:y=0:w=100:h=100:color=black:t=fill" -verbose 2>&1 | grep drawbox
```

Expected: FFmpeg debug log shows `drawbox` in both main and ref filter chains.

- [ ] **Step 3: Regression test without --pre-filter**

```bash
easyvmaf -d distorted.mp4 -r reference.mp4 --sync_only -sw 1
```

Expected: same output as before the change (sync offset and PSNR unchanged).

- [ ] **Step 4: Final commit**

No code changes — verification only.

---

## Summary

| Task | Files Modified | Lines Changed |
|------|---------------|---------------|
| 1 | `easyvmaf/ffmpeg.py` | +7 (new method) |
| 2 | `easyvmaf/vmaf.py` | +5 (param + apply) |
| 3 | `easyvmaf/cli.py` | +7 (arg + pass-through) |
| All | `tests/test_ffmpeg_filters.py` | ~150 (new file, 12 tests) |
