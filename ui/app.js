const $ = (id) => document.getElementById(id);
const SAMPLE = '3 + 5 * 2\n-----\n(8 / 4) + 7 * 2\n-----\n10 - (2 + 3) * 4\n';
const state = { ready: false, steps: [], tokens: [], index: 0, timer: null, section: 'stack', source: '', batch: null, fileText: null, request: 0, worker: null, pending: new Map(), evaluation: 0, evaluating: false };
const sections = {
  stack: { title: 'Stack class', start: 'class Stack', end: 'class ExpressionError', note: 'A stack follows last in, first out (LIFO). The most recently added item is the first one removed.', bullets: ['push() adds an item to the top.', 'pop() removes and returns the top item.', 'peek() reads the top without removing it.', 'snapshot() copies the stack for the visual demo.'] },
  tokens: { title: 'Tokenize the expression', start: 'def tokenize', end: 'def apply_operator', note: 'Read the expression from left to right and separate it into numbers, operators, and parentheses.', bullets: ['Whitespace is ignored.', 'Decimals are recognized as one number.', 'Each token keeps its original column.', 'Unexpected characters produce a clear error.'] },
  apply: { title: 'Apply an operator', start: 'def apply_operator', end: 'def evaluate_expression', note: 'Take values from the stack, calculate, and push the answer back. Operand order matters for subtraction and division.', bullets: ['Pop the right operand first, then the left.', 'Unary signs need only one value.', 'Compute left operator right.', 'Division by zero is reported as an error.'] },
  evaluate: { title: 'Evaluate with two stacks', start: 'def evaluate_expression', end: 'def format_result', note: 'One stack stores numbers; the other stores pending operators. Precedence decides when an operator can be applied.', bullets: ['Numbers are pushed onto the value stack.', 'Higher or equal priority operators are applied first.', 'Parentheses protect a group until it closes.', 'The optional trace records each actual engine operation.'] },
  files: { title: 'Read and write files', start: 'def format_result', end: 'def main(', note: 'Read each expression from input.txt, evaluate it, and replace it with its result in output.txt.', bullets: ['Separator and blank lines are copied unchanged.', 'Line endings and outer spacing are preserved.', 'A bad expression gets an error line; later expressions still run.', 'Input and output cannot be the same file.'] },
  run: { title: 'Run the program', start: 'def main(', end: null, note: 'The command-line entry point selects the input and output paths and runs the file processor.', bullets: ['Run python3 main.py for the sample files.', 'Optional arguments choose other input and output paths.', 'A summary is printed after processing.', 'The exit code is 1 if an error occurred, otherwise 0.'] },
};
function element(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function stopPlayback() { clearTimeout(state.timer); state.timer = null; $('play').replaceChildren(element('span', '▶'), document.createTextNode(' Play')); }
function showView(view) { stopPlayback(); document.querySelectorAll('.view').forEach(node => node.classList.toggle('active', node.id === `view-${view}`)); document.querySelectorAll('[data-view]').forEach(button => { const active = button.dataset.view === view; button.classList.toggle('selected', active); if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current'); }); history.replaceState(null, '', `#${view}`); }
function setSection(section) {
  state.section = sections[section] ? section : 'stack'; const info = sections[state.section];
  $('code-title').textContent = info.title;
  $('code-note').replaceChildren(element('h3', 'How it works'), element('p', info.note));
  const list = element('ul'); info.bullets.forEach(text => list.append(element('li', text))); $('code-note').append(list);
  document.querySelectorAll('[data-section]').forEach(button => button.classList.toggle('selected', button.dataset.section === state.section));
  if (!state.source) return;
  const start = state.source.indexOf(info.start); const end = info.end ? state.source.indexOf(info.end, start + 1) : state.source.length;
  const firstLine = state.source.slice(0, start).split('\n').length;
  $('source-code').replaceChildren();
  state.source.slice(start, end).trimEnd().split('\n').forEach((text, index) => { const row = element('span', undefined, 'source-line'); if (/^\s*(class |def )/.test(text)) row.classList.add('definition'); if (/^\s*#/.test(text)) row.classList.add('comment'); row.append(element('span', firstLine + index, 'line-number'), document.createTextNode(text || ' ')); $('source-code').append(row); });
}
function renderStack(id, entries) { const container = $(id); container.replaceChildren(); if (!entries.length) { container.append(element('p', 'Stack is empty', 'empty-stack')); return; } [...entries].reverse().forEach((text, index) => { const display = text === 'u-' ? '− (unary)' : text === 'u+' ? '+ (unary)' : text; const item = element('div', display, 'stack-item'); if (String(text).length > 10) item.classList.add('with-long-value'); if (index === 0) item.prepend(element('span', 'TOP', 'top-marker')); container.append(item); }); }
function renderStep() {
  const step = state.steps[state.index]; if (!step) return;
  $('step-count').textContent = `Step ${state.index + 1} / ${state.steps.length}`;
  $('step-action').textContent = step.action; $('step-message').textContent = step.message;
  $('action-icon').textContent = String(state.index + 1).padStart(2, '0');
  renderStack('value-stack', step.values); renderStack('operator-stack', step.operators);
  $('tokens').replaceChildren(); state.tokens.forEach(token => { const node = element('span', token.text, 'token'); node.classList.toggle('active', token.column === step.column); node.classList.toggle('past', token.column < step.column); $('tokens').append(node); });
  $('timeline').value = state.index;
  $('previous').disabled = state.index === 0; $('next').disabled = state.index === state.steps.length - 1; $('restart').disabled = false; $('play').disabled = state.steps.length < 2;
  document.querySelectorAll('.trace-row').forEach((row, index) => { row.classList.toggle('active', index === state.index); row.setAttribute('aria-current', index === state.index ? 'step' : 'false'); });
  const row = $('trace-list').children[state.index]; if (row) { const top = row.offsetTop - $('trace-list').offsetTop; if (top < $('trace-list').scrollTop || top + row.offsetHeight > $('trace-list').scrollTop + $('trace-list').clientHeight) $('trace-list').scrollTop = Math.max(0, top - 40); }
}
function renderTrace() { $('trace-list').replaceChildren(); state.steps.forEach((step, index) => { const row = element('button', undefined, 'trace-row'); row.append(element('span', String(index + 1).padStart(2, '0'), 'trace-index'), element('span', step.action), element('span', `[${step.values.join(', ')}]`, 'trace-state')); row.addEventListener('click', () => { stopPlayback(); state.index = index; renderStep(); }); $('trace-list').append(row); }); $('timeline').max = Math.max(0, state.steps.length - 1); $('timeline').disabled = !state.steps.length; }
function request(type, input) { return new Promise((resolve, reject) => { const id = ++state.request; state.pending.set(id, { resolve, reject }); state.worker.postMessage({ type, input, id }); }); }
function setBusy(busy) { state.evaluating = busy; $('evaluate-button').disabled = busy || !state.ready; $('evaluate-button').textContent = busy ? 'Evaluating…' : 'Evaluate expression'; }
async function evaluate() {
  if (!state.ready || state.evaluating) return;
  const expression = $('expression').value; const version = ++state.evaluation; stopPlayback(); setBusy(true);
  try {
    const data = await request('evaluate', expression); if (version !== state.evaluation || $('expression').value !== expression) return;
    state.steps = data.steps; state.tokens = data.tokens; state.index = 0;
    $('result-panel').classList.toggle('error', !data.ok); $('result').textContent = data.ok ? data.result : 'Invalid expression';
    $('result-caption').textContent = data.ok ? 'Calculated by the Python stack engine.' : data.error;
    renderTrace(); if (state.steps.length) renderStep(); else { renderStack('value-stack', []); renderStack('operator-stack', []); $('tokens').replaceChildren(); $('step-action').textContent = 'Check the expression'; $('step-message').textContent = data.error; $('step-count').textContent = 'No trace available'; ['previous', 'next', 'play', 'restart'].forEach(id => $(id).disabled = true); }
    if (!data.ok && state.steps.length) { $('result-caption').textContent = `${data.error} The trace shows operations before the error.`; }
  } catch (error) { $('result-panel').classList.add('error'); $('result').textContent = 'Could not calculate'; $('result-caption').textContent = error.message; }
  finally { setBusy(false); }
}
function playback() {
  if (state.timer) { stopPlayback(); return; }
  if (state.index >= state.steps.length - 1) state.index = 0;
  $('play').replaceChildren(element('span', 'Ⅱ'), document.createTextNode(' Pause')); renderStep();
  function tick() { if (state.index < state.steps.length - 1) { state.index++; renderStep(); if (state.index < state.steps.length - 1) state.timer = setTimeout(tick, Number($('speed').value)); else stopPlayback(); } else stopPlayback(); }
  state.timer = setTimeout(tick, Number($('speed').value));
}
function download(filename, text) { const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' })); const link = element('a'); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
async function runFile() {
  if (!state.ready) return;
  $('run-file').disabled = true; $('run-file').textContent = 'Running…'; $('file-feedback').textContent = ''; $('download-output').disabled = true;
  try {
    state.batch = await request('batch', state.fileText ?? $('file-input').value); const data = state.batch;
    $('file-output').textContent = data.output || '(Empty output file)'; $('file-output').classList.remove('output-placeholder');
    $('file-count').textContent = `${data.count} EXPRESSION${data.count === 1 ? '' : 'S'}`;
    $('file-feedback').textContent = data.errors.length ? `${data.count} expression(s) processed. ${data.errors.length} error(s); other expressions were still evaluated.` : `${data.count} expression(s) processed. Separators and line endings preserved.`;
    $('file-feedback').classList.toggle('error', !!data.errors.length); $('download-output').disabled = false; $('file-results').replaceChildren();
    data.rows.forEach(row => { const node = element('div', undefined, `file-result-row${row.ok ? '' : ' error'}`); const inspect = element('button', 'Inspect', 'secondary'); inspect.addEventListener('click', async () => { $('expression').value = row.expression; showView('demo'); await evaluate(); }); node.append(element('span', `Line ${row.line}`), element('code', row.expression), element('strong', row.result), inspect); $('file-results').append(node); }); return data;
  } catch (error) { $('file-feedback').textContent = error.message; $('file-feedback').classList.add('error'); throw error; }
  finally { $('run-file').disabled = !state.ready; $('run-file').textContent = 'Run file'; }
}
function resetFileOutput() { state.batch = null; $('download-output').disabled = true; $('file-output').textContent = 'Run the input file to see the results.'; $('file-output').classList.add('output-placeholder'); $('file-count').textContent = 'OUTPUT'; $('file-results').replaceChildren(); $('file-feedback').textContent = ''; }
function initEngine() {
  if (state.worker) state.worker.terminate(); state.ready = false; $('retry').classList.add('hidden');
  $('engine-status').className = 'engine-status'; $('engine-status').replaceChildren(element('span', undefined, 'spinner'), document.createTextNode('Loading Python engine…'));
  state.worker = new Worker('engine.js');
  const fail = () => { state.ready = false; $('engine-status').className = 'engine-status failed'; $('engine-status').textContent = 'Engine unavailable'; $('result').textContent = 'Server unavailable'; $('result-caption').textContent = 'Start demo.py on your laptop, keep its window open, and retry.'; $('retry').classList.remove('hidden'); state.pending.forEach(item => item.reject(new Error('Python engine is unavailable.'))); state.pending.clear(); setBusy(false); $('run-file').disabled = true; };
  state.worker.onerror = fail;
  state.worker.onmessage = ({ data }) => { if (data.type === 'ready') { state.ready = true; $('engine-status').className = 'engine-status ready'; $('engine-status').textContent = 'Python engine ready'; setBusy(false); $('run-file').disabled = false; evaluate(); return; } if (data.type === 'load-error') { fail(); return; } const item = state.pending.get(data.id); if (item) { state.pending.delete(data.id); if (data.error) item.reject(new Error(data.error)); else item.resolve(data.result); } };
}
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => showView(button.dataset.view)));
document.querySelectorAll('[data-section]').forEach(button => button.addEventListener('click', () => setSection(button.dataset.section)));
document.querySelectorAll('[data-expression]').forEach(button => button.addEventListener('click', () => { $('expression').value = button.dataset.expression; evaluate(); }));
$('expression-form').addEventListener('submit', event => { event.preventDefault(); evaluate(); });
$('expression').addEventListener('keydown', event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); evaluate(); } });
$('expression').addEventListener('input', () => { stopPlayback(); $('result-caption').textContent = 'Expression changed. Evaluate to update the result and trace.'; });
$('retry').addEventListener('click', initEngine);
$('restart').addEventListener('click', () => { stopPlayback(); state.index = 0; renderStep(); });
$('previous').addEventListener('click', () => { stopPlayback(); state.index = Math.max(0, state.index - 1); renderStep(); });
$('next').addEventListener('click', () => { stopPlayback(); state.index = Math.min(state.steps.length - 1, state.index + 1); renderStep(); });
$('play').addEventListener('click', playback);
$('timeline').addEventListener('input', () => { stopPlayback(); state.index = Number($('timeline').value); renderStep(); });
$('step-code').addEventListener('click', () => { setSection(state.steps[state.index]?.section || 'evaluate'); showView('code'); });
$('run-file').addEventListener('click', () => { runFile().catch(() => {}); });
$('sample-file').addEventListener('click', () => { $('file-input').value = SAMPLE; state.fileText = null; resetFileOutput(); });
$('file-input').addEventListener('input', () => { state.fileText = null; resetFileOutput(); });
$('file-upload').addEventListener('change', async event => { const file = event.target.files[0]; if (!file) return; if (file.size > 1000000) { $('file-feedback').textContent = 'Choose a text file smaller than 1 MB.'; return; } try { const content = await file.text(); $('file-input').value = content; state.fileText = content; resetFileOutput(); $('file-feedback').textContent = `Loaded ${file.name}. Select Run file to evaluate it.`; } catch { $('file-feedback').textContent = 'Could not read this file. Try loading it again.'; } event.target.value = ''; });
$('download-output').addEventListener('click', () => { if (state.batch) download('output.txt', state.batch.output); });
$('download-input').addEventListener('click', () => download('input.txt', state.fileText ?? $('file-input').value));
fetch('main.py').then(response => { if (!response.ok) throw new Error(); return response.text(); }).then(source => { state.source = source; setSection(state.section); }).catch(() => { $('source-code').textContent = 'Could not load the source. Please reload the page.'; });
setSection('stack'); if (['demo', 'files', 'code'].includes(location.hash.slice(1))) showView(location.hash.slice(1)); initEngine();

if (document.modelContext?.registerTool) {
  const lifecycle = new AbortController();
  const tool = { name: 'evaluate_stack_expression', title: 'Evaluate a stack expression', description: 'Evaluate an arithmetic expression and update the visible calculator result and stack trace.', inputSchema: { type: 'object', properties: { expression: { type: 'string', minLength: 1, maxLength: 10000 } }, required: ['expression'], additionalProperties: false }, annotations: { readOnlyHint: false, untrustedContentHint: true }, async execute(input) { if (!input || typeof input.expression !== 'string' || !input.expression.trim() || input.expression.length > 10000 || Object.keys(input).some(key => key !== 'expression')) throw new Error('Provide one nonempty expression, up to 10,000 characters.'); if (!state.ready || state.evaluating) throw new Error('Wait until the Python engine is ready and idle.'); $('expression').value = input.expression; showView('demo'); await evaluate(); return { result: $('result').textContent, detail: $('result-caption').textContent, steps: state.steps.length }; } };
  try { Promise.resolve(document.modelContext.registerTool(tool, { signal: lifecycle.signal })).catch(() => {}); } catch {}
  window.addEventListener('pagehide', () => lifecycle.abort(), { once: true });
}
