import subprocess


# 1. 判断 WSL / Windows
def env_type():
    try:
        with open("/proc/version", "r") as f:
            if "microsoft" in f.read().lower():
                return "WSL"
    except Exception:
        pass
    return "Windows"


# 2. CUDA / Driver（nvidia-smi）
def nvidia_info():
    try:
        out = subprocess.check_output(["nvidia-smi"], text=True)

        def pick(key):
            for line in out.splitlines():
                if key in line:
                    return line.split(":")[-1].strip()
            return None

        return {
            "driver_version": pick("Driver Version"),
            "cuda_version": pick("CUDA Version"),
        }
    except Exception:
        return None


# 3. cuDNN + CUDA 是否可用（最准确：torch）
def cudnn_info():
    try:
        import torch

        return {
            "torch_cuda_available": torch.cuda.is_available(),
            "cuda_device_name": torch.cuda.get_device_name(0)
            if torch.cuda.is_available()
            else None,
            "cudnn_enabled": torch.backends.cudnn.enabled,
            "cudnn_version": torch.backends.cudnn.version(),
            "torch_cuda_version": torch.version.cuda,
        }
    except Exception:
        return None


print("ENV:", env_type())
print("NVIDIA:", nvidia_info())
print("cuDNN:", cudnn_info())
