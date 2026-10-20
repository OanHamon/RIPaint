"""Écriture de sous-titres .srt à partir d'entrées (image_début, image_fin, texte)."""

from pathlib import Path


def _ts(frame: int, fps: int) -> str:
    ms = round(frame * 1000 / fps)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(entries, fps: int = 60, total_frames: int | None = None) -> str:
    out = []
    items = []
    for start, end, text in sorted(entries, key=lambda e: (e[0], e[1])):
        if total_frames is not None:
            end = min(end, total_frames)
        if end > start:
            items.append((start, end, text))
    for i, (start, end, text) in enumerate(items, 1):
        out.append(f"{i}\n{_ts(start, fps)} --> {_ts(end, fps)}\n{text}\n")
    return "\n".join(out)


def write_srt(path: Path, entries, fps: int = 60, total_frames: int | None = None) -> None:
    Path(path).write_text(to_srt(entries, fps, total_frames), encoding="utf-8")
