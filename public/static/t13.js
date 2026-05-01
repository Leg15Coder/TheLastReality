document.addEventListener('DOMContentLoaded', function(){
    const form = document.getElementById('t13-form');
    const status = document.getElementById('status');
    const results = document.getElementById('results');
    const modal = document.getElementById('img-modal');
    const modalImg = document.getElementById('modal-img');
    const modalCaption = document.getElementById('modal-caption');
    const modalClose = document.getElementById('modal-close');

    function setStatus(msg){ status.textContent = msg; }

    form.addEventListener('submit', async function(e){
        e.preventDefault();
        setStatus('Выполняется...');
        results.innerHTML = '';
        const data = new FormData(form);
        try{
            const resp = await fetch('/api/stats/t13/run', { method: 'POST', body: data });
            if(!resp.ok){
                const txt = await resp.text();
                setStatus('Ошибка сервера: '+resp.status);
                console.error(txt);
                return;
            }
            const json = await resp.json();
            setStatus('Готово');
            renderResults(json);
        }catch(err){
            console.error(err);
            setStatus('Ошибка запроса');
        }
    });

    document.getElementById('reset-btn').addEventListener('click', function(){
        form.reset();
        setStatus('');
        results.innerHTML = '';
    });

    function renderResults(data){
        const { results: arr } = data;
        arr.forEach(r => {
            const card = document.createElement('div');
            card.className = 'result-card card';
            const title = document.createElement('h3');
            title.textContent = `p = ${r.p}`;
            card.appendChild(title);

            const row = document.createElement('div');
            row.className = 'result-row';

            const imgWrap = document.createElement('div');
            imgWrap.className = 'result-img';
            const img = document.createElement('img');
            img.src = r.images.hist;
            img.alt = `hist p=${r.p}`;
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'contain';
            img.addEventListener('click', ()=> openModal(r.images.hist, `Bootstrap hist (p=${r.p})`));
            imgWrap.appendChild(img);

            const meta = document.createElement('div');
            meta.className = 'result-meta';
            const pre = document.createElement('pre');
            pre.textContent = `theoretical: ${r.theoretical}\nsample_quantile: ${r.sample_quantile}\nbootstrap_std: ${r.bootstrap_std}\nci_95: ${r.ci_95.join(' , ')}`;
            meta.appendChild(pre);

            row.appendChild(imgWrap);
            row.appendChild(meta);
            card.appendChild(row);
            results.appendChild(card);
        });
    }

    function openModal(src, caption){
        modalImg.src = src;
        modalCaption.textContent = caption || '';
        modal.setAttribute('aria-hidden', 'false');
    }
    modalClose.addEventListener('click', ()=> modal.setAttribute('aria-hidden','true'));
    modal.addEventListener('click', (e)=>{ if(e.target === modal) modal.setAttribute('aria-hidden','true'); });
});
