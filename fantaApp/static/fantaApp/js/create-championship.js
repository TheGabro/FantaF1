/* FantaF1 — form «Crea campionato» (#157, #67).
   Vale per la pagina create_championship e per il pop-up di I miei campionati:
   - righe lega aggiunte al formset Django;
   - tendina «La tua lega» popolata dai nomi digitati;
   - campi del giocatore visibili solo con «Partecipo anch'io»;
   - pop-up: i link [data-open-create-dialog] aprono #create-championship-dialog
     invece della pagina. Senza JavaScript restano link alla pagina, che funziona
     da sola; se il form del pop-up ha errori il server lo manda già aperto. */
(function () {
  'use strict';

  Array.prototype.forEach.call(
    document.querySelectorAll('form[data-create-championship-form]'),
    setupForm
  );
  setupDialog();

  function setupForm(form) {
    var addButton = form.querySelector('[data-add-league]');
    var container = form.querySelector('[data-league-forms]');
    var template = form.querySelector('[data-league-empty-form]');
    var totalForms = form.querySelector(
      'input[name="' + form.dataset.formsetPrefix + '-TOTAL_FORMS"]'
    );
    var leagueSelect = form.querySelector('select[name="player_league_index"]');
    var leagueField = form.querySelector('[data-player-league-field]');

    if (addButton && container && template && totalForms) {
      addButton.addEventListener('click', function () {
        var index = parseInt(totalForms.value, 10);
        var html = template.innerHTML.replaceAll('__prefix__', index);
        container.insertAdjacentHTML('beforeend', html);
        totalForms.value = index + 1;
        syncLeagueChoices();
      });
      container.addEventListener('input', syncLeagueChoices);
    }

    /* Le leghe non esistono ancora nel database: la tendina "La tua lega" si
       popola dai nomi digitati qui sopra e invia la posizione, non un id.
       L'ordine delle opzioni segue quello dei campi non vuoti, cioè lo stesso
       ordine in cui la view crea le leghe. */
    function syncLeagueChoices() {
      if (!container || !leagueSelect || !leagueField) return;
      var names = [];
      container.querySelectorAll('input[type="text"]').forEach(function (input) {
        var name = input.value.trim();
        if (name) names.push(name);
      });
      if (!names.length) names.push('Lega Unica');

      var previous = leagueSelect.value;
      leagueSelect.innerHTML = '';
      names.forEach(function (name, index) {
        var option = document.createElement('option');
        option.value = index;
        option.textContent = name;
        leagueSelect.appendChild(option);
      });
      if (parseInt(previous, 10) < names.length) leagueSelect.value = previous;
      // Con una lega sola non c'è niente da scegliere: si nasconde la riga.
      leagueField.classList.toggle('hidden', names.length < 2);
    }
    syncLeagueChoices();

    /* I campi del giocatore servono solo a chi partecipa davvero */
    var checkbox = form.querySelector('input[name="join_as_player"]');
    var fields = form.querySelector('[data-player-fields]');
    if (checkbox && fields) {
      var toggle = function () { fields.classList.toggle('hidden', !checkbox.checked); };
      checkbox.addEventListener('change', toggle);
      toggle();
    }
  }

  function setupDialog() {
    var dialog = document.getElementById('create-championship-dialog');
    if (!dialog || typeof dialog.showModal !== 'function') return;

    /* Il focus va sul nome del campionato, non sul pulsante di chiusura */
    function open() {
      dialog.showModal();
      var first = dialog.querySelector('input[name="name"]');
      if (first) first.focus();
    }

    /* Errori dal server: il dialog arriva già aperto (attributo open, non
       modale). Lo si riapre come modale, con lo sfondo scuro e Esc. */
    if (dialog.open) {
      dialog.close();
      open();
    }

    Array.prototype.forEach.call(
      document.querySelectorAll('[data-open-create-dialog]'),
      function (link) {
        link.addEventListener('click', function (event) {
          event.preventDefault();
          open();
        });
      }
    );

    Array.prototype.forEach.call(
      dialog.querySelectorAll('[data-close-dialog]'),
      function (button) {
        button.addEventListener('click', function () { dialog.close(); });
      }
    );
  }
})();
