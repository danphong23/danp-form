# H05 — Hoàn thiện UX chọn target và tạo Shape Key

**Phụ thuộc H01, H02, H04. Bàn giao:** Source/Controller hiển thị target đang
được chỉnh, chuyển target có kiểm tra và lệnh tạo key mới an toàn.

1. Dùng một nguồn trạng thái target (active Source key) cho panel và operator;
   tránh dropdown giữ giá trị khác Blender. Hiển thị base/Basis, tên key,
   locked/stale/unsupported và trạng thái đang preview.
2. Lệnh New Shape Key tạo từ target được H01 cho phép; không tự đổi giá trị
   key, mute, drivers hoặc animation. Khôi phục `show_only_shape_key` sau khi
   rời Controller Edit Mode và khi cancel/error.
3. Quy định phản hồi khi người dùng đổi/xóa/khóa key giữa transaction; chặn
   lệnh trước ghi và giữ selection/mode nhất quán.

**Kiểm thử:** background cho tạo/chọn/khóa/lưu-mở; UI thật cho panel, edit,
chuyển target, rời mode, Undo/Redo trên bản sao an toàn. So sánh key values,
mute và tọa độ các key không chọn. **Gate:** người dùng luôn thấy đúng target;
không có thay đổi ngoài ý muốn. **Commit:**
`feat(dan-form): complete deformation target workflow`.
