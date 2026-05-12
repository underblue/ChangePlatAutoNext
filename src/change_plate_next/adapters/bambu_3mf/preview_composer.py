"""Preview composition for exported 3MF packages."""

from __future__ import annotations

import shutil
from pathlib import Path

from change_plate_next.domain.models import QueueEntry


def copy_or_compose_preview(queue: list[QueueEntry], target_preview: Path, target_small: Path) -> tuple[str, ...]:
    warnings: list[str] = []
    previews = [item.plate.assets.preview for item in queue if item.copies > 0 and item.plate.assets.preview and item.plate.assets.preview.exists()]
    if not previews:
        warnings.append("未找到 plate 预览图")
        return tuple(warnings)
    target_preview.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        shutil.copy2(previews[0], target_preview)
        shutil.copy2(previews[0], target_small)
        warnings.append("未安装 Pillow，已复制第一个预览图作为预览")
        return tuple(warnings)

    count = len(previews)
    cols = max(1, int(count**0.5 + 0.999))
    rows = max(1, (count + cols - 1) // cols)
    cell_w = max(1, 512 // cols)
    cell_h = max(1, 512 // rows)
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("Arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    entries = [item for item in queue if item.copies > 0 and item.plate.assets.preview and item.plate.assets.preview.exists()]
    try:
        for idx, item in enumerate(entries):
            image = Image.open(item.plate.assets.preview).convert("RGBA")
            image.thumbnail((cell_w, cell_h))
            x = (idx % cols) * cell_w
            y = (idx // cols) * cell_h
            canvas.alpha_composite(image, (x, y))
            draw.text((x + 4, y + cell_h - 34), f"x{item.copies}", fill=(18, 110, 130, 255), font=font)
    except Exception:
        shutil.copy2(previews[0], target_preview)
        shutil.copy2(previews[0], target_small)
        warnings.append("预览图无法识别，已复制第一个预览图作为保底")
        return tuple(warnings)
    canvas.save(target_preview)
    small = canvas.copy()
    small.thumbnail((128, 128))
    small.save(target_small)
    return tuple(warnings)
