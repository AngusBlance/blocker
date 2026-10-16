// The page a tab lands on when focus mode blocks it.
const params = new URLSearchParams(location.search);
const until = Number(params.get('until'));
const allow = (params.get('allow') || '').split(',').filter(Boolean);

function render() {
  const status = document.getElementById('status');
  const left = until - Date.now();
  if (!until || left <= 0) {
    status.textContent = 'Focus has ended. You can go back now.';
    return;
  }
  const clock = new Date(until).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const minutes = Math.ceil(left / 60000);
  status.textContent = `Focus is on until ${clock} (${minutes} min left).`;
}

if (allow.length) {
  document.getElementById('allowed').textContent = `Only ${allow.join(', ')} can be open.`;
}
render();
setInterval(render, 15000);
