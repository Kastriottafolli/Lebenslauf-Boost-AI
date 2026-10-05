/* Only immutable application assets. Never cache API responses, documents or keys. */
const CACHE='boosty-shell-__BUILD_ID__';
const scope=new URL(self.registration.scope);
const SHELL=['','index.html','assets/css/professional.css?v=__BUILD_ID__','assets/js/app.js?v=__BUILD_ID__','static/icon.svg','static/boosti.svg','static/boosty-3d.png','static/fonts/NotoSans-Regular.ttf','static/fonts/NotoSans-Bold.ttf','static/fonts/NotoSerif-Regular.ttf','static/fonts/NotoSerif-Bold.ttf',...__PRECACHE_CHUNKS__];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL.map(path=>new URL(path,scope).href))));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  if(url.pathname.replace(/\/$/,'').endsWith('/admin'))return;
  if(request.method!=='GET'||url.origin!==scope.origin||url.pathname.includes('/api/')||!url.pathname.startsWith(scope.pathname))return;
  const path=url.pathname.slice(scope.pathname.length);
  if(request.mode==='navigate'){event.respondWith(fetch(request).catch(()=>caches.match(new URL('index.html',scope))));return;}
  // Static paths are controlled by the build; user uploads are never served here.
  if(!/^(assets\/|static\/|manifest\.webmanifest$)/.test(path))return;
  event.respondWith(caches.match(request).then(cached=>cached||fetch(request).then(response=>{if(response.ok&&response.type!=='opaque'){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(request,copy));}return response;})));
});
