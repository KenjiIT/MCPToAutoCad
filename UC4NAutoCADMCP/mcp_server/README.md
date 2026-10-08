# U-C4N MCP HTTP Server

Server độc lập. `run.py` nạp source U-C4N từ `upstream/` rồi phục vụ MCP Streamable HTTP tại **http://127.0.0.1:8768/mcp**. Không cần MCP client chạy để server hoạt động.

Chạy PowerShell tại folder này:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1 -Backend com -Background
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/stop.ps1
```

`-Backend com`: AutoCAD qua COM trên Windows. `-Backend ezdxf`: thao tác DXF độc lập. Bỏ `-Background` để chạy foreground. `-Port` đổi cổng HTTP. Setup tạo môi trường `.venv` riêng.

File CAD cho phép đọc/ghi: `data/drawings/`. Log: `data/server.stdout.log`, `data/server.stderr.log`. Đổi đường dẫn bằng `.venv/Scripts/python.exe run.py --backend com --drawings-dir <folder>`.

Engine được chọn khi khởi động, không đổi từ client. Server chỉ bind 127.0.0.1. Có thể đặt biến môi trường `MCP_AUTH_TOKEN` để yêu cầu Bearer token. Nhiều client dùng chung document/engine; không có khóa toàn phương án giữa các client.

Source gốc: [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP), MIT, version 1.6.0, commit `cdb10638963898b3ea9b10cdd96a2c9bc495f184`. Setup clone đúng commit nếu source thiếu. Source upstream không sửa.
