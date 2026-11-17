// Frontend localization. User-authored content and build JSON are never rewritten.
const EN = {
  "已保存到 {path}": "Saved to {path}",
  "方块工坊 BlockAtelier": "BlockAtelier",
  "方块工坊": "BlockAtelier",
  "目标版本": "Target version",
  "模型与渲染设置": "Model & rendering settings",
  "文字 + 参考": "Text & references",
  "3D 模型转换": "3D model conversion",
  "建筑描述": "Building description",
  "例：一座湖边的两层木构茶楼，深色云杉梁柱，青色歇山顶，带回廊和灯笼": "Example: A two-story lakeside timber teahouse with dark spruce beams, a teal hip-and-gable roof, a veranda, and lanterns",
  "风格提示": "Style",
  "可选": "Optional",
  "中世纪 / 蒸汽朋克 / 现代极简 …": "Medieval / steampunk / modern minimalist …",
  "参考图": "Reference images",
  "概念图、照片、设计图；需要支持看图的模型": "Concept art, photos, or plans; requires a vision-capable model",
  "点击或拖入图片": "Click or drop images here",
  "参考结构": "Reference structures",
  "从右侧参考库勾选；不选则按关键词自动匹配": "Select from the reference library, or leave blank for keyword matching",
  "参考库为空": "The reference library is empty",
  "3D 模型文件": "3D model file",
  "点击或拖入模型": "Click or drop a model here",
  "最长边（方块）": "Longest side (blocks)",
  "朝上的轴": "Up axis",
  "自动": "Auto",
  "配色用的方块范围": "Block palette",
  "填充内部（默认只保留外壳）": "Fill interior (surface only by default)",
  "换材质说明": "Material changes",
  "可选，交给模型把配色映射成指定材质": "Optional instructions for remapping materials",
  "例：整体做成风化的砂岩遗迹，屋顶用深色板岩": "Example: Weathered sandstone ruins with a dark deepslate roof",
  "尺寸上限": "Maximum dimensions",
  "东西 × 高 × 南北": "East–west × height × north–south",
  "生成": "Generate",
  "生成中…": "Generating…",
  "在当前作品上修改": "Revise the current build",
  "保留原指令，按说明改": "Use the existing program as the starting point",
  "例：屋顶改成红色，正面加一个带栏杆的阳台": "Example: Make the roof red and add a balcony with railings to the front",
  "生成修改版": "Generate revision",
  "还没有作品。在左侧写一段描述，或上传一个 3D 模型。": "No build yet. Enter a description on the left or upload a 3D model.",
  "重置视角": "Reset view",
  "自动旋转": "Auto-rotate",
  "流程": "Progress",
  "校验报告": "Validation",
  "用料清单": "Materials",
  "建筑指令": "Build program",
  "渲染与导出": "Render & export",
  "每一步的进展会显示在这里。": "Progress for each stage will appear here.",
  "作品库": "Build library",
  "参考库": "References",
  "搜索标题 / 描述 / 标签": "Search titles / descriptions / tags",
  "只看收藏": "Favorites only",
  "放入你收集的 .litematic / .schem / .nbt 或参考图。结构文件会被解析成尺寸和用料摘要，生成时提供给模型。": "Add .litematic, .schem, .nbt, or reference images. Structure dimensions and material summaries are available during generation.",
  "点击或拖入参考文件": "Click or drop reference files here",
  "结构文件同时入作品库（可预览、转格式、渲染）": "Also add structures to the build library for preview, conversion, and rendering",
  "模型提供方": "Model provider",
  "模型名": "Model identifier",
  "填你账号里可用的模型名": "A model available to your account",
  "接口地址": "Base URL",
  "留空用预设": "Leave blank to use the preset",
  "留空表示不修改": "Leave blank to keep the saved key",
  "校验失败时修复轮数": "Validation repair rounds",
  "看图自评轮数": "Visual review rounds",
  "模型支持看图（参考图、渲染自评）": "Model supports images (references and visual review)",
  "SearXNG 地址": "SearXNG URL",
  "可选，联网找参考": "Optional online reference search",
  "Blender 可执行文件": "Blender executable",
  "取消": "Cancel",
  "保存": "Save",
  "3D 预览加载失败: ": "Could not load the 3D preview: ",
  "块": "blocks",
  "图片": "Image",
  "删除": "Delete",
  "还没有参考文件。": "No reference files yet.",
  "文字": "Text",
  "3D 模型": "3D model",
  "导入": "Imported",
  "修改版": "Revision",
  "收藏": "Favorite",
  "改名": "Rename",
  "标签": "Tags",
  "作品库是空的。": "No saved builds yet.",
  "新标题": "New title",
  "标签（空格分隔）": "Tags (separated by spaces)",
  "删除「{title}」及其全部文件？": "Delete “{title}” and all its files?",
  "指令错误：": "Program error: ",
  "尺寸 (x·y·z)": "Dimensions (x·y·z)",
  "方块数": "Blocks",
  "方块种类": "Block types",
  "自动补连接": "Auto-connections",
  "处": "connections",
  "预览网格": "Preview mesh",
  "三角面": "triangles",
  "用时": "Time",
  "模型": "Model",
  "来源": "Source",
  "校验通过：方块 id 全部有效，结构连通且落地。": "Validation passed: no issues reported.",
  "描述：": "Description: ",
  "方案：": "Design: ",
  "方块": "Block",
  "数量": "Count",
  "约合组（64）": "Stacks (64)",
  "无数据": "No data",
  "这个作品不是由指令生成的（3D 模型转换或导入）。": "This build has no program (converted from a 3D model or imported).",
  "下载 .litematic": "Download .litematic",
  "下载 .schem (v3)": "Download .schem (v3)",
  ".schem (v2 旧版)": ".schem (legacy v2)",
  "OBJ + 贴图 (Blender / MCprep)": "OBJ + textures (Blender / MCprep)",
  "指令 JSON": "Program JSON",
  "宽": "Width",
  "高": "Height",
  "采样": "Samples",
  "方位角": "Azimuth",
  "俯角": "Elevation",
  "张数": "Views",
  "未找到 Blender，见设置": "Blender not found; check settings",
  "Blender 渲染": "Render in Blender",
  "交给已连接 Blender MCP 的模型执行": "Run through a connected Blender MCP client",
  "复制 Blender MCP 脚本": "Copy Blender MCP script",
  "四视角预览": "Four-angle preview",
  "已复制。把它交给 Blender MCP 的“执行代码”工具即可在你的 Blender 里渲染。": "Copied. Run the script through Blender MCP to render in Blender.",
  "复制失败，请在 {url} 手动获取": "Copy failed. Retrieve the script manually at {url}",
  "请写下要怎么改": "Enter the changes to make",
  "（快照）": " (snapshot)",
  "全部实心方块": "All solid blocks",
  "混凝土 + 羊毛 + 陶瓦": "Concrete + wool + terracotta",
  "仅混凝土": "Concrete only",
  "仅羊毛": "Wool only",
  "仅陶瓦": "Terracotta only",
  "石质": "Stone",
  "木板": "Wood planks",
  "离线模拟（未接入模型）": "Offline demo (no model connected)",
  "未填模型名": "Model not set",
  "已保存": "Saved",
  "未设置": "Not set",
  "已找到": "Found",
  "未找到": "Not found",
  "必填": "Required",
  "Key 只保存在本机 workspace/config.json；也可以用环境变量 ATELIER_API_KEY。": "Keys are stored locally in workspace/config.json. ATELIER_API_KEY is also supported.",
  "无法连接后端: ": "Could not connect to the server: ",
  "输入整理": "Input",
  "找参考": "References",
  "需求分析": "Design brief",
  "生成指令": "Build program",
  "校验修复": "Repair",
  "看图自评": "Visual review",
  "体素化": "Voxelization",
  "换材质": "Material mapping",
  "导出入库": "Export & save",
  "渲染": "Rendering",
  "出错": "Error",
  "进行中": "Running",
  "完成": "Done",
  "注意": "Warning",
  "失败": "Failed",
  "离线规则引擎，不联网，用于自检和演示": "Offline rule-based generator for checks and demonstrations",
  "Claude (Messages API)": "Claude (Messages API)",
  "Google Gemini (OpenAI 兼容端点)": "Google Gemini (OpenAI-compatible endpoint)",
  "通义千问 (DashScope 兼容模式)": "Qwen (DashScope-compatible endpoint)",
  "OpenRouter (聚合多家)": "OpenRouter (multiple providers)",
  "本地 Ollama": "Local Ollama",
  "本机 opencode CLI（使用已配置的模型）": "Local opencode CLI (configured models)",
  "opencode 可执行文件": "opencode executable",
  "opencode 默认模型": "opencode default model",
  "本机 Codex CLI（使用 ChatGPT 登录）": "Local Codex CLI (ChatGPT sign-in)",
  "Codex 可执行文件": "Codex executable",
  "Codex 默认模型": "Codex default model",
  "留空使用 Codex 默认模型": "Leave blank for the Codex default model",
  "需安装 Codex CLI 0.166.0 或更新版本，先运行 codex login 并使用 ChatGPT 账号登录。使用套餐中的 Codex 额度，无需 API Key，仍受套餐用量限制。": "Install Codex CLI 0.166.0 or later, then run codex login and sign in with ChatGPT. Uses your plan's Codex allowance; no API key is needed. Plan usage limits still apply.",
  "provider/model，留空使用 opencode 默认模型": "provider/model; leave blank for the opencode default",
  "需安装 opencode 2.x 并先完成模型登录。使用 opencode 的模型配置，无需在这里填写 API Key。": "Install opencode 2.x and sign in to a model provider first. Uses your opencode model configuration; no API key is needed here.",
  "任何 OpenAI 兼容服务 (LM Studio / vLLM / 中转)": "Custom OpenAI-compatible service (LM Studio / vLLM / proxy)",
  "语言": "Language",
  "中文": "简体中文",
  "English": "English",
  "结构为空: 没有放置任何方块": "The structure is empty: no blocks were placed",
  "整座建筑只用了 1 种方块，缺少材质层次": "The entire build uses one block type; consider adding material variety",
  "体素化 3D 模型…": "Voxelizing the 3D model…",
  "让模型按文字描述调整材质…": "Remapping materials from the description…",
  "整理参考资料…": "Preparing references…",
  "分析需求、定设计方案…": "Analyzing requirements and preparing the design…",
  "模型返回的 JSON 格式有误，正在请求修正…": "The model returned invalid JSON; requesting a correction…",
  "生成建筑指令…": "Generating the build program…",
  "渲染预览并让模型看图自评…": "Rendering previews for visual review…",
  "导出 .litematic / .schem / 3D 预览…": "Exporting .litematic / .schem / 3D previews…",
  "模型模式需要先上传 3D 模型": "Upload a 3D model before starting conversion",
  "请填写文字描述": "Enter a building description",
  "上传文件不存在": "The uploaded file was not found",
  "作品不存在": "Build not found",
  "任务不存在": "Job not found",
  "修改版有新问题，保留原版。": "The revision introduced new issues; keeping the original. "
};
const STORAGE_KEY = 'blockatelier.language';
function initialLanguage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'zh-CN' || saved === 'en') return saved;
  } catch { /* Storage may be disabled. */ }
  const preferred = (navigator.languages?.length ? navigator.languages : [navigator.language])
    .find(value => /^(zh|en)(-|$)/i.test(value || '')) || 'en';
  return /^zh/i.test(preferred) ? 'zh-CN' : 'en';
}
let language = initialLanguage();
export const getLanguage = () => language;
export function setLanguage(value) {
  language = /^zh(-|$)/i.test(value) ? 'zh-CN' : 'en';
  try { localStorage.setItem(STORAGE_KEY, language); } catch { /* Keep working without persistence. */ }
}
export function t(key, parameters = {}) {
  const value = language === 'en' ? (EN[key] ?? key) : key;
  return String(value).replace(/\{(\w+)\}/g, (match, name) => parameters[name] ?? match);
}
export function applyTranslations(root = document) {
  document.documentElement.lang = language;
  root.querySelectorAll('[data-i18n]').forEach(element => {
    element.textContent = t(element.dataset.i18n);
  });
  for (const attribute of ['placeholder', 'title', 'alt']) {
    root.querySelectorAll(`[data-i18n-${attribute}]`).forEach(element => {
      element.setAttribute(attribute, t(element.getAttribute(`data-i18n-${attribute}`)));
    });
  }
}

// Translate known application diagnostics at the display boundary. Captured values
// (names, counts, block IDs, paths, and model responses) retain their original text.
const MESSAGE_PATTERNS = [
  [/^目标版本 (.+?) \(DataVersion (.+?)\)，尺寸上限 (.+?)，模式 (.+)$/, (_, v, d, size, mode) => `Target: Java ${v} (DataVersion ${d}), maximum dimensions ${size}, mode ${mode}`],
  [/^参考结构 (\d+) 个，参考图 (\d+) 张$/, (_, a, b) => `${a} reference structures, ${b} reference images`],
  [/^联网检索到 (\d+) 条线索$/, (_, n) => `Found ${n} online references`],
  [/^(\d+) 条指令 -> (\d+) 个方块$/, (_, n, blocks) => `${n} operations → ${blocks} blocks`],
  [/^第 (\d+) 轮修复: (\d+) 个问题$/, (_, n, issues) => `Repair round ${n}: ${issues} issues`],
  [/^剩余问题 (\d+) 个$/, (_, n) => `${n} issues remaining`],
  [/^(\d+) 个三角面 -> (.+)，(\d+) 种方块$/, (_, n, size, kinds) => `${n} triangles → ${size}, ${kinds} block types`],
  [/^替换了 (\d+) 种材质。(.*)$/s, (_, n, notes) => `Remapped ${n} materials. ${notes}`],
  [/^完成: (.+)，(\d+) 个方块，用时 (.+)s$/, (_, size, n, time) => `Complete: ${size}, ${n} blocks, ${time}s`],
  [/^Blender (.+) 渲染中 \((.+), (.+) 采样\)…$/, (_, engine, size, samples) => `Rendering with Blender ${engine} (${size}, ${samples} samples)…`],
  [/^完成 (\d+) 张$/, (_, n) => `Rendered ${n} images`],
  [/^尺寸 (.+) \(x,y,z\) 超过要求的上限 (.+)$/, (_, size, max) => `Dimensions ${size} (x,y,z) exceed the maximum ${max}`],
  [/^有 (\d+) 处悬空的独立部件 \(共 (\d+) 块，不接地也不与主体相连\): (.+)$/, (_, n, total, examples) => `${n} floating components (${total} blocks, disconnected from the ground and main structure): ${examples.replace(/ 块 @ /g, ' blocks @ ')}`],
  [/^(\d+) 个受重力方块下方悬空 \(沙\/沙砾\/混凝土粉末会掉落\)$/, (_, n) => `${n} unsupported gravity-affected blocks (sand, gravel, or concrete powder may fall)`],
  [/^(\d+) 个门只有半扇 \(请用 door 指令\)$/, (_, n) => `${n} doors are missing a half (use the door operation)`],
  [/^未知方块 '(.+)' \((.+) 中不存在\)(?:，相近: (.+))?$/, (_, id, version, suggestions) => `Unknown block '${id}' (not available in ${version})${suggestions ? ', similar: ' + suggestions : ''}`],
  [/^(.+) 没有属性 (.+)，已忽略$/, (_, id, property) => `${id} has no property ${property}; ignored`],
  [/^(.+) 的 (.+)=(.+) 无效 \(可选 (.+)\)，已用默认值$/, (_, id, property, value, allowed) => `${id}: invalid ${property}=${value} (allowed: ${allowed}); using the default`],
  [/^不支持的文件类型 (.+)$/, (_, ext) => `Unsupported file type: ${ext}`],
  [/^找不到 Blender。(.*)$/s, () => 'Blender was not found. Set its executable path in settings, install a compatible bpy package, or use Blender MCP.'],
];
const PREFIXES = {
  '修复失败: ': 'Repair failed: ', '自评跳过: ': 'Visual review skipped: ',
  '材质调整跳过: ': 'Material mapping skipped: ', '已采纳修改: ': 'Revision applied: ',
  '通过: ': 'Passed: ', '指令错误：': 'Program error: ',
  '3D 预览加载失败: ': 'Could not load the 3D preview: ',
  '无法连接后端: ': 'Could not connect to the server: ',
  'Blender 渲染失败: ': 'Blender rendering failed: ', '无法解析方块: ': 'Cannot parse block: ',
};
export function localizeMessage(message) {
  const original = String(message ?? '');
  if (language !== 'en') return original;
  if (Object.hasOwn(EN, original)) return EN[original];
  for (const [prefix, replacement] of Object.entries(PREFIXES)) {
    if (original.startsWith(prefix)) return replacement + localizeMessage(original.slice(prefix.length));
  }
  if (original.startsWith('修改版有新问题，保留原版。')) {
    return EN['修改版有新问题，保留原版。'] + original.slice('修改版有新问题，保留原版。'.length);
  }
  const counted = original.match(/^(.*) ×(\d+)$/s);
  if (counted) return `${localizeMessage(counted[1])} ×${counted[2]}`;
  for (const [pattern, replacement] of MESSAGE_PATTERNS) {
    if (pattern.test(original)) return original.replace(pattern, replacement);
  }
  return original.replace(/ \(别名\/改名\)$/, ' (alias/rename)')
    .replace(/ \(拼写修正\)$/, ' (spelling correction)')
    .replace(/ \(近似匹配\)$/, ' (approximate match)');
}
