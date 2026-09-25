# H06 — Agent API biết target

**Phụ thuộc H01, H02, H05. Bàn giao:** agent có thể liệt kê/chọn target và đặt
target control qua primitive chung với UI, không mô phỏng click.

1. Bổ sung truy vấn target và trạng thái key, lựa chọn target có kiểm tra
revision/identity, thông báo unsupported/locked/stale rõ ràng.
2. Dùng operation handle chụp target ngay lúc begin; `set_knot_targets` là
tọa độ tuyệt đối cho tập selected đầy đủ, kiểm tra thiếu/thừa ID và finite.
3. Mọi kết quả báo target/revision/changed count; agent và UI dùng cùng
expand-selection, P0, solver, writeback, cancel và Undo.

**Kiểm thử:** gọi API trực tiếp và qua MCP thực tế; so sánh tọa độ, Shape Key,
network/masks, kết quả lỗi với thao tác UI tương đương; thử target đổi giữa
operation, stale handle và multi-Source isolation. **Gate:** parity số học và
lifecycle; không đường agent nào ghi bypass adapter. **Commit:**
`feat(dan-form): expose target-aware agent operations`.
