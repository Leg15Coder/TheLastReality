document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('params-form');
  const status = document.getElementById('status');
  const runsContainer = document.getElementById('runs-container');
  const runBtn = document.getElementById('run-btn');
  const modal = document.getElementById('image-modal');
  const modalImg = document.getElementById('modal-img');
  const modalCaption = document.getElementById('modal-caption');
  const modalClose = document.getElementById('modal-close');
  const modalBackdrop = document.getElementById('modal-backdrop');

  function clearResults() {
    runsContainer.innerHTML = '';
  }

  function showStatus(msg, isError = false) {
    status.textContent = msg;
    status.className = isError ? 'status error' : 'status';
  }

  function openModal(src, caption) {
    modalImg.src = src;
    modalCaption.textContent = caption || '';
    modal.setAttribute('aria-hidden', 'false');
    modal.classList.add('open');
  }

  function closeModal() {
    modalImg.src = '';
    modalCaption.textContent = '';
    modal.setAttribute('aria-hidden', 'true');
    modal.classList.remove('open');
  }

  modalClose.addEventListener('click', closeModal);
  modalBackdrop.addEventListener('click', closeModal);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeModal();
  });

  async function runSimulation() {
    clearResults();
    showStatus('Running...');
    runBtn.disabled = true;

    const formData = new FormData(form);

    const binsInput = document.getElementById('bins');
    let bins = parseInt(binsInput.value || '20', 10);
    if (isNaN(bins) || bins < 1) bins = 20;
    formData.set('bins', String(bins));

    try {
      const res = await fetch('/api/stats/t6/run', {
        method: 'POST',
        body: formData,
        headers: {
          'x-requested-with': 'XMLHttpRequest'
        }
      });

      if (!res.ok) {
        const txt = await res.text();
        showStatus('Server error: ' + res.status + ' - ' + txt, true);
        return;
      }

      const data = await res.json();
      showStatus('Done');
      renderResults(data.results);
    } catch (err) {
      showStatus('Request failed: ' + (err.message || err), true);
    } finally {
      runBtn.disabled = false;
    }
  }

  runBtn.addEventListener('click', function (e) {
    e.preventDefault();
    runSimulation();
  });
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    runSimulation();
  });

  function createImageCard(imgSrc, label) {
    const col = document.createElement('div');
    col.className = 'img-col';

    const labelEl = document.createElement('div');
    labelEl.className = 'img-label';
    labelEl.textContent = label;

    const wrapper = document.createElement('div');
    wrapper.className = 'img-wrapper';

    const img = document.createElement('img');
    img.className = 'result-img';
    img.alt = label;
    img.src = imgSrc;

    img.addEventListener('click', function () {
      openModal(imgSrc, label);
    });

    const actions = document.createElement('div');
    actions.className = 'img-actions';

    const openBtn = document.createElement('button');
    openBtn.type = 'button';
    openBtn.className = 'open-full-btn';
    openBtn.textContent = 'Open full size';
    openBtn.addEventListener('click', function () {
      openModal(imgSrc, label);
    });

    const download = document.createElement('a');
    download.href = imgSrc;
    download.download = `${label.replace(/\s+/g, '_')}.png`;
    download.className = 'download-btn';
    download.textContent = 'Download';

    actions.appendChild(openBtn);
    actions.appendChild(download);

    wrapper.appendChild(img);
    wrapper.appendChild(actions);

    col.appendChild(labelEl);
    col.appendChild(wrapper);

    return col;
  }

  function renderResults(results) {
    if (!Array.isArray(results) || results.length === 0) {
      showStatus('No results returned', true);
      return;
    }

    results.forEach((r, idx) => {
      const card = document.createElement('div');
      card.className = 'result-card';
      const title = document.createElement('h3');
      title.textContent = `Run ${idx + 1} — theta = ${Number(r.theta).toFixed(3)}`;
      card.appendChild(title);

      const images = r.images || {};
      const grid = document.createElement('div');
      grid.className = 'images-grid';

      const order = ['medians', 'means', 'median_norm', 'mean_norm'];
      order.forEach((key) => {
        if (!images[key]) return;
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        const col = createImageCard(images[key], label);
        grid.appendChild(col);
      });

      card.appendChild(grid);
      runsContainer.appendChild(card);
    });

    runsContainer.scrollIntoView({behavior: 'smooth'});
  }
});
