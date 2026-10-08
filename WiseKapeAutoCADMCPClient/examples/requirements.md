# Yêu cầu thử đọc bản vẽ

Mục tiêu: đọc thông tin bản vẽ hiện hành trong AutoCAD.

1. Lấy tên bản vẽ và số entity bằng `drawing_info`.
2. Lấy đơn vị bằng `system_get_variable` với biến `INSUNITS`.
3. Không tạo, sửa, xóa entity hoặc lưu bản vẽ.

Hãy lập phương án gọi các tool đọc tương ứng để người vận hành xem và duyệt.
