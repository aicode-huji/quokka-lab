// The "next step" guide on mission control (port 9080).
//
// One short tip at a time, shown inside the panel to use next, which also gets
// a soft outline. It follows what the student has done:
//   start  nothing sent yet               -> your email panel
//   watch  Quokka is busy with an email    -> Quokka's shell
//   check  the run ended, notes still v5   -> the release notes
//   stuck  a few tries ended, still v5     -> the Hints & report button
//          (Part 2: a few tries ended, no code submitted yet: the same, worded for the code)
//   form   a level adds the feedback form  -> the form (says it exists, nothing more)
//   defend the defend view is open, nothing saved for this level yet -> its editor
// After the first level is won, only "stuck" and "form" are left: the student
// knows the loop by then.
//
// The tips never name an attack, a defense or a lesson: they only say where to
// look. "Hide tip" hides a tip for good (remembered in this browser; "#guide" at
// the end of the URL brings them all back).

function Guide(opts) {
  const KEY = 'quokka-guide:';
  const TIPS = {
    start: {at: 'p-webmail', text: 'Start here: write an email to Ronit.'},
    watch: {at: 'p-shell', text: 'Watch Quokka read your email.'},
    check: {at: 'p-public', text: 'Did the release notes change? Still v5: try a different email.'},
    stuck: {at: 'p-public', ring: ['mission-btn'], text: 'Still v5. Stuck? Hints are under Hints & report.'},
    stuck2: {at: 'p-public', ring: ['mission-btn'], text: 'No launch code yet? Hints are under Hints & report.'},
    form: {at: 'p-public', ring: ['feedback'], text: 'New on this level: a feedback form, under the release notes.'},
    defend: {at: 'dv-edit', ring: ['dv-save'], text: 'Write your defense, then Save & test.'},
  };
  const STUCK_AFTER = 3;   // finished tries on this level before pointing at the hints

  const remember = {
    get(k) { try { return localStorage.getItem(KEY + k) === 'done'; } catch (e) { return false; } },
    set(k) { try { localStorage.setItem(KEY + k, 'done'); } catch (e) { /* private mode */ } },
    clear() {
      try {
        Object.keys(localStorage).filter(k => k.startsWith(KEY))
          .forEach(k => localStorage.removeItem(k));
      } catch (e) { /* private mode */ }
    },
  };
  if (/(^|[#&])guide\b/.test(location.hash)) remember.clear();

  const tip = document.createElement('div');
  tip.className = 'guide-tip';
  tip.setAttribute('role', 'status');
  tip.innerHTML = '<span class="guide-dot" aria-hidden="true"></span>' +
    '<span class="guide-text"></span>' +
    '<button type="button" class="guide-ok" title="Hide this tip for good">Hide tip</button>';
  const text = tip.querySelector('.guide-text');
  let current = null, key = null, lit = [];

  tip.querySelector('.guide-ok').onclick = () => {
    if (key) remember.set(key);
    show(null);
  };

  function show(id) {
    if (id === current) return;
    current = id;
    lit.forEach(el => el.classList.remove('guide-on'));
    lit = [];
    if (!id) { tip.remove(); return; }
    const t = TIPS[id], panel = $(t.at);
    text.textContent = t.text;
    // Right under the panel's title bar: it never covers what is in the panel.
    // (The defend view has no title bar: there the tip goes at the top.)
    const head = panel.querySelector('.panel-h');
    if (head) head.after(tip); else panel.prepend(tip);
    // (the ring goes on the panel itself, or on the one thing in it to look at)
    lit = (t.ring ? t.ring.map($) : [panel]).filter(Boolean);
    // (restart the pulse so a new tip is noticed)
    lit.forEach(el => { el.classList.remove('guide-on'); void el.offsetWidth; el.classList.add('guide-on'); });
  }

  // s: the split view (see Lab.view("split")); busy: is Quokka still at work
  // (an email queued or being read, or the shell still typing)?
  function pick(s, busy) {
    const site = s.site, level = site.level;
    const won = site.levels.some(l => l.completed);        // any level, ever
    const tries = s.ronit.inbox.filter(m => !m.from.startsWith('quokka@'));
    const ended = tries.filter(m => ['done', 'quarantined', 'stopped'].includes(m.status)).length;
    const last = tries[tries.length - 1];
    // (a crash is the model's fault: no "try a different email" tip then)
    const crashed = !!last && last.status === 'failed';
    const want = [];
    if (site.version === site.target) return null;          // the level is won: the debrief takes over
    // (no "Hints are under..." tip on a level that has no hints)
    const noHints = !site.hints.length && !site.hints_left;
    if (site.secret) {          // Part 2: the student knows the loop by now
      const cur = site.levels.find(l => l.number === level) || {};
      if (cur.completed || busy || ended < STUCK_AFTER || noHints) return null;
      return remember.get('stuck:' + level) ? null : ['stuck2', 'stuck:' + level];
    }
    if (site.feedback_form && !tries.some(m => m.from === 'feedback@quokka-labs.example'))
      want.push(['form', 'form:' + level]);
    if (busy) { if (!won) want.push(['watch', 'watch']); }
    else if (!tries.length) { if (!won) want.push(['start', 'start']); }
    else if (ended >= STUCK_AFTER) { if (!noHints) want.push(['stuck', 'stuck:' + level]); }
    else if (!won && !crashed) want.push(['check', 'check']);
    return want.find(([, k]) => !remember.get(k)) || null;
  }

  return {update(s, busy) {
    // Wait while the welcome card or a debrief is open (they cover the page anyway).
    // In the defend view, the only tip is the defend one.
    const html = document.documentElement;
    const d = s.site.defend || {};
    const next = html.classList.contains('dv-open')
      ? (!d.saved && !remember.get('defend:' + s.site.level) ? ['defend', 'defend:' + s.site.level] : null)
      : html.classList.contains('db-open') ? null : pick(s, busy);
    key = next && next[1];
    show(next && next[0]);
  }};
}
