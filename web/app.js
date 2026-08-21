/* Debugging Saga frontend. Vanilla JS, no build step. Talks to the API via
   the base URL injected as config.js at deploy. */

(function () {
  'use strict';

  var API = (window.DSG_API_BASE || '').replace(/\/$/, '');
  var state = {
    mode: 'showcase',
    sagas: [],
    tones: [],
    selectedSaga: null,
    selectedTone: null,
    busy: false
  };

  var el = function (id) { return document.getElementById(id); };

  var WAITING_LINES = [
    'The bard is composing. Five to twenty seconds of artistic suffering.',
    'The narrator is clearing their throat.',
    'Consulting the muses. The muses are rate-limited.',
    'Dramatizing. The facts are being kept safe.'
  ];

  // ---- rendering ----

  function renderShowcase() {
    var wrap = el('showcase-cards');
    wrap.innerHTML = '';
    state.sagas.forEach(function (s) {
      var b = document.createElement('button');
      b.className = 'card' + (state.selectedSaga === s.id ? ' selected' : '');
      b.setAttribute('data-id', s.id);
      b.innerHTML =
        '<div class="card-title"></div>' +
        '<div class="card-meta"></div>' +
        '<div class="card-teaser"></div>';
      b.querySelector('.card-title').textContent = s.title;
      b.querySelector('.card-meta').textContent = s.project + ' · ' + s.date;
      b.querySelector('.card-teaser').textContent = s.teaser;
      b.addEventListener('click', function () {
        state.selectedSaga = s.id;
        renderShowcase();
        updateGenerate();
      });
      wrap.appendChild(b);
    });
  }

  function renderTones() {
    var wrap = el('tone-pills');
    wrap.innerHTML = '';
    state.tones.forEach(function (t) {
      var b = document.createElement('button');
      b.className = 'pill' + (state.selectedTone === t.id ? ' selected' : '');
      b.setAttribute('role', 'radio');
      b.setAttribute('aria-checked', String(state.selectedTone === t.id));
      b.textContent = t.name;
      b.addEventListener('click', function () {
        state.selectedTone = t.id;
        renderTones();
        updateGenerate();
      });
      wrap.appendChild(b);
    });
  }

  function updateGenerate() {
    var ready = !state.busy && state.selectedTone &&
      (state.mode === 'showcase'
        ? !!state.selectedSaga
        : el('own-text').value.trim().length > 0);
    el('generate').disabled = !ready;
  }

  function setMode(mode) {
    state.mode = mode;
    el('mode-showcase').classList.toggle('active', mode === 'showcase');
    el('mode-own').classList.toggle('active', mode === 'own');
    el('mode-showcase').setAttribute('aria-selected', String(mode === 'showcase'));
    el('mode-own').setAttribute('aria-selected', String(mode === 'own'));
    el('showcase-pane').hidden = mode !== 'showcase';
    el('own-pane').hidden = mode !== 'own';
    updateGenerate();
  }

  function setStatus(msg, isError) {
    var s = el('status');
    s.textContent = msg || '';
    s.className = 'status' + (isError ? ' error' : '');
  }

  function showResult(data, truthText) {
    el('saga-title').textContent = data.title;
    var credits = data.tone_name + ' · written by ' + data.model;
    if (data.audio) {
      credits += ' · narrated by ' + data.audio.voice;
    }
    el('credits').textContent = credits;

    var player = el('player');
    var note = el('audio-note');
    if (data.audio) {
      player.src = data.audio.url;
      player.hidden = false;
      note.hidden = true;
    } else {
      player.removeAttribute('src');
      player.hidden = true;
      note.textContent = 'The narrator lost their voice (' +
        (data.audio_error || 'unknown reason') + '). The text stands alone.';
      note.hidden = false;
    }

    var textWrap = el('saga-text');
    textWrap.innerHTML = '';
    data.saga.split(/\n\n+/).forEach(function (para) {
      var p = document.createElement('p');
      p.textContent = para;
      textWrap.appendChild(p);
    });

    el('truth-text').textContent = truthText;
    el('truth').open = false;
    el('result').hidden = false;
    el('result').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ---- unattended premiere ----

  function renderAutoPremiere(rec) {
    if (!rec) return;
    el('auto-title').textContent = rec.title;
    var credits = rec.tone_name + ' · written by ' + rec.model;
    if (rec.audio) { credits += ' · narrated by ' + rec.audio.voice; }
    el('auto-credits').textContent = credits;

    var player = el('auto-player');
    var note = el('auto-audio-note');
    if (rec.audio) {
      player.src = rec.audio.url;
      player.hidden = false;
      note.hidden = true;
    } else {
      player.removeAttribute('src');
      player.hidden = true;
      note.textContent = 'The narrator lost their voice (' +
        (rec.audio_error || 'unknown reason') + '). The text stands alone.';
      note.hidden = false;
    }

    var textWrap = el('auto-saga-text');
    textWrap.innerHTML = '';
    rec.saga.split(/\n\n+/).forEach(function (para) {
      var p = document.createElement('p');
      p.textContent = para;
      textWrap.appendChild(p);
    });

    el('auto-note').textContent = 'Generated on its own at ' +
      rec.generated_at.replace('T', ' ').slice(0, 16) + ' UTC, no human involved. ' +
      'Rotates through the showcase automatically every few hours.';
    el('now-showing').hidden = false;
  }

  function fetchAutoPremiere() {
    fetch(API + '/latest-auto')
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) { renderAutoPremiere(data.latest); })
      .catch(function () { /* the premiere is a bonus, not the main act */ });
  }

  // ---- actions ----

  function generate() {
    if (state.busy) return;
    state.busy = true;
    updateGenerate();
    el('result').hidden = true;
    setStatus(WAITING_LINES[Math.floor(Math.random() * WAITING_LINES.length)]);

    var body = { tone: state.selectedTone };
    var truthText;
    if (state.mode === 'showcase') {
      body.showcase_id = state.selectedSaga;
      var entry = state.sagas.find(function (s) { return s.id === state.selectedSaga; });
      truthText = entry ? entry.story : '';
    } else {
      body.text = el('own-text').value.trim();
      truthText = body.text;
    }

    fetch(API + '/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function (r) {
        return r.json().then(function (data) { return { ok: r.ok, data: data }; });
      })
      .then(function (res) {
        if (!res.ok) {
          throw new Error(res.data.error || 'the stage machinery jammed');
        }
        setStatus('');
        showResult(res.data, truthText);
      })
      .catch(function (err) {
        setStatus('No saga this time: ' + err.message + '. Try again in a moment.', true);
      })
      .finally(function () {
        state.busy = false;
        updateGenerate();
      });
  }

  // ---- init ----

  el('mode-showcase').addEventListener('click', function () { setMode('showcase'); });
  el('mode-own').addEventListener('click', function () { setMode('own'); });
  el('own-text').addEventListener('input', function () {
    el('char-count').textContent = String(el('own-text').value.length);
    updateGenerate();
  });
  el('generate').addEventListener('click', generate);
  el('again').addEventListener('click', function () {
    el('result').hidden = true;
    el('player').pause();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  if (!API) {
    el('showcase-cards').innerHTML = '';
    setStatus('No API configured. config.js is missing its base URL.', true);
    return;
  }

  fetchAutoPremiere();

  fetch(API + '/showcase')
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (data) {
      state.sagas = data.sagas;
      state.tones = data.tones;
      renderShowcase();
      renderTones();
    })
    .catch(function (err) {
      el('showcase-cards').innerHTML = '';
      var p = document.createElement('p');
      p.className = 'loading-note';
      p.textContent = 'Could not fetch the repertoire (' + err.message +
        '). Refresh, or bring your own bug; the paste box still works.';
      el('showcase-cards').appendChild(p);
    });
})();
