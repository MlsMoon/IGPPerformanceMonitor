"""Test: metrics sampler PID tracking + wrapper handoff (real processes).

No fakes: driven by the test's own real process (``os.getpid()`` + its real
name), exercising the real ``psutil.Process`` / ``find_pids_by_name`` /
``track_pid`` / ``_refresh_dynamic_pids`` paths and the wrapper→sampler PID
handoff in ``PresentMonWrapper._handle_frame``.
"""

import os

import psutil

from src.core import metrics_sampler as ms
from src.core.data_store import DataStore
from src.core.presentmon import PresentMonWrapper
from src.models import SessionConfig
from src.tests._factory import make_frame


def run():
    my_pid = os.getpid()
    my_name = psutil.Process(my_pid).name()  # the real running test process

    # 1) Explicit PID tracking (real process handle).
    s1 = ms.SystemMetricsSampler(DataStore())
    s1.configure(SessionConfig(process_ids=[my_pid]))
    assert my_pid in s1._proc_handles, "explicit real PID tracked"

    # 2) Name-based discovery via REAL process enumeration.
    assert my_pid in ms.mc.find_pids_by_name(my_name), \
        "find_pids_by_name sees this process"
    s2 = ms.SystemMetricsSampler(DataStore())
    s2.configure(SessionConfig(process_names=[my_name]))
    assert my_pid in s2._proc_handles, "PID discovered by real process name"

    # 3) Dynamic refresh re-discovers without dropping tracked PIDs.
    s2._refresh_dynamic_pids()
    assert my_pid in s2._proc_handles, "PID still tracked after dynamic refresh"

    # 4) Wrapper hands a frame's PID to the real sampler.
    store = DataStore()
    store.start_session()
    sampler = ms.SystemMetricsSampler(store)
    wrapper = PresentMonWrapper(store)
    wrapper.set_metrics_sampler(sampler)
    wrapper.configure(SessionConfig(process_names=["TestApp.exe"]))
    frame = make_frame(application="TestApp.exe", process_id=my_pid, fps=60.0)
    assert wrapper._handle_frame(frame), "frame accepted (name matches config)"
    assert my_pid in sampler._proc_handles, "wrapper registered the frame's real PID"
    assert store.get_frame_count() == 1, "frame stored"

    # 5) Real-0 preservation — regression guard for the App VRAM empty-chart bug.
    #    The bug was `app_vram = app_vram if app_vram else None`: truthiness nulled
    #    a genuine 0.0 (a process NVML/perf-counter reports with zero committed).
    #    Synthetic-data tests never hit it (they feed non-zero values). Stub the
    #    metric sources to return a real 0.0 and confirm the sampler keeps 0.0
    #    (NOT None) through _latest_per_process — the value the chart/CSV read.
    s3 = ms.SystemMetricsSampler(store)
    s3.configure(SessionConfig(process_ids=[my_pid]))
    orig_vram, orig_gpu = ms.mc.sample_all_process_vram_mb, ms.mc.sample_process_gpu
    ms.mc.sample_all_process_vram_mb = lambda: {my_pid: 0.0}
    ms.mc.sample_process_gpu = lambda pid: {"app_gpu_percent": 0.0}
    try:
        s3._sample_once()
    finally:
        ms.mc.sample_all_process_vram_mb = orig_vram
        ms.mc.sample_process_gpu = orig_gpu
    pp = s3.latest_per_process(my_pid)
    assert pp.get("app_vram_mb") == 0.0, (
        f"real 0.0 VRAM must be preserved, not truthiness-nulled; got {pp.get('app_vram_mb')!r}")
    assert pp.get("app_gpu_percent") == 0.0, (
        f"real 0.0 GPU% must be preserved; got {pp.get('app_gpu_percent')!r}")
