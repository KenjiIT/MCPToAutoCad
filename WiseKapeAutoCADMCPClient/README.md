# MCP HTTP Client

## Model và Codex agent

Nhập token client, bấm **Tải / làm mới model** hoặc kết nối MCP để tự tải danh sách.
Chọn model và mức suy luận từ catalog do Codex app-server trả về; nút **Lưu mặc định**
lưu vào `data/ai-settings.json`. Quyền sử dụng cuối cùng được dịch vụ kiểm tra khi
gọi model; client báo lỗi và không âm thầm đổi model. Ảnh/PDF có ảnh cần model hỗ trợ ảnh.

Chế độ **Codex agent · app-server** dùng tiến trình Codex riêng qua stdio, theo dõi
sự kiện bắt đầu/xử lý/hoàn tất/lỗi và tạo proposal JSON có kiểm tra schema. Agent nhận
skill Coordinator cùng dữ liệu CAD do client cung cấp; không được tự thực thi CAD.
Mỗi lượt dùng một thread tạm, lịch sử công việc vẫn do client lưu trong SQLite.
Không có nhiều agent độc lập ở bản này. **Codex CLI · tương thích** giữ adapter cũ,
vẫn áp dụng model/mức suy luận đã chọn nhưng không phát sự kiện agent.

Model `default` và mức suy luận mặc định được chuyển thành giá trị cụ thể lúc tạo
công việc; các giai đoạn, câu trả lời bổ sung và lần đánh giá tiếp theo giữ nguyên
cấu hình đó. Phương án/kết quả có trường `ai` ghi cấu hình đã dùng. Thay đổi bộ chọn
chỉ áp dụng khi bắt đầu công việc mới. Dừng client bằng script sẽ dừng cả tiến trình
Codex do client tạo; không dừng MCP server hay phiên Codex khác.

Catalog được cache tối đa 5 phút, hỗ trợ phân trang và làm mới thủ công. Giao thức:
[Codex app-server](https://learn.chatgpt.com/docs/app-server).

Coordinator được nạp trực tiếp từ `skills/coordinator/SKILL.md` vào mỗi lần gọi AI.
Client tự cập nhật toàn bộ catalog MCP và đọc `system_status`, `drawing_info`;
không cần tích chọn công cụ cho AI. Sau khi thực thi một phương án AI, client tự
gửi yêu cầu gốc, lịch sử thao tác, kết quả và trạng thái hiện tại để AI đánh giá.
Phương án tiếp theo hiển thị để duyệt, không tự thực thi. Gọi tool thủ công không
kích hoạt vòng điều phối. Mỗi lượt đánh giá có thể gọi Codex thêm một lần.

Lịch sử lưu tại `data/coordinator.sqlite3`, bao gồm yêu cầu/tài liệu dạng chữ,
kế hoạch và kết quả có cấu trúc; ảnh kết quả MCP không được gửi lại cho AI.
Hiện giới hạn 12 giai đoạn/công việc để chặn vòng lặp; không giới hạn số tool call
trong một phương án. Khởi động lại hoặc đổi phiên MCP không tự khôi phục thực thi;
cần kết nối và lập phương án mới. Kiểm tra tự động hiện chỉ đọc metadata bản vẽ;
các phép đo chi tiết phải được AI đưa vào phương án và duyệt trước khi chạy.

Web client độc lập tại **http://127.0.0.1:8771**. Kết nối MCP qua Streamable HTTP; không khởi động/dừng server và không cần source WiseKape.

Chạy PowerShell tại folder này:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1 -Background
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/stop.ps1
```

Setup tạo `.venv` riêng. Bỏ `-Background` để chạy foreground. `-Port` đổi cổng web client.

Nhập token ở `data/operator-token.txt`, endpoint server (mặc định `http://127.0.0.1:8769/mcp`) và Bearer token nếu server yêu cầu. Sau đó kết nối, nhập prompt/tài liệu yêu cầu, xem phương án và duyệt thực thi. Engine COM/ezdxf thuộc cấu hình server.

Hỗ trợ TXT/MD, JSON/CSV, DOCX, XLSX, PDF và ảnh. File upload xử lý và lưu tại client, tối đa 20 MB/file; PDF tối đa 12 trang. Khi lập phương án, chữ/ảnh được gửi cho Codex CLI đã đăng nhập. Token client và token MCP không gửi cho AI.

Đóng client chỉ ngắt phiên HTTP. Server có thể tiếp tục chạy. Nếu server mất kết nối, khởi động server lại rồi kết nối và lập phương án mới. Log client nằm tại `data/client.stdout.log`, `data/client.stderr.log`. Dữ liệu/token cũ được giữ trong folder `data/` này.
