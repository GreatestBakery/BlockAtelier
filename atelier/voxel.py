"""稀疏体素网格: {(x,y,z): 规范方块状态}。坐标 x=东, y=上, z=南 (与游戏一致)。"""
import numpy as np


class VoxelGrid:
    def __init__(self):
        self.cells = {}

    def set(self, x, y, z, state):
        if state is None or state.endswith(":air") or state == "air":
            self.cells.pop((x, y, z), None)
        else:
            self.cells[(x, y, z)] = state

    def get(self, x, y, z): return self.cells.get((x, y, z))
    def __len__(self): return len(self.cells)

    def bounds(self):
        if not self.cells: return (0, 0, 0), (0, 0, 0)
        a = np.array(list(self.cells.keys()))
        return tuple(int(v) for v in a.min(0)), tuple(int(v) for v in a.max(0))

    def size(self):
        if not self.cells: return (0, 0, 0)
        lo, hi = self.bounds()
        return tuple(h - l + 1 for l, h in zip(lo, hi))

    def merge(self, other, dx=0, dy=0, dz=0):
        for (x, y, z), s in other.cells.items():
            self.cells[(x + dx, y + dy, z + dz)] = s

    def normalized(self):
        """平移到原点。"""
        lo, _ = self.bounds()
        g = VoxelGrid()
        g.cells = {(x - lo[0], y - lo[1], z - lo[2]): s for (x, y, z), s in self.cells.items()}
        return g

    def counts(self):
        c = {}
        for s in self.cells.values(): c[s] = c.get(s, 0) + 1
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))

    def to_dense(self):
        """-> (palette 列表[0]=air, int32 数组[x,y,z], 原点偏移)"""
        lo, hi = self.bounds()
        shape = tuple(h - l + 1 for l, h in zip(lo, hi)) if self.cells else (1, 1, 1)
        arr = np.zeros(shape, np.int32)
        pal, idx = ["minecraft:air"], {}
        for (x, y, z), s in self.cells.items():
            i = idx.get(s)
            if i is None:
                i = idx[s] = len(pal); pal.append(s)
            arr[x - lo[0], y - lo[1], z - lo[2]] = i
        return pal, arr, lo

    @classmethod
    def from_dense(cls, pal, arr):
        g = cls()
        xs, ys, zs = np.nonzero(arr)
        for x, y, z in zip(xs.tolist(), ys.tolist(), zs.tolist()):
            s = pal[arr[x, y, z]]
            if not s.endswith(":air"): g.cells[(x, y, z)] = s
        return g
