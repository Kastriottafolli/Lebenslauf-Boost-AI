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

test("optional registration details normalize dates and languages and allowlist profile fields",()=>{
 const base={email:" user@example.com ",password:"  password with intentional spaces  ",displayName:" Era ",language:"sq",termsAccepted:true,privacyAcknowledged:true};
 const payload=registrationPayload({...base,profile:{first_name:" Era ",last_name:" Tafolli ",phone:"",gender:"undisclosed",date_of_birth:"",street:" Street 1 ",postal_code:" 10115 ",city:" Berlin ",country:" de ",spoken_languages:[" sq "," English "],role:"admin",password_hash:"secret",credits:999,verified:true,preferences:{email_notifications:true}}});
 assert.equal(payload.first_name,"Era");assert.equal(payload.last_name,"Tafolli");assert.equal(payload.phone,"");assert.equal(payload.date_of_birth,null);assert.equal(payload.country,"DE");assert.deepEqual(payload.spoken_languages,["sq","English"]);assert.equal(payload.password,base.password);
 for(const key of ["role","password_hash","credits","verified","preferences"])assert.equal(payload[key],undefined,key);
 const minimal=registrationPayload(base);assert.equal(minimal.first_name,undefined);assert.equal(minimal.date_of_birth,undefined);assert.equal(minimal.phone,undefined);
});

test("registration rejects impossible or future dates and bounds optional personal details",()=>{
 const base={email:"user@example.com",password:"private-password",termsAccepted:true,privacyAcknowledged:true};
 const future=new Date(Date.now()+86400000).toISOString().slice(0,10);
 for(const profile of [{date_of_birth:"2025-02-29"},{date_of_birth:"1990-13-01"},{date_of_birth:"1990-01-01T00:00:00Z"},{date_of_birth:future},{date_of_birth:false},{gender:"other"},{country:"Germany"},{country:"12"},{first_name:"x".repeat(101)},{spoken_languages:Array(21).fill("de")},{spoken_languages:["x".repeat(41)]},{spoken_languages:[" "]},{spoken_languages:[42]}])assert.throws(()=>registrationPayload({...base,profile}),/PROFILE_INVALID/);
 assert.equal(registrationPayload({...base,profile:{date_of_birth:"2000-02-29"}}).date_of_birth,"2000-02-29");
 assert.throws(()=>registrationPayload({...base,displayName:"x".repeat(201)}),/PROFILE_INVALID/);
});

test("profile reading keeps the optional personal details and timestamp without copying privileged fields",()=>{
 const value=readAccountProfile({profile:{display_name:"x".repeat(200),gender:"female",date_of_birth:"1990-12-31",street:"Example street",postal_code:"10115",city:"Berlin",country:"DE",spoken_languages:["de","sq","Italian",42],language:"en",updated_at:"2026-10-06T12:34:56.123456Z",role:"admin",recovery_hash:"secret"}});
 assert.equal(value.display_name.length,200);assert.equal(value.gender,"female");assert.equal(value.date_of_birth,"1990-12-31");assert.equal(value.city,"Berlin");assert.deepEqual(value.spoken_languages,["de","sq","Italian"]);assert.equal(value.language,"en");assert.equal(value.updated_at,"2026-10-06T12:34:56.123456Z");assert.equal(value.role,undefined);assert.equal(value.recovery_hash,undefined);
 const empty=readAccountProfile({});assert.equal(empty.gender,"undisclosed");assert.equal(empty.date_of_birth,null);assert.deepEqual(empty.spoken_languages,[]);
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

test("all personal fields stay optional and account form labels have German English and Albanian copy",async()=>{
 const html=await readFile("frontend/index.html","utf8");
 const registration=html.match(/<div id="registerNameField"[\s\S]*?<\/details>\s*<\/div>/)[0];
 const profile=html.match(/<form id="accountProfileForm"[\s\S]*?<\/form>/)[0];
 assert.ok(!/\brequired\b/.test(registration));assert.ok(!/\brequired\b/.test(profile));assert.match(registration,/<details><summary[^>]*data-sq=/);
 for(const region of [registration,profile])for(const label of region.matchAll(/<label class="field"><span([^>]*)>/g))for(const language of ["de","en","sq"])assert.ok(label[1].includes(`data-${language}=`));
 for(const prefix of ["register-profile-","account-profile-"])for(const field of ["first_name","last_name","phone","gender","date_of_birth","street","postal_code","city","country","spoken_languages","other_languages"])assert.ok(html.includes(`id="${prefix}${field}"`),prefix+field);
 for(const prefix of ["register-profile-","account-profile-"])assert.match(html,new RegExp(`<select id="${prefix}spoken_languages" multiple`));
 assert.match(profile,/Bevorzugte Kontosprache/);assert.match(profile,/Du wählst die Sprache jeder Bewerbung weiterhin separat/);
});
