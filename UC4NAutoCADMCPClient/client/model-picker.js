let modelCatalog = [];
let modelLoadVersion = 0;

function selectedModel() {
  return $('model').value === 'default'
    ? modelCatalog.find(model => model.isDefault) || modelCatalog[0]
    : modelCatalog.find(model => model.model === $('model').value);
}

function renderEfforts(preferred = '') {
  const model = selectedModel();
  const presets = model?.supportedReasoningEfforts || [];
  const labels = {low: 'Thấp', medium: 'Vừa', high: 'Cao', xhigh: 'Rất cao', max: 'Tối đa', ultra: 'Ultra'};
  const option = (value, text) => {
    const entry = document.createElement('option');
    entry.value = value;
    entry.textContent = text;
    return entry;
  };
  $('effort').replaceChildren(
    option('', `Mặc định${model ? ' (' + model.defaultReasoningEffort + ')' : ''}`),
    ...presets.map(preset => option(preset.reasoningEffort,
      labels[preset.reasoningEffort] || preset.reasoningEffort))
  );
  $('effort').value = presets.some(preset => preset.reasoningEffort === preferred) ? preferred : '';
  showModelInfo();
}

function showModelInfo() {
  const model = selectedModel();
  if (!model) {
    $('modelInfo').textContent = 'Nhập token client rồi tải danh sách model từ Codex.';
    return;
  }
  const effort = $('effort').value || model.defaultReasoningEffort;
  const preset = model.supportedReasoningEfforts.find(item => item.reasoningEffort === effort);
  const modalities = model.inputModalities || ['text', 'image'];
  $('modelInfo').textContent = `${model.displayName} · ${model.model} · ${effort}. `
    + (modalities.includes('image') ? 'Hỗ trợ chữ và ảnh. ' : 'Chỉ hỗ trợ chữ. ')
    + (preset?.description || '')
    + ' Catalog không bảo đảm quyền truy cập cuối cùng; lỗi từ dịch vụ sẽ được báo rõ.';
}

async function loadModels(refresh = false) {
  const version = ++modelLoadVersion;
  const token = $('token').value;
  const previous = modelCatalog.length ? modelSettings() : null;
  $('modelInfo').textContent = 'Đang tải danh sách model từ Codex…';
  let data;
  try {
    data = await api('models' + (refresh ? '?refresh=true' : ''));
  } catch (error) {
    if (version === modelLoadVersion) $('modelInfo').textContent = 'Không tải được model: ' + error.message;
    throw error;
  }
  if (version !== modelLoadVersion || token !== $('token').value) return;
  modelCatalog = data.models;
  const defaultModel = modelCatalog.find(model => model.isDefault) || modelCatalog[0];
  const defaultOption = document.createElement('option');
  defaultOption.value = 'default';
  defaultOption.textContent = `Mặc định Codex — ${defaultModel.displayName}`;
  $('model').replaceChildren(defaultOption, ...modelCatalog.map(model => {
    const option = document.createElement('option');
    option.value = model.model;
    option.textContent = model.displayName;
    return option;
  }));
  const saved = previous || data.settings;
  const available = saved.model === 'default' || modelCatalog.some(model => model.model === saved.model);
  $('model').value = available ? saved.model : 'default';
  $('engine').value = saved.engine;
  renderEfforts(saved.reasoning_effort || '');
  if (!available) {
    $('modelInfo').textContent = `Model đã lưu (${saved.model}) không còn trong catalog. `
      + 'Đang hiển thị mặc định Codex; hãy chọn và lưu lại cấu hình mong muốn.';
  }
}

function modelSettings() {
  return {model: $('model').value, reasoning_effort: $('effort').value || null, engine: $('engine').value};
}

async function refreshAgentStatus() {
  const status = await api('agent/status');
  const labels = {idle: 'Chưa chạy', ready: 'Sẵn sàng', starting: 'Đang mở lượt agent',
    thinking: 'Đang xử lý', completed: 'Đã hoàn tất', error: 'Có lỗi'};
  $('agentPhase').textContent = labels[status.phase] || status.phase;
  $('agentActivity').textContent = status.events.map(event => {
    const stamp = new Date(event.time * 1000).toLocaleTimeString('vi-VN');
    return `${stamp} · ${labels[event.phase] || event.phase}`
      + (event.model ? ` · ${event.model} / ${event.reasoning_effort}` : '')
      + (event.message ? ` · ${event.message}` : '');
  }).join('\n') || 'Agent chưa có hoạt động. CLI cũ không phát sự kiện tại đây.';
}

$('loadModels').onclick = () => busy('loadModels', () => loadModels(true));
$('saveModels').onclick = () => busy('saveModels', async () => {
  await api('ai-settings', modelSettings());
  $('modelInfo').textContent += ' Đã lưu cho công việc mới.';
});
$('model').onchange = () => renderEfforts();
$('effort').onchange = showModelInfo;
$('engine').onchange = () => {
  showModelInfo();
  $('modelInfo').textContent += ' Thay đổi này áp dụng cho công việc mới; công việc hiện tại giữ cấu hình đã chọn.';
};

let modelLoadTimer;
function scheduleModelLoad() {
  clearTimeout(modelLoadTimer);
  if (!$('token').value.trim()) {
    modelLoadVersion++;
    $('modelInfo').textContent = 'Nhập token client để tự tải danh sách model; không cần kết nối AutoCAD.';
    return;
  }
  modelLoadTimer = setTimeout(() => loadModels().catch(() => {}), 600);
}
$('token').addEventListener('input', scheduleModelLoad);
$('token').addEventListener('change', scheduleModelLoad);
scheduleModelLoad();
