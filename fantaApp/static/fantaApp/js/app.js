/* FantaF1 — comportamenti globali: toggle tema, menu mobile, toast */
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

  // Menu mobile
  var navToggle = document.getElementById('nav-toggle');
  var navMenu = document.getElementById('nav-menu');
  if (navToggle && navMenu) {
    navToggle.addEventListener('click', function () {
      navMenu.classList.toggle('hidden');
    });
  }

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
