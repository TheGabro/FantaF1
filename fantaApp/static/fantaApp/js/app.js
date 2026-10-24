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
    });
  }

  // Menu (pannello mobile e menu utente): il pulsante [data-menu-toggle] apre il
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

  // Toast: chiusura manuale e auto-dismiss
  document.querySelectorAll('[data-toast]').forEach(function (toast) {
    var close = toast.querySelector('[data-toast-close]');
    var remove = function () {
      toast.style.transition = 'opacity .3s';
      toast.style.opacity = '0';
      setTimeout(function () { toast.remove(); }, 300);
    };
    if (close) close.addEventListener('click', remove);
    setTimeout(remove, 6000);
  });
})();
