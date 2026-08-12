"""ASR backend selection + faster-whisper JSON mapping (no model download)."""

from types import SimpleNamespace

from asr_backend import (
    FASTER_DEFAULT_MODEL,
    MLX_DEFAULT_MODEL,
    faster_whisper_result_to_dict,
    resolve_asr_name,
    resolve_model_name,
)
from transcribe import collect_words


def test_resolve_asr_auto_by_platform():
    assert resolve_asr_name("auto", platform="darwin", mlx_importable=True) == "mlx"
    assert resolve_asr_name("auto", platform="darwin", mlx_importable=False) == "faster"
    assert resolve_asr_name("auto", platform="win32", mlx_importable=True) == "faster"
    assert resolve_asr_name("auto", platform="linux", mlx_importable=True) == "faster"


def test_resolve_asr_explicit():
    assert resolve_asr_name("mlx", platform="win32") == "mlx"
    assert resolve_asr_name("faster", platform="darwin") == "faster"


def test_resolve_model_mlx_default_to_faster():
    assert resolve_model_name("faster", MLX_DEFAULT_MODEL) == FASTER_DEFAULT_MODEL
    assert resolve_model_name("faster", "mlx-community/whisper-small") == "small"
    assert resolve_model_name("faster", "large-v3") == "large-v3"


def test_resolve_model_faster_name_to_mlx():
    assert resolve_model_name("mlx", "large-v3-turbo") == MLX_DEFAULT_MODEL
    assert resolve_model_name("mlx", MLX_DEFAULT_MODEL) == MLX_DEFAULT_MODEL
    assert resolve_model_name("mlx", None) == MLX_DEFAULT_MODEL
    assert resolve_model_name("faster", None) == FASTER_DEFAULT_MODEL


def test_faster_whisper_result_maps_to_collect_words():
    segs = [
        SimpleNamespace(
            start=0.0,
            end=1.2,
            text=" Hello world.",
            words=[
                SimpleNamespace(word=" Hello", start=0.0, end=0.4, probability=0.91),
                SimpleNamespace(word=" world.", start=0.4, end=1.2, probability=0.88),
            ],
        )
    ]
    result = faster_whisper_result_to_dict(segs, "en")
    assert result["language"] == "en"
    assert "Hello" in result["text"]
    words = collect_words(result["segments"])
    assert [w["word"] for w in words] == ["Hello", "world."]
    assert words[0]["start"] == 0.0
    assert words[1]["end"] == 1.2
    assert words[0]["probability"] == 0.91
