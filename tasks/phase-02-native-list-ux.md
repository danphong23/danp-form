# Phase 2 bổ sung — Native list UX

**Trạng thái: kế hoạch mới; chưa triển khai hoặc test các task NL2.1–NL2.4.**

Đọc [kế hoạch sidebar native](../docs/roadmap/phase-02-native-list-ux.md),
[interaction](../docs/blender/interaction.md),
[control model](../docs/core/control-model.md),
[development contract](../docs/roadmap/development-contract.md).
Đây là đợt thay thế bố cục UI hiện có, vẫn thuộc Phase 2.

## NL2.1 — Dữ liệu danh sách

- [ ] Projection UIList đọc Source definitions; active UUID riêng theo Source.
- [ ] Rename trực tiếp, Enter/Cancel và reorder ↑/↓ giữ identity/masks/network.
- [ ] Cập nhật list cache đúng context, undo/redo/load; panel draw không ghi Source.
- [ ] Test tên trùng, reorder giữ active item, đổi model không lẫn index/selection;
      metadata edit không thay effective network. Commit sau khi test đạt.

## NL2.2 — Thao tác +/−/Sync

- [ ] + nhận Source selection hoặc mapped proxy selection trong Edit Mode.
- [ ] − xóa definition active, giữ phần chung và chọn dòng kế tiếp hợp lệ.
- [ ] Sync replace membership active từ selection, giữ UUID/name/order.
- [ ] Prune masks theo union còn định nghĩa; không auto Reveal; no-op không đổi revision.
- [ ] Validate/rollback và undo/redo; Source topology/coordinates không bị sửa.
- [ ] Test empty selection, mixed point/edge, duplicate overlap, shared junction,
      Source/controller Edit và unsupported modes. Commit sau khi test đạt.

## NL2.3 — Sidebar tối giản

- [ ] UIList cuộn; dòng chỉ tên/mắt; cột +/−/menu/↑/↓; đúp tên sửa inline.
- [ ] Click dòng chọn active/highlight; Select/Shift+Select ở Edit không ngầm Reveal.
- [ ] Con mắt On/Partial/Hidden và tooltip overlap theo kế hoạch.
- [ ] Matrix object/mode đúng; init/rebuild là empty/error state, không panel phụ thường trực.
- [ ] Không còn row boxes lặp nhiều nút, tên proxy/status kỹ thuật hay Display/Maintenance.
- [ ] Test sidebar hẹp, 0/1/20 đường, click/rename/menu/list scroll. Commit sau test đạt.

## NL2.4 — Test live và bàn giao

- [ ] Workflow CUA: chọn selection → + → chọn dòng → Select → sửa selection → Sync →
      reorder → đúp tên → mắt → −; lặp trong các Edit context hợp lệ.
- [ ] MCP assertions Source IDs, union/masks, geometry, active object/mode và shared elements.
- [ ] Regression overlay/highlight, context, undo/redo, load và package reload.
- [ ] Test đúng phiên Blender/file đang mở; bảo toàn dirty work, fixture được dọn.
- [ ] Báo cáo ca đã test và NOT RUN, version/ZIP nhất quán, commit sau test đạt.

Hoàn tất tiêu chí native list của [P2-UX](../docs/testing/acceptance-gates.md) trước
Phase 3. Báo cáo UX trước chỉ là bằng chứng cho bản cũ; không đánh dấu task mới pass.
