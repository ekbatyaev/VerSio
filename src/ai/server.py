import asyncio
import hashlib
import shlex
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from huggingface_hub import HfApi, hf_hub_download
from src.settings import settings, logger


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(16 << 20):
            h.update(chunk)
    return h.hexdigest()


def _remote_sha256() -> str:
    """Хеш файла из метаданных Hugging Face. Нужен, пока GGUF_SHA256 не закреплён."""
    info = HfApi(token=settings.hf_token).model_info(
        settings.gguf_repo, revision=settings.gguf_revision, files_metadata=True)
    for f in info.siblings:
        if f.rfilename == settings.gguf_file and f.lfs:
            logger.warning(f"Закрепи в .env: GGUF_REVISION={info.sha}  GGUF_SHA256={f.lfs.sha256}")
            return f.lfs.sha256
    raise RuntimeError(f"В {settings.gguf_repo} нет файла {settings.gguf_file}")


def ensure_model() -> Path:
    """Качает модель, только если её нет или хеш не совпал."""
    target = settings.models_path / settings.gguf_file
    marker = target.with_name(target.name + ".sha256")
    expected = settings.gguf_sha256.lower() or _remote_sha256()

    if target.exists() and marker.exists() and marker.read_text() == expected:
        logger.info(f"Модель уже скачана: {target.name}")
        return target

    logger.info(f"Скачиваю {settings.gguf_repo}/{settings.gguf_file}")
    hf_hub_download(settings.gguf_repo, settings.gguf_file, revision=settings.gguf_revision,
                    local_dir=settings.models_path, token=settings.hf_token)

    if (actual := _sha256(target)) != expected:
        target.unlink()
        raise RuntimeError(f"sha256 не совпал: ожидался {expected}, получен {actual}")
    marker.write_text(expected)
    return target


async def _wait_ready(proc: asyncio.subprocess.Process, timeout: int = 600) -> None:
    url = f"http://127.0.0.1:{settings.llm_port}/health"
    async with httpx.AsyncClient() as client:
        for _ in range(timeout // 2):
            if proc.returncode is not None:
                raise RuntimeError(f"llama-server завершился с кодом {proc.returncode}")
            try:
                if (await client.get(url)).status_code == 200:   # 503 — модель ещё грузится
                    logger.info("LLM-сервер готов")
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(2)
    raise TimeoutError("llama-server не поднялся")


@asynccontextmanager
async def llm_server():
    """Модель на месте → llama-server запущен → по выходу из блока остановлен."""
    model = await asyncio.to_thread(ensure_model)
    proc = await asyncio.create_subprocess_exec(
        settings.llm_server_bin, "-m", str(model),
        "--alias", settings.llm_model_name,
        "--host", "127.0.0.1", "--port", str(settings.llm_port),
        "--jinja",
        "-c", str(settings.llm_context),
        "--parallel", str(settings.llm_parallel),
        *shlex.split(settings.llm_extra_args),
    )
    try:
        await _wait_ready(proc)
        yield
    finally:
        proc.terminate()
        await proc.wait()