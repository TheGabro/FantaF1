/* FantaF1 — impedisce di scegliere lo stesso pilota in più select.
   Si applica a tutte le <select data-dedupe> della pagina. */
(function () {
  'use strict';

  var selects = Array.prototype.slice.call(document.querySelectorAll('select[data-dedupe]'));
  if (!selects.length) return;

  function refresh() {
    var chosen = {};
    selects.forEach(function (select) {
      if (select.value) chosen[select.value] = true;
    });

    selects.forEach(function (select) {
      Array.prototype.forEach.call(select.options, function (option) {
        if (!option.value) {
          option.hidden = false;
          option.disabled = false;
          return;
        }
        var takenElsewhere = chosen[option.value] && select.value !== option.value;
        option.hidden = takenElsewhere;
        option.disabled = takenElsewhere;
      });
    });
  }

  selects.forEach(function (select) {
    select.addEventListener('change', refresh);
  });
  refresh();
})();
