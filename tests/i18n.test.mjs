// Run with: node --experimental-vm-modules tests/i18n.test.mjs
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { SourceTextModule, createContext } from 'node:vm';

const source = await readFile(new URL('../web/i18n.js', import.meta.url), 'utf8');
async function locale({ languages = ['en-US'], saved, blocked = false } = {}) {
  const storage = new Map(saved ? [['blockatelier.language', saved]] : []);
  const context = createContext({
    navigator: { languages },
    localStorage: {
      getItem(key) { if (blocked) throw Error('Storage disabled'); return storage.get(key); },
      setItem(key, value) { if (blocked) throw Error('Storage disabled'); storage.set(key, value); },
    },
  });
  const module = new SourceTextModule(source, { context });
  await module.link(() => {});
  await module.evaluate();
  return { ...module.namespace, storage };
}

for (const [options, expected] of [
  [{ languages: ['zh-TW'] }, 'zh-CN'],
  [{ languages: ['en-GB'] }, 'en'],
  [{ languages: ['fr-FR', 'zh-CN'] }, 'zh-CN'],
  [{ languages: ['fr-FR'] }, 'en'],
  [{ languages: ['en-US'], saved: 'zh-CN' }, 'zh-CN'],
  [{ languages: ['zh-CN'], saved: 'en' }, 'en'],
  [{ languages: ['zh-CN'], saved: 'unsupported' }, 'zh-CN'],
]) {
  assert.equal((await locale(options)).getLanguage(), expected);
}

const current = await locale();
assert.equal(current.t('生成'), 'Generate');
current.setLanguage('zh-CN');
assert.equal(current.t('生成'), '生成');
assert.equal(current.storage.get('blockatelier.language'), 'zh-CN');
assert.equal(current.localizeMessage('12 条指令 -> 100 个方块'), '12 条指令 -> 100 个方块');
current.setLanguage('en');
assert.equal(current.localizeMessage('12 条指令 -> 100 个方块'), '12 operations → 100 blocks');
assert.equal(current.localizeMessage("未知方块 'missing' (1.21.11 中不存在) ×2"), "Unknown block 'missing' (not available in 1.21.11) ×2");
assert.equal(current.t('删除「{title}」及其全部文件？', { title: '用户的楼' }), 'Delete “用户的楼” and all its files?');
assert.equal(current.localizeMessage('User content 用户原文'), 'User content 用户原文');
assert.equal(current.localizeMessage('修复失败: user detail'), 'Repair failed: user detail');
assert.equal(current.t('unknown translation key'), 'unknown translation key');

const blocked = await locale({ blocked: true });
blocked.setLanguage('zh-CN');
assert.equal(blocked.getLanguage(), 'zh-CN');
assert.equal(blocked.t('保存'), '保存');
console.log('Frontend localization tests passed.');
