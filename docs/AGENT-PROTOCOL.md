# Analysis Agent Protocol v1

Giao thức của dự án, độc lập nhà cung cấp và độc lập MCP. MCP dành cho công cụ CAD ở một ranh giới khác. Model không cần tự hỗ trợ MCP để làm agent phân tích.

## Request

Command nhận một JSON document qua stdin và EOF; HTTP nhận POST JSON. Envelope gồm:

```json
{
  "protocol_version": "1.0",
  "instructions": "Application analysis instructions",
  "input": {
    "text": "rectangle 5000 x 4000 mm",
    "attachments": []
  },
  "output_schema": {}
}
```

Trong request thực, `output_schema` luôn là toàn bộ JSON Schema sinh từ `DrawingProposal`, không phải object rỗng như ký hiệu rút gọn trong ví dụ. Schema đầy đủ ở `contracts/drawing-proposal.v1.schema.json` và GET `/contracts/proposal`.

Core gửi instruction tách với input để wrapper có thể đưa vào system/user role tương ứng. Wrapper chịu trách nhiệm gọi provider, lấy JSON từ response và trả đúng proposal. Không nối token operator vào prompt, headers, môi trường hay log của wrapper.

## Response

Trả trực tiếp một DrawingProposal hợp lệ: không bọc Markdown, không envelope `choices`, không thêm `approved`, `execute` hoặc mã thực thi. Command stdout chỉ chứa JSON; chẩn đoán gửi stderr. HTTP trả status 200 và `application/json`. Lỗi provider, timeout hoặc sai schema trở thành lỗi phân tích; không phát sinh phương án được xác nhận.

`examples/command_agent.py` là ví dụ chạy được theo hợp đồng. Các test command và HTTP dùng hai transport thật trên localhost/process để kiểm tra khả năng thay thế, không chỉ mock method call.

## Khả năng và tài nguyên

Registry công bố `modalities`: text/image/audio. Agent không khai báo hỗ trợ ảnh sẽ bị chặn trước khi nhận request có ảnh. Reference chỉ là định danh, chưa phải nội dung đã được tải. Wrapper phải có cách truy cập hợp lệ đến tài nguyên đó; không truy cập được thì trả `unresolved_questions`, không giả vờ đã phân tích.

Giọng nói có thể được chuyển thành transcript trước để dùng agent text; phải cho người dùng sửa transcript và kiểm tra số đo. Bản base chưa tích hợp speech-to-text/OCR.

## Checklist thêm agent

1. Cài một wrapper đáng tin, chỉ đọc request và xuất DrawingProposal.
2. Thêm cấu hình vào `agents.local.json`; chọn `id`, transport và modalities đúng khả năng.
3. Đặt credential bằng biến môi trường tên riêng qua `api_key_env`, không dùng token operator.
4. Restart server, tạo request với `agent_id` mới, kiểm tra câu hỏi thiếu dữ liệu và provenance.
5. Chạy test conformance; chỉ sau khi người vận hành kiểm tra bản xem trước mới approve.

Mỗi nhà cung cấp có định dạng API khác nhau nên vẫn cần wrapper thích hợp. Không phải thay tên model là mọi agent tự hoạt động. Core, database và cổng xác nhận không cần sửa khi wrapper giữ đúng hợp đồng v1.
