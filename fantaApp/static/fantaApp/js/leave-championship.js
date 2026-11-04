/* FantaF1 — disiscrizione dal campionato in due passaggi (#160).
   «Procedi alla disiscrizione» apre #leave-confirm-dialog («Sei sicuro?»);
   «Continua» apre #leave-name-dialog, dove viene spostato il form: il
   pulsante finale si attiva solo quando il nome scritto è quello del
   campionato. Il controllo vero lo rifà la view.
   Senza JS (o senza <dialog>) il form resta nella card: nessuna regressione. */
(function () {
  'use strict';

  var start = document.querySelector('[data-leave-start]');
  var form = document.querySelector('[data-leave-form]');
  var confirmDialog = document.getElementById('leave-confirm-dialog');
  var nameDialog = document.getElementById('leave-name-dialog');
  if (!start || !form || !confirmDialog || !nameDialog) return;
  if (typeof confirmDialog.showModal !== 'function') return;

  var input = form.querySelector('[data-leave-name]');
  var submit = form.querySelector('[data-leave-submit]');
  var slot = nameDialog.querySelector('[data-leave-dialog-slot]');
  if (!input || !submit || !slot) return;

  var expected = (input.dataset.expected || '').trim();

  function sync() {
    submit.disabled = input.value.trim() !== expected;
  }

  /* Il form passa nel secondo dialog; nella card resta solo il pulsante */
  slot.appendChild(form);
  form.querySelectorAll('[data-leave-cancel]').forEach(function (button) {
    button.hidden = false;
  });
  start.hidden = false;
  sync();

  input.addEventListener('input', sync);

  start.addEventListener('click', function () {
    confirmDialog.showModal();
  });

  confirmDialog.querySelector('[data-leave-continue]').addEventListener('click', function () {
    confirmDialog.close();
    input.value = '';
    sync();
    nameDialog.showModal();
    input.focus();
  });

  [confirmDialog, nameDialog].forEach(function (dialog) {
    dialog.querySelectorAll('[data-leave-cancel]').forEach(function (button) {
      button.addEventListener('click', function () {
        dialog.close();
      });
    });
  });
})();
