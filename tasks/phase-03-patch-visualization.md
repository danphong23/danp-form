# Phase 3 — Patch graph và hiển thị patch

**Đầu vào:** Gate P2 pass. **Đầu ra:** patch đúng topology, lớp hiển thị bật/tắt để
người dùng kiểm tra. Gate P3; không tắt/bật phép biến dạng của patch.

## Đọc bắt buộc

[Patch model](../docs/core/patch-model.md),
[control model](../docs/core/control-model.md),
[leg examples](../docs/product/leg-control-examples.md),
[geometry cases](../docs/testing/geometry-cases.md).

## Work packages

- **P3.1 — Face adjacency:** dựng graph qua Source edges; bỏ adjacency qua effective
  control edges, tính connected components thành patch. Lưu face membership, vertices,
  boundary và incident-patch lookup theo IDs. Point control không tự tạo đường cắt.
- **P3.2 — Invalidation:** create/remove/Hide/Reveal thực sự đổi effective network
  thì invalidate partition và constraint cache. Đổi tọa độ không đổi face partition
  nhưng geometry display và distance data tương lai phải cập nhật.
- **P3.3 — Overlay UX:** màu patch, highlight patch/biên đang quan tâm, nút Show
  Patches; nếu có toggle từng patch chỉ ẩn lớp màu. Giữ Source geometry thật và mọi
  patch trong solver. Không xóa/hide faces Source để loại chúng khỏi tính toán.
- **P3.4 — Context/lifecycle:** overlay đúng transform Source, refresh khi network
  đổi, cleanup khi unregister/file load/source delete, không tạo datablock rác.
- **P3.5 — Test partition:** fixtures grid, cylinder, đường mở không chia được,
  loop kín, branch/junction, point, partial Hide. Record số patch và face membership
  trước/sau; không mặc định một đường dọc trên cylinder tạo hai patch.

## Test và bàn giao

Tắt/bật overlay không đổi Source coordinates, effective masks, revisions hay face
partition. Hide một đường thật phải đổi graph khi nó là cut có khả năng phân tách;
Reveal phục hồi graph theo topology hiện tại. Parenting/scale không làm màu lệch mesh.

Gate P3 pass khi assertions partition đúng và UX bật/tắt chỉ tác động hiển thị.
Bàn giao fixture trước/sau Hide với overlay, incident-patch API và cache invalidation
tests. API này được phase 4 dùng để capture scope và propagation; không có ownership
cha/con cho patch/control. Bước sau P4.1.
