# H03 — Bảo vệ object khi mất liên kết sở hữu

**Trạng thái: PASS lifecycle safety, 2026-09-25.** Bằng chứng ở
[báo cáo H03](../../docs/testing/2026-09-25-h03-owned-object-safety.md).

**Độc lập; có thể song song H01/H02. Bàn giao:** lifecycle không xóa vĩnh viễn
mesh đang nằm trong scene chỉ vì marker DANP không tìm được Source.

1. Kiểm kê controller, face/overlay helper, marker, parent và duplicate cả cặp.
   Phân biệt object trong scene, orphan thật, object liên kết library và dữ liệu
   do người dùng chỉnh sửa.
2. Thay auto-remove trong load/depsgraph bằng trạng thái cần repair hoặc dọn
   riêng bằng thao tác tường minh có preview danh sách. Chỉ dọn runtime cache
   không chứa dữ liệu người dùng tự động.
3. Khi Source bị xóa/undo/duplicate, giữ quan hệ một Controller–một Source,
   báo lỗi ổn định và cung cấp đường phục hồi không phá dữ liệu.

**Kiểm thử:** fixture tạo object có stale marker nhưng vẫn trong scene, xóa
Source, undo, load/reload, duplicate mesh và cả cặp; assert object và mesh data
không bị xóa ngoài lệnh dọn tường minh. **Gate:** mọi đường handler không xóa
object người dùng khi thông tin sở hữu mơ hồ. **Commit:**
`fix(dan-form): make ownership recovery non-destructive`.

## Kết quả triển khai

- Load/depsgraph chỉ đánh dấu stale ownership và gỡ cảnh báo khi owner hợp lệ
  xuất hiện; không xóa object hoặc mesh datablock.
- Sidebar cung cấp thao tác Undoable để bỏ marker cũ, giữ geometry, transform
  và datablock.
- Fixture Blender kiểm tra stale Controller/face object qua load/depsgraph,
  explicit unbind, owner xuất hiện lại và duplicate lifecycle.
- Interactive Undo sau khi bấm nút trong 3D View là NOT RUN. Fixture nền không
  có UI undo context; lần gọi operator từ timer trong cửa sổ thử riêng không
  đại diện cho thao tác click thật và không được dùng làm bằng chứng PASS.
