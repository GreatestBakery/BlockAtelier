"""Sponge schematic v2/v3 serialization with block properties and palettes."""
import time
import numpy as np
import nbtlib
from nbtlib import tag
from ..blocks import format_state


def _varints(arr):
    out = bytearray()
    for v in arr.tolist():
        while v >= 0x80:
            out.append((v & 0x7F) | 0x80); v >>= 7
        out.append(v)
    return out


def write_schem(grid, reg, path, name="Unnamed", author="BlockAtelier", version=3):
    g = grid.normalized()
    pal, arr, _ = g.to_dense()                     # arr[x,y,z]
    W, H, L = arr.shape
    full = ["minecraft:air"] + [format_state(*reg.full_props(s)) for s in pal[1:]]
    data = np.transpose(arr, (1, 2, 0)).reshape(-1)   # 索引 = x + z*W + y*W*L
    raw = _varints(data)
    block_data = tag.ByteArray(np.frombuffer(bytes(raw), dtype=np.int8))
    palette = tag.Compound({s: tag.Int(i) for i, s in enumerate(full)})
    meta = tag.Compound({"Name": tag.String(name), "Author": tag.String(author),
                         "Date": tag.Long(int(time.time() * 1000)), "RequiredMods": tag.List[tag.String]([])})
    common = {"DataVersion": tag.Int(reg.data_version), "Width": tag.Short(W), "Height": tag.Short(H),
              "Length": tag.Short(L), "Offset": tag.IntArray([0, 0, 0]), "Metadata": meta}
    if version == 3:
        body = tag.Compound({"Version": tag.Int(3), **common,
                             "Blocks": tag.Compound({"Palette": palette, "Data": block_data,
                                                     "BlockEntities": tag.List[tag.Compound]([])})})
        f = nbtlib.File({"Schematic": body}, gzipped=True, root_name="")
    elif version == 2:
        body = {"Version": tag.Int(2), **common, "PaletteMax": tag.Int(len(full)), "Palette": palette,
                "BlockData": block_data, "BlockEntities": tag.List[tag.Compound]([])}
        f = nbtlib.File(body, gzipped=True, root_name="Schematic")
    else:
        raise ValueError("schem version 只能是 2 或 3")
    f.save(str(path))
    return str(path)
