"""UI-only regression checks with mocked chat/CAD APIs; no real CAD calls."""
import json
from pathlib import Path
import sys
import tempfile
from playwright.sync_api import sync_playwright, expect

OUT = Path(__file__).parent
ROOT = Path('UC4NAutoCADMCPClient')

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
        headless=True,
    )
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.set_default_timeout(6000)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    checks = []
    for name, route in [('chat', '/chat'), ('settings', '/'), ('tools', '/tools')]:
        page.goto('http://127.0.0.1:8767' + route)
        page.evaluate('document.fonts.ready')
        assert '??' not in page.locator('body').inner_text()
        assert page.locator('[aria-current=page]').count() == (0 if name == 'tools' else 1)
        assert page.evaluate("document.fonts.check('14px \"Be Vietnam Pro\"')")
        ids = page.locator('[id]').evaluate_all('(nodes)=>nodes.map(n=>n.id)')
        assert len(ids) == len(set(ids)), 'Duplicate IDs'
        for theme in ['light', 'dark']:
            page.evaluate('(theme)=>document.documentElement.dataset.theme=theme', theme)
            for width in [320, 375, 414, 768, 1280, 1440]:
                page.set_viewport_size({'width': width, 'height': 900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), (name, theme, width)
                # Ensure interactive controls really fit, rather than merely clipping the root.
                overflow = page.locator('button,a.nav-link,input:not(.visually-hidden),textarea,select').evaluate_all('''nodes=>nodes.filter(n=>{
                    const r=n.getBoundingClientRect(); return r.width>0 && (r.right>innerWidth+1||r.left< -1);
                }).map(n=>n.id||n.textContent)''')
                assert not overflow, (name, theme, width, overflow)
            page.set_viewport_size({'width': 1440, 'height': 1000})
            page.screenshot(path=str(OUT/f'{name}-{theme}.png'), full_page=True)
        checks.append(f'{name}: both themes, 6 widths, fonts, IDs, no clipped controls')

    page.goto('http://127.0.0.1:8767/chat')
    page.get_by_role('button', name='Chuyển sang giao diện tối').click()
    page.reload()
    assert page.evaluate('document.documentElement.dataset.theme') == 'dark'
    page.get_by_role('button', name='Chuyển sang giao diện sáng').click()
    page.get_by_role('button', name='Đọc bản vẽ hiện tại', exact=True).click()
    assert page.locator('#message').input_value().startswith('Đọc bản vẽ')
    page.locator('#message').fill('')
    page.locator('#send').click()
    assert 'Nhập tin nhắn' in page.locator('#notice').inner_text()
    page.locator('#token').fill('ui-test-token')
    state = {'session': 'mock-session', 'tool_count': 248, 'status': {'connected': True, 'backend': 'com'}}
    page.route('**/api/status', lambda route: route.fulfill(json=state))
    page.route('**/api/reconnect', lambda route: route.fulfill(json=state))
    page.locator('#connect').click()
    expect(page.locator('#connection')).to_have_attribute('data-state', 'connected')
    page.locator('#reconnect').click()
    page.locator('[data-connection-settings]').evaluate('(node)=>node.open=false')

    proposal = {'id': 'mock-plan', 'job_id': 'mock-job', 'decision': 'plan', 'summary': 'Đọc thông tin bản vẽ để xác định đơn vị và số đối tượng.', 'steps': [{'tool': 'drawing_info', 'arguments': {}, 'explanation': 'Kiểm tra tên bản vẽ, đơn vị và số đối tượng đang có.'}], 'messages': [{'role': 'user', 'content': 'Đọc tài liệu đính kèm giúp tôi.'}, {'role': 'assistant', 'content': 'Mình đã đọc yêu cầu. Trước tiên, cần kiểm tra thông tin bản vẽ hiện hành.'}]}
    requests = []
    page.route('**/api/files', lambda route: route.fulfill(json={'id': 'mock-file', 'name': 'yeu-cau.txt'}))
    def reply(route):
        requests.append(route.request.post_data_json)
        route.fulfill(json=proposal)
    page.route('**/api/chat', reply)
    page.locator('#file').set_input_files({'name': 'yeu-cau.txt', 'mimeType': 'text/plain', 'buffer': b'CAD drawing requirements'})
    assert page.locator('#clearFile').is_visible()
    page.locator('#message').fill('Đọc tài liệu đính kèm giúp tôi.')
    page.locator('#send').click()
    page.locator('#proposalCard').wait_for(state='visible')
    assert requests[0]['attachment_id'] == 'mock-file'
    assert page.locator('#clearFile').is_hidden()
    assert page.locator('#execute').is_disabled()
    assert page.locator('#messages .bubble').count() == 2
    for width in [320, 375, 414, 768]:
        page.set_viewport_size({'width': width, 'height': 900})
        bounds = page.locator('#execute').bounding_box()
        assert bounds and bounds['x'] + bounds['width'] <= width, ('approval overflow', width)
    page.set_viewport_size({'width': 1440, 'height': 1000})
    assert not page.locator('#steps details').evaluate('(e)=>e.open')
    page.locator('#steps summary').click()
    assert page.locator('#steps pre').is_visible()
    result = json.loads((ROOT/'data/http-live-check.json').read_text(encoding='utf-8'))['result']
    result['results'] = result['results'][:1]
    page.route('**/api/plans/mock-plan/execute', lambda route: route.fulfill(json=result))
    page.locator('#confirm').check()
    page.locator('#execute').click()
    page.locator('#result dl').first.wait_for(state='visible')
    assert page.locator('#result dl').count() > 0
    assert page.locator('#execute').is_disabled()
    assert page.locator('#result details').is_visible()
    assert not page.locator('#result details').evaluate('(e)=>e.open')
    page.set_viewport_size({'width': 1440, 'height': 1000})
    page.screenshot(path=str(OUT/'chat-result.png'), full_page=True)
    page.set_viewport_size({'width': 375, 'height': 900})
    page.screenshot(path=str(OUT/'chat-mobile.png'), full_page=True)
    page.locator('#newChat').click()
    assert page.locator('#proposalCard').is_hidden()
    assert page.locator('#resultCard').is_hidden()
    page.goto('http://127.0.0.1:8767/')
    page.locator('#token').fill('ui-test-token')
    settings_response = {'models':[{'model':'model-a','displayName':'Model A','isDefault':True,'defaultReasoningEffort':'medium','supportedReasoningEfforts':[{'reasoningEffort':'medium','description':'Default'},{'reasoningEffort':'high','description':'More reasoning'}],'inputModalities':['text','image']}], 'settings':{'model':'default','reasoning_effort':None,'engine':'agent'}, 'source':'codex-app-server'}
    saved_settings=[]
    page.route('**/api/models*',lambda route:route.fulfill(json=settings_response))
    page.route('**/api/ai-settings',lambda route:(saved_settings.append(route.request.post_data_json),route.fulfill(json=route.request.post_data_json)))
    page.locator('#loadModels').click()
    expect(page.locator('#model')).to_have_value('default')
    page.locator('#model').select_option('model-a')
    page.locator('#effort').select_option('high')
    page.locator('#engineCli').check()
    page.locator('#saveSettings').click()
    expect(page.locator('#settingNotice')).to_contain_text('Đã lưu cấu hình')
    assert saved_settings == [{'model':'model-a','reasoning_effort':'high','engine':'cli'}]
    setting_status={'session':None,'tool_count':0,'status':{'connected':False}}
    connected={'session':'mock-settings','tool_count':248,'status':{'connected':True,'backend':'com'}}
    page.route('**/api/status',lambda route:route.fulfill(json=setting_status))
    page.route('**/api/connect',lambda route:route.fulfill(json=connected))
    page.route('**/api/reconnect',lambda route:route.fulfill(json=connected))
    page.locator('#connect').click()
    expect(page.locator('#connection')).to_contain_text('com đã kết nối')
    page.locator('#reconnect').click()
    page.locator('#refresh').click()
    assert not errors,errors
    checks.append('Theme persistence, navigation, mobile layout, agent/model/effort settings, MCP endpoint actions, suggestions, file upload, chat, approval, result rendering. All APIs mocked; no CAD calls.')
    sys.path.insert(0, str(Path('UC4NAutoCADMCPClient').resolve()))
    from client import api as client_api
    original = {name:getattr(client_api,name) for name in ['SETTINGS_FILE','coordinate','resolve_selection','save_job']}
    selected = {}
    async def capture_job(job):
        selected.update({'model':job['model'],'reasoning_effort':job['reasoning_effort'],'engine':job['engine']})
        outcome={'job_id':job['id'],'summary':'Preferences applied','decision':'complete','ai':{'model':job['model'],'engine':job['engine']}}
        job['last_decision']=outcome
        return outcome
    try:
        with tempfile.TemporaryDirectory() as temp:
            client_api.SETTINGS_FILE=Path(temp)/'ai-settings.json'
            client_api.SETTINGS_FILE.write_text(json.dumps({'model':'model-b','reasoning_effort':'high','engine':'cli'}),encoding='utf-8')
            client_api.coordinate=capture_job
            client_api.resolve_selection=lambda model,effort,has_images=False:(model,effort or 'medium')
            client_api.save_job=lambda job:None
            from fastapi.testclient import TestClient
            with TestClient(client_api.app) as web:
                client_api.bridge.session='mock-session'
                response=web.post('/api/chat',headers={'Authorization':'Bearer '+client_api.TOKEN},json={'message':'Use saved preferences'})
                assert response.status_code==200,response.text
                assert selected=={'model':'model-b','reasoning_effort':'high','engine':'cli'},selected
    finally:
        for name,value in original.items():setattr(client_api,name,value)
    checks.append('API integration: saved agent/model/reasoning preferences populate a new chat job; persistence isolated in temporary storage.')
    assert not errors, errors
    (OUT/'checks.json').write_text(json.dumps({'passed': checks, 'browser_errors': errors, 'cad_calls': 'mocked'}, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close()
    print('PASS: responsive UI and mocked workflow checks. No CAD operations executed.')
