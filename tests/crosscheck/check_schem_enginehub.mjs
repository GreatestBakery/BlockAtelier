import fs from 'fs'; import zlib from 'zlib';
import { loadSchematic } from '@enginehub/schematicjs'; import { decode } from '@enginehub/nbt-ts';
const exp=JSON.parse(fs.readFileSync('expect.json'));
for (const f of ['v3b.schem','v3.schem','v2.schem']) { try {
  const s=loadSchematic(decode(zlib.gunzipSync(fs.readFileSync(f)),{unnamed:false,useMaps:true}).value); let ok=0,bad=0,first=null;
  for (const [k,st] of Object.entries(exp)) { const [x,y,z]=k.split(',').map(Number);
    const b=s.getBlock({x,y,z}); const want=st.split('[')[0]; const wp=Object.fromEntries((st.match(/\[(.*)\]/)||['',''])[1].split(',').filter(Boolean).map(kv=>kv.split('=')));
    const match=b && ('minecraft:'+b.type.replace('minecraft:',''))===want && Object.entries(wp).every(([p,v])=>String(b.properties[p])===v);
    if(match) ok++; else {bad++; if(!first) first=[k,st,JSON.stringify(b)];} }
  console.log(f,'format',s.format,'dv',s.dataVersion,'size',s.width,s.height,s.length,'match',ok,'mismatch',bad,first||'');
} catch(e){ console.log(f,'ERR',String(e).slice(0,300)); } }
