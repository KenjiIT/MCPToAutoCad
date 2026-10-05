# Nối AutoCAD thật

Trạng thái: **chưa xác minh**. `config/cad.json` mặc định simulation và `verified: false`. Đổi cờ thành true không thể mở khóa adapter chưa triển khai.

## Các điểm chưa biết

| Điểm cần xác minh | Nguồn kiểm chứng | Ranh giới thay đổi |
|---|---|---|
| Kết nối được phiên AutoCAD của người dùng | AutoCAD đang chạy + thử đọc không ghi | `src/ai_autocad/cad.py` |
| COM hay plugin .NET phù hợp để tạo hình và đọc lại | Thử trên DWG kiểm thử trong AutoCAD 2027 | `src/ai_autocad/cad.py` |
| Target document ổn định, đơn vị và WCS đúng | API AutoCAD, kể cả khi đổi active drawing | `src/ai_autocad/cad.py` |
| Đóng gói MCP riêng cho client ngoài | Tool discovery + initialize + gọi tool thử | Adapter/transport tương lai; không đổi agent contract |

Không đoán cổng localhost, tên tool Autodesk, cơ chế auth hoặc mặc định AutoCAD đã hỗ trợ ghi qua MCP tích hợp.

## Trình tự nghiệm thu

1. Mở AutoCAD, hoàn tất kích hoạt, tạo DWG thử; chạy `scripts/check_environment.ps1`.
2. Thực hiện phép đọc phiên bản, bản vẽ, units và layer bằng kết nối được tài liệu hóa. Ghi rõ cơ chế và kết quả.
3. Triển khai CadAdapter trong `cad.py`. Gắn chính xác document identity; chỉ nhận hình học đã compile sau gate. Xử lý document lock, undo group, timeout, trạng thái bận và đọc lại.
4. Với người dùng xác nhận, thử đường bao 5000 × 4000 mm: kiểm tra vertices, layer, closed, WCS, document identity, lưu/mở DWG. Phải thử cả đổi bản vẽ đang active, units không khớp, bản vẽ đóng và lỗi giữa chừng.
5. Kiểm tra không ghi khi chưa duyệt, sau sửa revision, khi token sai, khi approval hết hạn. Kiểm tra double-click, crash và đối soát sau lỗi. Có bằng chứng conformance mới đánh dấu verified và cho chọn mode thật.

## Giới hạn base hiện tại

Conformance tự động hiện có chứng minh workflow và hình học trên simulation; **không phải** bằng chứng AutoCAD đã vẽ đúng. Không bật chế độ thật chỉ vì toàn bộ unit tests xanh. Workflow `needs_reconciliation` yêu cầu người vận hành kiểm tra trạng thái CAD; chưa có chức năng tự phục hồi hoặc tự rollback.
