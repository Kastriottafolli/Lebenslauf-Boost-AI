import test from 'node:test';
import assert from 'node:assert/strict';
import {PROVIDERS,providerRequest,providerText,callProvider} from '../js/core/providers.js';
import {parseProfile,demoPackage,validatePackage,assessPackage,applicationPrompt,profileSource} from '../js/core/application.js';
import {SAMPLE} from '../js/browser/demo.js';
import {zipSync,unzipSync,strToU8} from 'fflate';

test('all five provider request/response contracts preserve credentials outside URL',()=>{
 for(const p of PROVIDERS){const options=p.id==='azure'?{model:'my-deployment',endpoint:'https://test.openai.azure.com'}:{};const request=providerRequest(p.id,'synthetic-key','source-only',[{role:'user',content:'verified facts'}],options);assert.ok(!request.endpoint.includes('synthetic-key'));assert.equal(request.model,options.model||p.default_model);let response;if(p.id==='claude'){assert.equal(request.body.system,'source-only');response={content:[{type:'text',text:'# Resume'}]};}else if(p.id==='gemini'){assert.equal(request.body.contents[0].parts[0].text,'verified facts');response={candidates:[{content:{parts:[{text:'# Resume'}]}}]};}else{assert.equal(request.body.store,false);assert.equal(request.body.input[0].content,'source-only');response={output:[{type:'message',content:[{type:'output_text',text:'# Resume'}]}]};}assert.equal(providerText(p.id,response),'# Resume');}
 assert.throws(()=>providerRequest('azure','key','system',[],{model:'x',endpoint:'https://test.openai.azure.com.evil.test'}));
 assert.throws(()=>providerText('openai',{status:'incomplete'}),/incomplete/);
});
test('AI adapter does not silently return templates on key error',async()=>{
 const original=globalThis.fetch;globalThis.fetch=async()=>new Response('{}',{status:401});try{await assert.rejects(callProvider('openai','synthetic-key','system',[]),/401/);}finally{globalThis.fetch=original;}
});
test('profile and complete demo package retain all source facts and expose placeholders',()=>{
 const profile=parseProfile(SAMPLE.de.cv);assert.equal(profile.name,'Alex Beispiel');assert.equal(profile.email,'alex@example.com');assert.equal(profile.confirmed,false);assert.equal(profile.location,'');const job={description:'Kubernetes Terraform frontend',title:'Frontend Developer',company:'Example'};const documents=demoPackage(profile,job);for(const line of SAMPLE.de.cv.split('\n').filter(Boolean))assert.ok(documents.cv.includes(line),line);assert.ok(!documents.cv.includes('Kubernetes'));assert.deepEqual(Object.keys(validatePackage(documents)),['cv','cover_letter','motivation_letter','email']);assert.equal(assessPackage(documents,job,SAMPLE.de.cv).checks.placeholders,true);assert.ok(applicationPrompt('en').includes('Never invent'));assert.ok(profileSource(profile).includes(SAMPLE.de.cv));assert.throws(()=>validatePackage({cv:'incomplete'}),/incomplete/);
});
test('ZIP bundles can be read back without losing Unicode document content',()=>{const documents=demoPackage(parseProfile(SAMPLE.de.cv),{description:SAMPLE.de.job});const bytes=zipSync(Object.fromEntries(Object.entries(documents).map(([key,value])=>[key+'.txt',strToU8(value)])));const contents=unzipSync(bytes);assert.equal(new TextDecoder().decode(contents['cv.txt']),documents.cv);});
