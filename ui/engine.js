const ready = fetch('/api/health').then(async response => {
  if (!response.ok || !(await response.json()).ready) throw new Error('Server unavailable.');
  postMessage({ type: 'ready' });
});
ready.catch(() => postMessage({ type: 'load-error' }));
self.onmessage = async ({ data }) => {
  try {
    await ready;
    const response = await fetch(data.type === 'batch' ? '/api/batch' : '/api/evaluate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ input: data.input }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not calculate.');
    postMessage({ id: data.id, result });
  } catch (error) {
    postMessage({ id: data.id, error: error.message || 'The local server is unavailable. Start demo.py and try again.' });
  }
};
