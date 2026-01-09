import os
import subprocess


def set_nvidia_persistence_mode(enabled: bool) -> None:
    """
    Enable or disable NVIDIA persistence mode.

    Persistence mode keeps the NVIDIA driver loaded even when no applications
    are using the GPU, reducing initialization latency for subsequent GPU access.
    """
    if not os.path.exists('/usr/bin/nvidia-smi'):
        return

    subprocess.run(
        ['nvidia-smi', '-pm', '1' if enabled else '0'],
        capture_output=True,
    )
