import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { analyze, demoCv, demoRefine, SAMPLE } from '../js/browser/demo.js';
import { uploadCv, generateCv, refineCv, requestAI } from '../js/browser/api.js';
import { createPdf, createDocx, exportDocument } from '../js/browser/export.js';
import { PDFDocument } from 'pdf-lib';
import mammoth from 'mammoth';
const body={content:SAMPLE.de.cv,design:'modern',format:'pdf',filename:'Lebenslauf',photo:null};

test('demo preserves source facts and never inserts missing job skills',()=>{
  for(const provider of ['claude','openai']) {
    const result=demoCv(SAMPLE.de.cv,'React Kubernetes Terraform', 'de', provider);
    assert.match(result,/DEMO/);
    assert.ok(!result.includes('Kubernetes'));
    for(const line of SAMPLE.de.cv.split('\n').filter(Boolean)) assert.ok(result.includes(line),line);
  }
});
test('keyword matching uses words, excludes notices and counts missing requirements',()=>{
  assert.deepEqual(analyze('React\n> Kubernetes','React Kubernetes'),{ats_score:50,matched_keywords:['react'],missing_keywords:['kubernetes']});
  assert.equal(analyze('education','API').ats_score,0);
});
test('shortening modifies bullets without inventing numbers',()=>{
  const result=demoRefine(SAMPLE.de.cv,'Kürzer');
  assert.ok(result.length<SAMPLE.de.cv.length);
  assert.match(result,/Ausbildung/);
  assert.throws(()=>demoRefine(SAMPLE.de.cv,'Invent an award'),/API-Key/);
});
test('empty, unsupported and oversized uploads fail clearly',async()=>{
  await assert.rejects(uploadCv({file:new File(['hi'],'empty.txt')}),/lesbarer/);
  await assert.rejects(uploadCv({file:new File(['12345678901'],'bad.exe')}),/PDF/);
  await assert.rejects(uploadCv({file:{name:'large.txt',size:11*1024*1024}}),/10 MB/);
});
test('sample upload, comparison and refinement work with no network or key',async()=>{
  const original=globalThis.fetch; globalThis.fetch=()=>{throw new Error('Unexpected network request');};
  try {
    await uploadCv({file:new File([SAMPLE.de.cv],'sample.txt')});
    const generated=await generateCv({job_description:SAMPLE.de.job,provider:'compare',language:'de',technique:'auto',keys:{}});
    assert.equal(generated.results.length,2);
    assert.ok(generated.results.every(x=>x.is_demo));
    assert.match(generated.recommendation,/regelbasiert/);
    const refined=await refineCv({current_content:generated.results[0].content,instruction:'Kürzer',provider:'claude',language:'de',keys:{}});
    assert.ok(refined.content.length<generated.results[0].content.length);
  } finally {globalThis.fetch=original;}
});
test('provider adapters send the proper payload; failures never silently become demo',async()=>{
  const original=globalThis.fetch;
  try {
    for(const provider of ['claude','openai']) {
      globalThis.fetch=async(url,options)=>{
        const payload=JSON.parse(options.body);
        assert.equal(options.credentials,'omit');
        if(provider==='claude') {assert.match(url,/api.anthropic.com/);assert.equal(options.headers['x-api-key'],'test-only');assert.ok(payload.system);}
        else {assert.match(url,/api.openai.com/);assert.equal(options.headers.Authorization,'Bearer test-only');assert.equal(payload.store,false);}
        return Response.json(provider==='claude'?{content:[{type:'text',text:'# Alex'}]}:{choices:[{message:{content:'# Alex'},finish_reason:'stop'}]});
      };
      assert.equal((await requestAI(provider,'test-only',[{role:'user',content:'Test'}],'de','auto')).content,'# Alex');
    }
    globalThis.fetch=async()=>new Response('{}',{status:401});
    await assert.rejects(requestAI('openai','test-only',[],'en','auto'),/Invalid API key/);
    await assert.rejects(generateCv({job_description:SAMPLE.de.job,provider:'openai',language:'en',keys:{openai:'test-only'}}),/Invalid API key/);
    globalThis.fetch=async()=>Response.json({choices:[{message:{content:'truncated'},finish_reason:'length'}]});
    await assert.rejects(requestAI('openai','test-only',[],'en','auto'),/too long/);
  } finally {globalThis.fetch=original;}
});
test('all six PDF designs export valid paginated documents with Unicode',async()=>{
  const font=await readFile('static/fonts/NotoSans-Regular.ttf');
  for(const design of ['modern','classic','minimal','sapphire','cobalt','slate']) {
    const bytes=await createPdf({...body,design,content:body.content+'\n\n## Über mich\nGrüße — Fähigkeiten'},font);
    assert.equal((await PDFDocument.load(bytes)).getPageCount(),1);
  }
  const long=await createPdf({...body,content:body.content+'\n'+('- Long résumé bullet with Grüße and experience.\n'.repeat(160))},font);
  assert.ok((await PDFDocument.load(long)).getPageCount()>2);
});
test('Word is a real readable DOCX that preserves resume text',async()=>{
  const blob=await createDocx(body);
  const result=await mammoth.extractRawText({buffer:Buffer.from(await blob.arrayBuffer())});
  assert.match(result.value,/Alex Beispiel/);
  assert.match(result.value,/25 %/);
  assert.match(result.value,/Kenntnisse/);
});
test('export validates formats and produces a safe filename',async()=>{
  await assert.rejects(exportDocument({...body,format:'exe'}),/Format/);
  const result=await exportDocument({...body,format:'docx',filename:'../../my:CV.docx'});
  assert.equal(result.filename,'.._.._my_CV.docx');
});
