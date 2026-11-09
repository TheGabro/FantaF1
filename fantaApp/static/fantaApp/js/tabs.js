/* FantaF1 — schede dentro una pagina (#233).
   Un contenitore [data-tabs] con link [data-tab="x"] (href="#x") e sezioni
   [data-tab-panel="x"]: si mostra una sezione alla volta, la prima o quella
   dell'ancora nell'indirizzo (#griglia). Senza JavaScript le sezioni restano
   tutte visibili, una sotto l'altra, e i link sono ancore. */
(function () {
  'use strict';

  Array.prototype.forEach.call(document.querySelectorAll('[data-tabs]'), function (box) {
    var tabs = Array.prototype.slice.call(box.querySelectorAll('[data-tab]'));
    var panels = Array.prototype.slice.call(box.querySelectorAll('[data-tab-panel]'));
    if (tabs.length < 2) return;

    function show(name) {
      tabs.forEach(function (tab) {
        var active = tab.dataset.tab === name;
        tab.classList.toggle('championship-subtab-active', active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      panels.forEach(function (panel) {
        panel.hidden = panel.dataset.tabPanel !== name;
        /* Il margine serve solo quando le sezioni sono una sotto l'altra */
        panel.classList.remove('mt-6');
      });
    }

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function (event) {
        event.preventDefault();
        show(tab.dataset.tab);
        if (window.history && history.replaceState) history.replaceState(null, '', '#' + tab.dataset.tab);
      });
    });

    var fromHash = window.location.hash.slice(1);
    var known = tabs.some(function (tab) { return tab.dataset.tab === fromHash; });
    show(known ? fromHash : tabs[0].dataset.tab);
  });
})();
