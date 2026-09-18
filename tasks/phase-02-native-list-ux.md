# Phase 2 bổ sung — Native list UX

**Trạng thái: core UIList đã triển khai; lifecycle và controller cố định topology 0.2.2 đã qua regression live.
Các checkbox rộng bên dưới vẫn là gate cần bằng chứng riêng, không tự đánh dấu hoàn tất.**

## Bổ sung 0.2.2 — Lifecycle và controller chỉ chỉnh vị trí

- [x] Tên sản phẩm DANP Form; giữ namespace/schema cũ để đọc file hiện có.
- [x] Model luôn có Init và Remove DANP Form màu đỏ; Init lặp không tạo thêm proxy.
- [x] Remove gỡ binding, definitions, masks, ID layers và controller/mesh không còn dùng;
      giữ model, hình học, dữ liệu ngoài addon và mode Source Object/Edit.
- [x] Controller không có Sync, +/−; tạo/Sync/xóa definitions chỉ trên model.
- [x] Chặn shortcut topology trong Controller Edit; khôi phục thay đổi từ native
      operators/BMesh theo IDs và connectivity, giữ pose hợp lệ gần nhất.
- [x] MCP live: 37 checks trên fixture được dọn trong file đang mở và 33 checks trên
      model hiện có; Computer Use xác nhận bố cục model/controller và navigation.

Bằng chứng và ca NOT RUN: [báo cáo 0.2.2](../docs/testing/phase-02-controller-lifecycle-report.md).

## Bổ sung 0.2.1 — Sidebar phản hồi nhanh

- [x] Mapping/draw/sidebar chỉ đọc; cache invalidation theo geometry, undo/redo/load.
- [x] Handler chỉ sync khi Source geometry đổi, bỏ mesh update nếu tọa độ không đổi.
- [x] Bỏ handler/overlay trùng khi nạp lại addon đang cài.
- [x] Chọn dòng highlight tức thì ở Object; tự chọn Source/proxy IDs trong Edit.
- [x] Hide/Show Controls là display-only; Edit Control / Back to Model nhớ mode.
- [x] Overlay theo ngữ cảnh: Source-backed khi chọn model, controller-backed khi
      chọn proxy Object Mode, và tắt lớp phụ trong Controller Edit Mode.
- [x] Sync ghi membership mới, no-op giữ revision; active row giữ đúng UUID sau rebuild.
- [x] MCP live regression 33 assertions và Computer Use click sidebar trên file đang mở.

Bằng chứng: [báo cáo 0.2.1](../docs/testing/phase-02-sidebar-performance-report.md).

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

- [ ] + nhận Source selection trong Source Edit Mode; controller từ chối tạo definition.
- [ ] − xóa definition active, giữ phần chung và chọn dòng kế tiếp hợp lệ.
- [ ] Sync replace membership active từ selection, giữ UUID/name/order.
- [ ] Prune masks theo union còn định nghĩa; không auto Reveal; no-op không đổi revision.
- [ ] Validate/rollback và undo/redo; Source topology/coordinates không bị sửa.
- [ ] Test empty selection, mixed point/edge, duplicate overlap, shared junction,
      Source/controller Edit và unsupported modes. Commit sau khi test đạt.

## NL2.3 — Sidebar tối giản

- [ ] UIList cuộn; dòng chỉ tên/mắt; cột +/−/menu/↑/↓; đúp tên sửa inline.
- [ ] Click dòng chọn active/highlight và selection ở Edit không ngầm Reveal; kiểm tra thêm Shift selection.
- [ ] Con mắt On/Partial/Hidden và tooltip overlap theo kế hoạch.
- [ ] Matrix object/mode đúng; model có Init/Remove, controller chỉ sửa; không panel phụ thường trực.
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
