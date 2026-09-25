# H04 — Ổn định transaction G/R/S trong Blender

**Phụ thuộc H02, H03. Bàn giao:** một nguồn trạng thái transform cho mỗi thao tác
controller Edit Mode; loại bỏ nhảy giữa hai kết quả khi Scale toàn control.

1. Truy vết modal transform, depsgraph/timer, preview ownership, affine path và
   cache. Chặn re-entry/race; mỗi update dùng P0 bất biến và target mới nhất.
2. Củng cố commit/cancel/Undo, chuyển mode/selection/target khi modal, all-control
   và partial control; giữ exact stationary constraints và no-op.
3. Ghi kết quả toàn mesh so với phép G/R/S affine khi mọi control hữu hiệu đã
   chọn, proportional radius 0; đo sai số theo float32 hợp lý.

**Kiểm thử:** pure + background fixture, sau đó **thao tác chuột G/R/S thật**
trên bản sao model có Shape Key và model không key; thử nhiều khung preview,
confirm/cancel/undo/redo, tất cả/ một phần control, object scale khác 1.
Quan sát có/không flicker, đo tọa độ chứ không chỉ ảnh. **Gate:** một kết quả
xác định, không giật/trạng thái xen kẽ, không drift sau cancel/undo; có log và
video/ảnh nếu cần. **Commit:** `fix(dan-form): stabilize native transform transactions`.

**Nghiệm thu 2026-09-25:** background fixture Blender 5.2.1 pass 23 assertion;
người dùng xác nhận đã thử các gate G/R/S bằng chuột trên bản sao an toàn với
control đầy đủ/một phần, object scale khác 1, có/không Shape Key, confirm/cancel
và Undo/Redo; báo cáo mọi thứ hoạt động ổn. Đây là nghiệm thu do người dùng cung
cấp, không kèm video/ảnh/log UI. Chi tiết:
[`2026-09-25-h04-native-transform.md`](../../docs/testing/2026-09-25-h04-native-transform.md).
