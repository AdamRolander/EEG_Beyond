// Block likert + per-trial flagging modal.
// Resolves with { likert, flagsBest, flagsBad } when submitted.

let pendingResolve = null;

export function showLikert(blockIdx, blockTrials) {
  return new Promise((resolve) => {
    pendingResolve = resolve;
    const modal = document.getElementById('likert-modal');
    document.getElementById('likert-block-label').textContent = `Block ${blockIdx + 1}`;

    // Reset radio buttons
    document.querySelectorAll('input[name="likert"]').forEach(i => i.checked = false);

    // Build per-trial flag rows
    const tbody = document.getElementById('flag-table-body');
    tbody.innerHTML = '';
    for (let i = 0; i < blockTrials.length; i++) {
      const t = blockTrials[i];
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td>${t.cls}</td>
        <td><input type="checkbox" class="flag-best" data-pos="${i}"></td>
        <td><input type="checkbox" class="flag-bad" data-pos="${i}"></td>
      `;
      tbody.appendChild(tr);
    }

    // Enforce mutual exclusion (a trial can't be both best AND bad)
    tbody.addEventListener('change', enforceFlagExclusion);

    document.getElementById('btn-submit-likert').onclick = handleSubmit;
    modal.hidden = false;
  });
}

function enforceFlagExclusion(e) {
  const cb = e.target;
  if (!cb.matches('.flag-best, .flag-bad')) return;
  if (!cb.checked) return;
  const pos = cb.dataset.pos;
  const sibling = cb.classList.contains('flag-best')
    ? document.querySelector(`.flag-bad[data-pos="${pos}"]`)
    : document.querySelector(`.flag-best[data-pos="${pos}"]`);
  if (sibling) sibling.checked = false;
}

function handleSubmit() {
  const likertInput = document.querySelector('input[name="likert"]:checked');
  if (!likertInput) {
    alert('Please select a likert rating (1-5).');
    return;
  }
  const likert = parseInt(likertInput.value);

  const flagsBest = [...document.querySelectorAll('.flag-best:checked')]
    .map(c => parseInt(c.dataset.pos));
  const flagsBad = [...document.querySelectorAll('.flag-bad:checked')]
    .map(c => parseInt(c.dataset.pos));

  // Spec V1: ≤ 2 best, ≤ 2 bad
  if (flagsBest.length > 2) {
    alert('Maximum 2 "best" flags per block.');
    return;
  }
  if (flagsBad.length > 2) {
    alert('Maximum 2 "bad" flags per block.');
    return;
  }

  document.getElementById('likert-modal').hidden = true;
  if (pendingResolve) {
    const r = pendingResolve;
    pendingResolve = null;
    r({ likert, flagsBest, flagsBad });
  }
}