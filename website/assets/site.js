/* Thetis landing page: the sticky nav, the photo demo and the dose card. The page reads fine without this file. */
(function () {
  'use strict';

  var calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Nav turns white once the page moves */
  var nav = document.getElementById('nav');
  function onScroll() { nav.classList.toggle('is-stuck', window.scrollY > 8); }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------- The photo demo: outlines draw across the slide, and any call can be corrected */
  var lab = document.getElementById('lab');
  if (lab) photoDemo(lab);

  function photoDemo(root) {
    var ORDER = ['live', 'abnormal', 'dead'];
    var NAME = { live: 'Live', abnormal: 'Abnormal', dead: 'Dead' };
    var STEP_MS = 13;
    var stocked = 10000000;
    // Same estimate as the app: counted live and abnormal, over the volume in view, scaled up by the sample (20 L, 50×).
    var per_larva = (1 / 0.0049152) * 1000 * (20 / 50);

    var stage = root.querySelector('.slide');
    var svg = stage.querySelector('svg');
    var tip = stage.querySelector('.tip');
    var status = root.querySelector('[data-lab-status]');
    var paths = Array.prototype.slice.call(svg.querySelectorAll('path'));
    var start = paths.map(function (p) { return { c: p.getAttribute('data-c'), u: p.hasAttribute('data-u') }; });

    // Left to right, so the outlines sweep across the slide
    var byX = paths.slice().sort(function (a, b) { return centre(a).x - centre(b).x; });
    byX.forEach(function (p, i) {
      p.setAttribute('data-rank', i);
      p.style.setProperty('--i', i);
      p.setAttribute('tabindex', i === 0 ? '0' : '-1');
      p.setAttribute('role', 'button');
      p.setAttribute('aria-label', spoken(p));
      if (p.hasAttribute('data-u')) addBadge(p);
    });

    function centre(p) {
      var b = p.getBBox();
      return { x: b.x + b.width / 2, y: b.y + b.height / 2, top: b.y, right: b.x + b.width };
    }

    function spoken(p) {
      var unsure = p.hasAttribute('data-u') ? ', unsure' : '';
      return NAME[p.getAttribute('data-c')] + unsure + ', ' + p.getAttribute('data-um') + ' micrometres. Press Enter to change.';
    }

    function addBadge(p) {
      var c = centre(p);
      var mark = document.createElement('span');
      mark.className = 'q';
      mark.textContent = '?';
      mark.setAttribute('aria-hidden', 'true');
      mark.style.left = (Math.min(c.right, 1590) / 16) + '%';
      mark.style.top = (Math.max(c.top, 10) / 12) + '%';
      p.mark = mark;
      stage.appendChild(mark);
    }

    function counts(limit) {
      var n = { live: 0, abnormal: 0, dead: 0, unsure: 0 };
      paths.forEach(function (p) {
        if (limit !== undefined && Number(p.getAttribute('data-rank')) >= limit) return;
        n[p.getAttribute('data-c')] += 1;
        if (p.hasAttribute('data-u')) n.unsure += 1;
      });
      return n;
    }

    function millions(value) { return (value / 1000000).toFixed(1) + 'M'; }

    function render(limit) {
      var n = counts(limit);
      var total = n.live + n.abnormal + n.dead;
      ORDER.forEach(function (c) {
        root.querySelector('[data-n="' + c + '"]').textContent = n[c];
        root.querySelector('[data-p="' + c + '"]').textContent = (total ? Math.round((n[c] / total) * 100) : 0) + '% of counted';
      });
      root.querySelector('[data-unsure]').textContent = limit === undefined && n.unsure === 0 ? 'Nothing left to check.' : n.unsure + ' to check';
      var estimate = (n.live + n.abnormal) * per_larva;
      root.querySelector('[data-est]').textContent = millions(estimate);
      root.querySelector('[data-est-pct]').textContent = Math.round((estimate / stocked) * 100) + '%';
      return n;
    }

    /* Tooltip */
    function showTip(p) {
      var c = centre(p);
      var verb = window.matchMedia('(hover: none)').matches ? 'Tap' : 'Click';
      var unsure = p.hasAttribute('data-u') ? ' · Unsure' : '';
      tip.innerHTML = '';
      tip.appendChild(document.createTextNode(NAME[p.getAttribute('data-c')] + ' · ' + p.getAttribute('data-um') + ' µm' + unsure));
      var hint = document.createElement('span');
      hint.textContent = verb + ' to change';
      tip.appendChild(hint);
      tip.style.left = Math.max(12, Math.min(88, c.x / 16)) + '%';
      var below = c.top < 170;
      tip.classList.toggle('below', below);
      tip.style.top = (below ? (c.top + (c.y - c.top) * 2) : c.top) / 12 + '%';
      tip.hidden = false;
    }
    function hideTip() { tip.hidden = true; }

    /* Correcting a call */
    var tipTimer = null;
    function correct(p) {
      var next = ORDER[(ORDER.indexOf(p.getAttribute('data-c')) + 1) % ORDER.length];
      p.setAttribute('data-c', next);
      p.removeAttribute('data-u');
      if (p.mark) p.mark.hidden = true;
      p.setAttribute('aria-label', spoken(p));
      var n = render();
      showTip(p);
      clearTimeout(tipTimer);
      if (window.matchMedia('(hover: none)').matches) tipTimer = setTimeout(hideTip, 1800);
      status.textContent = 'Changed to ' + NAME[next] + '. Live ' + n.live + ', abnormal ' + n.abnormal + ', dead ' + n.dead + '.';
    }

    svg.addEventListener('click', function (e) {
      if (e.target.tagName.toLowerCase() === 'path') correct(e.target);
    });
    svg.addEventListener('pointerover', function (e) {
      if (e.target.tagName.toLowerCase() === 'path') showTip(e.target);
    });
    svg.addEventListener('pointerout', function (e) {
      if (e.target.tagName.toLowerCase() === 'path' && e.pointerType === 'mouse') hideTip();
    });
    svg.addEventListener('focusin', function (e) {
      if (e.target.matches && e.target.matches(':focus-visible')) showTip(e.target);
    });
    svg.addEventListener('focusout', hideTip);
    svg.addEventListener('keydown', function (e) {
      var p = e.target;
      if (p.tagName.toLowerCase() !== 'path') return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        correct(p);
        return;
      }
      var step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      if (!step) return;
      e.preventDefault();
      var at = Number(p.getAttribute('data-rank'));
      var to = byX[(at + step + byX.length) % byX.length];
      p.setAttribute('tabindex', '-1');
      to.setAttribute('tabindex', '0');
      to.focus();
    });

    /* Saving the check */
    var save = root.querySelector('[data-save]');
    function saved(isSaved) {
      Array.prototype.forEach.call(save.querySelectorAll('[data-when]'), function (el) {
        el.hidden = el.getAttribute('data-when') !== (isSaved ? 'saved' : 'ready');
      });
    }
    saved(false);
    save.querySelector('[data-save-btn]').addEventListener('click', function () {
      saved(true);
      status.textContent = 'Check saved. T-03 is now Critical. 3 decisions waiting.';
      save.querySelector('[data-save-link]').focus();
    });

    /* The sweep */
    var played = false;
    var timer = null;
    function play() {
      played = true;
      hideTip();
      if (calm) { render(); return; }
      clearTimeout(timer);
      stage.classList.add('armed');
      stage.classList.remove('run');
      void stage.getBoundingClientRect();
      stage.classList.add('run');
      var began = performance.now();
      (function frame(now) {
        var shown = Math.floor((now - began) / STEP_MS);
        if (shown < paths.length) {
          render(shown);
          requestAnimationFrame(frame);
        } else {
          render();
        }
      })(began);
      timer = setTimeout(function () { stage.classList.remove('armed', 'run'); }, paths.length * STEP_MS + 560);
    }

    root.querySelector('[data-lab-replay]').addEventListener('click', function () {
      paths.forEach(function (p, i) {
        p.setAttribute('data-c', start[i].c);
        if (start[i].u) p.setAttribute('data-u', '');
        if (p.mark) p.mark.hidden = false;
        p.setAttribute('aria-label', spoken(p));
      });
      saved(false);
      status.textContent = 'Back to the first analysis.';
      play();
    });

    if ('IntersectionObserver' in window && !calm) {
      stage.classList.add('armed');
      new IntersectionObserver(function (entries, observer) {
        if (entries[0].isIntersecting && !played) {
          observer.disconnect();
          play();
        }
      }, { threshold: 0.35 }).observe(stage);
    }
  }

  /* ---------- The dose card: switch the chemical, approve a step */
  var dose = document.getElementById('dose');
  if (dose) {
    var outs = dose.querySelectorAll('.dose-out');
    var chem = document.querySelector('[data-chem]');
    dose.addEventListener('change', function (e) {
      if (e.target.name !== 'buffer') return;
      Array.prototype.forEach.call(outs, function (out) { out.hidden = out.getAttribute('data-k') !== e.target.value; });
      chem.textContent = e.target.getAttribute('data-name');
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll('.step'), function (step) {
    var actions = step.querySelector('.step-actions');
    var state = step.querySelector('.step-state');
    step.addEventListener('click', function (e) {
      var button = e.target.closest ? e.target.closest('[data-act]') : null;
      if (!button) return;
      var act = button.getAttribute('data-act');
      if (act === 'undo') {
        step.removeAttribute('data-state');
        state.hidden = true;
        actions.hidden = false;
        actions.querySelector('button').focus();
      } else {
        step.setAttribute('data-state', act);
        state.querySelector('.state-text').textContent = act === 'approve' ? step.getAttribute('data-done') : 'Dismissed';
        actions.hidden = true;
        state.hidden = false;
        state.querySelector('button').focus();
      }
    });
  });
})();
