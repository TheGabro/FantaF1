/* FantaF1 — conferma prima del submit.
   Ogni form con data-confirm-submit viene intercettato: si apre il <dialog>
   #confirm-dialog (vedi _confirm_dialog.html) e il form parte solo dopo
   conferma. Il testo arriva da data-confirm-text sul bottone che ha fatto
   partire il submit, altrimenti dal valore di data-confirm-submit del form.
   Senza JS (o senza <dialog>) i form salvano direttamente: nessuna regressione. */
(function () {
  'use strict';

  var forms = document.querySelectorAll('form[data-confirm-submit]');
  if (!forms.length) return;

  var dialog = document.getElementById('confirm-dialog');
  if (!dialog || typeof dialog.showModal !== 'function') return;

  var textEl = dialog.querySelector('[data-confirm-text]');
  var okButton = dialog.querySelector('[data-confirm-ok]');
  var cancelButton = dialog.querySelector('[data-confirm-cancel]');
  if (!textEl || !okButton) return;

  var pending = null;

  Array.prototype.forEach.call(forms, function (form) {
    form.addEventListener('submit', function (event) {
      /* Secondo giro, dopo la conferma: lasciamo passare il submit */
      if (form.dataset.confirmed === 'true') {
        form.dataset.confirmed = '';
        return;
      }
      event.preventDefault();

      var submitter = event.submitter || form.querySelector('[type="submit"]');
      pending = { form: form, submitter: submitter };

      textEl.textContent =
        (submitter && submitter.dataset.confirmText) ||
        form.dataset.confirmSubmit ||
        'Vuoi confermare?';
      okButton.textContent = (submitter && submitter.dataset.confirmOk) || 'Conferma';

      dialog.showModal();
    });
  });

  okButton.addEventListener('click', function () {
    if (!pending) return;
    /* Letto prima della close(), che azzera pending tramite l'handler 'close' */
    var form = pending.form;
    var submitter = pending.submitter;
    pending = null;
    dialog.close();

    form.dataset.confirmed = 'true';
    /* requestSubmit conserva name/value del bottone premuto (l'id del pilota) */
    if (typeof form.requestSubmit === 'function') {
      form.requestSubmit(submitter);
    } else {
      if (submitter && submitter.name) {
        var hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = submitter.name;
        hidden.value = submitter.value;
        form.appendChild(hidden);
      }
      form.submit();
    }
  });

  if (cancelButton) {
    cancelButton.addEventListener('click', function () {
      pending = null;
      dialog.close();
    });
  }

  dialog.addEventListener('close', function () { pending = null; });
})();
