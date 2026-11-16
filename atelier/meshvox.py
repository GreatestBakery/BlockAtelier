"""3D 模型 (.obj/.glb/.gltf/.stl/.ply/.fbx* ) -> 体素 -> 方块。
流程借鉴 ObjToSchematic / BlockBlender: 表面体素化 -> 采样颜色 -> 在 CIELAB 空间找最接近的方块。
(*fbx 等格式取决于 trimesh 能否读取；读不了时先在 Blender 里转成 glb。)
"""
import numpy as np
from scipy.spatial import cKDTree
from scipy import ndimage
from .voxel import VoxelGrid


def _rgb2lab(rgb):
    c = np.asarray(rgb, np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


class BlockMatcher:
    def __init__(self, reg, group="all"):
        pal = reg.building_palette(group)
        if not pal: raise ValueError(f"调色板 {group} 为空")
        self.ids = [b for b, _ in pal]
        self.tree = cKDTree(_rgb2lab(np.array([c for _, c in pal])))

    def match(self, rgb):
        _, i = self.tree.query(_rgb2lab(rgb))
        return np.asarray(i)


def load_mesh(path, up="auto"):
    """读入并合并为单个网格，统一为 y 轴朝上，返回 (vertices, faces, face_colors Nx3 uint8)。"""
    import trimesh
    scene = trimesh.load(str(path), process=False)
    geoms = scene.dump() if isinstance(scene, trimesh.Scene) else [scene]
    V, F, C, off = [], [], [], 0
    for g in geoms:
        if not isinstance(g, trimesh.Trimesh) or len(g.faces) == 0: continue
        try:
            vis = g.visual.to_color() if g.visual.kind == "texture" else g.visual
            fc = np.asarray(vis.face_colors)[:, :3]
            if len(fc) != len(g.faces): raise ValueError
        except Exception:
            fc = np.full((len(g.faces), 3), 180, np.uint8)
        V.append(np.asarray(g.vertices, np.float64)); F.append(np.asarray(g.faces) + off); C.append(fc)
        off += len(g.vertices)
    if not V: raise ValueError("模型里没有三角网格")
    V, F, C = np.concatenate(V), np.concatenate(F), np.concatenate(C)
    ext = str(path).lower().rsplit(".", 1)[-1]
    if up == "z" or (up == "auto" and ext in ("stl", "ply", "3mf")):     # 这些格式惯例是 z 朝上
        V = np.stack([V[:, 0], V[:, 2], -V[:, 1]], 1)
    return V, F, C


def voxelize(path, reg, max_size=48, palette="all", solid=False, up="auto", samples=400_000):
    """-> (VoxelGrid, info)。max_size = 最长边的方块数。"""
    V, F, C = load_mesh(path, up)
    lo, hi = V.min(0), V.max(0)
    extent = max((hi - lo).max(), 1e-9)
    scale = (max_size - 1e-6) / extent
    V = (V - lo) * scale
    dims = np.maximum(np.ceil((hi - lo) * scale).astype(int), 1)
    # 表面采样: 按面积均匀撒点，每个点落入一个体素；颜色取落入点的平均
    tri = V[F]
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    n = int(min(max(samples, area.sum() * 12), 3_000_000))
    rng = np.random.default_rng(0)
    fi = rng.choice(len(F), n, p=area / area.sum())
    r1, r2 = np.sqrt(rng.random(n)), rng.random(n)
    pts = (1 - r1)[:, None] * tri[fi, 0] + (r1 * (1 - r2))[:, None] * tri[fi, 1] + (r1 * r2)[:, None] * tri[fi, 2]
    pts = np.concatenate([pts, V, tri.mean(1)])                       # 顶点和面心也算，保证小三角不漏
    cols = np.concatenate([C[fi], np.full((len(V), 3), -1), C]).astype(np.float64)
    cell = np.clip(np.floor(pts).astype(int), 0, dims - 1)
    key = (cell[:, 0] * dims[1] + cell[:, 1]) * dims[2] + cell[:, 2]
    occ = np.zeros(dims, bool); occ.reshape(-1)[np.unique(key)] = True
    valid = cols[:, 0] >= 0
    # 每个体素取“出现最多的颜色”而不是平均色: 平均会在两种材质交界处造出不存在的混色
    ck = (cols[valid] // 8).astype(np.int64)
    pair = key[valid].astype(np.int64) * 32768 + (ck[:, 0] * 1024 + ck[:, 1] * 32 + ck[:, 2])
    up_, cnt_ = np.unique(pair, return_counts=True)
    vox_ = up_ // 32768
    order = np.lexsort((cnt_, vox_))
    last = np.r_[vox_[order][1:] != vox_[order][:-1], True]
    surf_idx = vox_[order][last]
    cc = up_[order][last] % 32768
    surf_rgb = np.stack([cc // 1024, cc // 32 % 32, cc % 32], 1) * 8.0 + 4.0
    surf_xyz = np.stack(np.unravel_index(surf_idx, dims), 1)
    filled = 0
    if solid:
        inner = ndimage.binary_fill_holes(occ) & ~occ
        filled = int(inner.sum()); occ |= inner
    xyz = np.stack(np.nonzero(occ), 1)
    tree = cKDTree(surf_xyz)
    _, nn = tree.query(xyz)                                            # 内部/无色体素取最近表面色
    rgb = surf_rgb[nn]
    matcher = BlockMatcher(reg, palette)
    q = (rgb // 8).astype(int)                                         # 颜色量化后去重再匹配
    uq, inv = np.unique(q, axis=0, return_inverse=True)
    bi = matcher.match(uq * 8 + 4)[inv.reshape(-1)]
    g = VoxelGrid()
    for (x, y, z), b in zip(xyz.tolist(), bi.tolist()):
        g.cells[(x, y, z)] = "minecraft:" + matcher.ids[b]
    info = {"triangles": int(len(F)), "size": [int(d) for d in dims], "surface_voxels": int(len(surf_idx)),
            "filled_inside": filled, "palette_group": palette, "distinct_blocks": len(set(bi.tolist()))}
    return g, info


def remap_blocks(grid, mapping):
    """按 {旧方块: 新方块} 换材质 (模型根据文字描述给出映射)。"""
    g = VoxelGrid()
    for p, s in grid.cells.items():
        g.cells[p] = mapping.get(s, mapping.get(s.replace("minecraft:", ""), s))
    return g
