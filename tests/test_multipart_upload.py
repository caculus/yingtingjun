"""multipart/form-data parsing without cgi (Python 3.13+)."""

import pytest

from serve_player import extract_multipart_file


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
