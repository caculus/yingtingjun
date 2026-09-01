"""multipart/form-data parsing without cgi (Python 3.13+)."""

import pytest

from serve_player import extract_multipart_file, extract_multipart_import
from stem_utils import StemError, sanitize_stem


def _multipart(field: str, filename: str, data: bytes, *, boundary: str = "----ytj") -> tuple[bytes, str]:
    disposition = (
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"'
    ).encode("ascii")
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("ascii"),
            disposition + b"\r\n",
            b"Content-Type: application/octet-stream\r\n\r\n",
            data,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    ctype = f"multipart/form-data; boundary={boundary}"
    return body, ctype


def _multipart_with_stem(
    filename: str,
    data: bytes,
    stem: str,
    *,
    boundary: str = "----ytj",
) -> tuple[bytes, str]:
    file_part = (
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("ascii")
    stem_part = (
        f'Content-Disposition: form-data; name="stem"\r\n\r\n{stem}\r\n'
    ).encode("utf-8")
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("ascii"),
            file_part,
            data,
            b"\r\n",
            f"--{boundary}\r\n".encode("ascii"),
            stem_part,
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def test_extract_multipart_file_ok():
    body, ctype = _multipart("file", "meeting.m4a", b"AUDIO")
    name, payload = extract_multipart_file(body, ctype)
    assert name == "meeting.m4a"
    assert payload == b"AUDIO"


def test_extract_multipart_file_strips_path():
    body, ctype = _multipart("file", "nested/dir/clip.wav", b"WAV")
    name, payload = extract_multipart_file(body, ctype)
    assert name == "clip.wav"
    assert payload == b"WAV"


def test_extract_multipart_file_missing_field():
    body, ctype = _multipart("other", "a.bin", b"x")
    with pytest.raises(ValueError, match="缺少 file"):
        extract_multipart_file(body, ctype)


def test_extract_multipart_file_rejects_non_multipart():
    with pytest.raises(ValueError, match="multipart"):
        extract_multipart_file(b"x", "application/json")


def test_extract_multipart_import_with_stem():
    body, ctype = _multipart_with_stem("20250826.m4a", b"AUDIO", "超市結帳")
    name, payload, stem = extract_multipart_import(body, ctype)
    assert name == "20250826.m4a"
    assert payload == b"AUDIO"
    assert stem == "超市結帳"


def test_extract_multipart_import_without_stem():
    body, ctype = _multipart("file", "meeting.m4a", b"AUDIO")
    name, payload, stem = extract_multipart_import(body, ctype)
    assert name == "meeting.m4a"
    assert payload == b"AUDIO"
    assert stem is None


def test_sanitize_stem_for_import():
    assert sanitize_stem("面試練習") == "面試練習"
    with pytest.raises(StemError):
        sanitize_stem("///")
