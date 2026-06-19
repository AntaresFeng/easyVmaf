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
