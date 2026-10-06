import test from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {TERMS_VERSION,consumeAccountLink,registrationPayload,readAccountProfile,accountErrorCopy,explainerMedia} from "../js/core/account.js";

test("verification and reset links clear secrets from navigation before retaining them in memory",()=>{
 for(const kind of ["verify-email","reset-password"]){
  const token="synthetic-token-"+"x".repeat(40),location={href:`https://tafolliboost.com/?lang=sq#${kind}=${token}`};
  let clean;
  const result=consumeAccountLink(location,{replaceState(_state,_title,url){clean=url;}});
  assert.deepEqual(result,{kind,token});assert.equal(new URL(clean).hash,"");assert.equal(new URL(clean).searchParams.get("lang"),"sq");assert.ok(!clean.includes(token));
 }
});

test("malformed or duplicate email tokens are removed and never used",()=>{
 for(const fragment of ["#verify-email=short","#reset-password=not%20a%20token","#verify-email="+"x".repeat(40)+"&verify-email="+"y".repeat(40)]){
  let changed=false;
  assert.equal(consumeAccountLink({href:"https://tafolliboost.com/"+fragment},{replaceState(){changed=true;}}).token,null);
  assert.equal(changed,true);
 }
 assert.equal(consumeAccountLink({href:"https://tafolliboost.com/#how-it-works"},{replaceState(){throw Error("unchanged");}}),null);
});

test("registration separates explicit terms agreement from privacy acknowledgement",()=>{
 const values={email:" user@example.com ",password:"synthetic-safe-password",language:"sq",displayName:" Era ",termsAccepted:true,privacyAcknowledged:true};
 assert.deepEqual(registrationPayload(values),{email:"user@example.com",password:values.password,display_name:"Era",language:"sq",terms_version:TERMS_VERSION,terms_accepted:true,privacy_acknowledged:true});
 for(const field of ["termsAccepted","privacyAcknowledged"]){assert.throws(()=>registrationPayload({...values,[field]:false}),/TERMS_REQUIRED/);assert.throws(()=>registrationPayload({...values,[field]:"true"}),/TERMS_REQUIRED/);}
});

test("account profile retains only its own editable fields, without inventing CV facts",()=>{
 const profile=readAccountProfile({profile:{display_name:"Era",first_name:"Era",headline:"Designer",language:"sq",password:"secret",preferences:{email_notifications:"true"}}});
 assert.equal(profile.display_name,"Era");assert.equal(profile.language,"sq");assert.equal(profile.first_name,"Era");assert.equal(profile.last_name,"");assert.equal(profile.preferences.email_notifications,false);assert.equal(profile.password,undefined);
});

test("account errors offer translated recovery actions without displaying private server errors",()=>{
 assert.match(accountErrorCopy({code:"EMAIL_VERIFICATION_REQUIRED"},"en"),/Confirm/);
 assert.match(accountErrorCopy({code:"ACCOUNT_LINK_INVALID"},"de"),/abgelaufen/);
 for(const language of ["de","en","sq"])assert.ok(!accountErrorCopy({message:"private exception password=secret"},language).includes("secret"));
});

test("explainer switches audio, captions and poster together and keeps assets on the current app",()=>{
 for(const language of ["de","en","sq"]){const media=explainerMedia(language,"https://tafolliboost.com/");assert.equal(media.video,`https://tafolliboost.com/static/video/tafolliboost-${language}.mp4`);assert.equal(media.captions,`https://tafolliboost.com/static/video/tafolliboost-${language}.vtt`);assert.ok(media.poster.endsWith(`poster-${language}.jpg`));}
 assert.ok(explainerMedia("invalid","https://example.com/project/").video.endsWith("/project/static/video/tafolliboost-de.mp4"));
});

test("account templates keep deletion behind settings and a separate confirmed form; IDs stay unique",async()=>{
 const html=await readFile("frontend/index.html","utf8");
 const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(match=>match[1]);assert.equal(new Set(ids).size,ids.length,"duplicate DOM IDs can break account forms");
 for(const id of ["accountProfileForm","accountDocuments","exportAccount","registerTerms","registerPrivacy","deleteAccountForm","deleteAccountPassword","deleteAccountConfirmation","acceptTermsForm","withdrawalForm"])assert.ok(ids.includes(id),id);
 const registration=html.match(/<div id="registrationTerms"[\s\S]*?<\/div>/)[0];assert.ok(!/\bchecked\b/.test(registration));
 const payment=html.match(/<div id="checkoutConsents"[\s\S]*?<\/div>/)[0];assert.ok(!/\bchecked\b/.test(payment));
 assert.match(html,/<details class="account-danger">[\s\S]*?id="deleteAccount"[\s\S]*?<\/details>/);
 assert.match(html,/<video id="explainerVideo" controls playsinline preload="none"/);assert.ok(!/<video[^>]*autoplay/.test(html));assert.match(html,/kind="captions"/);
});
