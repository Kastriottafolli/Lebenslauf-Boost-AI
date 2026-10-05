import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {translate} from '../js/core/locale.js';

test('every public UI text and placeholder has reviewed Albanian copy',async()=>{
 const html=await readFile('frontend/index.html','utf8');
 for(const tag of html.matchAll(/<[^>]+data-(?:placeholder-)?de="[^>]+>/g)) {
  assert.match(tag[0],/data-(?:placeholder-)?sq="[^"]+"/);
 }
 assert.equal(translate('sq','Lebenslauf','Resume'),'CV');
 assert.equal(translate('sq','Berufliche Überschrift','Professional headline'),'Titulli profesional');
 assert.equal(translate('en','Anschreiben','Cover letter'),'Cover letter');
});

test('pasted job facts are extracted only from explicit labels',async()=>{
 const {jobDetails}=await import('../js/core/job.js');
 assert.deepEqual(jobDetails('Pozicioni: Developer\nKompania: Studio Example\nEmail: jobs@example.com'),{title:'Developer',company:'Studio Example',email:'jobs@example.com'});
 assert.deepEqual(jobDetails('We are a great company and need a person.'),{title:'',company:'',email:''});
});
