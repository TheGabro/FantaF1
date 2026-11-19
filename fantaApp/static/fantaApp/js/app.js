/* FantaF1 — comportamenti globali: toggle tema, menu, toast */
(function () {
  'use strict';

  // Toggle tema (l'inizializzazione avviene inline in <head> per evitare flash)
  var themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', function () {
      var next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem('ff1-theme', next); } catch (e) { /* storage non disponibile */ }
      // Barra del browser sul telefono (#296): stesso colore dell'header nel tema scelto.
      var bars = document.querySelectorAll('meta[name="theme-color"]');
      for (var i = 0; i < bars.length; i++) bars[i].content = bars[i].getAttribute('data-' + next);
    });
  }

  // Menu a tendina (oggi il menu utente): il pulsante [data-menu-toggle] apre il
  // pannello indicato da aria-controls, che si mostra con l'attributo data-open.
  var toggles = Array.prototype.slice.call(document.querySelectorAll('[data-menu-toggle]'));
  var setOpen = function (toggle, open) {
    var panel = document.getElementById(toggle.getAttribute('aria-controls'));
    if (!panel) return;
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) panel.setAttribute('data-open', '');
    else panel.removeAttribute('data-open');
  };
  var isOpen = function (toggle) { return toggle.getAttribute('aria-expanded') === 'true'; };
  var panelOf = function (toggle) { return document.getElementById(toggle.getAttribute('aria-controls')); };

  toggles.forEach(function (toggle) {
    toggle.addEventListener('click', function () { setOpen(toggle, !isOpen(toggle)); });
  });
  // Escape chiude i menu aperti e riporta il focus sul loro pulsante.
  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    toggles.forEach(function (toggle) {
      if (!isOpen(toggle)) return;
      setOpen(toggle, false);
      toggle.focus();
    });
  });
  // Un clic fuori dal pulsante e dal suo pannello chiude il menu.
  document.addEventListener('click', function (event) {
    toggles.forEach(function (toggle) {
      var panel = panelOf(toggle);
      if (!isOpen(toggle) || toggle.contains(event.target) || (panel && panel.contains(event.target))) return;
      setOpen(toggle, false);
    });
  });

  // Toast: si chiudono con «×». Gli errori (role="alert") restano finché non
  // si chiudono (WCAG 2.2.1); gli altri spariscono dopo 6 secondi, ma non
  // mentre hanno il puntatore sopra o il focus: il conto riparte quando escono.
  document.querySelectorAll('[data-toast]').forEach(function (toast) {
    var close = toast.querySelector('[data-toast-close]');
    var timer = null;
    var hovered = false;
    var focused = false;
    var remove = function () {
      clearTimeout(timer);
      toast.style.transition = 'opacity .3s';
      toast.style.opacity = '0';
      setTimeout(function () { toast.remove(); }, 300);
    };
    var schedule = function () {
      clearTimeout(timer);
      if (!hovered && !focused) timer = setTimeout(remove, 6000);
    };
    if (close) close.addEventListener('click', remove);
    if (toast.getAttribute('role') === 'alert') return;

    toast.addEventListener('mouseenter', function () { hovered = true; clearTimeout(timer); });
    toast.addEventListener('mouseleave', function () { hovered = false; schedule(); });
    toast.addEventListener('focusin', function () { focused = true; clearTimeout(timer); });
    toast.addEventListener('focusout', function (event) {
      if (toast.contains(event.relatedTarget)) return;
      focused = false;
      schedule();
    });
    schedule();
  });
})();
