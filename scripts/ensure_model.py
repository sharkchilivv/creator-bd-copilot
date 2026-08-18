"""启动时确保 Embedding 模型已就位：缺失则从 HuggingFace 下载到 MODEL_DIR。

云端部署时 MODEL_DIR 通常位于持久卷（如 /data/models），
首次启动会下载一次，之后卷内已存在则跳过，不重复下载。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config  # noqa: E402


def _has_model() -> bool:
    if not config.MODEL_DIR or not os.path.isdir(config.MODEL_DIR):
        return False
    # 至少有一个权重文件即可认为就绪
    for name in ("model.safetensors", "pytorch_model.bin", "onnx/model.onnx"):
        if os.path.exists(os.path.join(config.MODEL_DIR, name)):
            return True
    # 兼容 modelscope 嵌套快照结构
    return bool(
        __import__("glob").glob(os.path.join(config.MODEL_DIR, "**", "model.safetensors"), recursive=True)
    )


def main():
    if _has_model():
        print(f"[ensure_model] 模型已存在，跳过下载：{config.MODEL_DIR}")
        return

    os.makedirs(config.MODEL_DIR, exist_ok=True)
    print(f"[ensure_model] 未检测到模型，开始下载 {config.EMBEDDING_MODEL_ID} -> {config.MODEL_DIR}")

    # 优先 HuggingFace（只取必要文件，约 470MB，避免 onnx/openvino/重复权重）
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            config.EMBEDDING_MODEL_ID,
            local_dir=config.MODEL_DIR,
            local_dir_use_symlinks=False,
            allow_patterns=[
                "*.safetensors",
                "*.json",
                "*.txt",
                "*.model",
                "tokenizer*",
                "modules.json",
                "special_tokens_map.json",
                "sentencepiece*",
            ],
        )
        print("[ensure_model] 已从 HuggingFace 下载完成")
        return
    except Exception as e:  # noqa: BLE001
        print(f"[ensure_model] HuggingFace 下载失败，尝试 ModelScope：{e}")

    # 兜底：ModelScope（云端镜像未预装，本地可用）
    try:
        from modelscope import snapshot_download as ms_download

        ms_download(config.EMBEDDING_MODEL_ID, cache_dir=config.MODEL_DIR)
        print("[ensure_model] 已从 ModelScope 下载完成")
    except Exception as e:  # noqa: BLE001
        print(f"[ensure_model] 下载失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
