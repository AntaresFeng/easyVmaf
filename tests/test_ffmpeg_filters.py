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
