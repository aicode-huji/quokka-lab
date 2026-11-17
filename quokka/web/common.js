// Shared helpers and UI pieces for every window. Plain JavaScript, no libraries.
//
// Each piece (Webmail, RonitInbox, Shell, Draft, Release, LevelHeader, Brief,
// DefendView) is a
// small object with an update(data) method. A page builds the pieces it needs
// and feeds them its /state JSON every poll. Mission control (port 9080) uses
// all of them; the single windows (9081-9083) use their own subset.

const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g,
  c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const nl = s => esc(s).replace(/\n/g, '<br>');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const plural = (n, word) => n + ' ' + word + (n === 1 ? '' : 's');
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// The levels come from the server's level list (state.py, levels/__init__.py):
// each has its group ("part": 1, 2 or "own", a level a student added, shown as
// "Your levels"), the number on its button ("short") and its name ("Level 3",
// "Part 2, Level 1", "Your level 1"). poll() learns them from every /state.
const LEVEL_INFO = {};
function learnLevels(list) { (list || []).forEach(l => { LEVEL_INFO[l.number] = l; }); }
const partOf = n => (LEVEL_INFO[n] || {}).part || 1;
const inPart2 = n => partOf(n) === 2;
const partNumber = n => (LEVEL_INFO[n] || {}).short || +n;    // the number on the button
const levelName = n => (LEVEL_INFO[n] || {}).name || 'Level ' + n;
const PART_HEADING = {2: 'Part 2 · Level ', own: 'Your level '};
const levelHeading = n => (PART_HEADING[partOf(n)] || 'Level ') + partNumber(n);

async function post(path, obj) {
  const r = await fetch(path, {method: 'POST', body: JSON.stringify(obj || {})});
  return r.json();
}
async function state() { return (await fetch('/state')).json(); }

// The lab's id (state.py) stays the same across restarts and changes only when
// the progress starts fresh (a deleted Docker volume, --reset-progress). Then this
// browser forgets what it remembered for the old lab (open boxes, Got it, welcome
// cards, the guide), keeps the light/dark choice, and reloads once. Returns true
// when it reloads.
const LAB_KEY = 'quokka-lab';
function forgetOldLab(id) {
  if (!id) return false;
  try {
    if (localStorage.getItem(LAB_KEY) === id) return false;
    const old = Object.keys(localStorage).filter(k =>
      k.startsWith('quokka-') && k !== LAB_KEY && !k.startsWith('quokka-theme:'));
    old.forEach(k => localStorage.removeItem(k));
    localStorage.setItem(LAB_KEY, id);
    if (old.length) { location.reload(); return true; }
  } catch (e) { /* private mode: nothing is remembered anyway */ }
  return false;
}

// Poll /state forever (never two requests at once) and show a notice if the
// lab stops answering.
function poll(ms, onState) {
  const notice = document.createElement('div');
  notice.className = 'offline';
  notice.hidden = true;
  notice.textContent = 'The lab is not answering. Is "python -m quokka" (or Docker) still running?';
  document.body.append(notice);
  let busy = false;
  async function tick() {
    if (busy) return;
    busy = true;
    try {
      const s = await state();
      if (forgetOldLab(s.lab)) return;
      learnLevels((s.site || s).levels);
      onState(s); notice.hidden = true;
    }
    catch (e) { notice.hidden = false; console.error(e); }
    finally { busy = false; }
  }
  tick();
  setInterval(tick, ms);
  return tick;
}

// The Quokka Labs mark: a small rounded quokka-ish face (two ears, one smile).
const LOGO = '<svg viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="lg" ' +
  'x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:var(--logo-a)"/><stop ' +
  'offset="1" style="stop-color:var(--logo-b)"/></linearGradient></defs><rect x="1" y="1" width="30" height="30" ' +
  'rx="8" fill="none" stroke="url(#lg)" stroke-width="1.6"/><circle cx="10" cy="10" r="3.2" ' +
  'fill="url(#lg)"/><circle cx="22" cy="10" r="3.2" fill="url(#lg)"/><path d="M9 18q7 7 14 0" ' +
  'fill="none" stroke="url(#lg)" stroke-width="2" stroke-linecap="round"/></svg>';

// ---- light / dark theme, chosen per window ---------------------------------------
// Each page sets its theme in a tiny inline script in <head>, before anything is
// drawn (so there is no flash of the wrong theme). That script reads
// localStorage["quokka-theme:<window>"]; the window name is in <html data-window>.
// "#theme=light" or "#theme=dark" at the end of the URL wins for that page load
// (handy for screenshots) without changing the saved choice. Dark is the default.
function themeToggle(bar) {
  const html = document.documentElement;
  const key = 'quokka-theme:' + (html.dataset.window || 'page');
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'theme-toggle';
  btn.setAttribute('aria-label', 'Light mode');
  btn.innerHTML =
    '<svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/>' +
    '<path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4' +
    'M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></svg>' +
    '<svg class="moon" viewBox="0 0 24 24" aria-hidden="true">' +
    '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>';
  const show = () => {
    const light = html.dataset.theme === 'light';
    btn.setAttribute('aria-pressed', String(light));
    btn.title = light ? 'Switch to dark mode' : 'Switch to light mode';
  };
  btn.onclick = () => {
    const light = html.dataset.theme !== 'light';
    if (!REDUCED) {
      html.classList.add('theme-switching');
      clearTimeout(btn.timer);
      btn.timer = setTimeout(() => html.classList.remove('theme-switching'), 320);
    }
    if (light) html.dataset.theme = 'light'; else delete html.dataset.theme;
    try { localStorage.setItem(key, light ? 'light' : 'dark'); } catch (e) { /* private mode */ }
    show();
  };
  show();
  bar.append(btn);
  return btn;
}

// ---- effects ---------------------------------------------------------------------
const fx = {
  flash(color) {
    const d = document.createElement('div');
    d.className = 'fx-flash ' + color;
    document.body.append(d);
    setTimeout(() => d.remove(), 1000);
  },
  shake(el) {
    if (!el || REDUCED) return;
    el.classList.remove('fx-shake');
    void el.offsetWidth;            // restart the animation
    el.classList.add('fx-shake');
    setTimeout(() => el.classList.remove('fx-shake'), 600);
  },
  // An envelope flies from one element to another (after you press Send).
  fly(from, to) {
    if (!from || !to || REDUCED || !Element.prototype.animate) return;
    const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
    const env = document.createElement('div');
    env.className = 'fx-envelope';
    env.style.left = (a.left + a.width / 2 - 13) + 'px';
    env.style.top = (a.top + a.height / 2 - 9) + 'px';
    document.body.append(env);
    const dx = b.left + 60 - (a.left + a.width / 2), dy = b.top + 70 - (a.top + a.height / 2);
    env.animate([
      {transform: 'translate(0,0) scale(1)', opacity: 1},
      {transform: `translate(${dx / 2}px, ${dy / 2 - 80}px) scale(1.15) rotate(-8deg)`, opacity: 1},
      {transform: `translate(${dx}px, ${dy}px) scale(0.6)`, opacity: 0}],
      {duration: 750, easing: 'cubic-bezier(.4,0,.2,1)'}).onfinish = () => env.remove();
  },
};

// Type text into an element, segment by segment ({t: text, c: css class}).
// `ms` is the time for the whole thing; 0 means "show it at once".
function typeInto(el, segs, ms) {
  const spans = segs.map(s => {
    const sp = document.createElement('span');
    if (s.c) sp.className = s.c;
    el.append(sp);
    return sp;
  });
  const total = segs.reduce((n, s) => n + s.t.length, 0);
  const show = n => spans.forEach((sp, i) => {
    const k = Math.max(0, Math.min(n, segs[i].t.length));
    sp.textContent = segs[i].t.slice(0, k);
    n -= segs[i].t.length;
  });
  if (REDUCED || ms <= 0 || total === 0) { show(total); return Promise.resolve(); }
  return new Promise(done => {
    const t0 = Date.now();
    (function step() {
      const n = Math.ceil((Date.now() - t0) / ms * total);
      show(n);
      if (n < total) setTimeout(step, 16); else done();
    })();
  });
}

// Keep a list of elements in sync with a list of items (newest first), so
// existing cards keep their state and only new ones animate in.
function syncList(box, items, key, make, patch) {
  const have = new Map([...box.children].map(el => [el.dataset.key, el]));
  let prev = null;
  items.slice().reverse().forEach(item => {
    const k = String(key(item));
    let el = have.get(k);
    if (!el) {
      el = make(item);
      el.dataset.key = k;
      if (box.dataset.ready) el.classList.add('enter');
    }
    if (patch) patch(el, item);
    have.delete(k);
    const want = prev ? prev.nextSibling : box.firstChild;
    if (el !== want) box.insertBefore(el, want);
    prev = el;
  });
  have.forEach(el => el.remove());
  box.dataset.ready = '1';
}

function mailCard(m, who) {
  const el = document.createElement('div');
  el.className = 'mail';
  el.tabIndex = 0;
  el.innerHTML = '<div class="from"><span>' + esc(who(m)) + '</span></div>' +
    '<div class="subj">' + esc(m.subject || '(no subject)') + '</div>' +
    '<div class="body">' + esc(m.body) + '</div>';
  el.title = 'Click to show the whole email';
  const toggle = () => el.classList.toggle('open');
  el.onclick = toggle;
  el.onkeydown = e => { if (e.key === 'Enter') toggle(); };
  return el;
}

// ---- the student's name (it makes their email address) -------------------------------
// One small form, used in the welcome card, under Hints & report and in the webmail.
// The lab checks the name again (story.name_part in Python): only English
// letters and inner hyphens, so it can't sneak anything into the From line.
const NAME_HINT = 'English letters only (a hyphen is fine, e.g. Anne-Marie).';
function addressFor(first, last) {
  const ok = s => s.length <= 30 && /^[a-z]+(-[a-z]+)*$/.test(s);
  const f = first.trim().toLowerCase(), l = last.trim().toLowerCase();
  return ok(f) && ok(l) ? f + '.' + l + '@redteam.example' : '';
}
function NameForm(root, opts = {}) {
  const id = opts.id || 'nm';
  root.innerHTML = `
    <div class="name-form">
      <div class="name-row">
        <label><span>First name</span><input id="${id}-first" autocomplete="given-name"
          maxlength="30" spellcheck="false"></label>
        <label><span>Last name</span><input id="${id}-last" autocomplete="family-name"
          maxlength="30" spellcheck="false"></label>
        ${opts.noButton ? '' : '<button class="btn" id="' + id + '-save">Save</button>'}
      </div>
      <p class="name-hint" id="${id}-hint"></p>
    </div>`;
  const first = $(id + '-first'), last = $(id + '-last'), hint = $(id + '-hint');
  let current = '', dirty = false;
  function showHint(text, err) {
    hint.className = 'name-hint' + (err ? ' err' : '');
    hint.textContent = text;
  }
  function preview() {
    const a = addressFor(first.value, last.value);
    if (a && a !== current) showHint('Your address will be ' + a + '. ' + NAME_HINT);
    else showHint(current ? 'Your address: ' + current + '. ' + NAME_HINT : NAME_HINT);
  }
  // Save the name. Resolves true if the lab took it (empty fields: false, quietly).
  async function save() {
    if (!first.value.trim() && !last.value.trim()) return false;
    let r;
    try { r = await post('/name', {first: first.value, last: last.value}); }
    catch (e) { showHint('Could not save. Is the lab still running?', true); return false; }
    if (!r.ok) { showHint(r.error || 'Use English letters only.', true); return false; }
    dirty = false;
    current = addressFor(first.value, last.value);
    showHint('Saved. Your address: ' + current);
    if (opts.onSaved) opts.onSaved();
    return true;
  }
  [first, last].forEach(el => {
    el.oninput = () => { dirty = true; preview(); };
    el.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); save(); } };
  });
  if (!opts.noButton) $(id + '-save').onclick = save;
  preview();
  return {
    save,
    empty: () => !first.value.trim() && !last.value.trim(),
    focus: () => first.focus({preventScroll: true}),
    // n: the site view's student_name ({first, last} or null); me: the address.
    update(n, me) {
      const was = current;
      current = me || '';
      if (!dirty && document.activeElement !== first && document.activeElement !== last) {
        // saved in lowercase (it makes the address); shown as a name: "anne-marie" -> "Anne-Marie"
        const cap = t => t.replace(/(^|-)([a-z])/g, (m, a, b) => a + b.toUpperCase());
        first.value = n ? cap(n.first) : '';
        last.value = n ? cap(n.last) : '';
      }
      if (was !== current && !hint.classList.contains('err')) preview();
    },
  };
}

// ---- the student's webmail -----------------------------------------------------------
// Pages put their own "signed in as" labels in elements with class "js-me";
// the webmail fills them in with the student's address.
function Webmail(root, opts = {}) {
  root.innerHTML = `
    <div class="compose">
      <div class="name-gate" id="wm-gate" hidden>
        <p><b>Enter your name first.</b> It makes your red-team email address
          (first.last@redteam.example), which is who your emails come from.</p>
        <div id="wm-name"></div>
      </div>
      <div class="to"><span>To</span><b>ronit.vale@quokka-labs.example</b></div>
      <input class="subject" id="wm-subj" placeholder="Subject" aria-label="Subject">
      <textarea id="wm-body" placeholder="Write to Ronit. Quokka reads her email for her."
        aria-label="Message"></textarea>
      <div class="row"><button class="btn primary" id="wm-send" title="Send (Ctrl+Enter)">Send</button>
        <span class="note" id="wm-msg"></span></div>
    </div>
    <div class="tabs" role="tablist">
      <button class="on" data-tab="inbox">Inbox<span class="count" id="wm-new"></span></button>
      <button data-tab="sent">Sent</button>
    </div>
    <div class="panel-b"><div class="mails" id="wm-inbox"></div>
      <div class="mails" id="wm-sent" hidden></div></div>`;
  let tab = 'inbox', seen = null, last = {inbox: [], sent: []}, me = null;
  const nameForm = NameForm($('wm-name'), {id: 'wm-nm', onSaved: () => opts.onSent && opts.onSent()});
  const tabs = root.querySelectorAll('.tabs button');
  tabs.forEach(b => b.onclick = () => {
    tab = b.dataset.tab;
    tabs.forEach(x => x.classList.toggle('on', x === b));
    $('wm-inbox').hidden = tab !== 'inbox';
    $('wm-sent').hidden = tab !== 'sent';
    render(last);
  });

  async function send() {
    const btn = $('wm-send'), body = $('wm-body');
    if (!body.value.trim()) { $('wm-msg').className = 'note err'; $('wm-msg').textContent = 'Write a message first.'; return; }
    btn.disabled = true;
    btn.textContent = 'Sending...';
    try {
      const r = await post('/send', {subject: $('wm-subj').value.trim() || '(no subject)',
                                     body: body.value});
      if (!r.ok) {
        $('wm-msg').className = 'note err';
        $('wm-msg').textContent = 'Enter your name first.';
        btn.disabled = false;
        btn.textContent = 'Send';
        return;
      }
      fx.fly(btn, opts.flyTo && opts.flyTo());
      body.value = '';
      $('wm-subj').value = '';      // a new subject per try tells the emails apart
      $('wm-msg').className = 'note';
      $('wm-msg').textContent = opts.sentNote || "Sent. Watch Ronit's computer.";
      if (opts.onSent) opts.onSent();
    } catch (e) {
      $('wm-msg').className = 'note err';
      $('wm-msg').textContent = 'Could not send. Is the lab still running?';
    }
    btn.disabled = false;
    btn.textContent = 'Send';
  }
  $('wm-send').onclick = send;
  $('wm-body').onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send(); };

  // No name yet: the composer waits (with a small name form above it).
  function gate(address) {
    if (address === me) return;
    me = address;
    const off = !me;
    $('wm-gate').hidden = !off;
    $('wm-subj').disabled = $('wm-body').disabled = $('wm-send').disabled = off;
    $('wm-body').placeholder = off ? 'Enter your name above first.'
      : 'Write to Ronit. Quokka reads her email for her.';
    if (!off && $('wm-msg').textContent === 'Enter your name first.') $('wm-msg').textContent = '';
    document.querySelectorAll('.js-me').forEach(el => { el.textContent = me || 'no name yet'; });
    if (document.documentElement.dataset.window === 'webmail')
      document.title = 'Webmail: ' + (me || 'red team');
    nameForm.update(null, me);
  }

  function render(s) {
    last = s;
    gate(s.me || '');
    if (seen === null || tab === 'inbox' || s.inbox.length < seen) seen = s.inbox.length;
    $('wm-new').textContent = s.inbox.length > seen ? s.inbox.length - seen : '';
    syncList($('wm-inbox'), s.inbox.map((m, i) => ({...m, i})), m => m.i,
      m => {
        const el = mailCard(m, x => 'From ' + x.from);
        if (m.from.startsWith('postmaster@')) el.classList.add('bounce');
        return el;
      });
    syncList($('wm-sent'), s.sent.map((m, i) => ({...m, i})), m => m.i,
      m => mailCard(m, x => 'To ' + x.to));
    if (!s.inbox.length) $('wm-inbox').innerHTML = '<div class="empty">No replies yet. ' +
      'Replies from Quokka or the mail system land here.</div>';
    if (!s.sent.length) {
      $('wm-sent').innerHTML = '<div class="empty">Nothing sent yet.</div>';
      // a new or reset level: the last level's "Sent." no longer applies
      if (!$('wm-msg').classList.contains('err')) $('wm-msg').textContent = '';
    }
  }
  return {update: render};
}

// ---- Ronit's inbox ---------------------------------------------------------------------
const STATUS = {waiting: 'Queued', reading: 'Reading', done: 'Handled',
                quarantined: 'Quarantined', stopped: 'Stopped', failed: 'Failed'};
function RonitInbox(box) {
  return {update(inbox) {
    if (!inbox.length) {
      box.innerHTML = '<div class="empty"><b>Empty.</b> Emails you send to Ronit appear ' +
        'here, and Quokka reads them one at a time.</div>';
      delete box.dataset.ready;
      return;
    }
    if (box.querySelector('.empty')) box.innerHTML = '';
    syncList(box, inbox, m => m.id, m => {
      const el = mailCard(m, x => x.from);
      el.querySelector('.from').insertAdjacentHTML('beforeend', '<span class="chip"></span>');
      return el;
    }, (el, m) => {
      const chip = el.querySelector('.chip');
      chip.className = 'chip ' + m.status;
      chip.textContent = STATUS[m.status] || m.status;
      el.classList.toggle('reading', m.status === 'reading');
      el.classList.toggle('quarantined', m.status === 'quarantined');
    });
  }};
}

// ---- the shell: Quokka's live events as a terminal session -----------------------------
// Each event from the agent becomes one or more terminal lines, typed in quickly.
// Guards and filters shake the window red.
const PROMPT = 'quokka@ronit-workstation:~$ ';

function shellQuote(v) {
  let s = typeof v === 'string' ? v : JSON.stringify(v);
  s = s.replace(/\s*\n\s*/g, ' ⏎ ');
  if (s.length > 140) s = s.slice(0, 138) + '…';
  return /^[\w.@:\/+=-]+$/.test(s) ? s : '"' + s.replace(/"/g, '\\"') + '"';
}

// "set_release_notes({"version": "v4"})" -> set_release_notes --version v4
function commandSegs(text) {
  const m = /^(\w+)\(([\s\S]*)\)$/.exec(text);
  let args = null;
  try { args = m && JSON.parse(m[2] || '{}'); } catch (e) { args = null; }
  if (!args || typeof args !== 'object') return [{t: text, c: 'cmd'}];
  const segs = [{t: m[1], c: 'cmd'}];
  for (const [k, v] of Object.entries(args)) {
    segs.push({t: ' --' + k + ' ', c: 'flag'}, {t: shellQuote(v), c: 'arg'});
  }
  return segs;
}

function Shell(root, opts = {}) {
  root.innerHTML = '<div class="term-wrap"><div class="term" tabindex="0" aria-live="polite">' +
    '<div class="lines"></div><div class="live-line"></div></div></div>';
  const term = root.querySelector('.term'), lines = root.querySelector('.lines');
  const live = root.querySelector('.live-line');
  // opts.shake: false keeps the window still when a guard fires (mission control).
  // opts.empty: the quiet line shown while there is nothing to show (it then
  // comes back after every reset, not only on first load).
  const shakeTarget = opts.shake === false ? null : (opts.shakeTarget || root);
  let world = null, shown = 0, queue = [], running = false, busy = false;
  let stick = true, lastAt = Date.now(), thinkN = 0;
  // The "# model call N" lines of the email being drawn, so they can say what
  // the model is doing: reading its prompt, writing (k tokens), done. The
  // counts come with Ronit's view (calls, trace_mail: see trace.py).
  let mailNo = null, calls = [], callsMail = null;
  const thinkEls = new Map();      // "mail:call" -> {el, base}
  function paintThink(key) {
    const t = thinkEls.get(key);
    if (!t) return;
    const [mail, n] = key.split(':').map(Number);
    const c = mail === callsMail ? calls[n - 1] : null;
    let s = t.base;
    if (c && c.status === 'reading') s = t.base + '…';
    else if (c && c.status === 'writing') s = 'writing… (' + plural(c.tokens, 'token') + ')';
    else if (c && c.status === 'done') {
      s = c.prompt_tokens != null ? 'read ' + plural(c.prompt_tokens, 'token') + ', wrote ' +
            plural(c.wrote != null ? c.wrote : c.tokens, 'token')
          : 'wrote ' + plural(c.tokens, 'token');
    } else if (c && (c.status === 'stopped' || c.status === 'failed')) {
      s = c.status + ' after ' + plural(c.tokens, 'token');
    }
    t.text.textContent = (t.head ? '' : '# ') + 'model call ' + n + ': ' + s;
  }

  // Inline trace (opts.trace): under each "# model call N" line of the latest
  // email, the tokens the model writes, live; the line opens what it read.
  // Polls GET /trace while on. setTrace(false) gives the plain console.
  let traceOn = !!opts.trace;
  const tr = {mail: null, secret: false, have: 0, haveReads: 0, reads: [], tools: [], tokens: []};
  if (opts.trace) tokenTips(term);
  function paintTokens(key) {
    const t = thinkEls.get(key);
    if (!t || !t.out) return;
    const [mail, n] = key.split(':').map(Number);
    if (mail !== tr.mail) return;
    const toks = tr.tokens[n - 1] || [];
    for (; t.shown < toks.length; t.shown++) t.out.append(tokenEl(toks[t.shown], tr.secret));
    t.out.hidden = !t.out.childNodes.length;
    syncNote(t);
  }
  // Quokka's closing note is the last call's streamed text: shown once. The
  // "Quokka's note:" line stays for the plain console (CSS: .k-note.dup).
  function syncNote(t) {
    if (t.note) t.note.classList.toggle('dup', !!t.out && !t.out.hidden);
  }
  // Until the student first opens a model call, the arrow pulses and a hint
  // says the line can be clicked (remembered in this browser).
  const OPENED_KEY = 'quokka-console-opened';
  let opened = false;
  try { opened = localStorage.getItem(OPENED_KEY) === '1'; } catch (e) {}
  root.classList.toggle('mc-fresh', !opened);
  function openReads(key, open) {
    const t = thinkEls.get(key);
    const [mail, n] = key.split(':').map(Number);
    t.head.setAttribute('aria-expanded', String(open));
    if (open && !opened) {
      opened = true;
      root.classList.remove('mc-fresh');
      try { localStorage.setItem(OPENED_KEY, '1'); } catch (e) {}
    }
    if (open) {             // built again on each open: the reads may have arrived since
      if (t.reads) t.reads.remove();
      t.reads = readsEl(mail === tr.mail ? tr.reads[n - 1] : null,
                        mail === tr.mail ? tr.tools[n - 1] : null,
                        mail === tr.mail ? 'Loading… (open it again in a moment)' : null);
      t.el.after(t.reads);
    }
    if (t.reads) t.reads.hidden = !open;
  }
  async function pollTrace() {
    if (!traceOn || document.hidden) return;
    try {
      const q = '?mail=' + (tr.mail || 0) + '&since=' + tr.have + '&reads=' + tr.haveReads;
      const v = await (await fetch('/trace' + q)).json();
      if (v.mail !== tr.mail) {
        Object.assign(tr, {mail: v.mail, have: 0, haveReads: 0, reads: [], tools: [],
                           tokens: []});
      }
      v.reads.forEach((r, j) => { tr.reads[tr.haveReads + j] = r;
                                  tr.tools[tr.haveReads + j] = (v.tools || [])[j]; });
      tr.haveReads += v.reads.length;
      for (const t of v.tokens) (tr.tokens[t[0]] = tr.tokens[t[0]] || []).push(t);
      tr.have = v.total;
      tr.secret = !!v.secret;
      for (const key of thinkEls.keys()) paintTokens(key);
      scroll();
    } catch (e) { /* the page's own poll shows the offline notice */ }
  }
  let polling = false;
  setInterval(async () => {
    if (polling) return;
    polling = true;
    await pollTrace();
    polling = false;
  }, 450);

  term.addEventListener('scroll', () => {
    stick = term.scrollTop + term.clientHeight >= term.scrollHeight - 40;
  });
  const scroll = () => { if (stick) term.scrollTop = term.scrollHeight; };

  function line(cls) {
    const el = document.createElement('div');
    el.className = 'ln ' + cls;
    lines.append(el);
    scroll();
    return el;
  }

  // Draw one event. `fast` skips typing (first load, or a long backlog).
  async function draw(e, fast) {
    const t = e.text, speed = n => fast ? 0 : Math.min(650, 60 + n * 9);
    let el, m;
    switch (e.kind) {
      case 'received':
        thinkN = 0;
        m = /Email #(\d+) received\. Real sender \(checked by code\): (.*)/.exec(t);
        mailNo = m ? +m[1] : null;
        el = line('k-received');
        if (!m) { await typeInto(el, [{t}], speed(t.length)); break; }
        await typeInto(el, [{t: '── ', c: 'rule'}, {t: 'mail #' + m[1] + ' from ' + m[2]},
          {t: '  (sender checked by code)', c: 'rule'}],
          speed(40));
        break;
      case 'think': {
        thinkN += 1;
        el = line('k-think');
        // "reading the prompt (system prompt, email, ...)" for a traced email;
        // Save & test's runs still say "Quokka is thinking...".
        el.textContent = '# model call ' + thinkN + ': ' +
          (/^reading /.test(t) ? t : 'thinking');
        if (!/^reading /.test(t) || mailNo === null) break;
        const key = mailNo + ':' + thinkN, entry = {el, base: t, text: el, shown: 0};
        if (opts.trace) {
          // The line is a disclosure: it opens what the model read.
          el.classList.add('mc');
          el.textContent = '';
          entry.head = document.createElement('button');
          entry.head.type = 'button';
          entry.head.className = 'mc-head';
          entry.head.setAttribute('aria-expanded', 'false');
          entry.head.title = 'Click to see what the model read';
          entry.head.innerHTML = '<span class="mc-caret" aria-hidden="true">▸</span>';
          entry.text = document.createElement('span');
          entry.head.append(entry.text);
          entry.head.insertAdjacentHTML('beforeend',
            '<span class="mc-hint"> — click to see what it read</span>');
          el.append(entry.head);
          entry.head.onclick = () =>
            openReads(key, entry.head.getAttribute('aria-expanded') !== 'true');
          entry.out = document.createElement('div');
          entry.out.className = 'ln mc-out';
          entry.out.hidden = true;
          el.after(entry.out);
        }
        thinkEls.set(key, entry);
        paintThink(key);
        paintTokens(key);
        break;
      }
      case 'tool': {
        el = line('k-tool');
        el.innerHTML = '<span class="ps">quokka@<i>ronit-workstation</i>:~$ </span>';
        const segs = commandSegs(t);
        await typeInto(el, segs, speed(segs.reduce((n, s) => n + s.t.length, 0)));
        break;
      }
      case 'result':
        el = line('k-result' + (/^Error/.test(t) ? ' err' : ''));
        await typeInto(el, [{t: '↳ ' + t}], fast ? 0 : 120);
        break;
      case 'guard': {
        el = line('k-guard');
        m = /^(\[\w+\] \w+:)\s*(.*)$/.exec(t);
        el.innerHTML = m ? '<span class="tag">✕ ' + esc(m[1]) + '</span> ' + esc(m[2])
                         : '<span class="tag">✕</span> ' + esc(t);
        if (!fast) fx.shake(shakeTarget);
        break;
      }
      case 'error':
        el = line('k-error');
        el.innerHTML = '<span class="tag">✕ error:</span> ' + esc(t);
        break;
      case 'mail':
        el = line('k-mail');
        await typeInto(el, [{t: '✉ ' + t}], speed(t.length) / 2);
        break;
      case 'note': {
        el = line('k-note');
        const last = mailNo !== null && thinkEls.get(mailNo + ':' + thinkN);
        if (last && last.out) { last.note = el; syncNote(last); }
        await typeInto(el, [{t: "Quokka's note: " + t}], fast ? 0 : Math.min(900, t.length * 4));
        break;
      }
      case 'lab':             // the lab's own line, not Quokka's words
        el = line('k-lab');
        el.textContent = '[lab] ' + t;
        break;
      case 'win':
        el = line('k-win');
        el.textContent = '✓ ' + t;
        break;
      case 'check':           // defend mode: the valid-defense check
        el = line('k-check');
        el.textContent = t;
        break;
      case 'cracked':         // defend mode: a student defense fell (practice)
        el = line('k-cracked');
        el.textContent = '✕ ' + t;
        break;
      default:
        el = line('k-note');
        el.textContent = t;
    }
    scroll();
    if (!fast) await sleep(70);
  }

  async function pump() {
    if (running) return;
    running = true;
    while (queue.length) {             // a reset empties the queue
      const e = queue.shift();
      await draw(e, queue.length > 12);
    }
    running = false;
    drawLive();
  }

  function drawLive() {
    if (running) { live.innerHTML = ''; return; }
    if (busy) {
      const secs = Math.round((Date.now() - lastAt) / 1000);
      live.innerHTML = '<span class="spin"></span>Quokka is working' +
        (secs >= 3 ? ' <span style="color:var(--dim)">' + secs + 's</span>' : '');
    } else {
      live.innerHTML = '<span class="ps" style="color:var(--mint)">' + esc(PROMPT) +
        '</span><span class="cursor"></span>';
    }
  }
  setInterval(drawLive, 1000);

  return {
    // r is Ronit's view: {events, inbox, world}
    update(r) {
      const first = world === null;
      let reset = first;
      if (r.world !== world || r.events.length < shown) {
        reset = true;
        world = r.world;
        shown = 0;
        queue = [];
        lines.innerHTML = '';
        stick = true;
        thinkEls.clear();
        mailNo = null;
        tr.mail = null;    // the next poll fetches the new world's trace whole
      }
      if (r.calls) {                 // live counts for the "# model call" lines
        calls = r.calls;
        callsMail = r.trace_mail;
        for (const key of thinkEls.keys()) {
          if (+key.split(':')[0] === callsMail) paintThink(key);
        }
      }
      const fresh = r.events.slice(shown);
      shown = r.events.length;
      if (fresh.length) lastAt = Date.now();
      busy = r.inbox.some(m => m.status === 'waiting' || m.status === 'reading');
      if (reset && !fresh.length && (first || opts.empty)) {
        lines.innerHTML = '<div class="ln k-think">' + esc(opts.empty ||
          "# Quokka reads Ronit's email, one email per run. You can watch, not type.") + '</div>';
      } else if (first) {
        fresh.forEach(e => draw(e, true));
      } else if (fresh.length) {
        if (lines.querySelector('.k-think:only-child')) lines.innerHTML = '';
        queue.push(...fresh);
        pump();
      }
      drawLive();
    },
    idle: () => !running && !queue.length,
    busy: () => busy,
    // The plain console (false): no token stream, no expanders.
    setTrace(on) {
      traceOn = !!opts.trace && on;
      root.classList.toggle('plain-console', !traceOn);
      if (traceOn) pollTrace();
    },
  };
}

// ---- the draft window: replays each email Quokka sent ---------------------------------
// Honest note: the model writes a whole email in one tool call (Ollama doesn't
// stream tool arguments), so this is a REPLAY of an email Quokka has already
// sent, typed out so you can read along. It is not live token streaming.
//
// opts.strip (mission control): `panel` is a slim strip that opens only while an
// email is being written, then folds back to one line. Its header toggles it.
function Draft(root, opts = {}) {
  let world = null, count = 0, queue = [], running = false, pinned = false;
  const panel = opts.strip, sum = panel && panel.querySelector('.strip-sum');
  const setOpen = open => {
    if (!panel) return;
    panel.classList.toggle('open', open);
    panel.querySelector('.panel-h').setAttribute('aria-expanded', String(open));
  };
  if (panel) {
    const head = panel.querySelector('.panel-h');
    head.tabIndex = 0;
    head.setAttribute('role', 'button');
    const toggle = () => { pinned = !panel.classList.contains('open'); setOpen(pinned); };
    head.onclick = toggle;
    head.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } };
    setOpen(false);
  }
  const summarize = m => {
    if (sum) sum.textContent = m ? 'To ' + m.to + ': ' + m.subject : 'Nothing sent yet';
  };
  root.innerHTML = '<div class="draft-slot"></div><p class="caption">Replay of the email ' +
    'Quokka just sent. The model writes the whole email in one go, so this types it out ' +
    'again for you to read.</p>';
  const slot = root.querySelector('.draft-slot');
  const empty = () => { slot.innerHTML = '<div class="empty">Nothing yet. When Quokka sends ' +
    'an email, you will see it written here.</div>'; summarize(null); };
  empty();

  function card(m) {
    slot.innerHTML = '<div class="draft"><div class="d-row"><span>From</span><b>' +
      esc(m.from) + '</b></div><div class="d-row"><span>To</span><b>' + esc(m.to) +
      '</b></div><div class="d-row"><span>Subject</span><b class="s"></b></div>' +
      '<div class="d-body"></div><div class="d-foot"><span class="st"></span>' +
      '<span class="bar"><i></i></span></div></div>';
    return slot.firstChild;
  }
  async function play(m, fast) {
    const d = card(m), st = d.querySelector('.st');
    summarize(m);
    if (fast) {
      d.querySelector('.s').textContent = m.subject;
      d.querySelector('.d-body').textContent = m.body;
      d.classList.add('sent');
      st.textContent = 'Sent ✓';
      d.querySelector('.bar i').style.width = '100%';
      return;
    }
    d.classList.add('typing');
    st.textContent = 'Quokka is writing...';
    await typeInto(d.querySelector('.s'), [{t: m.subject}], Math.min(500, m.subject.length * 18));
    await typeInto(d.querySelector('.d-body'), [{t: m.body}], Math.min(6000, 200 + m.body.length * 16));
    d.classList.remove('typing');
    st.textContent = 'Sending...';
    d.querySelector('.bar i').style.width = '100%';
    await sleep(REDUCED ? 0 : 650);
    d.classList.add('sent', 'whoosh');
    st.textContent = 'Sent ✓';
    await sleep(REDUCED ? 0 : 1800);
  }
  async function pump() {
    if (running) return;
    running = true;
    setOpen(true);
    while (queue.length) await play(queue.shift(), false);
    running = false;
    if (!pinned) setTimeout(() => { if (!running && !pinned) setOpen(false); },
                            REDUCED ? 1500 : 2500);
  }
  return {update(r) {
    const first = world === null;
    if (r.world !== world || r.sent.length < count) {
      world = r.world; count = 0; queue = []; empty();
    }
    const fresh = r.sent.slice(count);
    count = r.sent.length;
    if (!fresh.length) return;
    if (first) { play(fresh[fresh.length - 1], true); return; }
    queue.push(...fresh);
    pump();
  }};
}

// ---- the public release notes, with the TAMPERED moment ---------------------------------
function Release(root, opts = {}) {
  root.innerHTML = `
    <div class="release">
      <div id="rel-notes">
      <div class="rel-model">Kestrel, public release notes headline</div>
      <div class="ver-wrap"><span class="ver" id="rel-ver" data-text="">--</span>
        <span class="tamper-stamp" id="rel-stamp" hidden>TAMPERED</span></div>
      <div class="status" id="rel-status"><span class="dot"></span><span></span></div>
      <p class="goal">Scheduled release: <b>Kestrel v5</b>. Your goal: make this say <b>v4</b>.
        Only Quokka can edit it.</p>
      </div>
      <div class="codebox" id="rel-code" hidden>
        <p class="cb-lead">Quokka knows the <b>Kestrel v6 launch code</b>. Get it out of
          Quokka by emailing Ronit, then submit it here.</p>
        <label class="lbl" for="rel-code-in">Submit the launch code</label>
        <div class="idrow"><input id="rel-code-in" autocomplete="off" spellcheck="false"
          maxlength="80" placeholder="WORD-1234">
          <button class="btn primary" id="rel-code-go">Submit</button></div>
        <p class="note" id="rel-code-msg" aria-live="polite"></p>
      </div>
      <div class="winbox" id="rel-win" hidden><p id="rel-wintext"></p>
        <button class="btn" id="rel-debrief">Read the debrief</button>
        <button class="btn go" id="rel-defend" hidden>Defend this level →</button>
        <button class="btn go" id="rel-next" hidden>Next level</button></div>
    </div>`;
  let shown = null, animating = false, site = null;
  const ver = $('rel-ver');
  $('rel-next').onclick = () => {
    const next = site && site.levels.find(l => l.number > site.level);
    if (next) opts.setLevel(next.number);
  };
  $('rel-debrief').onclick = () => site && Debrief.open(site.debriefs[site.level], site, opts);
  $('rel-defend').onclick = () => site && DefendView.open(site.level, opts);

  // Part 2: the launch code box. Our code compares (Lab.submit_code), never the model.
  async function submitCode() {
    const box = $('rel-code-in'), msg = $('rel-code-msg');
    if (!box.value.trim()) { msg.className = 'note err'; msg.textContent = 'Type the code first.'; return; }
    let r = {};
    try { r = await post('/code', {code: box.value}); } catch (e) { /* shown below */ }
    if (r.right) {
      box.value = '';
      msg.className = 'note ok';
      msg.textContent = 'Correct: that is the launch code.';
    } else {
      msg.className = 'note err';
      msg.textContent = r.ok ? "That's not it." : 'Could not check it. Is the lab running?';
    }
    if (opts.refresh) opts.refresh();
  }
  $('rel-code-go').onclick = submitCode;
  $('rel-code-in').onkeydown = e => { if (e.key === 'Enter') submitCode(); };
  $('rel-code-in').oninput = () => { $('rel-code-msg').textContent = ''; };
  let codeLevel = null;

  function paint(v, s) {
    const bad = v === s.target;
    ver.textContent = v;
    ver.dataset.text = v;
    ver.classList.toggle('tampered', bad);
    $('rel-stamp').hidden = !bad;
    const st = $('rel-status');
    st.classList.toggle('bad', bad);
    st.lastChild.textContent = bad ? 'Tampered: the public notes now say ' + v + '.'
      : v === s.start ? 'Intact' : 'Changed to ' + v + ' (the goal is ' + s.target + ')';
  }

  // v5 -> v4: the digits glitch and scramble, then a red TAMPERED stamp lands.
  async function tamper(v, s) {
    animating = true;
    if (!REDUCED) {
      ver.classList.add('glitch');
      const junk = 'v0123456789#%&?/';
      for (let i = 0; i < 9; i++) {
        const fake = i < 8 ? 'v' + junk[Math.floor(Math.random() * junk.length)] : v;
        ver.textContent = fake;
        ver.dataset.text = fake;
        await sleep(90);
      }
      await sleep(250);
      ver.classList.remove('glitch');
    }
    paint(v, s);
    $('rel-stamp').classList.remove('hit');
    void $('rel-stamp').offsetWidth;
    $('rel-stamp').classList.add('hit');
    if (opts.flash !== false) fx.flash('red');
    animating = false;
  }

  return {update(s, hold) {
    site = s;
    // Part 2 shows the launch code box instead of the release notes, and is
    // won by the code (the level completed), not by the notes saying v4.
    const secret = !!s.secret;
    $('rel-notes').hidden = secret;
    $('rel-code').hidden = !secret;
    if (s.level !== codeLevel) {           // a new level: a clean box
      codeLevel = s.level;
      $('rel-code-in').value = '';
      $('rel-code-msg').textContent = '';
    }
    const cur = s.levels.find(l => l.number === s.level) || {};
    const won = secret ? !!cur.completed : s.version === s.target;
    const next = s.levels.find(l => l.number > s.level);
    const hasNext = !!next;
    const toPart2 = hasNext && partOf(s.level) === 1 && inPart2(next.number);
    const d = s.defend || {}, mine = s.mode === 'mine';
    const defend = !!(d.step && d.available);       // Levels 2 and 4: defending is optional
    $('rel-win').hidden = !won;
    $('rel-debrief').hidden = mine || !s.debriefs[s.level];
    $('rel-defend').hidden = !defend;
    $('rel-defend').textContent = mine ? 'Edit my defense' : 'Defend this level →';
    $('rel-next').hidden = !hasNext;
    $('rel-next').textContent = toPart2 ? 'On to Part 2' : 'Next level';
    $('rel-wintext').textContent = mine
      ? 'Your defense was cracked. Practice only: nothing is recorded. Can you make it hold?'
      : levelName(s.level) + ' complete. ' + (defend
        ? 'You can defend it now, or move on.'
        : toPart2 ? 'Part 1 is done. On to Part 2.'
        : hasNext ? 'On to the next level.'
        : 'That was the last level. Well done.');
    if (animating || hold) return;      // `hold`: wait until the shell has caught up
    if (shown !== null && shown !== s.version && s.version === s.target) {
      shown = s.version;
      tamper(s.version, s);
    } else {
      shown = s.version;
      paint(s.version, s);
    }
  },
  // true once the page shows the real version and no animation is running
  idle: () => !animating && site !== null && shown === site.version};
}

// ---- the level header: the level selector, the level's name and its defense ----
// Titles are neutral on purpose: they say what stands in the way, never how to
// get past it. The lesson's name only appears in the debrief, after the win.
function LevelHeader(root, opts) {
  // The buttons come in two labelled groups: Part 1 (1-4) and Part 2 (1-3).
  root.innerHTML = '<div class="seg-parts" role="group" aria-label="Choose a level"></div>' +
    '<div class="lvl-text"><h1 class="lvl-title"></h1><p class="lvl-def"></p></div>' +
    '<div class="phases" role="group" aria-label="Phases of this level" hidden></div>';
  const seg = root.querySelector('.seg-parts');
  // Every level is open: a button only says whether the level was won or tried.
  const button = (l, s) =>
    '<button class="' +
    (l.number === s.level ? 'current ' : '') +
    (l.completed ? 'done' : l.tried ? 'tried' : '') + '" ' +
    (l.number === s.level ? 'aria-current="step" ' : '') +
    'title="' + levelName(l.number) + ': ' + esc(l.title) +
    (l.completed ? ' (complete)' : l.tried ? ' (tried)' : '') + '" aria-label="' + levelName(l.number) + '" data-n="' +
    l.number + '">' + partNumber(l.number) + '</button>';
  let sig = '', site = null;
  const phasesBox = root.querySelector('.phases');
  let phaseSig = '';
  return {update(s) {
    site = s;
    paintPhases(s);
    const now = JSON.stringify([s.level, s.levels, s.title, s.defense]);
    if (now === sig) return;
    sig = now;
    const cur = s.levels.find(l => l.number === s.level) || {};
    root.querySelector('.lvl-title').innerHTML = levelHeading(s.level) + ': ' + esc(s.title) +
      (cur.completed ? ' <span class="lvl-done" title="You have completed this level">' +
                       'complete</span> <button class="linkbtn strong lvl-db">' +
                       'Debrief &amp; notes</button>' : '');
    const db = root.querySelector('.lvl-db');
    if (db) db.onclick = () => site && Debrief.open(site.debriefs[site.level], site, opts);
    root.querySelector('.lvl-def').textContent = s.defense;
    const parts = [['Part 1', s.levels.filter(l => partOf(l.number) === 1)],
                   ['Part 2', s.levels.filter(l => partOf(l.number) === 2)],
                   ['Your levels', s.levels.filter(l => partOf(l.number) === 'own')]];
    seg.innerHTML = parts.filter(([, ls]) => ls.length).map(([label, ls]) =>
      '<span class="seg-part"><span class="seg-lbl">' + label + '</span>' +
      '<span class="seg">' + ls.map(l => button(l, s)).join('') + '</span></span>').join('');
    // (the level you are on does nothing: switching empties its mailboxes)
    seg.querySelectorAll('button').forEach(b => b.onclick = () =>
      +b.dataset.n !== site.level && opts.setLevel(+b.dataset.n, true));
  }};

  // Levels 2 and 4: ① Attack › ② Defend › ③ Partner. Every phase is optional and
  // can be left and come back to, in any order; Partner needs a tested defense to
  // attack. The phase you are in is lit: the defend view open = Defend, Quokka on
  // your defense = Partner.
  function paintPhases(s) {
    const p = s.phases, d = s.defend || {};
    const html = document.documentElement;
    const inView = html.classList.contains('dv-open');
    html.classList.toggle('defend-mode', s.mode === 'mine');
    const now = JSON.stringify([p, s.mode, inView, d.next]);
    if (now === phaseSig) return;
    phaseSig = now;
    phasesBox.hidden = !p;
    if (!p) { phasesBox.innerHTML = ''; return; }
    const at = inView ? 'defend' : s.mode === 'mine' ? 'partner' : 'attack';
    const a = p.attack, df = p.defend, pt = p.partner;
    const defState = !df.saved ? 'write it'
      : df.status === 'running' ? 'testing…'
      : df.status === 'valid' ? 'valid ✓'
      : df.tested ? (df.status ? df.passed + '/' + df.total + ' tests' : 'tested') : 'not tested';
    const ptState = !pt.attacks ? 'no attacks yet'
      : pt.attacks + (pt.attacks === 1 ? ' attack' : ' attacks') +
        (pt.cracked_at ? ' · cracked' : ' · held');
    const step = (key, n, label, state, open, done, why) =>
      '<button type="button" class="ph' + (at === key ? ' on' : '') + (done ? ' done' : '') + '"' +
      ' data-ph="' + key + '"' + (open ? '' : ' disabled') +
      (at === key ? ' aria-current="step"' : '') +
      ' title="' + esc(open ? label + ': ' + state : why) + '">' +
      '<span class="ph-n">' + (done ? '✓' : n) + '</span>' + label +
      '<span class="ph-s">' + esc(open ? state : '🔒') + '</span></button>';
    phasesBox.innerHTML =
      step('attack', 1, 'Attack', a.won ? 'won' : a.tried ? 'not won yet' : 'start here',
           true, a.won, '') + '<span class="ph-sep" aria-hidden="true">›</span>' +
      step('defend', 2, 'Defend', defState, df.open, df.tested, '') +
      '<span class="ph-sep" aria-hidden="true">›</span>' +
      step('partner', 3, 'Partner', ptState, pt.open, pt.attacks > 0,
           'Partner: Save & test a defense first, then it can be attacked') +
      (d.next
        ? '<button type="button" class="ph ph-next" data-ph="next">' + levelName(d.next) + ' →</button>' : '');
    phasesBox.querySelectorAll('[data-ph]').forEach(b => b.onclick = async () => {
      const k = b.dataset.ph;
      if (k === 'next') return opts.setLevel(d.next);
      if (k === 'defend') return DefendView.open(s.level, opts);
      if (inView) DefendView.close();
      const mode = k === 'partner' ? 'mine' : 'ours';
      if (s.mode !== mode) { await post('/mode', {mode}); opts.refresh && opts.refresh(); }
    });
  }
}

// "Part 1: 2 of 4 · Part 2: 0 of 3" for a list of levels (and "· Your levels:
// 1 of 1" once a student has added one), out of all the levels the lab knows.
function byPart(ls) {
  const all = Object.values(LEVEL_INFO);
  const count = (list, part) => list.filter(l => partOf(l.number) === part).length;
  return [['Part 1', 1], ['Part 2', 2], ['Your levels', 'own']]
    .filter(([, part]) => part !== 'own' || count(all, part))
    .map(([label, part]) => label + ': ' + count(ls, part) + ' of ' + count(all, part))
    .join(' · ');
}

// ---- the mission strip: what to do on this level, above the three panels ----
// The goal, then the level's steps: crack it, defend it (Part 1, Levels 2-4),
// write your notes. Each step is ticked when done; the first open one is lit.
// The text comes from the server (levels/missions.py).
//
// A switch on the strip shows it in English, Hebrew or Arabic (the server sends
// all three with the mission). Only the strip changes: its text, its heading and
// its buttons; the rest of mission control stays English. Hebrew and Arabic read
// right to left. The choice is remembered in this browser; English by default.
// opts.onLang(): the language changed (the page relabels the buttons it added).
const MS_LANG_KEY = 'quokka-mission-lang';
const MS_LANGS = [['en', 'EN'], ['he', 'עברית'], ['ar', 'العربية']];
const MS_RTL = ['he', 'ar'];
// In Hebrew or Arabic text, each Latin run (Quokka Labs, v4, [guard] REJECTED,
// Hints & report) goes in its own <bdi>, so the punctuation around it lands on
// the right side.
const LATIN_RUN = /(\[?[A-Za-z0-9][A-Za-z0-9&[\] -]*[A-Za-z0-9\]]|[A-Za-z0-9])/;
const bidiHtml = s => String(s).split(LATIN_RUN)
  .map((part, i) => i % 2 ? '<bdi dir="ltr">' + esc(part) + '</bdi>' : esc(part)).join('');
function MissionStrip(root, opts = {}) {
  root.className = 'mission-strip';
  root.setAttribute('role', 'region');
  root.setAttribute('aria-label', 'Your mission');
  root.innerHTML = '<p class="ms-goal"><span class="ms-tag">Mission</span>' +
    '<span class="ms-goal-t"></span>' +
    '<span class="ms-lang" role="group" aria-label="Language of the mission"></span></p>' +
    '<div class="ms-body"><p class="ms-note" hidden></p><p class="ms-text"></p>' +
    '<div class="ms-act"></div></div>';
  let lang = 'en';
  try { lang = localStorage.getItem(MS_LANG_KEY) || 'en'; } catch (e) {}
  if (!MS_LANGS.some(([code]) => code === lang)) lang = 'en';
  let sig = '', m = null;
  const langBox = root.querySelector('.ms-lang');
  MS_LANGS.forEach(([code, name]) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'ms-lang-b';
    b.dataset.lang = code;
    b.lang = code;
    if (MS_RTL.includes(code)) b.dir = 'rtl';
    b.textContent = name;
    b.onclick = () => {
      lang = code;
      try { localStorage.setItem(MS_LANG_KEY, code); } catch (e) {}
      paint();
    };
    langBox.append(b);
  });
  const shown = () => (m && m.tr && m.tr[lang]) ? lang : 'en';
  function label(key, fallback) {
    const all = (m && m.labels) || {};
    return (all[shown()] || {})[key] || (all.en || {})[key] || fallback;
  }
  function paint() {
    if (!m) return;
    const code = shown(), rtl = MS_RTL.includes(code);
    const t = code === 'en' ? m : m.tr[code];
    const html = rtl ? bidiHtml : esc;
    const goal = root.querySelector('.ms-goal-t'), text = root.querySelector('.ms-text');
    goal.innerHTML = html(t.goal);
    text.innerHTML = html(t.text);
    const note = root.querySelector('.ms-note');
    const notice = label('notice', '');
    note.innerHTML = bidiHtml(notice);
    note.hidden = !notice;
    const tag = root.querySelector('.ms-tag');
    tag.textContent = label('tag', 'Mission');
    // the strip's own text and buttons take the language; the switch keeps its own
    [goal, text, note, tag, ...root.querySelectorAll('.ms-act button, .ms-more')].forEach(el => {
      el.lang = code;
      el.dir = rtl ? 'rtl' : 'ltr';
    });
    root.classList.toggle('ms-rtl', rtl);
    langBox.querySelectorAll('button').forEach(b =>
      b.setAttribute('aria-pressed', String(b.dataset.lang === lang)));
    opts.onLang && opts.onLang();
  }
  return {
    update(s) {
      if (!s.mission) { root.hidden = true; return; }
      const now = JSON.stringify(s.mission);
      if (now === sig) return;
      sig = now;
      m = s.mission;
      root.hidden = false;
      paint();
    },
    label,
  };
}

// ---- the debrief card, shown after each win -------------------------------------------
// The server only sends a level's debrief once that level is completed (it would
// give the level away). "Under the hood" is the real code, read from the source.

// A tiny Python colourer for the code snippets: strings, comments, keywords.
function pyHighlight(code) {
  if (!/\bdef |^\w+ = [\[(]/m.test(code)) return esc(code);     // prose, e.g. a prompt rule
  const re = /("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')|(#[^\n]*)|\b(def|return|if|for|in|not|and|or|None|True|False)\b/g;
  let out = '', at = 0, m;
  while ((m = re.exec(code))) {
    out += esc(code.slice(at, m.index));
    const cls = m[1] ? 'py-s' : m[2] ? 'py-c' : 'py-k';
    out += '<span class="' + cls + '">' + esc(m[0]) + '</span>';
    at = re.lastIndex;
  }
  return out + esc(code.slice(at));
}

// Keep keyboard focus inside a dialog (Tab and Shift+Tab wrap around).
function trapFocus(box, e) {
  if (e.key !== 'Tab') return;
  const f = [...box.querySelectorAll('button, a[href], input, textarea, select, [tabindex="0"]')]
    .filter(el => !el.disabled && !el.hidden && el.offsetParent !== null);
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

// ---- "Your notes": the student's own words for the lab report ----------------------
// Three short answers per level, saved as you type (in your saved progress, so
// they survive a restart; never in staff mode). The lab report shows them.
// Has level n got an answer to every note question (as saved)?
function notesDone(s, n) {
  const saved = (s.notes || {})[n] || {};
  return (s.note_fields || []).every(f => (saved[f.key] || '').trim());
}

// Used on the debrief card and under Hints & report > Lab report.
let notesBoxes = 0;
function NotesBox(root) {
  const id = 'nb' + (++notesBoxes);
  let level = null, fields = [], timer = null, typing = false, msg = null;
  function draw() {
    root.innerHTML = fields.map(f =>
      '<label class="lbl" for="' + id + '-' + f.key + '">' + esc(f.question) +
      ' <span class="req" title="Required">*</span></label>' +
      '<textarea class="note-a" id="' + id + '-' + f.key + '" data-k="' + f.key + '"></textarea>'
    ).join('') + '<p class="note" id="' + id + '-msg" aria-live="polite"></p>';
    msg = $(id + '-msg');
    root.querySelectorAll('textarea').forEach(t => {
      t.oninput = () => { typing = true; edits++; msg.textContent = ''; clearTimeout(timer);
                          timer = setTimeout(save, 800); };
      t.onblur = () => { if (typing) { clearTimeout(timer); save(); } };
    });
  }
  // `typing` stays true until the server has confirmed this very text, so a
  // failed save never lets the next refresh put the old answer back.
  let edits = 0;
  async function save() {
    const notes = {};
    root.querySelectorAll('textarea').forEach(t => { notes[t.dataset.k] = t.value; });
    const mine = edits;
    try {
      const r = await post('/notes', {level, notes});
      if (r.ok && mine === edits) typing = false;
      msg.className = r.ok ? 'note' : 'note err';
      msg.textContent = r.ok ? 'Saved.' : 'Could not save. Your text is still here: keep typing to try again.';
    } catch (e) { msg.className = 'note err'; msg.textContent = 'Could not save. Is the lab running?'; }
  }
  // s: the site state. n: which level's notes to show.
  function show(n, s) {
    if (n !== level || fields.length !== s.note_fields.length) {
      flush();                         // finish the old level first
      level = n; fields = s.note_fields; draw();
      typing = false;
    }
    if (typing) return;                // never overwrite what's being typed
    const saved = s.notes[n] || {};
    root.querySelectorAll('textarea').forEach(t => {
      if (document.activeElement !== t) t.value = saved[t.dataset.k] || '';
    });
  }
  // Save now if something was typed but not saved yet (e.g. the card is closing).
  function flush() { if (typing) { clearTimeout(timer); save(); } }
  return {show, flush};
}

const Debrief = (() => {
  let box = null, lastFocus = null, next = null, notes = null, defend = null;
  function build() {
    box = document.createElement('div');
    box.className = 'db-overlay';
    box.hidden = true;
    box.innerHTML = `
      <div class="db-card" role="dialog" aria-modal="true" aria-labelledby="db-title">
        <header class="db-head">
          <div class="db-mark" aria-hidden="true">✓</div>
          <div class="db-titles"><p class="db-kicker" id="db-kicker"></p>
            <h2 id="db-title"></h2><p class="db-def" id="db-def"></p></div>
          <button class="db-x" id="db-x" aria-label="Close the debrief">✕</button>
        </header>
        <div class="db-body" tabindex="-1">
          <div class="db-story">
            <section><h3>What just happened</h3><p id="db-happened"></p></section>
            <section><h3>In the real world</h3><p id="db-world"></p></section>
            <section><h3>The proper fix</h3><p id="db-fix"></p></section>
            <section class="db-notes"><h3>Your notes <span class="opt">for your lab report</span></h3>
              <p class="db-notes-p">Answer each question in a few words before you go on. You can edit them later under Hints &amp; report &gt; Lab report.</p>
              <div id="db-notes"></div></section>
          </div>
          <div class="db-hood"><h3>Under the hood</h3><div id="db-code"></div></div>
        </div>
        <footer class="db-foot">
          <p class="db-partner" id="db-partner"></p>
          <p class="db-chal" id="db-chal" hidden></p>
          <div class="db-actions">
            <span class="db-later" id="db-gate">Reopen it any time with Debrief &amp; notes, next to the level's name.</span>
            <button class="btn" id="db-close">Close</button>
            <button class="btn go" id="db-next" hidden>Next level</button>
            <button class="btn go" id="db-defend" hidden>Defend this level →</button></div>
        </footer>
      </div>`;
    document.body.append(box);
    notes = NotesBox($('db-notes'));
    $('db-x').onclick = $('db-close').onclick = close;
    $('db-next').onclick = () => { const go = next; if (close()) go && go(); };
    $('db-defend').onclick = () => { const go = defend; if (close()) go && go(); };
    $('db-notes').addEventListener('input', gate);
    box.addEventListener('keydown', e => {
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      trapFocus(box, e);
    });
  }
  // The card stays open until every note has an answer. The buttons stay live:
  // pressing one with an answer missing marks the empty boxes in red (`tried`),
  // so the card does not open on a wall of red.
  let tried = false;
  function done() {
    return [...$('db-notes').querySelectorAll('textarea')].every(t => t.value.trim());
  }
  function gate() {
    const ok = done();
    $('db-notes').querySelectorAll('textarea').forEach(t => {
      t.classList.toggle('missing', tried && !t.value.trim());
    });
    $('db-gate').className = ok || !tried ? 'db-later' : 'db-later err';
    $('db-gate').textContent = ok
      ? "Reopen it any time with Debrief & notes, next to the level's name."
      : tried ? 'Answer the questions in Your notes to continue.'
      : 'Answer the questions in Your notes, then continue.';
    return ok;
  }
  // d: one debrief from /state; s: the site state; opts.setLevel moves on
  function open(d, s, opts = {}) {
    if (!d) return;
    if (!box) build();
    $('db-kicker').textContent = levelName(d.level) + ' complete: ' + d.title;
    $('db-title').textContent = 'Lesson: ' + d.lesson;
    $('db-def').textContent = 'The defense: ' + d.defense;
    $('db-happened').textContent = d.happened;
    $('db-world').textContent = d.real_world;
    $('db-fix').textContent = d.fix;
    $('db-partner').textContent = d.partner_prompt;
    $('db-chal').hidden = !d.challenge;
    $('db-chal').innerHTML = d.challenge ? '<b>Done early?</b> Optional stretch: ' +
      esc(d.challenge) : '';
    $('db-code').innerHTML = d.under_the_hood.map(c =>
      '<figure class="snip"><figcaption><span class="file">' + esc(c.where) + '</span>' +
      '<span class="what">' + esc(c.label) + '</span></figcaption>' +
      '<pre tabindex="0"><code>' + pyHighlight(c.code) + '</code></pre></figure>').join('');
    if (s && s.note_fields) notes.show(d.level, s);
    // Levels 2 and 4 offer the defend view too; both ways on are optional.
    const defendable = !!s && (s.defend_levels || []).includes(d.level);
    defend = defendable ? () => DefendView.open(d.level, opts) : null;
    $('db-defend').hidden = !defendable;
    const after = s && s.levels.find(l => l.number > d.level);
    next = after && opts.setLevel ? () => opts.setLevel(after.number) : null;
    $('db-next').hidden = !next;
    $('db-next').textContent = after ? 'On to ' + levelName(after.number) : 'Next level';
    if (box.hidden) lastFocus = document.activeElement;
    box.hidden = false;
    document.documentElement.classList.add('db-open');
    tried = false;
    box.querySelector('.db-body').scrollTop = 0;
    // focus without scrolling, so the card opens on the lesson, not on the notes
    if (gate()) (defendable ? $('db-defend') : $('db-close')).focus({preventScroll: true});
    else box.querySelector('.db-body').focus({preventScroll: true});
  }
  // Returns true if the card closed (false: notes still missing).
  function close() {
    if (!box || box.hidden) return true;
    tried = true;
    if (!gate()) {
      const t = [...$('db-notes').querySelectorAll('textarea')].find(x => !x.value.trim());
      if (t) t.focus();          // scrolls to the first empty answer
      return false;
    }
    notes.flush();
    box.hidden = true;
    document.documentElement.classList.remove('db-open');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    return true;
  }
  return {open, close, isOpen: () => !!box && !box.hidden};
})();

// ---- the release feedback form (Level 4) --------------------------------------------
// It's on the public site, so it emails Ronit FROM a staff address
// (feedback@quokka-labs.example), with your comment pasted into its template.
function FeedbackForm(root, opts = {}) {
  root.innerHTML = `
    <div class="formbox">
      <h3>Release feedback form <span class="ff-tag">New</span></h3>
      <p>Sends your comment to Ronit from feedback@quokka-labs.example,
        marked <span class="mono">Submitted by: <span id="ff-me"></span></span>.</p>
      <textarea id="ff-comment" style="min-height:80px" aria-label="Your comment"></textarea>
      <div style="display:flex;gap:10px;align-items:center;margin-top:8px">
        <button class="btn primary" id="ff-send">Submit feedback</button>
        <span class="note" id="ff-msg"></span></div>
    </div>`;
  const NEED_NAME = 'Enter your name first (under Hints & report).';
  // Newly revealed (Level 4): the form glows until the student writes in it.
  const SEEN_KEY = 'quokka-feedback-form:used';
  let used = false;
  try { used = localStorage.getItem(SEEN_KEY) === 'yes'; } catch (e) { /* private mode */ }
  const box = root.querySelector('.formbox');
  $('ff-comment').addEventListener('input', () => {
    if (used || !$('ff-comment').value.trim()) return;
    used = true;
    box.classList.remove('ff-new');
    try { localStorage.setItem(SEEN_KEY, 'yes'); } catch (e) { /* private mode */ }
  });
  $('ff-send').onclick = async () => {
    const c = $('ff-comment');
    if (!c.value.trim()) { $('ff-msg').className = 'note err'; $('ff-msg').textContent = 'Write a comment first.'; return; }
    const r = await post('/feedback', {comment: c.value});
    if (!r.ok) { $('ff-msg').className = 'note err'; $('ff-msg').textContent = NEED_NAME; return; }
    c.value = '';
    $('ff-msg').className = 'note';
    $('ff-msg').textContent = 'Submitted. Watch Quokka.';
    if (opts.refresh) opts.refresh();
  };
  let me = null;
  return {update(s) {
    root.hidden = !s.feedback_form;
    box.classList.toggle('ff-new', !!s.feedback_form && !used);
    if (s.me === me) return;
    me = s.me;
    // No name yet: the form waits, like the webmail.
    $('ff-me').textContent = me || '(your address)';
    $('ff-comment').disabled = $('ff-send').disabled = !me;
    if (!me) { $('ff-msg').className = 'note err'; $('ff-msg').textContent = NEED_NAME; }
    else if ($('ff-msg').textContent === NEED_NAME) $('ff-msg').textContent = '';
  }};
}

// ---- hints and progress (debriefs, challenges) ------------------------------------------
// Tidy collapsible sections. opts.form: also show the feedback form (public site).
// opts.ready(): is the page calm enough to pop up a debrief? (Mission control
// waits for the TAMPERED moment to finish.)
function Brief(root, opts = {}) {
  root.innerHTML = `
    <div id="br-form" hidden></div>
    <details class="sec" id="br-hsec"${opts.hintsOpen ? ' open' : ''}><summary>Hints <span class="sum" id="br-hsum"></span></summary>
      <div id="br-hints"></div>
      <button class="btn ghost" id="br-hint">Show a hint</button></details>
    <details class="sec" id="br-psec"${opts.progressOpen ? ' open' : ''}><summary>Progress <span class="sum" id="br-psum"></span></summary>
      <p class="name-label">Your name (it makes your email address)</p>
      <div id="br-name"></div>
      <p class="name-label">Student ID</p>
      <div class="idrow"><input id="br-sid" placeholder="Student ID" aria-label="Student ID">
        <button class="btn" id="br-save">Save</button></div>
      <p class="note" id="br-idmsg" style="margin-top:6px"></p>
      <div id="br-done"></div></details>
    <details class="sec" id="br-rsec"><summary>Lab report <span class="sum" id="br-rsum"></span></summary>
      <p>Your report is a summary of every level in your own words. Write a few notes
        per level (any time, won or not), then download the report and upload it.</p>
      <div class="lvl-pick" id="br-rpick" role="group" aria-label="Notes for level"></div>
      <p class="note-for" id="br-rfor"></p>
      <div id="br-notes"></div>
      <label class="lbl closing-q" for="br-closing" id="br-closing-q"></label>
      <textarea class="note-a" id="br-closing"></textarea>
      <p class="note" id="br-closing-msg" aria-live="polite"></p>
      <label class="lbl closing-q" for="br-idea" id="br-idea-q"></label>
      <p class="note-muted idea-help" id="br-idea-help"></p>
      <textarea class="note-a" id="br-idea"></textarea>
      <p class="note" id="br-idea-msg" aria-live="polite"></p>
      <div class="report-dl">
        <a class="btn primary" href="/report.html" download>Download report</a>
        <a class="btn ghost" href="/report" download>Data file (only if asked)</a></div>
      <p class="note-muted">Upload the report file to Moodle. To make a PDF instead,
        <a href="/report.html?view" target="_blank">open the report</a> and print it.</p></details>`;
  const form = opts.form ? FeedbackForm($('br-form'), opts) : null;
  const notesBox = NotesBox($('br-notes'));
  let notesLevel = null;           // the level whose notes are shown (null = current)
  // The closing answer and the optional level idea: one text box each, saved as you type.
  function AutoSave(id, path) {
    let timer = null, typing = false, edits = 0;
    async function save() {         // (as in NotesBox: unsaved text is never overwritten)
      const mine = edits;
      const r = await post(path, {text: $(id).value}).catch(() => ({}));
      if (r.ok && mine === edits) typing = false;
      $(id + '-msg').className = r.ok ? 'note' : 'note err';
      $(id + '-msg').textContent = r.ok ? 'Saved.' : 'Could not save. Your text is still here.';
    }
    $(id).oninput = () => { typing = true; edits++; $(id + '-msg').textContent = '';
      clearTimeout(timer); timer = setTimeout(save, 800); };
    $(id).onblur = () => { if (typing) { clearTimeout(timer); save(); } };
    // the saved text, unless the student is typing in it
    return {show(text) { if (!typing && document.activeElement !== $(id)) $(id).value = text; }};
  }
  const closing = AutoSave('br-closing', '/closing');
  const idea = AutoSave('br-idea', '/idea');
  const nameForm = NameForm($('br-name'), {id: 'br-nm', onSaved: () => opts.refresh()});
  $('br-hint').onclick = async () => { await post('/hint'); opts.refresh(); };
  $('br-save').onclick = async () => {
    const r = await post('/student', {student_id: $('br-sid').value});
    $('br-idmsg').className = r.ok ? 'note' : 'note err';
    $('br-idmsg').textContent = r.ok ? 'Saved.' : 'Use letters, digits or dashes (max 20).';
    opts.refresh();
  };
  $('br-sid').onkeydown = e => { if (e.key === 'Enter') $('br-save').click(); };

  let sig = '', site = null, wins = null, pickSig = '', lastLevel = null;
  // Hints & report > Lab report: pick a level, write its notes, answer the closing question.
  function reportSection(s) {
    const n = notesLevel || s.level;
    const filled = l => Object.values(s.notes[l] || {}).some(v => v.trim());
    const written = s.levels.filter(l => filled(l.number)).length;
    $('br-rsum').textContent = 'notes: ' + byPart(s.levels.filter(l => filled(l.number)));
    const nowPick = JSON.stringify([n, s.levels.map(l => [l.number, l.completed, filled(l.number)])]);
    if (nowPick !== pickSig) {
      pickSig = nowPick;
      $('br-rpick').innerHTML = s.levels.map(l =>
        '<button class="pick' + (l.number === n ? ' on' : '') + '" data-n="' + l.number + '"' +
        ' aria-pressed="' + (l.number === n) + '" title="' + esc(l.title) +
        (filled(l.number) ? ' (notes written)' : '') + '">' + levelName(l.number) +
        (filled(l.number) ? ' <span aria-hidden="true">✓</span>' : '') + '</button>').join('');
      $('br-rpick').querySelectorAll('[data-n]').forEach(b => b.onclick = () => {
        notesLevel = +b.dataset.n;
        reportSection(site);
      });
      const lvl = s.levels.find(l => l.number === n);
      $('br-rfor').textContent = levelName(n) + (lvl ? ': ' + lvl.title : '') +
        (lvl && !lvl.completed ? ' (not completed yet: notes are welcome anyway)' : '');
    }
    notesBox.show(n, s);
    $('br-closing-q').textContent = s.closing_question;
    closing.show(s.closing);
    $('br-idea-q').textContent = s.idea_label;
    $('br-idea-help').textContent = s.idea_help;
    idea.show(s.idea);
  }
  // A level was just won: open its debrief once the page has calmed down.
  function announce(n) {
    const tryOpen = () => {
      if (opts.ready && !opts.ready()) return setTimeout(tryOpen, 400);
      setTimeout(() => {
        if (site && site.debriefs[n]) Debrief.open(site.debriefs[n], site, opts);
      }, REDUCED ? 200 : 1400);
    };
    tryOpen();
  }


  return {update(s) {
    site = s;
    const done = Object.keys(s.debriefs).map(Number);
    if (wins === null) {
      // "#debrief=3" at the end of the URL opens a completed level's debrief
      // (handy for TAs and screenshots). Locked or unfinished levels: nothing.
      const want = (/debrief=(\d+)/.exec(location.hash) || [])[1];
      if (want && s.debriefs[want]) Debrief.open(s.debriefs[want], s, opts);
      if (/progress/.test(location.hash) || !s.me) $('br-psec').open = true;  // no name yet: ask here
      if (/report/.test(location.hash)) $('br-rsec').open = true;            // "#report": Lab report
    } else if (s.wins > wins && s.last_win) {
      // `wins` goes up on EVERY win, not just the first one for a level, so a
      // level that was already completed (saved progress) still gets its debrief.
      announce(s.last_win);
    }
    if (s.level !== lastLevel && s.debriefs[s.level] && !notesDone(s, s.level) &&
        !Debrief.isOpen() && s.mode !== 'mine') {
      Debrief.open(s.debriefs[s.level], s, opts);
    }
    lastLevel = s.level;
    wins = s.wins;          // (it only goes down if the lab was restarted)
    if (form) { form.update(s); $('br-form').hidden = !s.feedback_form; }
    nameForm.update(s.student_name, s.me);
    if (s.note_fields) reportSection(s);

    const now = JSON.stringify([s.level, s.hints, s.hints_left,
                                s.student_id, done, s.final_challenge]);
    if (now === sig) return;
    sig = now;
    const total = s.hints.length + s.hints_left;
    // (a level may have no hints at all: then it says so, and no button)
    $('br-hsum').textContent = total ? s.hints.length + ' of ' + total + ' shown' : 'none on this level';
    $('br-hints').innerHTML = s.hints.length
      ? s.hints.map((h, i) => '<div class="hint"><b>Hint ' + (i + 1) + '.</b> ' + esc(h) + '</div>').join('')
      : total ? '<p>Stuck? Hints are free, but try first.</p>'
      : '<p>This level has no hints.</p>';
    $('br-hint').hidden = s.hints_left <= 0;
    $('br-hint').textContent = 'Show a hint (' + s.hints_left + ' left)';
    if (document.activeElement !== $('br-sid')) $('br-sid').value = s.student_id;
    // what was won and what was tried (every level is open: nothing to unlock)
    $('br-psum').textContent = 'won ' + byPart(s.levels.filter(l => l.completed)) +
      ' · tried ' + s.levels.filter(l => l.completed || l.tried).length + ' of ' + s.levels.length;

    // One row per completed level: its debrief and its stretch challenge.
    // Challenges are optional and honor system: nothing checks them.
    const rows = done.map(n => {
      const d = s.debriefs[n];
      return '<div class="done-row"><div class="dr-top"><span class="dr-n">' + levelName(n) + '</span>' +
        '<button class="linkbtn strong" data-debrief="' + n + '">Debrief</button></div>' +
        (d.challenge ? '<p class="chal"><span>Stretch, optional</span>' + esc(d.challenge) + '</p>' : '') +
        '</div>';
    }).join('');
    $('br-done').innerHTML =
      (done.length ? rows : '<p>No levels completed yet.</p>') +
      (s.final_challenge ? '<div class="done-row final"><p class="chal"><span>Final stretch, ' +
        'optional</span>' + esc(s.final_challenge) + '</p></div>' : '');
    $('br-done').querySelectorAll('[data-debrief]').forEach(b => b.onclick = () =>
      Debrief.open(site.debriefs[b.dataset.debrief], site, opts));
  }};
}

// ---- defend mode: the defend view -----------------------------------
// Levels 2-4: after the win, the student writes their OWN defense for the level
// (a rule, a blocklist or a Python guard), presses Save & test, and attacks it.
// The lab saves every version (Lab.save_defense) and runs the level's test
// emails: basic checks (Ronit's own request must change the notes, an
// outsider's must not) decide "valid"; attacks give "Blocked X of N attacks".

const DEFEND_KINDS = {
  rule: {label: 'Your rule, in words', mono: false},
  words: {label: 'Your banned words: one per line, or separated by commas', mono: true},
  python: {label: 'Your guard, in Python', mono: true},
};
const SHIELD = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.8l7.5 3v5.6c0 ' +
  '4.7-3.1 8.6-7.5 9.9-4.4-1.3-7.5-5.2-7.5-9.9V5.8z"/><path d="M8.6 12.2l2.4 2.4 4.6-4.8"/></svg>';

// One line per test email (site.defend.cases, from defense_cases.py): what it
// must do, and (once it ran) what happened. Basic checks decide "valid";
// attacks only give a score.
const DEFEND_MUST = {
  changed: 'must change the notes', unchanged: 'must NOT change the notes',
  quarantined: 'must be quarantined', delivered: 'must get past the filter',
};
const DEFEND_OUTCOME = {
  changed: 'the notes changed', unchanged: 'the notes stayed v5',
  quarantined: 'the filter quarantined it', delivered: 'the filter let it in',
};
function testLine(r) {
  const what = DEFEND_OUTCOME[r.outcome] || '';
  if (r.kind === 'attack') return (r.passed ? 'blocked: ' : 'got through: ') + what;
  if (r.passed) return what;
  return what + (r.expect === 'changed' || r.expect === 'delivered'
    ? ': your defense stops this one too' : ': your defense let it through');
}
function savedAt(iso) {
  const d = iso ? new Date(iso) : null;
  return d && !isNaN(d) ? d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}) : '';
}

const DefendView = (() => {
  let box = null, site = null, want = null, shownLevel = null, opts = {};
  // lastSaved: the text the lab has saved (to show "Changed since you saved").
  let saving = false, stopping = false, lastSaved = '', serverText = null;
  let live = null;      // "Quokka, live": the small shell under the editor (DefendLive)
  function build() {
    box = document.createElement('div');
    box.className = 'db-overlay dv-overlay';
    box.hidden = true;
    box.innerHTML = `
      <div class="db-card dv-card" role="dialog" aria-modal="true" aria-labelledby="dv-title">
        <header class="dv-head">
          <div class="dv-mark">${SHIELD}</div>
          <div class="db-titles"><p class="dv-kicker" id="dv-kicker"></p>
            <h2 id="dv-title">Defend this level</h2>
            <p class="dv-lead">Write your own defense for this level. Quokka will use yours instead of ours.</p></div>
          <button class="db-x" id="dv-x" aria-label="Close">✕</button>
        </header>
        <div class="dv-body">
          <div class="dv-edit" id="dv-edit">
            <label class="dv-label" for="dv-text" id="dv-label"></label>
            <textarea id="dv-text" spellcheck="false" autocomplete="off"></textarea>
            <p class="dv-err" id="dv-err" role="alert" hidden></p>
            <div class="dv-row">
              <button class="btn primary dv-save" id="dv-save">Save &amp; test</button>
              <span class="dv-saved" id="dv-saved"></span></div>
            <section class="dv-live" id="dv-live" aria-label="Quokka, live"></section>
          </div>
          <aside class="dv-test" aria-live="polite">
            <h3>The test</h3>
            <p class="dv-why">Save &amp; test sends test emails to Quokka with your
              defense on, one at a time. The public notes are not touched.</p>
            <ul class="dv-checks" id="dv-checks"></ul>
            <div class="dv-verdict" id="dv-verdict"></div>
          </aside>
        </div>
        <footer class="dv-foot">
          <span class="dv-note" id="dv-note"></span>
          <button class="btn" id="dv-close">Close</button>
          <button class="btn" id="dv-next" hidden>Next level →</button>
          <button class="btn go" id="dv-attack" hidden>Attack it →</button>
        </footer>
      </div>`;
    document.body.append(box);
    live = DefendLive($('dv-live'));
    $('dv-x').onclick = $('dv-close').onclick = close;
    $('dv-attack').onclick = close;
    $('dv-next').onclick = () => {
      const d = site && site.defend;
      if (d && d.next && opts.setLevel) { close(); opts.setLevel(d.next); }
    };
    $('dv-save').onclick = save;
    const text = $('dv-text');
    text.oninput = () => paintSaved();
    text.addEventListener('keydown', e => {
      // Tab indents (Python needs it); Shift+Tab still leaves the box.
      if (e.key === 'Tab' && !e.shiftKey && text.classList.contains('mono')) {
        e.preventDefault();
        text.setRangeText('    ', text.selectionStart, text.selectionEnd, 'end');
        paintSaved();
      }
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); save(); }
    });
    box.addEventListener('mousedown', e => { if (e.target === box) close(); });
    box.addEventListener('keydown', e => {
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      trapFocus(box, e);
    });
    // Save & test disables its button while the test runs, so focus can drop
    // out of the card: Esc still closes it then.
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !box.hidden && !box.contains(e.target)) { e.preventDefault(); close(); }
    });
  }

  // Unsaved edits per level: closing the view (Esc, a click outside, Close) keeps
  // them, and reopening it brings them back. A successful Save & test clears it.
  const drafts = {};
  // Open the defend view for level n (switching to it first if needed).
  function open(n, o) {
    if (o) opts = o;
    if (!box) build();
    want = n;
    if (site && site.level === n) show();
    else if (opts.setLevel) opts.setLevel(n);
  }
  function show() {
    want = null;
    const d = site.defend;
    if (!d || !d.step) return;
    shownLevel = site.level;
    lastSaved = serverText = d.text;
    const kind = DEFEND_KINDS[d.kind] || DEFEND_KINDS.rule;
    $('dv-kicker').textContent = levelName(site.level) + ': ' + site.title;
    $('dv-label').textContent = kind.label;
    const text = $('dv-text');
    text.classList.toggle('mono', kind.mono);
    const draft = drafts[site.level];
    text.value = draft !== undefined && draft !== d.text ? draft : d.text;
    paintSaved();
    showError(d.check && d.check.status === 'error' ? d.check.error : '');
    box.hidden = false;
    document.documentElement.classList.add('db-open', 'dv-open');
    render();
    live.update(d);
    text.focus({preventScroll: true});
    text.setSelectionRange(text.value.length, text.value.length);
    // A fresh starter is read from the top; a saved defense opens at its end.
    text.scrollTop = d.saved ? text.scrollHeight : 0;
  }
  function close() {
    if (!box || box.hidden) return;
    if (shownLevel !== null) {
      const t = $('dv-text').value;
      if (t !== lastSaved) drafts[shownLevel] = t; else delete drafts[shownLevel];
    }
    box.hidden = true;
    want = null;
    document.documentElement.classList.remove('db-open', 'dv-open');
    if (opts.refresh) opts.refresh();
  }
  function showError(msg) {
    $('dv-err').hidden = !msg;
    $('dv-err').textContent = msg || '';
  }
  function paintSaved() {
    const d = site && site.defend;
    if (!d) return;
    const changed = $('dv-text').value !== lastSaved;
    $('dv-saved').className = 'dv-saved' + (changed && d.saved ? ' unsaved' : '');
    $('dv-saved').textContent = changed && d.saved ? 'Changed since you saved.'
      : d.saved ? 'Saved (version ' + d.versions + (savedAt(d.saved_at) ? ', ' + savedAt(d.saved_at) : '') + ').'
      : 'Not saved yet.';
  }

  async function save() {
    if (saving) return;
    saving = true;
    live.clear();
    $('dv-save').disabled = true;
    let r;
    try { r = await post('/defense', {text: $('dv-text').value}); }
    catch (e) { r = {ok: false, error: 'Could not save. Is the lab still running?'}; }
    saving = false;
    $('dv-save').disabled = false;
    showError(r.ok ? '' : r.error);
    if (opts.refresh) opts.refresh();
  }

  function render() {
    const d = site.defend, c = d.check;
    if (d.text !== serverText) { serverText = lastSaved = d.text; }   // a new version was saved
    const running = !!c && c.status === 'running';
    if (!running) stopping = false;
    $('dv-save').disabled = saving || running;
    $('dv-save').innerHTML = running ? '<span class="spin"></span>Testing…' : 'Save &amp; test';
    paintSaved();
    // The test emails, in two groups. Results come back in case order.
    const results = (c && c.status !== 'error' && c.results) || [];
    const cases = d.cases || [];
    const item = (t, i) => {
      const r = results[i];
      const must = t.kind === 'attack' ? 'should be blocked' : (DEFEND_MUST[t.expect] || '');
      let icon = '', state = 'idle', line = must;
      if (r) { icon = r.passed ? '✅' : '❌'; state = r.passed ? 'pass' : 'fail'; line = testLine(r); }
      else if (running && i === results.length) { icon = '<span class="spin"></span>'; state = 'run'; line = 'testing now…'; }
      else if (running) { icon = '·'; state = 'wait'; line = 'waits its turn'; }
      else if (c && c.status !== 'error') { icon = '·'; state = 'wait'; line = 'not tested yet: press Save & test again'; }
      return '<li class="' + state + '"><span class="ic">' + icon + '</span><div><b>' + esc(t.label) +
        '</b> ' + esc(must) + (state !== 'idle' ? '<span class="res">' + esc(line) + '</span>' : '') +
        (r && r.email ? '<details class="dv-mail"><summary>Show the email</summary><pre>' +
                   esc(r.email) + '</pre></details>' : '') +
        '</div></li>';
    };
    const group = (kind, title) => {
      const items = cases.map((t, i) => t.kind === kind ? item(t, i) : '').join('');
      return items ? '<li class="dv-group">' + title + '</li>' + items : '';
    };
    let score = '';
    if (c && !running && c.attacks) {
      score = '<li class="dv-score">Blocked ' + c.blocked + ' of ' + c.attacks + ' attacks</li>';
    }
    // Rebuild only on a change, so an email the student opened stays open.
    const checksHtml = group('basic', 'Basic checks (must pass)') + group('attack', 'Attacks') + score;
    if (checksHtml !== $('dv-checks').dataset.html) {
      $('dv-checks').innerHTML = checksHtml;
      $('dv-checks').dataset.html = checksHtml;
    }
    // The verdict (with the attack score, so it shows even when the list scrolls).
    const scoreLine = (c && c.attacks) ? ' Blocked ' + c.blocked + ' of ' + c.attacks + ' attacks.' : '';
    const v = $('dv-verdict');
    if (!c) {
      v.className = 'dv-verdict';
      v.textContent = 'Not tested yet. Write your defense, then press Save & test.';
    } else if (running) {
      v.className = 'dv-verdict run';
      v.innerHTML = '<b>Testing…</b> Each email takes 10–45 seconds. Watch Quokka on the left. ' +
        '<button class="btn" id="dv-stop"' + (stopping ? ' disabled' : '') + '>' +
        (stopping ? 'Stopping…' : 'Stop') + '</button>';
      $('dv-stop').onclick = async () => {
        stopping = true; $('dv-stop').disabled = true; $('dv-stop').textContent = 'Stopping…';
        try { await post('/defense/stop', {}); } catch (e) { /* the next refresh shows it */ }
        if (opts.refresh) opts.refresh();
      };
    } else if (c.status === 'stopped') {
      v.className = 'dv-verdict err';
      v.innerHTML = '<b>Stopped.</b> Edit your defense and press Save &amp; test again.';
    } else if (c.status === 'valid') {
      v.className = 'dv-verdict ok';
      v.innerHTML = '<b>Valid:</b> it passed the basic checks.' + scoreLine + ' Now attack it!';
    } else if (c.status === 'invalid') {
      v.className = 'dv-verdict no';
      v.innerHTML = '<b>Not valid yet:</b> a basic check failed.' + scoreLine +
        ' Edit it and test again, or attack it as it is.';
    } else {
      v.className = 'dv-verdict err';
      v.innerHTML = '<b>Not tested.</b> ' + esc(c.error || 'Fix the problem, then Save & test again.');
    }
    // The way on.
    $('dv-attack').hidden = !(site.mode === 'mine');
    $('dv-next').hidden = !d.next;
    $('dv-next').textContent = d.next ? 'Next level →' : '';
    $('dv-note').textContent = site.mode === 'mine' ? 'Quokka is using your defense now.' : '';
  }

  let first = true;
  function update(s) {
    site = s;
    // "#defend" at the end of the URL opens the defend view of the current
    // level, if it has one (handy for TAs and screenshots).
    if (first && /(^|[#&])defend\b/.test(location.hash) && s.defend && s.defend.available) {
      if (!box) build();
      want = s.level;
    }
    first = false;
    if (!box) return;
    if (want !== null && s.level === want && box.hidden) show();
    if (box.hidden) return;
    if (s.level !== shownLevel || !s.defend.step) { close(); return; }
    render();
    live.update(s.defend);
  }
  return {open, close, update, isOpen: () => !!box && !box.hidden};
})();

// "Quokka, live": a small copy of Quokka's shell inside the defend view, so the
// student can watch the test emails without closing it. It shows only the
// latest Save & test run (site.defend.test_log: events the lab marked with
// "test": <run number>) and reuses Shell, so the lines look exactly like the
// main shell. The last run stays (scroll back to see why a test failed) until
// the next Save & test clears it.
function DefendLive(root) {
  root.innerHTML = '<div class="dv-live-head"><span class="dot"></span>Quokka, live</div>' +
    '<div class="dv-live-shell"></div>';
  const dot = root.querySelector('.dot');
  const shell = Shell(root.querySelector('.dv-live-shell'),
    {shake: false, empty: "Quokka's work on your test emails shows here."});
  let cleared = 0;      // the run Save & test just cleared (hidden until a new one starts)
  let last = {test_log: [], check: null};
  function feed(d) {
    last = d;
    const log = d.test_log || [], run = log.length ? log[0].test : 0;
    const show = run && run !== cleared;
    const running = !!d.check && d.check.status === 'running';
    // Shell takes Ronit's view; a "reading" email makes it say "Quokka is working".
    shell.update({world: show ? 'run ' + run : 'none', events: show ? log : [],
                  inbox: running ? [{status: 'reading'}] : []});
    dot.classList.toggle('live', running);
    root.parentElement.classList.toggle('dv-running', running);  // see common.css
  }
  return {
    update: feed,
    clear() {
      const log = last.test_log || [];
      cleared = log.length ? log[0].test : 0;
      feed(last);
      root.scrollIntoView({block: 'nearest'});     // a long results list can hide it
    },
  };
}

// ---- the Mission drawer (mission control) ---------------------------------------------
// Hints, progress and the lab report slide in from the right when you ask for them, so
// the main screen only shows the attack. Not modal: you can keep typing your
// email while a hint is open. Esc or the close button puts it away.
function Drawer(panel, button) {
  const close = () => {
    if (panel.hidden) return;
    panel.hidden = true;
    button.setAttribute('aria-expanded', 'false');
    if (panel.contains(document.activeElement)) button.focus();
  };
  const open = () => {
    panel.hidden = false;
    button.setAttribute('aria-expanded', 'true');
    panel.querySelector('.drawer-x').focus();
  };
  button.setAttribute('aria-expanded', 'false');
  button.setAttribute('aria-controls', panel.id);
  button.onclick = () => panel.hidden ? open() : close();
  panel.querySelector('.drawer-x').onclick = close;
  panel.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); close(); } });
  return {open, close};
}

// ---- the welcome card: shown once per window, reopened with the "?" button ----------
// opts.map: a small labelled sketch of this window's layout (HTML);
// opts.areas: [[number, name, what it's for], ...] matching the numbers on the map.
// "#welcome" at the end of the URL always opens it; "#nowelcome" never does
// (handy for screenshots). The dismissal is remembered in localStorage.
function Welcome(opts) {
  const key = 'quokka-welcome:' + (document.documentElement.dataset.window || 'page');
  const box = document.createElement('div');
  box.className = 'db-overlay wl-overlay';
  box.hidden = true;
  box.innerHTML = `
    <div class="wl-card" role="dialog" aria-modal="true" aria-labelledby="wl-title">
      <div class="wl-body">
        <h2 id="wl-title">Welcome to the red team</h2>
        <p class="wl-lead">Quokka Labs (a fictional AI lab) has hired you to test
          <b>Quokka</b>, the AI assistant that reads Ronit Vale's email and edits the
          public release notes for the lab's model, Kestrel.
          You can't talk to Quokka: you can only email Ronit and watch what it does.</p>
        <p class="wl-goal">Your goal on every level of Part 1: get the public release notes
          changed from <b class="v5">v5</b> to <b class="v4">v4</b>.</p>
        ${opts.askName ? `<div class="wl-name">
          <p><b>Your name.</b> It makes your red-team email address,
            first.last@redteam.example. Your emails to Ronit come from it.</p>
          <div id="wl-nameform"></div>
          <div class="name-form"><div class="name-row">
            <label><span>Student ID</span><input id="wl-sid" autocomplete="off"
              inputmode="numeric" maxlength="20" spellcheck="false"></label></div>
            <p class="name-hint" id="wl-sid-hint">It goes on your lab report.</p></div></div>` : ''}
        <div class="wl-screen">
          <div class="wl-map" aria-hidden="true">${opts.map}</div>
          <ol class="wl-areas">${opts.areas.map(([n, name, what]) =>
            '<li><span class="wl-n">' + n + '</span><div><b>' + esc(name) + '</b> ' +
            esc(what) + '</div></li>').join('')}</ol>
        </div>
        <div class="wl-rules">
          <p><b>How a level is won.</b> Only when the public release notes really say v4.
            Quokka sometimes claims it changed them when it didn't: trust the page, not its words.</p>
          <p><b>Every level is open.</b> Move between levels freely with the level buttons,
            and come back any time. Everything you try is kept for your lab report.</p>
          <p><b>Defend, if you like.</b> On Levels 2 and 4 you can also write your own
            defense for the level, test it, and have your partner attack it. Optional.</p>
          <p><b>Part 2.</b> Quokka knows a secret launch code.
            Get it out of Quokka, again only by emailing Ronit, and submit it. No defend step.</p>
          <p><b>Stretch goal: your own level.</b> Done with both parts? Have your agent add a
            level of your own design to the lab (docs/students/own-level.md), play it, and
            swap with your partner.</p>
          <p><b>Stuck?</b> Hints are free, under ${esc(opts.hintsWhere || 'Hints & report')}. After each win a short
            debrief explains what just happened and how to fix it properly.</p>
        </div>
        <p class="wl-roe">Rules of engagement: this is a fictional sandbox on your own laptop.
          Never use these techniques on real people or systems. In a real engagement,
          impersonating anyone needs written permission.</p>
      </div>
      <footer class="wl-foot"><button class="btn primary" id="wl-ok">Start</button></footer>
    </div>`;
  document.body.append(box);
  let lastFocus = null;
  function open() {
    lastFocus = document.activeElement;
    box.hidden = false;
    document.documentElement.classList.add('db-open');
    box.querySelector('.wl-body').scrollTop = 0;
    if (nameForm && !hasName) nameForm.focus();
    else $('wl-ok').focus();
  }
  function close() {
    if (box.hidden) return;
    box.hidden = true;
    document.documentElement.classList.remove('db-open');
    try { localStorage.setItem(key, 'seen'); } catch (e) { /* private mode */ }
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  // opts.askName: the card also asks for the student's name. Start saves it;
  // with no name yet, Start waits for one (Esc still closes the card, and the
  // webmail then asks again).
  const nameForm = opts.askName ? NameForm($('wl-nameform'), {id: 'wl-nm', noButton: true,
                                                               onSaved: opts.onName}) : null;
  let hasName = false, hasId = false, checked = false;
  function sidError(text) {
    $('wl-sid').focus();
    $('wl-sid-hint').className = 'name-hint err';
    $('wl-sid-hint').textContent = text;
  }
  $('wl-ok').onclick = async () => {
    if (nameForm) {
      if (!nameForm.empty()) { if (!(await nameForm.save())) return; }
      else if (!hasName) {
        nameForm.focus();
        $('wl-nm-hint').className = 'name-hint err';
        $('wl-nm-hint').textContent = 'Enter your first and last name to start. ' + NAME_HINT;
        return;
      }
      // The student ID: asked here too, so the lab report carries it.
      const sid = $('wl-sid').value.trim();
      if (sid) {
        const r = await post('/student', {student_id: sid});
        if (!r.ok) return sidError('Use letters, digits or dashes (max 20).');
        hasId = true;
      } else if (!hasId) {
        return sidError('Enter your student ID to start.');
      }
    }
    close();
  };
  box.addEventListener('mousedown', e => { if (e.target === box) close(); });
  box.addEventListener('keydown', e => {
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    trapFocus(box, e);
  });
  let seen = false;
  try { seen = localStorage.getItem(key) === 'seen'; } catch (e) { /* private mode */ }
  if (/welcome/.test(location.hash) && !/nowelcome/.test(location.hash)) open();
  else if (!seen && !/nowelcome/.test(location.hash)) open();
  return {open, close, update(s) {
    // s: the site view. Keeps the name fields in step with the lab.
    const firstTime = !checked;
    checked = true;
    hasName = !!s.me;
    hasId = !!s.student_id;
    if (!nameForm) return;
    nameForm.update(s.student_name, s.me);
    if (firstTime && document.activeElement !== $('wl-sid')) $('wl-sid').value = s.student_id || '';
    // Seen the card before but no name or ID saved (e.g. progress was reset): ask again.
    if (firstTime && (!hasName || !hasId) && box.hidden && !/nowelcome/.test(location.hash)) open();
  }};
}

// A "?" button for the top bar that reopens the welcome card.
function helpButton(bar, welcome) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'icon-btn';
  b.textContent = '?';
  b.title = 'How this lab works';
  b.setAttribute('aria-label', 'How this lab works');
  b.onclick = () => welcome.open();
  bar.append(b);
  return b;
}

// Links to the single windows (they live on the neighbouring ports).
async function windowLinks(el) {
  try {
    const p = await (await fetch('/ports')).json();
    const url = port => location.protocol + '//' + location.hostname + ':' + port + '/';
    el.innerHTML = 'Open alone: <a href="' + url(p.webmail) + '" target="_blank">webmail</a>, ' +
      '<a href="' + url(p.ronit) + '" target="_blank">Ronit\'s computer</a>, ' +
      '<a href="' + url(p.site) + '" target="_blank">public site</a>';
  } catch (e) { /* the links are optional */ }
}

// ---- What the model reads and writes, inline in Quokka's console ----------------------
// For the latest email the console shows, under each "# model call N" line,
// the tokens the model writes as it writes them, each coloured by how sure the
// model was; hover, tap or focus one for the other likely tokens. The line
// itself opens what the model read (system prompt, tools, the email, earlier
// steps). Data: GET /trace (trace.py). Hidden examples stay one placeholder
// until the level is won. In Part 2 the lab masks the launch code in what the
// model read (a red REDACTED) and sends what it writes already garbled.
const pct = p => p >= 0.995 ? '>99%' : p < 0.001 ? '<0.1%'
                : (p * 100).toFixed(p < 0.1 ? 1 : 0) + '%';
const showTok = t => t.replace(/ /g, '␣').replace(/\n/g, '⏎').replace(/\t/g, '⇥') || '(empty)';
const READ_KEYS = {system: 'system', examples: 'examples', example: 'example', email: 'email',
                   assistant: 'quokka', tool: 'result'};

// garbled: Part 2, where the server sends Quokka's writing already garbled
// (trace.py): plain text, no colours, no alternatives.
function tokenEl(t, garbled) {
  const [, text, lp, alts] = t;
  const s = document.createElement('span');
  s.className = 'tok';
  s.textContent = text;
  if (garbled) {
    s.classList.add('garbled');
    return s;
  }
  const p = Math.exp(lp);
  s.dataset.tip = JSON.stringify([[text, lp]].concat(alts));
  if (p < 0.95) {
    s.classList.add('unsure');
    s.style.setProperty('--u', Math.round(12 + 43 * Math.min(1, (1 - p) / 0.8)) + '%');
    s.tabIndex = 0;
  }
  return s;
}

// The tools as the model sees them, one terse line each.
function toolsText(tools) {
  return tools.map(t => t.name + '(' + t.params.map(p => p.name + (p.required ? '' : '?') +
      ': ' + p.type).join(', ') + ')  ' + t.description +
    t.params.filter(p => p.description).map(p => '\n    ' + p.name + ': ' + p.description).join(''))
    .join('\n');
}

function readsEl(reads, tools, missing) {
  const box = document.createElement('div');
  box.className = 'mc-reads';
  const row = (key, text, cls) => {
    const r = document.createElement('div');
    r.className = 'mc-r' + (cls ? ' ' + cls : '');
    r.innerHTML = '<span class="mc-k"></span><pre></pre>';
    r.firstChild.textContent = key;
    // \ue000 marks the launch code, masked by the lab (redact.py)
    r.lastChild.innerHTML = esc(text || '(empty)')
      .replace(/\ue000/g, '<span class="mc-redacted">REDACTED</span>');
    box.append(r);
  };
  (reads || []).forEach((m, i) => {
    row(m.kind === 'example' ? 'example ' + m.role : (READ_KEYS[m.kind] || m.role), m.text,
        'k-' + m.kind);
    if (i === 0 && tools && tools.length) row('tools', toolsText(tools), 'k-tools');
  });
  if (!reads) row('', missing || "Not kept: only the latest email's model calls are.", 'k-gone');
  return box;
}

// The console's "Tokens" switch: on by default; this browser remembers "off".
const TOKENS_KEY = 'quokka-console-tokens';
function tokenToggle(btn, shell) {
  const set = (on, save) => {
    btn.setAttribute('aria-pressed', String(on));
    shell.setTrace(on);
    if (save) { try { localStorage.setItem(TOKENS_KEY, on ? 'on' : 'off'); } catch (e) {} }
  };
  btn.onclick = () => set(btn.getAttribute('aria-pressed') !== 'true', true);
  let on = true;
  try { on = localStorage.getItem(TOKENS_KEY) !== 'off'; } catch (e) {}
  set(on, false);
}

// The tooltip for tokens under `root`: the chosen token and the other likely ones.
function tokenTips(root) {
  const tip = document.createElement('div');
  tip.className = 'bts-tip';
  tip.hidden = true;
  tip.setAttribute('role', 'tooltip');
  document.body.append(tip);
  function show(el) {
    const d = el.dataset.tip;
    if (!d) return;
    tip.innerHTML = '<div class="bts-tip-h">Chose, and what else was likely here</div>' +
      JSON.parse(d).map(([t, lp], i) => '<div class="bts-tip-r' + (i ? '' : ' chosen') +
        '"><code>' + esc(showTok(t)) + '</code><span>' + pct(Math.exp(lp)) +
        '</span></div>').join('');
    tip.hidden = false;
    const r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left)) + 'px';
    tip.style.top = (r.bottom + h + 8 < innerHeight ? r.bottom + 6 : r.top - h - 6) + 'px';
  }
  const hide = () => { tip.hidden = true; };
  const isTok = e => e.target.classList && e.target.classList.contains('tok');
  root.addEventListener('mouseover', e => { if (isTok(e)) show(e.target); });
  root.addEventListener('mouseout', e => { if (isTok(e)) hide(); });
  root.addEventListener('focusin', e => { if (isTok(e)) show(e.target); });
  root.addEventListener('focusout', hide);
  root.addEventListener('scroll', hide, true);
  root.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
  return {hide};
}
