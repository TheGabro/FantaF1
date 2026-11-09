/* FantaF1 — selezione piloti per Sprint Race e Grand Prix.
   Config via data-attribute su #race-choice-layout:
   - data-max-drivers: numero esatto di piloti da selezionare (1 sprint, 2 GP)
   - data-has-pupillo: "true" se la gara prevede il pupillo (solo GP)
   - data-event-started: "true" per modalità sola lettura
   - data-qualifying-bonus-credit-discount: sconto crediti da pronostico qualifica
   - data-spendable-credit: crediti spendibili (per evidenziare lo sforamento)
   Le righe piloti espongono i dati in data-driver-* (vedi template). */
(function () {
  'use strict';

  var layout = document.getElementById('race-choice-layout');
  if (!layout) return;

  var maxDrivers = Number(layout.dataset.maxDrivers || 1);
  var hasPupillo = layout.dataset.hasPupillo === 'true';
  var eventStarted = layout.dataset.eventStarted === 'true';
  var bonusDiscount = Number(layout.dataset.qualifyingBonusCreditDiscount || 0);
  var spendableCredit = Number(layout.dataset.spendableCredit || 0);

  var rows = Array.prototype.slice.call(document.querySelectorAll('[data-driver-row]'));
  var inputsBox = document.getElementById('selected-drivers-inputs');
  var listBox = document.getElementById('selected-drivers-list');
  var totalEl = document.getElementById('selected-total-cost');
  var driversCostEl = document.getElementById('selected-drivers-cost');
  var pupilloDiscountEl = document.getElementById('selected-pupillo-discount');
  var pupilloInput = document.getElementById('pupillo-driver-input');
  var saveButton = document.getElementById('save-selection-button');

  if (!rows.length || !inputsBox || !listBox || !totalEl) return;

  var selectedIds = Array.prototype.slice
    .call(inputsBox.querySelectorAll('input[name="drivers"]'))
    .map(function (input) { return String(input.value); });

  function isSelected(id) { return selectedIds.indexOf(String(id)) !== -1; }
  function pupilloId() { return pupilloInput && pupilloInput.value ? String(pupilloInput.value) : ''; }
  function rowById(id) {
    return rows.filter(function (r) { return r.dataset.driverId === String(id); })[0] || null;
  }

  function renderHiddenInputs() {
    inputsBox.innerHTML = selectedIds
      .map(function (id) { return '<input type="hidden" name="drivers" value="' + id + '">'; })
      .join('');
  }

  function selectedCardHtml(row, index) {
    var d = row.dataset;
    var isPup = hasPupillo && pupilloId() === String(d.driverId);
    /* Prezzo pieno: lo sconto pupillo è mostrato nel riepilogo */
    var cost = Number(d.driverCost || 0);

    var action = '';
    if (!eventStarted && hasPupillo) {
      action = isPup
        ? '<p class="mt-2 text-sm font-bold text-accent">★ Pupillo ×' + (Number(d.driverPreviousPupilloStreak || 0) + 1) + '</p>'
        : '<button type="button" data-set-pupillo="' + d.driverId + '" class="btn-secondary mt-2 !px-3 !py-1 text-sm">Imposta come pupillo</button>';
    }

    return (
      '<div class="team-' + (d.driverTeamSlug || '') + ' rounded-lg border p-3 ' +
        (isPup ? 'border-accent/60 bg-accent-soft/40' : 'border-line bg-surface') + '">' +
        '<div class="flex items-start justify-between gap-3">' +
          '<div class="min-w-0">' +
            '<p class="text-[11px] uppercase tracking-wide text-muted">Pilota ' + (index + 1) + '</p>' +
            '<p class="team-chip truncate">' + d.driverName + '</p>' +
            '<p class="note mt-0.5">' + d.driverTeam + ' · P' + d.driverGrid + '</p>' +
          '</div>' +
          '<p class="shrink-0 font-black">' + cost + '<span class="note ml-1 font-semibold">cr</span></p>' +
        '</div>' +
        action +
      '</div>'
    );
  }

  function renderPanel() {
    if (!selectedIds.length) {
      listBox.innerHTML = '<div class="rounded-lg border border-dashed border-line p-3 text-muted">Nessun pilota selezionato.</div>';
    } else {
      listBox.innerHTML = selectedIds.map(function (id, i) {
        var row = rowById(id);
        return row ? selectedCardHtml(row, i) : '';
      }).join('');
    }

    var total = selectedIds.reduce(function (sum, id) {
      var row = rowById(id);
      if (!row) return sum;
      var isPup = hasPupillo && pupilloId() === String(id);
      return sum + (isPup
        ? Number(row.dataset.driverPupilloCost || row.dataset.driverCost)
        : Number(row.dataset.driverCost || 0));
    }, 0);

    if (driversCostEl) {
      driversCostEl.textContent = String(selectedIds.reduce(function (sum, id) {
        var row = rowById(id);
        return row ? sum + Number(row.dataset.driverCost || 0) : sum;
      }, 0));
    }

    /* Lo sconto qualifica si applica solo a selezione completa (come nel backend) */
    if (selectedIds.length === maxDrivers && bonusDiscount) {
      total = Math.max(total - bonusDiscount, 0);
    }

    totalEl.textContent = String(total);
    totalEl.classList.toggle('text-accent', spendableCredit > 0 && total > spendableCredit);

    if (pupilloDiscountEl) {
      var pupRow = isSelected(pupilloId()) ? rowById(pupilloId()) : null;
      var pupDiscount = pupRow ? Number(pupRow.dataset.driverPupilloDiscount || 0) : 0;
      pupilloDiscountEl.textContent = pupDiscount ? '−' + pupDiscount + ' cr' : '—';
      pupilloDiscountEl.classList.toggle('text-ok', pupDiscount > 0);
    }

    if (saveButton) {
      var canSave = selectedIds.length === maxDrivers &&
        (!hasPupillo || (!!pupilloId() && isSelected(pupilloId())));
      saveButton.disabled = !canSave;
    }
  }

  function refreshRows() {
    rows.forEach(function (row) {
      var selected = isSelected(row.dataset.driverId);
      var isPup = hasPupillo && pupilloId() === String(row.dataset.driverId);
      var button = row.querySelector('[data-select-driver]');
      var label = row.querySelector('[data-selected-label]');

      row.classList.toggle('row-selected', selected);
      if (button) button.textContent = selected ? 'Rimuovi' : 'Seleziona';
      if (label) {
        label.textContent = isPup ? '★ Pupillo' : (selected ? 'Scelto' : '—');
        label.className = isPup || selected ? 'badge-accent' : 'badge-muted';
      }
    });
  }

  function refresh() {
    renderHiddenInputs();
    renderPanel();
    refreshRows();
  }

  if (!eventStarted) {
    rows.forEach(function (row) {
      var button = row.querySelector('[data-select-driver]');
      if (!button) return;
      button.addEventListener('click', function () {
        var id = String(row.dataset.driverId);
        if (isSelected(id)) {
          selectedIds.splice(selectedIds.indexOf(id), 1);
          if (pupilloInput && pupilloId() === id) pupilloInput.value = '';
        } else {
          if (selectedIds.length >= maxDrivers) {
            window.alert('Puoi selezionare massimo ' + maxDrivers + ' pilot' + (maxDrivers === 1 ? 'a' : 'i') + '. Rimuovine uno prima di aggiungerne un altro.');
            return;
          }
          selectedIds.push(id);
        }
        refresh();
      });
    });

    if (hasPupillo && pupilloInput) {
      listBox.addEventListener('click', function (event) {
        var target = event.target.closest('[data-set-pupillo]');
        if (!target) return;
        var id = String(target.getAttribute('data-set-pupillo'));
        if (!isSelected(id)) return;
        pupilloInput.value = id;
        refresh();
      });
    }
  }

  refresh();
})();
