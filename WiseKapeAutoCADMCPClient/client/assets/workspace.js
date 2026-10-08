(() => {
  const themeButton = document.querySelector('[data-theme-toggle]');
  function syncTheme() {
    const dark = document.documentElement.dataset.theme === 'dark';
    themeButton?.setAttribute('aria-label', dark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối');
    themeButton?.setAttribute('title', dark ? 'Giao diện sáng' : 'Giao diện tối');
    themeButton?.setAttribute('aria-pressed', String(dark));
  }
  themeButton?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('uc4n-theme', next); } catch {}
    syncTheme();
  });
  syncTheme();
  document.querySelectorAll('label:not([for])').forEach(label => {
    const next = label.nextElementSibling;
    if (next?.matches('input[id],textarea[id],select[id]')) label.htmlFor = next.id;
  });
  document.querySelectorAll('[data-suggestion]').forEach(button => button.addEventListener('click', () => {
    const input = document.getElementById('message');
    if (input && !input.disabled) { input.value = button.dataset.suggestion; input.focus(); }
  }));
  const settings = document.querySelector('[data-connection-settings]');
  if (settings && !document.getElementById('token')?.value) settings.open = true;
  const file = document.getElementById('file');
  const clearFile = document.getElementById('clearFile');
  const fileInfo = document.getElementById('fileInfo');
  if (document.querySelector('.composer') && file && clearFile && fileInfo) {
    const syncFile = () => { clearFile.hidden = !file.files.length; fileInfo.title = fileInfo.textContent; };
    file.addEventListener('change', syncFile);
    new MutationObserver(syncFile).observe(fileInfo, {childList:true,subtree:true,characterData:true});
    syncFile();
  }
  const state = document.getElementById('connection');
  if (state) {
    const update = () => state.dataset.state = /^(MCP đã kết nối|Đã kết nối lại)/.test(state.textContent.trim()) ? 'connected' : 'disconnected';
    new MutationObserver(update).observe(state, {childList:true,subtree:true,characterData:true});
    update();
  }
})();
