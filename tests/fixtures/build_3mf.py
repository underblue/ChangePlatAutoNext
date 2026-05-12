from __future__ import annotations

import zipfile
from pathlib import Path

FINISH_SOUND_MARKER = ";=====printer finish  sound========="


def write_synthetic_3mf(path: Path, *, colors: tuple[str, ...] = ("#00FF00", "#FF0000"), include_model_settings: bool = True) -> Path:
    root = path.parent / f"{path.stem}_root"
    metadata = root / "Metadata"
    rels = root / "_rels"
    metadata.mkdir(parents=True, exist_ok=True)
    rels.mkdir(parents=True, exist_ok=True)
    plate_nodes = []
    model_nodes = []
    for index, color in enumerate(colors, start=1):
        plate_nodes.append(
            f'''  <plate>
    <metadata key="index" value="{index}"/>
    <metadata key="prediction" value="{60 * index}"/>
    <metadata key="weight" value="{index}.0"/>
    <metadata key="filament_maps" value="1"/>
    <metadata key="limit_filament_maps" value="0"/>
    <filament id="1" tray_info_idx="T{index}" type="PLA" color="{color}" used_m="{index}" used_g="{index}" nozzle_diameter="0.40"/>
    <warning msg="example" level="1"/>
  </plate>'''
        )
        model_nodes.append(
            f'''  <plate>
    <metadata key="plater_id" value="{index}"/>
    <metadata key="gcode_file" value="Metadata/plate_{index}.gcode"/>
    <metadata key="thumbnail_file" value="Metadata/plate_{index}.png"/>
    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{index}.png"/>
  </plate>'''
        )
        gcode = f"G0 Y254 F3000\nM620 S0A\nT0\nM73 P1 R5\nG1 X{index}\n{FINISH_SOUND_MARKER}\nM1006 S1\n{FINISH_SOUND_MARKER}\nM18\n"
        (metadata / f"plate_{index}.gcode").write_text(gcode, encoding="utf-8")
        (metadata / f"plate_{index}.png").write_bytes(b"not-a-real-png")
        (metadata / f"plate_no_light_{index}.png").write_bytes(b"not-a-real-png")
    (metadata / "slice_info.config").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<config>\n" + "\n".join(plate_nodes) + "\n</config>\n",
        encoding="utf-8",
    )
    if include_model_settings:
        (metadata / "model_settings.config").write_text(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<config>\n" + "\n".join(model_nodes) + "\n</config>\n",
            encoding="utf-8",
        )
    (metadata / "filament_sequence.json").write_text("{}", encoding="utf-8")
    (rels / ".rels").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<Relationships><Relationship Target=\"/Metadata/plate_1.png\" Id=\"r1\" Type=\"thumb\"/></Relationships>",
        encoding="utf-8",
    )
    with zipfile.ZipFile(path, "w") as archive:
        for file in root.rglob("*"):
            if file.is_file():
                archive.write(file, file.relative_to(root).as_posix())
    return path


def write_unsliced_3mf(path: Path) -> Path:
    root = path.parent / f"{path.stem}_root"
    metadata = root / "Metadata"
    model = root / "3D"
    metadata.mkdir(parents=True, exist_ok=True)
    model.mkdir(parents=True, exist_ok=True)
    (metadata / "slice_info.config").write_text("<config><header /></config>", encoding="utf-8")
    (metadata / "plate_1.png").write_bytes(b"preview")
    (model / "3dmodel.model").write_text("<model />", encoding="utf-8")
    with zipfile.ZipFile(path, "w") as archive:
        for file in root.rglob("*"):
            if file.is_file():
                archive.write(file, file.relative_to(root).as_posix())
    return path
