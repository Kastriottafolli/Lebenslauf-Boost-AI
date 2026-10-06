import { build } from 'esbuild';
import { cp, mkdir, readdir, writeFile, readFile, rm } from 'node:fs/promises';
import {createHash} from 'node:crypto';
await rm('frontend/build',{recursive:true,force:true});
const common={entryPoints:['frontend/js/app.js','frontend/js/admin-app.js','frontend/js/analytics-app.js'],bundle:true,splitting:true,format:'esm',platform:'browser',target:['es2022'],minify:true};
await build({...common,outdir:'_site/assets/js',define:{__RUNTIME__:JSON.stringify('browser'),__API_BASE__:JSON.stringify(process.env.PUBLIC_API_BASE||'')}});
await build({...common,outdir:'frontend/build',define:{__RUNTIME__:JSON.stringify('server'),__API_BASE__:JSON.stringify(process.env.PUBLIC_API_BASE||'')}});
for(const root of ['_site/assets/js','frontend/build']){
  await mkdir(`${root}/pdfjs`,{recursive:true});
  for(const dir of ['wasm','cmaps','standard_fonts'])await cp(`node_modules/pdfjs-dist/${dir}`,`${root}/pdfjs/${dir}`,{recursive:true});
  await cp('node_modules/pdfjs-dist/build/pdf.worker.mjs',`${root}/pdfjs/pdf.worker.mjs`);
  await mkdir(`${root}/ocr/core`,{recursive:true});
  await cp('node_modules/tesseract.js/dist/worker.min.js',`${root}/ocr/worker.min.js`);
  for(const name of await readdir('node_modules/tesseract.js-core'))if(/\.wasm(?:\.js)?$/.test(name))await cp(`node_modules/tesseract.js-core/${name}`,`${root}/ocr/core/${name}`);
}
const revision=createHash('sha256').update(await readFile('_site/assets/js/app.js')).update(await readFile('frontend/css/professional.css')).digest('hex').slice(0,12);
await writeFile('_site/index.html',(await readFile('_site/index.html','utf8')).replaceAll('__BUILD_ID__',revision));
await writeFile('_site/sw.js',(await readFile('frontend/public/sw.js','utf8')).replaceAll('__BUILD_ID__',revision).replace('__PRECACHE_CHUNKS__',JSON.stringify((await readdir('_site/assets/js')).filter(p=>p.endsWith('.js')&&p!=='app.js').map(p=>'assets/js/'+p))));
await writeFile('_site/health.json',JSON.stringify({build:'application-platform',runtime:'browser',built_at:new Date().toISOString()}));
console.log('Built browser and server applications with local PDF and OCR workers.');
