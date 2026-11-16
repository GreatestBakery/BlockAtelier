# 第三方软件与资源声明

核对日期：2026-11-16。此清单记录当前本机安装版本；`requirements.txt` 未锁版本，重新安装后应按实际版本复核。此处覆盖直接声明的依赖及随包前端库，不是全部传递依赖的完整 SBOM。

## 项目代码

BlockAtelier 原创代码及项目文档采用 **GPL-3.0-only**，版权声明见 [COPYRIGHT](COPYRIGHT)，完整条款见 [LICENSE](LICENSE)。选择 GPLv3 是为配合项目直接使用的 litemapy；各第三方组件仍保留各自许可证，不因本项目授权而被重新授权。

## 随包前端代码

`web/vendor/` 包含 **three.js r187** 及其 addons，包括 OrbitControls、GLTFLoader、BufferGeometryUtils 和 SkeletonUtils。

- 版权所有：2010–2026 three.js authors。
- 许可证：MIT，全文随附于 [web/vendor/LICENSE](web/vendor/LICENSE)。
- 上游：https://github.com/mrdoob/three.js
- 发布时保留原有文件头和 MIT 许可证。

## Python 直接依赖

下列许可证原文从当前安装包的 dist-info 中复制到 `LICENSES/`，保留其原始内容，包括发行包内列出的额外组件条款。这里只分发许可证文本，不分发 Python 库本身；若另行打包运行环境，须包含实际打包的传递依赖及其声明。

| 包 | 本机版本 | 许可证摘要 | 原始声明 |
|---|---|---|---|
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | [安装包声明](LICENSES/numpy/) |
| scipy | 1.18.0 | BSD-3-Clause（含随包组件条款） | [安装包声明](LICENSES/scipy/) |
| pillow | 12.3.0 | MIT-CMU | [安装包声明](LICENSES/pillow/) |
| trimesh | 5.2.1 | MIT | [安装包声明](LICENSES/trimesh/) |
| nbtlib | 2.0.4 | MIT | [安装包声明](LICENSES/nbtlib/) |
| litemapy | 0.11.0b0 | GPL-3.0（安装包声明） | [安装包声明](LICENSES/litemapy/) |
| fastapi | 0.163.1 | MIT | [安装包声明](LICENSES/fastapi/) |
| uvicorn | 0.40.0 | BSD-3-Clause | [安装包声明](LICENSES/uvicorn/) |
| python-multipart | 0.0.32 | Apache-2.0 | [安装包声明](LICENSES/python-multipart/) |
| mcp | 2.3.0 | MIT | [安装包声明](LICENSES/mcp/) |
| pytest | 9.0.3 | MIT | [安装包声明](LICENSES/pytest/) |

litemapy 上游：https://github.com/SmylerMC/litemapy （GPLv3）。Blender 是可选的外部渲染程序，并未随本项目分发；其条款参见 https://www.blender.org/about/license/ 。

## Minecraft 数据、贴图与模型

`data/versions/` 中的 `atlas.png` 以及来自游戏的贴图、模型和相关派生资源不在 BlockAtelier 的 GPL 授权范围内。本项目不能授予这些资源的额外复制、再分发或商业使用权。

- 数据获取工具：`tools/update_version.py`。
- 数据来源：misode/mcmeta（https://github.com/misode/mcmeta），由 Minecraft 游戏资源导出；取得数据的渠道不等于取得其开放许可。
- Minecraft 及相应游戏资源的权利归 Mojang / Microsoft 及相关权利人所有。
- Minecraft EULA：https://www.minecraft.net/en-us/eula
- Minecraft Usage Guidelines：https://www.minecraft.net/en-us/usage-guidelines

准备公开源码包时，应排除游戏贴图、模型及包含这些内容的派生文件，除非已确认具备对应的分发授权。示例 GLB / OBJ、导出的贴图和渲染图也应按其实际内容逐项检查；“仅供自用”并不构成再分发许可。本次仅补文档，未删除现有资源，也未将项目标记为已完成公开发布审查。

本项目是独立的非官方工具，与 Mojang 或 Microsoft 无隶属关系，亦未获其认可。

## 用户输入与生成内容

用户导入的参考图、结构、模型及模型生成内容不因使用本软件而自动采用 GPL。相应权利及使用条件取决于内容来源、作者、模型服务条款和所含第三方资源。包含游戏贴图的 GLB / OBJ 等输出仍须遵守对应资源条款。

## 致谢与未随包软件

README 中提及的 Mineways、jmc2obj、MCprep、Chunky、WorldEdit、Axiom、WorldPainter、deepslate、prismarine-viewer、ObjToSchematic、BlockBlender、BuilderGPT、T2BM、APT 和 SearXNG 等，仅作为格式兼容、外部工具或思路参考的说明；列出名称不表示已获授权或将其代码纳入本项目。以后实际引入代码时应补充对应版本及许可证。
