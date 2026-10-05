# AI AutoCAD

Base backend chạy trên Windows: **yêu cầu → agent phân tích → phương án + SVG xem trước → người dùng xác nhận → CAD adapter → đọc lại kết quả**.

**Hiện chạy ở chế độ mô phỏng. Chưa kết nối vẽ thật trong AutoCAD.** Agent demo chỉ hiểu `rectangle 5000 x 4000 mm`; đây là bộ phân tích tất định để thử luồng, không phải AI xử lý tiếng Việt, ảnh hoặc giọng nói.

## Chạy trên máy này

Môi trường `.venv` đã được tạo trong thư mục này. Mở PowerShell tại `AI_AutoCad`:

```powershell
$env:PYTHONUTF8 = '1'
$env:AI_AUTOCAD_OPERATOR_TOKEN = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
.\scripts\run.ps1
```

API docs: <http://127.0.0.1:8765/docs>. Health: <http://127.0.0.1:8765/health>.

Giữ token trong phiên PowerShell của người vận hành; không đưa token vào cấu hình agent hoặc commit Git. Nếu chạy `review.py` ở cửa sổ khác, đặt **cùng token** trong cửa sổ đó. Không tạo một token khác cho client.

```powershell
.\.venv\Scripts\python.exe scripts/review.py --text "rectangle 5000 x 4000 mm"
```

Client tạo phương án, in đầy đủ dữ liệu, mở SVG và **đợi người dùng gõ `APPROVE 1`**. Khi xác nhận mới gửi approve/execute. Kết quả nằm trong SQLite mô phỏng, không tạo DWG.

Để cài lại trên máy mới:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

## Đổi agent mà không đổi lõi

Agent phải trả **DrawingProposal JSON v1**, không trả lệnh AutoCAD hay trạng thái xác nhận. Không có SDK OpenAI, Claude hoặc Codex trong lõi.

Hai đường tích hợp đã được kiểm thử:

- **Command:** ứng dụng gửi JSON qua stdin, nhận JSON từ stdout. Dùng một wrapper cho agent CLI/local model của bạn.
- **HTTP:** ứng dụng POST cùng JSON tới endpoint của bạn; endpoint trả trực tiếp DrawingProposal. Dùng wrapper cho bất kỳ model API nào. Đây là giao thức riêng được công bố của ứng dụng, không mặc định tương thích trực tiếp với mọi API nhà cung cấp.

Sao chép `config/agents.json` thành `config/agents.local.json`, thêm agent rồi đặt biến môi trường trước khi chạy server:

```powershell
$env:AI_AUTOCAD_AGENTS_CONFIG = Join-Path $PWD 'config/agents.local.json'
```

Ví dụ file có một agent command chạy được với Python venv hiện tại:

```json
[
  {"id": "demo", "kind": "demo", "modalities": ["text"]},
  {
    "id": "my-agent",
    "kind": "command",
    "modalities": ["text"],
    "command": [".venv/Scripts/python.exe", "examples/command_agent.py"],
    "timeout_seconds": 60.0
  }
]
```

Ví dụ trên chứng minh cách thay agent, vẫn dùng analyzer demo. Thay phần phân tích trong wrapper bằng agent bạn chọn; giữ nguyên JSON input/output. Agent thực dùng Python, Node.js, C# hoặc ngôn ngữ khác đều được.

Agent HTTP được khai báo bằng `kind: "http"`, `url: "http://127.0.0.1:9000/analyze"`, `modalities: ["text"]`; thêm `api_key_env` nếu endpoint cần Bearer token. URL phải trỏ đến endpoint do bạn triển khai theo [hợp đồng](docs/AGENT-PROTOCOL.md). Restart server để nạp registry mới; chọn `agent_id` khi tạo yêu cầu.

## Cấu trúc

```text
src/ai_autocad/
  models.py       Hợp đồng dữ liệu, đơn vị, nguồn số đo
  agents.py       Registry + demo/HTTP/command adapters
  workflow.py     SQLite, phiên bản, xác nhận, chống thực thi trùng
  cad.py          CAD mô phỏng + khóa adapter AutoCAD chưa xác minh
  preview.py      SVG dựng từ hình học đã chuẩn hóa
  api.py          REST API + cổng token của người vận hành
config/           Agent registry và CAD mode
contracts/        JSON Schema v1 để agent khác tích hợp
scripts/          Chạy server, review, kiểm tra môi trường, xuất schema
tests/            Luồng xác nhận, đổi agent và các lỗi quan trọng
docs/             Kiến trúc, hợp đồng và checklist nối AutoCAD thật
```

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/smoke.py
.\.venv\Scripts\python.exe scripts/export_contracts.py
.\scripts\check_environment.ps1
```

API nền đã có; chưa xây giao diện sản phẩm, ghi âm, upload ảnh, dịch vụ nhận dạng tiếng nói, agent AI trả phí hay lưu DWG. `Attachment.reference` là mã tài nguyên do phía tích hợp quản lý; core không tự đọc file/URL và không giả định đã xem ảnh.

Kết quả nghiệm thu base ngày 2026-10-05: **27 tests passed**, Ruff pass, HTTP smoke pass (server thật, SQLite tạm, simulation). Smoke test tự xác nhận dữ liệu fixture trong môi trường mô phỏng để kiểm tra gate; không thay thế bước duyệt của người dùng khi vận hành. Có một cảnh báo deprecation từ Starlette TestClient về HTTPX; không có test lỗi. AutoCAD COM chỉ đọc đã attach thành công, phiên bản `26.0s`, chưa có bản vẽ mở.

## Phạm vi bảo vệ

API chỉ bind loopback qua script chạy. Token riêng cần cho cả approve và execute; agent adapter không được nhận token đó. Đây là base **một người dùng trên máy tin cậy**, chưa phải hệ thống nhiều tài khoản hay sandbox cho chương trình không tin cậy. Agent command chạy cùng tài khoản Windows có quyền của tài khoản đó; chỉ cài wrapper đáng tin. Muốn cách ly mạnh phải dùng tài khoản/process sandbox riêng, phân quyền người dùng và quản lý secrets trước khi triển khai nhiều người.

Việc thay agent không làm thay đổi cổng xác nhận, nhưng schema đúng không chứng minh số đo đúng. Người vận hành phải kiểm tra số liệu; xác nhận không đổi nhãn `inferred` thành số đo thực tế.
