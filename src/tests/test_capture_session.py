"""Test: CaptureSession lifecycle wiring without launching PresentMon."""

from src.core import capture_session as cs
from src.models import SessionConfig
from src.tests._factory import make_system_info


def run():
    calls: list[str] = []

    old_gather = cs._gather_system_info
    try:
        # ESCAPE HATCH make_system_info: inject a controlled SystemInfo to assert wiring.
        cs._gather_system_info = lambda: make_system_info(
            cpu_name="CPU", gpu_name="GPU",
            display_resolution="1920x1080", display_refresh_hz=60,
            display_outputs=["1920x1080@60Hz"],
        )
        session = cs.CaptureSession()
        assert session.data_store.get_system_info().display_outputs == ["1920x1080@60Hz"]

        session.wrapper.configure = lambda config: calls.append(f"wrapper:{config.process_names[0]}")
        session.sampler.configure = lambda config: calls.append(f"sampler:{config.process_names[0]}")
        session.sampler.start = lambda: calls.append("sampler_start")
        session.wrapper.start = lambda: calls.append("wrapper_start")
        session.sampler.stop = lambda: calls.append("sampler_stop")
        session.wrapper.stop = lambda: calls.append("wrapper_stop")
        session.sampler.isRunning = lambda: False
        session.wrapper.isRunning = lambda: False

        config = SessionConfig(process_names=["Game.exe"], timed_seconds=5)
        session.start(config)
        assert session.config is config, "config stored"
        assert session.data_store.get_system_info().cpu_name == "CPU"
        assert session.data_store.get_monitored_apps() == ["Game.exe"]
        assert calls == [
            "wrapper:Game.exe",
            "sampler:Game.exe",
            "sampler_start",
            "wrapper_start",
        ], f"unexpected start order: {calls}"

        session.stop()
        assert calls[-2:] == ["wrapper_stop", "sampler_stop"], "stop order"
    finally:
        cs._gather_system_info = old_gather
