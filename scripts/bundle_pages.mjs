import { build } from 'esbuild';
import { cp, mkdir } from 'node:fs/promises';
import path from 'node:path';

await build({
  entryPoints: ['frontend/js/pages-main.js'],
  outdir: '_site/assets/js', bundle: true, splitting: true, format: 'esm',
  platform: 'browser', target: ['es2022'], minify: true,
  plugins: [{ name: 'browser-api', setup(build) {
    build.onResolve({ filter: /(^|\/)api\.js$/ }, () => ({ path: path.resolve('frontend/js/browser/api.js') }));
  }}],
});
await mkdir('_site/assets/js/pdfjs', { recursive: true });
for (const dir of ['wasm', 'cmaps', 'standard_fonts']) {
  await cp(`node_modules/pdfjs-dist/${dir}`, `_site/assets/js/pdfjs/${dir}`, { recursive: true });
}
await cp('node_modules/pdfjs-dist/build/pdf.worker.mjs', '_site/assets/js/pdfjs/pdf.worker.mjs');
console.log('Built self-contained browser app.');
