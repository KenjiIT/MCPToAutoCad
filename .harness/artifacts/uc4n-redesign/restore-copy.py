from pathlib import Path

copy = [
    'Cùng U-C4N đọc tài liệu, trao đổi phương án và thực hiện bản vẽ AutoCAD.',
    'Trao đổi · U-C4N Workspace', 'Công cụ · U-C4N Workspace',
    'Đến nội dung chính', 'U-C4N — Trang trao đổi', 'Không gian làm việc',
    'Trao đổi', 'Công cụ', 'Đổi giao diện sáng tối', 'Không gian trao đổi',
    'Từ ý tưởng đến bản vẽ.', 'Trao đổi để làm rõ yêu cầu. Chốt phương án khi bạn sẵn sàng.',
    'Bạn duyệt trước khi thực hiện', 'Trao đổi với trợ lý CAD', 'Cuộc trao đổi của bạn',
    '+ Trao đổi mới', 'Lịch sử trao đổi', 'Bạn muốn dựng gì hôm nay?',
    'Mô tả ý tưởng hoặc đính kèm tài liệu. Mình sẽ cùng bạn làm rõ kích thước, bố trí và các bước thực hiện trên AutoCAD.',
    'Đọc bản vẽ hiện tại và cho mình biết các thông tin chính.', 'Đọc bản vẽ hiện tại',
    'Mình muốn dựng bản vẽ từ tài liệu đính kèm. Hãy đọc và hỏi lại những chi tiết còn thiếu.',
    'Dựng từ tài liệu', 'Yêu cầu của bạn', 'Mô tả điều bạn muốn làm với bản vẽ…',
    'Đính kèm', 'Shift + Enter để xuống dòng', 'Gửi tin nhắn',
    'Tài liệu, PDF hoặc ảnh · Tối đa 20 MB', 'Bỏ file', 'Chờ bạn duyệt',
    'Phương án thực hiện', 'Tôi đã xem các bước và chọn đúng bản vẽ cần thao tác.',
    'Chốt phương án & xử lý', 'Sau thực hiện', 'Kết quả xử lý',
    'Kết nối và hướng dẫn', 'Kết nối AutoCAD', 'Chưa kết nối',
    'Mở bản vẽ trong AutoCAD, sau đó kết nối để bắt đầu.', 'Cấu hình kết nối',
    'Nhập token client', 'Lấy token tại UC4NAutoCADMCPClient/data/operator-token.txt',
    'Địa chỉ MCP server', 'Bearer token MCP (nếu có)', 'Kết nối MCP',
    'Kết nối lại AutoCAD', 'Cùng làm từng bước', 'Chia sẻ yêu cầu',
    'Nhắn tin hoặc gửi tài liệu bạn đang có.', 'Hoàn thiện phương án',
    'Trao đổi thêm để chọn cách thực hiện.', 'Chốt và xử lý',
    'Xem các bước, duyệt rồi theo dõi kết quả.',
    'Cần xem danh sách công cụ hoặc cấu hình model? ', 'Mở trang công cụ →',
    'Không gian công cụ', 'Thiết lập & điều khiển.',
    'Quản lý kết nối, cấu hình AI và xem từng công cụ CAD.',
]
for filename in ['chat.html', 'index.html']:
    path = Path('UC4NAutoCADMCPClient/client') / filename
    content = path.read_text(encoding='utf-8')
    markup, scripts = content.split('<script>\nconst $=', 1)
    for text in sorted(copy, key=len, reverse=True):
        markup = markup.replace(text.encode('ascii', 'replace').decode(), text)
    path.write_text(markup + '<script>\nconst $=' + scripts, encoding='utf-8')
print('Restored UTF-8 interface copy.')
