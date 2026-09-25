# H01 — Chốt hợp đồng Deformation Target

**Độc lập. Bàn giao:** ADR mới và đặc tả thống nhất cho Source base/Basis/Shape Key;
không đổi solver hoặc dữ liệu scene. Đối chiếu [ADR-015](../../docs/decisions/ADR-015-shape-key-edit-target.md)
với đề xuất bên ngoài; nếu đổi phạm vi relative/absolute, phải ghi rõ ADR nào
được thay và cách xử lý file cũ.

1. Kiểm kê đường target hiện tại: UI, workflow, Source Edit Mode, controller,
   Undo/Redo, reset, duplicate, khóa key và value/mute/show-only.
2. Định nghĩa target ID ổn định trong một transaction, target được chọn lúc
   begin, cách phát hiện đổi/xóa/đổi tên key, Shape Key relative/absolute, Basis
   và mesh không có key. Chốt hỗ trợ absolute hoặc lỗi từ chối có tên; không
   âm thầm hạ phạm vi đang accepted.
3. Vẽ ranh giới adapter đọc/ghi/snapshot/khôi phục để core chỉ nhận tọa độ.
   Ghi rõ tạo key mới, cô lập hiển thị bằng `show_only_shape_key` mà không tự
   thay giá trị/mute, và giới hạn topology của Blender.

**Kiểm thử:** review ma trận tình huống và truy vết mỗi rule sang fixture H02–H06;
chạy validator tài liệu. **Gate:** không còn mâu thuẫn giữa ADR, data model,
UI/API và bảng lỗi. **Commit:** `docs(dan-form): settle deformation target contract`.
