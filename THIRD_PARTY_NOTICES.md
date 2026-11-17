# Third-party software and resource notices

Reviewed on 2026-11-16. The table below records the original development environment; requirements are unpinned and later installations can differ. The desktop build environment is recorded separately in [BUNDLED_DEPENDENCIES.md](BUNDLED_DEPENDENCIES.md). This inventory covers declared direct dependencies and the vendored frontend library, not a complete transitive SBOM.

## Project source

Original BlockAtelier code and documentation use GPL-3.0-only. See [COPYRIGHT](COPYRIGHT) and [LICENSE](LICENSE). Third-party components retain their original licenses. litemapy is distributed under GPLv3: https://github.com/SmylerMC/litemapy .

## Vendored frontend library

`web/vendor/` contains three.js r187 and the OrbitControls, GLTFLoader, BufferGeometryUtils, and SkeletonUtils addons.

- Copyright 2010–2026 three.js authors.
- License: MIT, preserved in [web/vendor/LICENSE](web/vendor/LICENSE).
- Upstream: https://github.com/mrdoob/three.js .
- Preserve the original source headers and license when redistributing these files.

## Python direct dependencies

License texts copied from the installed distributions are preserved under `LICENSES/`. These records include extra component terms where supplied by the original package. A redistributed runtime must also carry the notices applicable to its actual transitive dependencies.

| Package | Recorded version | License summary | Original notices |
|---|---|---|---|
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | [Package notices](LICENSES/numpy/) |
| scipy | 1.18.0 | BSD-3-Clause (with bundled-component terms) | [Package notices](LICENSES/scipy/) |
| pillow | 12.3.0 | MIT-CMU | [Package notices](LICENSES/pillow/) |
| trimesh | 5.2.1 | MIT | [Package notices](LICENSES/trimesh/) |
| nbtlib | 2.0.4 | MIT | [Package notices](LICENSES/nbtlib/) |
| litemapy | 0.11.0b0 | GPL-3.0（Package notices） | [Package notices](LICENSES/litemapy/) |
| fastapi | 0.163.1 | MIT | [Package notices](LICENSES/fastapi/) |
| uvicorn | 0.40.0 | BSD-3-Clause | [Package notices](LICENSES/uvicorn/) |
| python-multipart | 0.0.32 | Apache-2.0 | [Package notices](LICENSES/python-multipart/) |
| mcp | 2.3.0 | MIT | [Package notices](LICENSES/mcp/) |
| pytest | 9.0.3 | MIT | [Package notices](LICENSES/pytest/) |

Blender is an optional external renderer and is not bundled with the application. Its license is documented at https://www.blender.org/about/license/ .

## Minecraft rendering resources

Game-derived textures, models, texture atlases, and related resources are outside the project source-code license. Public source and desktop Release archives exclude locally prepared version profiles. The desktop app prepares the Java 1.21.11 profile on the user's computer during first-run setup.

- Preparation utility: `tools/update_version.py`.
- Data source: https://github.com/misode/mcmeta . Its role as a distribution channel does not itself grant an open license to game resources.
- Minecraft and its game resources belong to Mojang / Microsoft and the relevant rights holders.
- Minecraft EULA: https://www.minecraft.net/en-us/eula .
- Minecraft Usage Guidelines: https://www.minecraft.net/en-us/usage-guidelines .

Exported textured meshes, texture files, and example media must be assessed according to their actual contents and applicable permissions. The project does not grant additional redistribution rights over third-party resources.

BlockAtelier is an independent, unofficial project and is not affiliated with, endorsed by, or approved by Mojang or Microsoft.

## User inputs and generated content

Imported images, structures, models, and generated content do not automatically adopt GPL through use of the application. Their conditions depend on the authors, source material, model-service terms, and any incorporated third-party resources.

## Related tools

References to Mineways, jmc2obj, MCprep, Chunky, WorldEdit, Axiom, WorldPainter, deepslate, prismarine-viewer, ObjToSchematic, BlockBlender, BuilderGPT, T2BM, APT, and SearXNG describe external workflows, compatible formats, or related approaches. These references do not imply bundled code, endorsement, or a tested integration. Any future code integration requires notices for the actual component and version used.
