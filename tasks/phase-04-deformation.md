# Phase 4 — Biến dạng trong Edit Mode và proportional

**Đầu vào:** Gates P1–P3 pass. **Đầu ra:** chỉnh controller làm Source biến dạng
trong patch liên quan, confirm/cancel/undo ổn định. Gates P4, B, C, D.

## Đọc bắt buộc

[Selection/targets](../docs/core/selection-and-targets.md),
[operation semantics](../docs/core/operation-semantics.md),
[proportional](../docs/core/proportional.md),
[candidate interpolation](../docs/core/interpolation-baseline.md),
[errors/recovery](../docs/architecture/errors-and-recovery.md),
[integration cases](../docs/testing/blender-integration-cases.md),
[shared primitives](../docs/agent/shared-primitives.md).

## Work packages theo thứ tự

- **P4.1 — Selection và targets:** chọn vertex/dải/edge/loop trong controller Edit
  Mode; resolve unique Source IDs. G/R/S sinh absolute target từ P0 với pivot/axis
  rõ ràng. Selected junction thắng unselected membership; conflicting explicit
  targets trả lỗi. Chuyển world/local bằng transform đã capture, radius ban đầu
  tính source-local rest units. Chưa làm sparse.
- **P4.2 — Transaction thuần dữ liệu:** begin/update/commit/cancel, một owner mỗi
  Source. Capture P0 và union mọi incident patch của selection kể cả target ban
  đầu identity. Mỗi update reset captured scope về P0, tính affected hiện tại;
  outside scope giữ nguyên. Closed/busy/stale generation lỗi rõ; no-op vẫn cleanup.
- **P4.3 — Nội suy nhỏ và profiles:** thử candidate hiện có trên fixtures trước UI
  modal; dedup control samples theo Source ID. Hard-project selected targets và
  stationary enabled controls. Whole Patch và finite radius; thử attenuation đều,
  linear/smooth để người dùng so sánh. “Đều” là profile attenuation, không cam kết
  mọi vertex cùng displacement trong khi biên khác cố định. Apply proportional
  một lần, path/distance giới hạn trong patch; không dùng ngang/dọc anatomical.
- **P4.4 — Quyết định nội suy:** chạy Gates B/C, review G4/G5/G11 với người dùng và
  so sánh profiles; chọn candidate/default hoặc experiment nhỏ cho lỗi có tên.
  Ghi input, parameters, images và numeric assertions; chốt numerical/default bằng
  ADR/báo cáo evidence khi có đủ bằng chứng, không sửa quy tắc fixed để che lỗi.
- **P4.5 — Blender Edit Mode:** tích hợp modal G/R/S và radius/profile UI; đọc BMesh
  đúng mode, solve buffer rồi validate trước write. Dùng keymap/tool routing DAN
  Form có phạm vi controller và cho thấy khi thao tác DANP Form; không giả định
  operator transform native tự cung cấp transaction cần thiết. Prototype lựa
  chọn routing, đảm bảo thao tác mong đợi trên controller và không bắt nhầm Source.
- **P4.6 — Preview/lifecycle:** Source preview → proxy sync, cancel/confirm/undo/
  redo, target quay về P0, radius shrink, đổi profile; chặn structural edits trong
  tx. Hide/Reveal thực hiện giữa các thao tác, hidden verts theo mesh rồi Reveal
  ở vị trí mới. External topology interruption không ghi rollback bằng stale index.
- **P4.7 — Facade số tối thiểu:** expose cùng begin/set_targets/commit/cancel/query/
  control visibility primitives cho test không UI và agent phase 5. Không thêm
  solver hay direct Source-write đường riêng. Record full-path latency/memory.

## Test và bàn giao

G1/G2/G3/G6/G9/G10/G12–G21 phải pass theo measurement contract; G4/G5/G11 cần quyết
định chất lượng, không chỉ record failure. G7/G8 chờ extension sparse. Thử limb 2
loop + đường dọc: scale một/cả hai loop khi đường dọc bật/ẩn; junction được chọn
di chuyển, phần control bật không chọn đứng yên, hidden phần còn lại theo deformation.
Không bắt buộc midpoint đúng nửa hoặc scale affine toàn patch.

Blender cases: point/span/loop, transformed Source, no-op, pivot/axis, repeat G/R/S,
cancel, undo/redo, save/load, rebuild, two Sources, unsupported feature và topology
interruption. Gate D kiểm tra lifecycle thực, agent parity chờ phase 5.

Bàn giao bản cài tương tác được, facade contract, geometry report, quality decision,
performance report và thao tác thử. Gate P4 chỉ pass sau B/C/D; nếu candidate chưa
đạt chất lượng thì sửa tại phase này. Bước sau P5.1.
