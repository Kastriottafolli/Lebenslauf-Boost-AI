import test from "node:test";
import assert from "node:assert/strict";
import { build } from "esbuild";

test("the API client preserves ledger error codes for safe generation retries", async () => {
  const bundle=await build({entryPoints:['frontend/js/core/client.js'],bundle:true,write:false,format:'esm',define:{__RUNTIME__:'"server"',__API_BASE__:'""'}});
  const client=await import('data:text/javascript;base64,'+Buffer.from(bundle.outputFiles[0].text).toString('base64'));
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>new Response(JSON.stringify({detail:{code:'PACKAGE_IN_PROGRESS',message:'Still in progress'}}),{status:409,headers:{'Content-Type':'application/json'}});
    await assert.rejects(client.api('/api/package',{}),error=>error.status===409&&error.code==='PACKAGE_IN_PROGRESS'&&error.message==='Still in progress');
    globalThis.fetch=async()=>new Response(JSON.stringify({detail:{code:'CREDITS_EXHAUSTED'}}),{status:402,headers:{'Content-Type':'application/json'}});
    await assert.rejects(client.api('/api/package',{}),error=>error.status===402&&error.code==='CREDITS_EXHAUSTED');
  } finally { globalThis.fetch=original; }
});
