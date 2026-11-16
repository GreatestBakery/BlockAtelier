const fs=require('fs'); const {Schematic}=require('prismarine-schematic'); const {Vec3}=require('vec3');
(async()=>{ const exp=JSON.parse(fs.readFileSync('expect.json'));
 for (const f of ['v2.schem','v3b.schem']) { try {
   const s=await Schematic.read(fs.readFileSync(f)); let ok=0,bad=0,first=null;
   for (const [k,st] of Object.entries(exp)) { const [x,y,z]=k.split(',').map(Number);
     const b=s.getBlock(new Vec3(x,y,z).plus(s.offset)); const name='minecraft:'+b.name; const props=b.getProperties?b.getProperties():{};
     const want=st.split('[')[0]; const wp=Object.fromEntries((st.match(/\[(.*)\]/)||['',''])[1].split(',').filter(Boolean).map(kv=>kv.split('=')));
     let match = name===want && Object.entries(wp).every(([p,v])=>String(props[p])===v);
     if(match) ok++; else { bad++; if(!first) first=[k,st,name,JSON.stringify(props)]; } }
   console.log(f,'version',s.version,'size',s.size,'match',ok,'mismatch',bad,first||''); } catch(e){ console.log(f,'ERR',e.message.slice(0,200)); } }
})();
