// Only explicit labelled facts are imported from pasted text; uncertain fields stay blank.
export function jobDetails(description) {
 const field = labels => description.match(new RegExp(`^(?:${labels})\\s*:\\s*([^\\n]+)$`,'im'))?.[1]?.trim().slice(0,200) || '';
 const title=field('Position|Job title|Role|Stellentitel|Pozicioni|Titulli i punës');
 const company=field('Firma|Unternehmen|Company|Employer|Kompania|Punëdhënësi');
 const email=field('E-Mail|Email|Kontakt-E-Mail|Contact email|Email i kontaktit');
 return {title,company,email:/^[\w.+-]+@[\w.-]+\.[a-z]{2,}$/i.test(email)?email:''};
}
