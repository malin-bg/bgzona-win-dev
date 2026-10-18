(() => {
  const box = document.querySelector('#media-lightbox');
  const image = document.querySelector('#lightbox-image');
  const previews = [...document.querySelectorAll('.full-preview')];
  const previous = document.querySelector('#lightbox-prev');
  const next = document.querySelector('#lightbox-next');
  let opener = null, current = 0;

  function render(index) {
    current = (index + previews.length) % previews.length;
    const item = previews[current];
    image.src = item.dataset.full;
    image.alt = item.dataset.label;
    document.querySelector('#lightbox-page').href = item.dataset.page;
    document.querySelector('#lightbox-counter').textContent = `${current + 1} / ${previews.length}`;
    previous.disabled = next.disabled = previews.length < 2;
  }
  previews.forEach((link, index) => link.addEventListener('click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || !box?.showModal) return;
    event.preventDefault();
    opener = link;
    render(index);
    box.showModal();
  }));
  const close = () => { if (box?.open) box.close(); };
  document.querySelector('#lightbox-close')?.addEventListener('click', close);
  previous?.addEventListener('click', () => render(current - 1));
  next?.addEventListener('click', () => render(current + 1));
  box?.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      render(current + (event.key === 'ArrowRight' ? 1 : -1));
    }
    // Native dialog handles Escape and focus containment.
  });
  box?.addEventListener('click', event => { if (event.target === box) close(); });
  box?.addEventListener('close', () => { image.removeAttribute('src'); opener?.focus(); });
  let touchStart = null;
  image?.addEventListener('pointerdown', event => {
    if (event.pointerType === 'touch') touchStart = { x: event.clientX, y: event.clientY };
  });
  image?.addEventListener('pointerup', event => {
    if (!touchStart || event.pointerType !== 'touch') return;
    const dx = event.clientX - touchStart.x, dy = event.clientY - touchStart.y;
    touchStart = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) render(current + (dx < 0 ? 1 : -1));
  });
  image?.addEventListener('pointercancel', () => { touchStart = null; });

  function fallbackCopy(url) {
    const field = document.createElement('textarea');
    field.value = url;
    field.readOnly = true;
    field.className = 'media-sr-only';
    document.body.append(field);
    field.select();
    try { return document.execCommand('copy'); }
    finally { field.remove(); }
  }
  document.querySelectorAll('[data-copy-url]').forEach(button => {
    let timer;
    button.addEventListener('click', async () => {
      const status = button.closest('.media-card-controls, .media-page-controls').querySelector('.media-copy-status');
      clearTimeout(timer);
      let copied = false;
      try { await navigator.clipboard.writeText(button.dataset.copyUrl); copied = true; }
      catch { try { copied = fallbackCopy(button.dataset.copyUrl); } catch { /* Show failure below. */ } }
      button.focus({ preventScroll: true });
      status.textContent = copied ? 'Копирано!' : 'Копирането не е достъпно в този браузър.';
      timer = setTimeout(() => { status.textContent = ''; }, 5000);
    });
  });

  // Copy and lightbox are independent of the optional collage slideshow fetch.
  const config = window.mediaConfig;
  if (!config || document.querySelector('[data-media-collection="poslaniya"]')) return;
  const mode = new URLSearchParams(location.search).get('slideshow');
  const src = mode === 'missing' ? '/media/missing.json' : mode === 'broken' ? '/media/broken.json' : config.slideshowURL;
  let slides = [], idleTimer = null, slideTimer = null, index = 0;
  const show = document.querySelector('#slideshow'), slide = document.querySelector('#slide-image');
  const shuffle = list => { for (let i = list.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [list[i], list[j]] = [list[j], list[i]]; } };
  function open() {
    if (!slides.length || show.open || box?.open) return;
    clearTimeout(idleTimer); clearInterval(slideTimer); shuffle(slides);
    index = Math.floor(Math.random() * slides.length);
    slide.src = slides[index]; show.showModal();
    slideTimer = setInterval(() => { index = (index + 1) % slides.length; slide.src = slides[index]; }, config.slideMs);
  }
  function reset() {
    clearTimeout(idleTimer); clearInterval(slideTimer);
    if (show.open) show.close();
    if (slides.length) idleTimer = setTimeout(open, config.idleMs);
  }
  ['pointermove', 'pointerdown', 'keydown', 'touchstart', 'wheel'].forEach(type => document.addEventListener(type, reset, { passive: true }));
  document.addEventListener('click', event => {
    const link = event.target.closest?.('a[href="#slideshow"]');
    if (!link) return;
    event.preventDefault(); open();
  });
  fetch(src).then(response => { if (!response.ok) throw Error('HTTP ' + response.status); return response.json(); })
    .then(data => {
      if (data.schema_version !== 1 || !Array.isArray(data.images) || data.images.some(url => typeof url !== 'string' || !url.includes('/kolaji/full/'))) throw Error('Invalid slideshow');
      slides = [...data.images]; document.documentElement.dataset.slideshow = 'ready'; reset();
    }).catch(() => { document.documentElement.dataset.slideshow = 'unavailable'; });
})();
