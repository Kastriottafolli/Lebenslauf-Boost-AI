// Only explicit labelled facts are imported from pasted text; uncertain fields stay blank.
export function jobDetails(description) {
 const field = labels => description.match(new RegExp(`^(?:${labels})\\s*:\\s*([^\\n]+)$`,'im'))?.[1]?.trim().slice(0,200) || '';
 const title=field('Position|Job title|Role|Stellentitel|Pozicioni|Titulli i punës');
 const company=field('Firma|Unternehmen|Company|Employer|Kompania|Punëdhënësi');
 const email=field('E-Mail|Email|Kontakt-E-Mail|Contact email|Email i kontaktit');
 return {title,company,email:/^[\w.+-]+@[\w.-]+\.[a-z]{2,}$/i.test(email)?email:''};
}

export function validJobUrl(value) {
 let url;
 try { url=new URL(value.trim()); } catch { return null; }
 if(!['https:','http:'].includes(url.protocol)||url.username||url.password||value.length>2000) return null;
 return url.href;
}

// Never show server/parser internals when a job board blocks an import.
export function jobImportProblem(error) {
 if(error.status===429) return 'busy';
 if(error.code==='API_TIMEOUT') return 'timeout';
 if(error.status===401||error.status===403 && error.code==='ACCOUNT_REQUIRED') return 'login';
 return 'blocked';
}
