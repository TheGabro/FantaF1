/* FantaF1 — righe di tabella con dettaglio espandibile (#208).
   Ogni pulsante [data-expand] apre e chiude la riga indicata da aria-controls.
   Senza JavaScript i pulsanti restano nascosti e i dettagli tutti visibili;
   con JavaScript i dettagli partono chiusi. */
(function () {
  'use strict';

  Array.prototype.forEach.call(document.querySelectorAll('[data-expand]'), function (button) {
    var detail = document.getElementById(button.getAttribute('aria-controls'));
    if (!detail) return;

    function set(open) {
      detail.hidden = !open;
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    button.hidden = false;
    set(false);
    button.addEventListener('click', function () {
      set(detail.hidden);
    });
  });
})();
