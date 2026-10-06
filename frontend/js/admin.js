import { API_BASE, BROWSER_ONLY } from './core/client.js';
import { ADMIN_TIMEZONE, activeDuration, dateRangePreset, trafficOverview, validDateRange } from './core/traffic.js';

export function mountAdmin(root) {
  let token = '', expiryTimer, panel = 'overview', offset = 0, selectedAccount = '', generation = 0, userStatus = 'all';
  const english = document.documentElement.lang === 'en';
  const tr = (de, en) => english ? en : de;
  root.innerHTML = `<div class="admin-intro"><img src="${new URL('static/boosty-3d.png', new URL(document.querySelector('meta[name="app-base"]')?.content || './', location.href))}" alt="Boosty" width="56" height="60"><div><p class="eyebrow">BOOSTY AI · ADMIN</p><h1>${tr('Dein Überblick. Geschützt.', 'Your overview. Protected.')}</h1><p>${tr('Konten, Bewerbungen und Nutzung an einem Ort.', 'Accounts, applications and usage in one place.')}</p></div></div>
  <p class="admin-message" role="status" aria-live="polite"></p><button type="button" class="button outline admin-auth-retry" hidden>${tr('Anmeldung erneut laden', 'Reload sign-in')}</button>
  <section class="admin-auth" hidden><h2>${tr('Admin-Anmeldung', 'Admin sign-in')}</h2><p class="admin-auth-description"></p>
  <form class="admin-login"><label class="field">E-Mail<input name="email" type="email" autocomplete="username" maxlength="254" required></label><label class="field">${tr('Passwort', 'Password')}<input name="password" type="password" autocomplete="current-password" minlength="14" maxlength="128" required></label><label class="field admin-code">${tr('Authenticator-Code', 'Authenticator code')}<input name="code" inputmode="numeric" pattern="[0-9]{6}" autocomplete="one-time-code" maxlength="6" required></label><button class="button primary">${tr('Geschützt anmelden', 'Sign in securely')}</button></form>
  <details class="admin-setup"><summary>${tr('Ersteinrichtung mit privatem Einrichtungscode', 'First setup with private setup code')}</summary><p>${tr('Der Betreiber erstellt den Code auf dem Server. Öffentliche Registrierung vergibt keine Adminrechte.', 'The operator creates the code on the server. Public registration never grants administrator rights.')}</p><form class="admin-begin"><label class="field">E-Mail<input name="email" type="email" required maxlength="254" autocomplete="username"></label><label class="field">${tr('Einrichtungscode', 'Setup code')}<input name="setup_code" type="password" required autocomplete="off" maxlength="100"></label><button class="button outline">${tr('Authenticator verbinden', 'Connect authenticator')}</button></form>
  <form class="admin-finish" hidden><div class="admin-totp-setup"><p>${tr('In deiner Authenticator-App einen zeitbasierten Eintrag (TOTP, SHA-1, 6 Ziffern, 30 Sekunden) für Boosty AI hinzufügen. Diesen Schlüssel manuell eintragen:', 'Add a time-based entry (TOTP, SHA-1, 6 digits, 30 seconds) for Boosty AI in your authenticator app. Enter this key manually:')}</p><code class="admin-secret"></code></div><label class="field">${tr('Eigenes Passwort (mindestens 14 Zeichen)', 'Your password (at least 14 characters)')}<input name="password" type="password" autocomplete="new-password" minlength="14" maxlength="128" required></label><label class="field admin-code">${tr('Aktueller Authenticator-Code', 'Current authenticator code')}<input name="code" inputmode="numeric" pattern="[0-9]{6}" autocomplete="one-time-code" required maxlength="6"></label><button class="button primary">${tr('Einrichtung abschließen', 'Complete setup')}</button></form></details></section>
  <section class="admin-dashboard" hidden><div class="admin-toolbar"><strong class="admin-email"></strong><span>${tr('Sitzung: höchstens 15 Minuten', 'Session: at most 15 minutes')}</span><button class="button outline admin-logout">${tr('Abmelden', 'Sign out')}</button></div><nav class="admin-nav" aria-label="Admin"><button type="button" data-view="overview">${tr('Übersicht', 'Overview')}</button><button type="button" data-view="users">${tr('Nutzer', 'Users')}</button><button type="button" data-view="sessions">${tr('Sitzungen', 'Sessions')}</button><button type="button" data-view="applications">${tr('Bewerbungen', 'Applications')}</button><button type="button" data-view="traffic">Traffic</button><button type="button" data-view="events">${tr('Nutzungsverlauf', 'Activity')}</button><button type="button" data-view="audit">${tr('Admin-Protokoll', 'Admin audit')}</button><button type="button" data-view="database">${tr('Datenbank', 'Database')}</button></nav><div class="admin-filter"><label class="field admin-period-field">${tr('Zeitraum (UTC)', 'Period (UTC)')}<select class="admin-period"><option value="today">${tr('Heute', 'Today')}</option><option value="yesterday">${tr('Gestern', 'Yesterday')}</option><option value="7">7 ${tr('Tage', 'days')}</option><option value="30" selected>30 ${tr('Tage', 'days')}</option><option value="90">90 ${tr('Tage', 'days')}</option><option value="custom">${tr('Eigener Zeitraum / einzelner Tag', 'Custom range / single day')}</option></select></label><label class="field admin-date-field">${tr('Von (einschließlich)', 'From (inclusive)')}<input class="admin-start" type="date" required></label><label class="field admin-date-field">${tr('Bis (einschließlich)', 'To (inclusive)')}<input class="admin-end" type="date" required></label><label class="field admin-status-field">${tr('Kontostatus', 'Account status')}<select class="admin-status"><option value="all">${tr('Alle Kundenkonten', 'All customer accounts')}</option><option value="pending">${tr('Bestätigung ausstehend', 'Verification pending')}</option><option value="verified">${tr('Bestätigt', 'Verified')}</option><option value="active">${tr('Im Zeitraum aktiv', 'Active in period')}</option><option value="new">${tr('Im Zeitraum registriert', 'Registered in period')}</option></select></label><label class="field admin-search-field">${tr('E-Mail oder Name suchen', 'Search email or name')}<input class="admin-search" type="search" maxlength="254"></label><button type="button" class="button outline admin-refresh">${tr('Aktualisieren', 'Refresh')}</button></div><p class="admin-range-caption"></p><div class="admin-content"></div><div class="admin-pagination"><button class="button quiet admin-prev">← ${tr('Zurück', 'Previous')}</button><span class="admin-page"></span><button class="button quiet admin-next">${tr('Weiter', 'Next')} →</button></div></section>`;
  const $ = s => root.querySelector(s), content = $('.admin-content');
  let setupCredentials, authReady = false, requiresTotp = true;
  function clear() {
    generation++; token = ''; clearTimeout(expiryTimer);
    $('.admin-dashboard').hidden = true; $('.admin-auth').hidden = false;
    content.replaceChildren(); $('.admin-email').textContent = ''; $('.admin-secret').textContent = '';
    $('.admin-finish').hidden = true; setupCredentials = null;
    root.querySelectorAll('input[type="password"],input[name="code"]').forEach(e => e.value = '');
  }
  async function request(path, body, method = body ? 'POST' : 'GET') {
    const requestGeneration = generation;
    const response = await fetch(API_BASE + '/api/admin/' + path, { method, credentials: 'include', headers: {'X-Boosty-Request':'1', ...(body ? {'Content-Type':'application/json'} : {}), ...(token ? {Authorization:`Bearer ${token}`} : {})}, ...(body ? {body:JSON.stringify(body)} : {}), signal:AbortSignal.timeout(20000) });
    const data = await response.json();
    if (requestGeneration !== generation) throw new Error(tr('Admin-Sitzung beendet.', 'Admin session ended.'));
    if (!response.ok) { if ((response.status === 401 || response.status === 403) && !$('.admin-dashboard').hidden) clear(); const error = new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || tr('Eingaben prüfen.', 'Check input.')); error.status = response.status; error.code = data.detail?.code; throw error; }
    return data;
  }
  const guarded = work => async e => { e?.preventDefault(); const buttons = [...root.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true); $('.admin-message').textContent=''; try {await work(e);} catch(error){$('.admin-message').textContent=error.message;} finally {buttons.forEach(b => b.disabled=false); authButtons();} };
  function authButtons() {
    root.querySelectorAll('.admin-login button,.admin-begin button,.admin-finish button').forEach(b => b.disabled = !authReady);
  }
  function authMode(value) {
    if (typeof value.requires_totp !== 'boolean') throw new Error(tr('Anmeldung konnte nicht geladen werden.', 'Sign-in could not be loaded.'));
    requiresTotp = value.requires_totp; authReady = true;
    $('.admin-auth').hidden = false;
    root.querySelectorAll('.admin-code').forEach(field => {
      field.hidden = !requiresTotp;
      const input = field.querySelector('input'); input.required = requiresTotp; input.disabled = !requiresTotp;
      if (!requiresTotp) input.value = '';
    });
    $('.admin-totp-setup').hidden = !requiresTotp;
    $('.admin-auth-description').textContent = requiresTotp
      ? tr('Passwort und Authenticator-Code erforderlich. Die Sitzung endet nach 15 Minuten.', 'Password and authenticator code required. Sessions expire after 15 minutes.')
      : tr('Melde dich mit deiner E-Mail-Adresse und deinem Passwort an. Die Sitzung endet nach 15 Minuten.', 'Sign in with your email address and password. Sessions expire after 15 minutes.');
    $('.admin-begin button').textContent = requiresTotp ? tr('Authenticator verbinden', 'Connect authenticator') : tr('Weiter zum Passwort', 'Continue to password');
    $('.admin-auth-retry').hidden = true; authButtons();
  }
  function credentials(form) {
    if (!authReady) throw new Error(tr('Bitte Anmeldung erneut laden.', 'Please reload sign-in.'));
    const body = Object.fromEntries(new FormData(form));
    if (!requiresTotp) delete body.code;
    return body;
  }
  async function initializeAuth() {
    authReady = false; authButtons(); $('.admin-auth-retry').hidden = true;
    $('.admin-message').textContent = tr('Anmeldung wird geladen …', 'Loading sign-in …');
    try { authMode(await request('auth-options')); }
    catch { $('.admin-message').textContent = tr('Die Anmeldung konnte nicht geladen werden. Bitte erneut versuchen.', 'Sign-in could not be loaded. Please try again.'); $('.admin-auth-retry').hidden = false; return; }
    $('.admin-message').textContent = '';
  }
  function label(text, element='p') { const el=document.createElement(element); el.textContent=text; return el; }
  function table(headers, rows) {const box=document.createElement('div'); box.className='admin-table-scroll'; const t=document.createElement('table'), h=document.createElement('tr');headers.forEach(x=>h.append(label(x,'th'))); const head=document.createElement('thead');head.append(h);t.append(head);const body=document.createElement('tbody');rows.forEach(values=>{const row=document.createElement('tr');values.forEach(v=>{const c=document.createElement('td');if(v instanceof Node)c.append(v);else c.textContent=v??'–';row.append(c);});body.append(row);});t.append(body);box.append(t);return box;}
  const date=v=>v?new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(v)?v:v+'Z').toLocaleString(english?'en-GB':'de-DE', {timeZone:ADMIN_TIMEZONE}):'–';
  function button(text,work) {const b=label(text,'button');b.type='button';b.className='button quiet';b.addEventListener('click',guarded(work));return b;}
  function jsonView(title,data) {content.replaceChildren(label(title,'h2'));const p=document.createElement('pre');p.className='admin-record';p.textContent=JSON.stringify(data,null,2);content.append(p);$('.admin-pagination').hidden=true;}
  function range() {
    const start = $('.admin-start').value, end = $('.admin-end').value;
    if (!validDateRange(start, end)) throw new Error(tr('Bitte einen gültigen Zeitraum wählen. Das Enddatum muss am oder nach dem Startdatum liegen.', 'Choose a valid range. The end date must be on or after the start date.'));
    return {start, end};
  }
  function applyPreset() {
    if ($('.admin-period').value === 'custom') return;
    const value = dateRangePreset($('.admin-period').value);
    $('.admin-start').value = value.start; $('.admin-end').value = value.end;
  }
  function pagination(total) {
    $('.admin-page').textContent = `${total ? offset + 1 : 0}–${Math.min(offset + 25, total)} / ${total}`;
    $('.admin-prev').hidden = offset === 0; $('.admin-next').hidden = offset + 25 >= total;
  }
  async function navigate(view, status = 'all') {
    panel = view; offset = 0; selectedAccount = '';
    userStatus = status; $('.admin-status').value = status;
    await load();
  }
  const profileFields = [
    ['display_name', tr('Anzeigename', 'Display name'), 'text', 120],
    ['first_name', tr('Vorname', 'First name'), 'text', 100],
    ['last_name', tr('Nachname', 'Last name'), 'text', 100],
    ['gender', tr('Geschlecht', 'Gender'), 'select', [['undisclosed', tr('Keine Angabe', 'Undisclosed')], ['female', tr('Weiblich', 'Female')], ['male', tr('Männlich', 'Male')], ['diverse', tr('Divers', 'Diverse')]]],
    ['date_of_birth', tr('Geburtsdatum (optional)', 'Date of birth (optional)'), 'date'],
    ['phone', tr('Telefon (optional)', 'Phone (optional)'), 'tel', 100],
    ['street', tr('Straße und Hausnummer', 'Street and number'), 'text', 300],
    ['postal_code', tr('Postleitzahl', 'Postal code'), 'text', 32],
    ['city', tr('Stadt', 'City'), 'text', 200],
    ['country', tr('Land (ISO-Code, z. B. DE)', 'Country (ISO code, e.g. DE)'), 'text', 2],
    ['spoken_languages', tr('Gesprochene Sprachen (mit Komma trennen)', 'Spoken languages (comma separated)'), 'text', 800],
    ['location', tr('Standort', 'Location'), 'text', 300],
    ['headline', tr('Profilüberschrift', 'Headline'), 'text', 300],
    ['language', tr('App-Sprache', 'App language'), 'select', [['de', 'Deutsch'], ['en', 'English'], ['sq', 'Shqip']]],
  ];
  function profileValue(profile, name) {
    return name === 'spoken_languages' ? (profile[name] || []).join(', ') : String(profile[name] ?? '');
  }
  function reasonField(name) {
    const field = label(tr('Supportgrund (5–500 Zeichen)', 'Support reason (5–500 characters)'), 'label');
    field.className = 'field admin-reason-field';
    const input = document.createElement('textarea'); input.name = name; input.required = true; input.minLength = 5; input.maxLength = 500; input.rows = 3;
    field.append(input); return field;
  }
  function reason(form) {
    const value = form.elements.reason.value.trim();
    if (value.length < 5 || value.length > 500) throw new Error(tr('Bitte einen Supportgrund mit 5–500 Zeichen angeben.', 'Enter a support reason with 5–500 characters.'));
    return value;
  }
  function profileEditor(account) {
    const section = document.createElement('section'); section.className = 'admin-support-profile';
    section.append(label(tr('Kontoprofil', 'Account profile'), 'h3'));
    const editable = !account.is_admin && !account.reserved_admin && account.profile_editable === true;
    if (!editable) {
      section.append(label(tr('Betreiberkonto · Profil ist hier schreibgeschützt.', 'Operator account · profile is read-only here.')));
      section.append(table([tr('Feld', 'Field'), tr('Wert', 'Value')], profileFields.map(([name, title]) => [title, profileValue(account.profile || {}, name) || '–'])));
      return section;
    }
    const form = document.createElement('form'); form.className = 'admin-profile-form';
    const fieldset = document.createElement('fieldset'); fieldset.className = 'admin-profile-grid';
    fieldset.append(label(tr('Profil für den Support bearbeiten', 'Edit profile for support'), 'legend'));
    let originalProfile = account.profile || {}, expectedUpdatedAt = account.profile_updated_at ?? null;
    profileFields.forEach(([name, title, type, options]) => {
      const field = label(title, 'label'); field.className = 'field';
      const input = document.createElement(type === 'select' ? 'select' : 'input'); input.name = name;
      if (type === 'select') options.forEach(([value, text]) => { const option = label(text, 'option'); option.value = value; input.append(option); });
      else { input.type = type; if (options) input.maxLength = options; }
      if (name === 'country') { input.pattern = '[A-Za-z]{2}'; input.autocapitalize = 'characters'; }
      if (name === 'date_of_birth') input.max = dateRangePreset('today').end;
      input.value = profileValue(originalProfile, name) || (name === 'gender' ? 'undisclosed' : name === 'language' ? 'de' : '');
      field.append(input); fieldset.append(field);
    });
    const notice = label('', 'p'); notice.className = 'admin-save-notice'; notice.setAttribute('role', 'status'); notice.setAttribute('aria-live', 'polite');
    const conflict = document.createElement('div'); conflict.className = 'admin-profile-conflict'; conflict.hidden = true;
    const save = label(tr('Profil speichern', 'Save profile'), 'button'); save.type = 'submit'; save.className = 'button primary';
    form.append(fieldset, reasonField('reason'), save, notice, conflict);
    const draft = () => {
      const profile = Object.fromEntries(profileFields.map(([name]) => [name, form.elements[name].value.trim()]));
      profile.country = profile.country.toUpperCase();
      profile.date_of_birth = profile.date_of_birth || null;
      profile.spoken_languages = profile.spoken_languages.split(',').map(value => value.trim()).filter(Boolean);
      if (profile.spoken_languages.length > 20 || profile.spoken_languages.some(value => value.length > 40)) throw new Error(tr('Maximal 20 Sprachen mit jeweils bis zu 40 Zeichen angeben.', 'Enter up to 20 languages, each up to 40 characters.'));
      return profile;
    };
    form.addEventListener('submit', guarded(async () => {
      const profile = draft(), supportReason = reason(form); notice.textContent = ''; conflict.hidden = true;
      try {
        const updated = await request(`users/${encodeURIComponent(account.id)}/profile`, {profile, expected_updated_at: expectedUpdatedAt, reason: supportReason}, 'PATCH');
        originalProfile = updated.profile || profile; expectedUpdatedAt = updated.profile_updated_at ?? updated.updated_at ?? null;
        profileFields.forEach(([name]) => { form.elements[name].value = profileValue(originalProfile, name); });
        form.elements.reason.value = ''; notice.textContent = tr('Profil gespeichert. Die Änderung wurde mit dem Supportgrund protokolliert.', 'Profile saved. The change and support reason were recorded.');
      } catch (error) {
        if (error.status !== 409) throw error;
        notice.textContent = tr('Das Profil wurde inzwischen geändert. Dein Entwurf bleibt erhalten.', 'The profile changed while you were editing. Your draft is preserved.');
        const current = await request(`users/${encodeURIComponent(account.id)}`);
        conflict.replaceChildren(label(tr('Aktuelle Serverwerte mit deinem Entwurf vergleichen. Danach kannst du den Entwurf erneut speichern.', 'Compare the current server values with your draft. You can then retry saving the draft.')));
        const fields = profileFields.filter(([name]) => profileValue(current.profile || {}, name) !== profileValue(profile, name));
        conflict.append(table([tr('Feld', 'Field'), tr('Aktueller Serverwert', 'Current server value'), tr('Dein Entwurf', 'Your draft')], fields.map(([name, title]) => [title, profileValue(current.profile || {}, name) || '–', profileValue(profile, name) || '–'])));
        conflict.append(button(tr('Werte geprüft · Entwurf erneut speichern', 'Values reviewed · save draft again'), async () => {
          const retry = await request(`users/${encodeURIComponent(account.id)}/profile`, {profile: draft(), expected_updated_at: current.profile_updated_at ?? null, reason: reason(form)}, 'PATCH');
          originalProfile = retry.profile || draft(); expectedUpdatedAt = retry.profile_updated_at ?? retry.updated_at ?? null;
          profileFields.forEach(([name]) => { form.elements[name].value = profileValue(originalProfile, name); });
          form.elements.reason.value = ''; conflict.hidden = true;
          notice.textContent = tr('Profil gespeichert. Die Änderung wurde mit dem Supportgrund protokolliert.', 'Profile saved. The change and support reason were recorded.');
        }));
        conflict.hidden = false;
      }
    }));
    section.append(form);
    if (account.password_reset_allowed === true) {
      const reset = document.createElement('form'); reset.className = 'admin-reset-form';
      const resetNotice = label('', 'p'); resetNotice.setAttribute('role', 'status'); resetNotice.setAttribute('aria-live', 'polite');
      const resetButton = label(tr('Passwort-Reset per E-Mail senden', 'Send password reset email'), 'button'); resetButton.type = 'submit'; resetButton.className = 'button outline';
      reset.append(label(tr('Passwort-Hilfe', 'Password support'), 'h3'), label(tr('Ein sicherer Reset-Link wird an die registrierte Adresse gesendet.', 'A secure reset link will be sent to the registered email address.')), reasonField('reason'), resetButton, resetNotice);
      reset.addEventListener('submit', guarded(async () => {
        await request(`users/${encodeURIComponent(account.id)}/password-reset`, {reason: reason(reset)});
        reset.elements.reason.value = ''; resetNotice.textContent = tr('Die Passwort-Reset-E-Mail wurde zum Versand vorgemerkt.', 'The password reset email was queued for delivery.');
      }));
      section.append(reset);
    }
    return section;
  }
  async function details(id) {
    selectedAccount = id; const value = await request('users/' + encodeURIComponent(id));
    content.replaceChildren(button(tr('← Zur Nutzerliste', '← Back to users'), () => navigate('users', userStatus)), label(value.email, 'h2'));
    content.append(label(`${tr('Kontotyp', 'Account type')}: ${value.is_admin || value.reserved_admin ? tr('Betreiber (schreibgeschützt)', 'Operator (read-only)') : tr('Kunde', 'Customer')} · ${tr('E-Mail', 'Email')}: ${value.verified_at ? tr('Bestätigt', 'Verified') : tr('Bestätigung ausstehend', 'Verification pending')}`));
    content.append(profileEditor(value), label(tr('Persönliche Inhalte nur für Supportzwecke öffnen. Jeder Zugriff wird protokolliert.', 'Open personal content only for support. Every access is audited.')));
    const {start, end} = range();
    const inRange = timestamp => !timestamp || (timestamp.slice(0, 10) >= start && timestamp.slice(0, 10) <= end);
    content.append(label(tr('Bewerbungen im Zeitraum', 'Applications in period'), 'h3'), table(['ID', tr('Titel', 'Title'), 'Status', tr('Aktion', 'Action')], (value.applications || []).filter(p => inRange(p.updated_at)).map(p => [p.id, p.title, p.status, button(tr('Inhalt öffnen', 'Open content'), () => applicationDetails(p.id))])));
    content.append(label(tr('Sitzungen im Zeitraum', 'Sessions in period'), 'h3'), table(['ID', tr('Erstellt (UTC)', 'Created (UTC)'), tr('Aktion', 'Action')], (value.sessions || []).filter(s => inRange(s.created_at)).map(s => [s.id, date(s.created_at), button(tr('Sitzung ansehen', 'View session'), async () => jsonView(s.id, await request('sessions/' + encodeURIComponent(s.id))))])), button(tr('Nutzungsverlauf dieses Kontos', 'Activity for this account'), async () => { panel = 'events'; offset = 0; await load(); }));
    $('.admin-pagination').hidden = true;
  }
  async function applicationDetails(id) {
    let current = await request('applications/' + encodeURIComponent(id));
    let expectedRevision = current.revision;
    content.replaceChildren(button(tr('← Zur Bewerbungsliste', '← Back to applications'), () => navigate('applications')), label(current.title || tr('Bewerbung', 'Application'), 'h2'));
    content.append(label(tr('Inhalte nur für den angefragten Support bearbeiten. Änderungen werden mit deinem Supportgrund protokolliert.', 'Edit content only for the requested support. Changes are recorded with your support reason.')));
    const form = document.createElement('form'); form.className = 'admin-application-form';
    const metadata = document.createElement('div'); metadata.className = 'admin-profile-grid';
    const titleField = label(tr('Titel', 'Title'), 'label'); titleField.className = 'field';
    const titleInput = document.createElement('input'); titleInput.name = 'title'; titleInput.maxLength = 200; titleInput.required = true; titleInput.value = current.title || ''; titleField.append(titleInput);
    const statusField = label('Status', 'label'); statusField.className = 'field';
    const statusInput = document.createElement('select'); statusInput.name = 'status';
    [['draft', tr('Entwurf', 'Draft')], ['ready', tr('Fertig', 'Ready')], ['sent', tr('Versendet', 'Sent')], ['interview', tr('Vorstellungsgespräch', 'Interview')], ['offer', tr('Angebot', 'Offer')], ['rejected', tr('Abgelehnt', 'Rejected')]].forEach(([value, text]) => { const option = label(text, 'option'); option.value = value; statusInput.append(option); });
    statusInput.value = current.status || 'draft'; statusField.append(statusInput); metadata.append(titleField, statusField); form.append(metadata);
    const documentFields = [['cv', tr('Lebenslauf (Text / Markdown)', 'CV (text / Markdown)')], ['cover_letter', tr('Anschreiben', 'Cover letter')], ['motivation_letter', tr('Motivationsschreiben', 'Motivation letter')], ['email', tr('Bewerbungs-E-Mail', 'Application email')]];
    const editable = current.editable === true;
    const textField = (name, title, value, maxLength, rows) => {
      const field = label(title, 'label'); field.className = 'field'; const input = document.createElement('textarea');
      input.name = name; input.value = typeof value === 'string' ? value : ''; input.maxLength = maxLength; input.rows = rows; input.readOnly = !editable; field.append(input); return field;
    };
    form.append(textField('notes', tr('Notizen', 'Notes'), current.data?.notes, 4000, 4));
    documentFields.forEach(([name, title]) => form.append(textField(name, title, current.data?.documents?.[name], 60000, 12)));
    titleInput.readOnly = !editable; statusInput.disabled = !editable;
    const notice = label('', 'p'); notice.className = 'admin-save-notice'; notice.setAttribute('role', 'status'); notice.setAttribute('aria-live', 'polite');
    if (editable) {
      const save = label(tr('Bewerbung speichern', 'Save application'), 'button'); save.type = 'submit'; save.className = 'button primary';
      const conflict = document.createElement('div'); conflict.className = 'admin-profile-conflict'; conflict.hidden = true;
      form.append(reasonField('reason'), save, notice, conflict);
      const payload = revision => ({
        title: titleInput.value.trim(), status: statusInput.value, notes: form.elements.notes.value,
        documents: Object.fromEntries(documentFields.filter(([name]) => form.elements[name].value !== (typeof current.data?.documents?.[name] === 'string' ? current.data.documents[name] : '')).map(([name]) => [name, form.elements[name].value])),
        expected_revision: revision, reason: reason(form),
      });
      const saveVersion = async revision => {
        current = await request(`applications/${encodeURIComponent(id)}`, payload(revision), 'PATCH');
        expectedRevision = current.revision; titleInput.value = current.title; statusInput.value = current.status;
        form.elements.notes.value = current.data?.notes || '';
        documentFields.forEach(([name]) => {form.elements[name].value = typeof current.data?.documents?.[name] === 'string' ? current.data.documents[name] : '';});
        form.elements.reason.value = ''; conflict.hidden = true;
        notice.textContent = tr('Bewerbung gespeichert. Die Änderung wurde mit dem Supportgrund protokolliert.', 'Application saved. The change and support reason were recorded.');
      };
      form.addEventListener('submit', guarded(async () => {
        notice.textContent = ''; conflict.hidden = true;
        try { await saveVersion(expectedRevision); }
        catch (error) {
          if (error.status !== 409) throw error;
          notice.textContent = tr('Die Bewerbung wurde inzwischen geändert. Dein Entwurf bleibt erhalten.', 'The application changed while you were editing. Your draft is preserved.');
          const latest = await request('applications/' + encodeURIComponent(id));
          conflict.replaceChildren(label(tr('Aktuelle Inhalte vor erneutem Speichern prüfen:', 'Review the current content before saving again:')));
          const latestContent = document.createElement('details'); latestContent.append(label(tr('Aktuelle Serverwerte anzeigen', 'Show current server values'), 'summary'));
          latestContent.append(table([tr('Feld', 'Field'), tr('Aktueller Wert', 'Current value')], [[tr('Titel', 'Title'), latest.title], ['Status', latest.status], [tr('Notizen', 'Notes'), latest.data?.notes || '–']]));
          documentFields.forEach(([name, title]) => { const section = document.createElement('details'); section.append(label(title, 'summary')); const pre = label(latest.data?.documents?.[name] || '–', 'pre'); pre.className = 'admin-record'; section.append(pre); latestContent.append(section); });
          conflict.append(latestContent, button(tr('Inhalte geprüft · Entwurf erneut speichern', 'Content reviewed · save draft again'), () => saveVersion(latest.revision))); conflict.hidden = false;
        }
      }));
    } else form.append(label(tr('Diese Bewerbung ist im Support schreibgeschützt.', 'This application is read-only in support.')));
    content.append(form); $('.admin-pagination').hidden = true;
  }
  function metricCard(count, title, destination, status) {
    const card = document.createElement('button'); card.type = 'button'; card.className = 'admin-metric-card';
    card.append(label(String(count ?? 0), 'strong'), label(title, 'span'), label(tr('Details ansehen →', 'View details →'), 'small'));
    card.addEventListener('click', guarded(() => { $('.admin-search').value = ''; return navigate(destination, status); })); return card;
  }
  async function overview(params) {
    const value = await request('overview?' + params);
    const grid = document.createElement('div'); grid.className = 'admin-metrics';
    const metrics = [
      ['accounts', tr('Registrierte Kundenkonten', 'Registered customer accounts'), 'users', 'all'],
      ['pending_verifications', tr('E-Mail-Bestätigung ausstehend', 'Email verification pending'), 'users', 'pending'],
      ['verified_users', tr('Bestätigte Nutzerkonten', 'Verified user accounts'), 'users', 'verified'],
      ['new_accounts', tr('Neue Konten im Zeitraum', 'New accounts in period'), 'users', 'new'],
      ['applications', tr('Gespeicherte Bewerbungen im Zeitraum', 'Saved applications in period'), 'applications'],
      ['page_views', tr('Seitenaufrufe im Zeitraum', 'Page views in period'), 'traffic'],
      ['visit_sessions', tr('Besuchssitzungen im Zeitraum', 'Visit sessions in period'), 'traffic'],
      ['active_accounts', tr('Aktive Konten im Zeitraum', 'Active accounts in period'), 'users', 'active'],
    ];
    metrics.forEach(([key, title, destination, status]) => grid.append(metricCard(value.totals?.[key], title, destination, status)));
    if (value.ai_usage) { const ai = value.ai_usage; grid.append(label(`${ai.calls} OpenAI · ${ai.input_tokens + ai.output_tokens} Tokens · ≈ $${Number(ai.estimated_usd || 0).toFixed(4)}`, 'article')); }
    if (value.email_delivery) { const mail = value.email_delivery; grid.append(label(`${tr('E-Mail-Versand', 'Email delivery')}: ${mail.pending} ${tr('ausstehend', 'pending')} · ${mail.failed} ${tr('fehlgeschlagen / abgelaufen', 'failed / expired')}`, 'article')); }
    const daily = value.daily || [], timezone = value.timezone || ADMIN_TIMEZONE;
    content.append(grid, trafficOverview(daily, english, timezone), label(tr(value.measurement || 'Seitenaufrufe und gestartete App-Sitzungen; keine eindeutigen Personen.', 'Page views and started app sessions, not unique people. Bots, reloads and previews may be included.')), table([`${tr('Tag', 'Day')} (${timezone})`, tr('Aufrufe', 'Views'), tr('Sitzungen', 'Sessions'), tr('Registrierungen', 'Registrations')], daily.map(v => [v.day, v.page_views, v.visit_sessions, v.registrations])), label(tr('Verwendete Funktionen', 'Functions used'), 'h3'), table([tr('Funktion', 'Function'), tr('Anzahl', 'Count')], (value.operations || []).map(v => [v.event, v.count])));
  }
  function traffic(value) {
    content.append(label(tr('Besuche mit Einwilligung', 'Visits with consent'), 'h2'));
    const metrics = document.createElement('div'); metrics.className = 'admin-metrics admin-traffic-metrics';
    [
      [String(value.totals?.visits ?? 0), tr('Erfasste Besuche', 'Recorded visits')],
      [activeDuration(value.totals?.active_seconds), tr('Aktive Zeit insgesamt', 'Total active time')],
      [activeDuration(value.totals?.avg_active_seconds), tr('Ø aktive Zeit pro Besuch', 'Average active time per visit')],
    ].forEach(([count, title]) => { const card = document.createElement('article'); card.append(label(count, 'strong'), label(title)); metrics.append(card); });
    content.append(metrics, label(tr('Die bisherigen aggregierten Seitenaufrufe enthalten keine nachträglich rekonstruierbaren Angaben zu Gerät, Land oder IP. Die Besuchsliste erfasst ausschließlich neue Besuche mit Einwilligung. Aktive Sekunden messen Aktivität bei sichtbarer Seite, nicht die genaue Aufmerksamkeit eines Menschen.', 'Existing aggregate page counts cannot be enriched retroactively with device, country or IP data. This list records only new visits with consent. Active seconds measure activity while the page is visible, not a person’s exact attention.')));
    if (value.measurement) content.append(label(value.measurement));
    content.append(label(tr('Länder werden ungefähr aus der IP abgeleitet. Bei fehlender Zuordnung erscheint „Unbekannt“. Maskierte IP-Adressen verfallen nach der Aufbewahrungsfrist.', 'Countries are approximate IP-based locations. Missing locations appear as “Unknown”. Masked IP addresses expire after the retention period.')));
    const attribution = label('IP Geolocation by DB-IP', 'a'); attribution.href = 'https://db-ip.com'; attribution.target = '_blank'; attribution.rel = 'noopener noreferrer'; content.append(attribution);
    const breakdown = document.createElement('div'); breakdown.className = 'admin-traffic-breakdowns';
    const device = value => ({desktop: tr('Computer', 'Desktop'), mobile: tr('Mobilgerät', 'Mobile'), tablet: 'Tablet', unknown: tr('Unbekannt', 'Unknown')}[value] || value || tr('Unbekannt', 'Unknown'));
    const country = value => !value || value === 'unknown' ? tr('Unbekannt', 'Unknown') : value;
    const devices = document.createElement('section'); devices.append(label(tr('Geräte', 'Devices'), 'h3'), table([tr('Gerät', 'Device'), tr('Besuche', 'Visits')], (value.devices || []).map(v => [device(v.device), v.visits])));
    const countries = document.createElement('section'); countries.append(label(tr('Länder', 'Countries'), 'h3'), table([tr('Land', 'Country'), tr('Besuche', 'Visits')], (value.countries || []).map(v => [country(v.country), v.visits])));
    breakdown.append(devices, countries); content.append(breakdown);
    content.append(label(tr('Besuchsdetails', 'Visit details'), 'h3'), table([tr('Start (UTC)', 'Started (UTC)'), tr('Zuletzt gesehen (UTC)', 'Last seen (UTC)'), tr('Seite', 'Page'), tr('Gerät', 'Device'), tr('Land', 'Country'), tr('IP (maskiert)', 'IP (masked)'), tr('Aktive Zeit', 'Active time'), tr('Verstrichene Zeit', 'Elapsed time')], (value.items || []).map(v => [date(v.started_at), date(v.last_seen_at), v.page || '–', device(v.device), country(v.country), v.ip_masked || tr('Nicht erfasst / abgelaufen', 'Not recorded / expired'), activeDuration(v.active_seconds), activeDuration(v.elapsed_seconds)])));
    if (!value.items?.length) content.append(label(tr('In diesem Zeitraum wurden noch keine Besuche mit Einwilligung erfasst.', 'No visits with consent were recorded in this period yet.')));
  }
  async function load() {
    const dates = range();
    content.replaceChildren();
    $('.admin-pagination').hidden = ['overview', 'database'].includes(panel);
    $('.admin-search-field').hidden = panel !== 'users'; $('.admin-status-field').hidden = panel !== 'users';
    $('.admin-status').value = userStatus;
    root.querySelectorAll('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === panel)));
    $('.admin-range-caption').textContent = panel === 'database' ? tr('Tabellenbestand und sichere Supportansichten.', 'Table counts and safe support views.') : `${dates.start} – ${dates.end} · ${ADMIN_TIMEZONE} · ${tr('beide Tage einschließlich', 'both dates inclusive')}`;
    const params = new URLSearchParams({...dates, offset, limit: 25}); let value;
    if (panel === 'overview') { await overview(new URLSearchParams(dates)); return; }
    if (panel === 'database') {
      value = await request('database');
      const routes = {accounts: 'users', account_profiles: 'users', account_security: 'users', sessions: 'sessions', cv_documents: 'sessions', generations: 'sessions', generations_v2: 'sessions', messages: 'sessions', applications: 'applications', activities: 'events', activity: 'events', daily_metrics: 'traffic', traffic_visits: 'traffic', admin_audits: 'audit', admin_audit: 'audit'};
      content.append(label(`${value.engine} · ${tr('Integrität', 'Integrity')}: ${value.integrity}`, 'h2'), table([tr('Tabelle', 'Table'), tr('Datensätze', 'Records'), tr('Supportansicht', 'Support view')], (value.tables || []).map(v => [v.name, v.rows, routes[v.name] ? button(tr('Datensätze öffnen', 'Open records'), () => navigate(routes[v.name])) : tr('Nur Anzahl verfügbar', 'Count only')])), label(tr(value.note || 'Sichere Supportansichten.', 'Protected support views. Password hashes, keys and tokens are excluded.')));
      return;
    }
    if (panel === 'users') { params.set('q', $('.admin-search').value.trim()); params.set('status', userStatus); }
    if (panel === 'events' && selectedAccount) params.set('account_id', selectedAccount);
    value = await request(panel + '?' + params);
    if (panel === 'users') {
      content.append(label(tr('Kundenkonten', 'Customer accounts'), 'h2'), label(tr('Alle, ausstehende und bestätigte Konten zeigen den aktuellen Kundenbestand. Der Zeitraum gilt für neue und aktive Konten.', 'All, pending and verified accounts show the current customer inventory. The range applies to new and active accounts.')), table(['E-Mail', tr('Name', 'Name'), tr('Telefon', 'Phone'), tr('Registriert (UTC)', 'Registered (UTC)'), tr('Bestätigt', 'Verified'), tr('Zuletzt aktiv (UTC)', 'Last active (UTC)'), tr('Bewerbungen', 'Applications'), tr('Aktion', 'Action')], (value.items || []).map(v => [v.email, [v.first_name, v.last_name].filter(Boolean).join(' ') || v.display_name || '–', v.phone || v.profile?.phone || '–', date(v.created_at), v.is_admin ? tr('Betreiber', 'Operator') : v.verified_at ? date(v.verified_at) : tr('Ausstehend', 'Pending'), date(v.last_active_at), v.applications, button(tr('Details', 'Details'), () => details(v.id))])));
      if (!value.items?.length) content.append(label(tr('Keine Konten für diese Suche und diesen Filter gefunden.', 'No accounts match this search and filter.')));
    } else if (panel === 'applications') content.append(label(tr('Bewerbungen im Zeitraum', 'Applications in period'), 'h2'), table([tr('Titel', 'Title'), 'E-Mail', 'Status', tr('Aktualisiert (UTC)', 'Updated (UTC)'), tr('Aktion', 'Action')], (value.items || []).map(v => [v.title, v.email || tr('Anonym / unbekannt', 'Anonymous / unknown'), v.status, date(v.updated_at), button(tr('Inhalte / bearbeiten', 'Content / edit'), () => applicationDetails(v.id))])));
    else if (panel === 'traffic') traffic(value);
    else if (panel === 'sessions') content.append(table(['ID', tr('Konto-ID', 'Account ID'), tr('Erstellt (UTC)', 'Created (UTC)'), tr('Aktion', 'Action')], (value.items || []).map(v => [v.id, v.owner_id || tr('Anonym', 'Anonymous'), date(v.created_at), button(tr('Inhalte', 'Content'), async () => jsonView(v.id, await request('sessions/' + encodeURIComponent(v.id))))])));
    else if (panel === 'audit') content.append(table([tr('Zeit (UTC)', 'Time (UTC)'), tr('Betreiber', 'Operator'), tr('Aktion', 'Action'), tr('Ziel', 'Subject'), tr('Supportgrund', 'Support reason'), tr('Geänderte Felder', 'Changed fields')], (value.items || []).map(v => [date(v.created_at), v.email || '–', v.action, v.subject_id || '–', v.reason || '–', Array.isArray(v.changed_fields) ? v.changed_fields.join(', ') : '–'])));
    else content.append(table([tr('Zeit (UTC)', 'Time (UTC)'), tr('Konto', 'Account'), tr('Ereignis', 'Event'), 'HTTP'], (value.items || []).map(v => [date(v.created_at), v.email || tr('Anonym / unbekannt', 'Anonymous / unknown'), v.event, v.outcome])));
    pagination(value.total || 0);
  }
  async function signedIn(value) {token=value.access_token||'';$('.admin-email').textContent=value.email;$('.admin-auth').hidden=true;$('.admin-dashboard').hidden=false;root.querySelectorAll('form').forEach(f=>f.reset());applyPreset();$('.admin-secret').textContent='';setupCredentials=null;clearTimeout(expiryTimer);expiryTimer=setTimeout(()=>{clear();$('.admin-message').textContent=tr('Sitzung abgelaufen. Bitte erneut anmelden.','Session expired. Sign in again.');},(value.expires_in||900)*1000);await load();}
  $('.admin-login').addEventListener('submit',guarded(async e=>signedIn(await request('login',credentials(e.target)))));
  $('.admin-begin').addEventListener('submit',guarded(async e=>{setupCredentials=credentials(e.target);const value=await request('setup/begin',setupCredentials);authMode(value);$('.admin-secret').textContent=value.secret||'';$('.admin-finish').hidden=false;}));
  $('.admin-finish').addEventListener('submit',guarded(async e=>signedIn(await request('setup/finish',{...setupCredentials,...credentials(e.target)}))));
  $('.admin-logout').addEventListener('click',guarded(async()=>{try{await request('logout',{});}finally{clear();}}));
  root.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',guarded(() => navigate(b.dataset.view))));
  $('.admin-refresh').addEventListener('click',guarded(async()=>{offset=0;await load();}));$('.admin-prev').addEventListener('click',guarded(async()=>{offset=Math.max(0,offset-25);await load();}));$('.admin-next').addEventListener('click',guarded(async()=>{offset+=25;await load();}));
  $('.admin-period').addEventListener('change',guarded(async () => {applyPreset(); offset = 0; await load();}));
  root.querySelectorAll('.admin-start,.admin-end').forEach(input => input.addEventListener('change',guarded(async () => {$('.admin-period').value = 'custom'; offset = 0; await load();})));
  $('.admin-status').addEventListener('change',guarded(async () => {userStatus = $('.admin-status').value; offset = 0; await load();}));
  $('.admin-search').addEventListener('keydown',e => {if(e.key === 'Enter') guarded(async () => {offset = 0; await load();})(e);});
  applyPreset();
  if(BROWSER_ONLY){$('.admin-auth').hidden=true;$('.admin-message').textContent=tr('Der Adminbereich benötigt den App-Server.','Administration requires the app server.');}
  else { authButtons(); initializeAuth().then(() => { if (authReady) request('me').then(signedIn).catch(()=>{}); }); }
  $('.admin-auth-retry').addEventListener('click',guarded(initializeAuth));
  return {clear};
}
