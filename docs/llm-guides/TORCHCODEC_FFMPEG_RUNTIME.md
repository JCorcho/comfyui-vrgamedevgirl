# TorchCodec and FFmpeg Runtime Repair

This guide records the Windows embedded-Python repair used for the media error that displayed a missing `torch_from_blob` entry point from `libtorchcodec_core4.dll`.

## Cause

The error is a native-binary compatibility failure, not an image/video tensor shape error. The affected runtime used PyTorch `2.10.0+cu130` with TorchCodec `0.14.0`. TorchCodec `0.14` targets PyTorch `>=2.11`, while TorchCodec `0.10` is the compatible release for PyTorch `2.10`.

TorchCodec also requires FFmpeg **shared** libraries on Windows. A static `ffmpeg.exe` alone is insufficient.

## Repair used on this installation

1. Preserve a copy of the existing `torchcodec` package and its `.dist-info` directory under the Easy-Install runtime backup directory.
2. Install the CPython 3.12 Windows wheel `torchcodec==0.10.0` into the embedded Python with `--no-deps`. Do not upgrade or downgrade PyTorch, CUDA, torchvision, or ComfyUI to solve this mismatch.
3. Make FFmpeg 8 shared DLLs discoverable by the embedded `python.exe`. This installation uses the already-installed PyAV FFmpeg shared bundle, with generic aliases such as `avcodec-62.dll`, `avformat-62.dll`, `avutil-60.dll`, `swresample-6.dll`, and `swscale-9.dll` next to the embedded Python executable. Keep the original dependency DLLs beside those aliases.
4. Verify in a fresh embedded-Python process:

```powershell
python_embeded\python.exe -c "import torch; import torchcodec; print(torch.__version__, torchcodec.__version__)"
```

Expected pairing: `2.10.0+cu130` and `0.10.0`.

5. Restart ComfyUI after replacing native DLLs, then perform the normal user-approved video-generation test.

## Guardrails

- Do not use `pip install -U torchcodec`; it can reintroduce a package targeting a newer PyTorch ABI.
- Do not resolve this by changing the project workflow or silently moving tensors to CPU. The exception happens during the TorchCodec native import, before a workflow tensor reaches FFmpeg.
- Run `python -m pip check` only as an inventory signal in this broad Easy-Install environment; unrelated third-party optional-node dependency conflicts may already exist. Confirm the TorchCodec import directly.
