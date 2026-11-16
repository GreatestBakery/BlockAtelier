"""导出 Litematica (.litematic)。位打包等细节复用开源库 litemapy，本文件只管版本字段。"""
import time
from litemapy import Region, BlockState


def litematic_format_version(data_version):
    # Litematica 自 1.20.5 (DataVersion 3837) 起写 Version 7；更早的 mod 只认到 6。
    # 两者的方块存储完全相同，差别在实体/方块实体的物品 NBT —— 本软件不写这些，所以只需标对版本号。
    return 7 if data_version >= 3837 else 6


def write_litematic(grid, reg, path, name="Unnamed", author="BlockAtelier", description=""):
    g = grid.normalized()
    w, h, l = (max(1, s) for s in g.size())
    region = Region(0, 0, 0, w, h, l)
    cache = {}
    for (x, y, z), s in g.cells.items():
        bs = cache.get(s)
        if bs is None:
            bid, props = reg.full_props(s)
            bs = cache[s] = BlockState("minecraft:" + bid, **props)
        region[x, y, z] = bs
    sch = region.as_schematic(name=name[:60] or "Unnamed", author=author, description=description[:200])
    sch.mc_version = reg.data_version
    sch.lm_version = litematic_format_version(reg.data_version)
    sch.lm_subversion = 1
    sch.save(str(path))
    return str(path)
