# H07 — Chính sách topology và phục hồi mapping

**Phụ thuộc H01, H03; có thể song song H05/H06. Bàn giao:** topology đổi ngoài
DANP có trạng thái rõ, giữ dữ liệu và phục hồi tường minh.

1. Định nghĩa thay đổi được chấp nhận (tọa độ, topology không đụng control,
   mất/cắt cạnh/đỉnh control) theo persistent IDs, face connectivity, Shape Key
   constraints và duplicate. Đối chiếu chính sách hiện tại chặn toàn mesh trên
   fingerprint mismatch; không tự tuyên bố mọi thay đổi không đụng control là an
   toàn vì patch có thể đổi.
2. Implement Validate/Repair có preview ảnh hưởng, cấp ID mới khi không mơ hồ,
   rebuild proxy/patch/cache và giữ mask nếu còn hợp lệ. Trường hợp mơ hồ phải
   trả `STALE_MAPPING` và hướng dẫn Reset hoặc sửa tay.
3. Giữ object/key/control khi repair thất bại; thao tác không ghi vào index cũ.

**Kiểm thử:** thêm/xóa đỉnh xa control, loop cut trong patch, thay connectivity
giữ nguyên count, xóa cạnh control, duplicate ID, Shape Key đang tồn tại,
Undo/Redo và save/reopen. **Gate:** không ghi sai Source hoặc xóa control im lặng;
mọi auto-accept đều có fixture chứng minh patch/mapping hợp lệ. **Commit:**
`feat(dan-form): make topology recovery explicit`.

**Nghiệm thu 2026-09-25:** fixture nền Blender 5.2.1 pass 20 assertion. Người
dùng xác nhận Validate/Repair và Undo/Redo đã hoạt động ổn trên giao diện.
Nghiệm thu này do người dùng báo lại, không kèm video/ảnh/log UI. Chi tiết:
[`2026-09-25-h07-topology-recovery.md`](../../docs/testing/2026-09-25-h07-topology-recovery.md).
