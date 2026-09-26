# Phase 2 bổ sung — Native list UX

Selection UX is being delivered in two bounded phases. Phase 1 adds Shift-click
multi-control selection and full/partial/empty row markers derived from the
current Edit selection. See the [Phase 1 report](../docs/testing/selection-phase-1-report.md).

- [x] Phase 1 — dedicated row selection action, Shift-add, derived row state,
  overlap/hidden/empty tests, active row for shared actions.
- [ ] Phase 2 — review the existing viewport quick-pick shortcut and define its
  overlap/hidden behavior before changing it; do not alter deformation or pivots.

**Trạng thái: core UIList đã triển khai; lifecycle và controller cố định topology 0.2.2 đã qua regression live.
Các checkbox rộng bên dưới vẫn là gate cần bằng chứng riêng, không tự đánh dấu hoàn tất.**

## Bổ sung 0.2.3 — Edit Mode hiệu năng và viền front

- [x] Profile trực tiếp Source Edit với 37 definitions: xác định đọc ID từng đỉnh
      lặp lại trong effective network, UI projection và overlay.
- [x] Đọc topology/ID/coordinates theo lô; cache union theo mapping và canonical masks.
- [x] Giữ GPU buffers ở idle; invalidate theo geometry, context, masks, highlight,
      transforms, runtime refresh; Controller Edit vẽ cyan từ BMesh sống.
- [x] Chỉ thêm chấm cho explicit point handles, không chồng lên mọi edge endpoint.
- [x] MCP: 38 cache/highlight + 37 lifecycle + 34 sidebar + 36 segment/visibility
      checks; tổng 145, fixture được dọn.
- [x] Ctrl+Alt+Click chọn span giữa giao điểm; Shift cộng selection; menu/F3/MCP
      dùng active/single edge hoặc canonical edge ID. Kiểm tra cả projection pick.
- [x] H edge mode chỉ ẩn cạnh, giữ giao điểm của đường còn bật; vertex mode ẩn
      node và các cạnh chạm nó. Alt-H dùng current Source để Reveal.
- [x] Hide/Show Controls chuyển sang canonical toàn bộ, mọi mắt Hidden/On,
      giữ object/mode, bao gồm controller Edit rỗng; ADR-010 thay quy tắc 0.2.1.
- [x] Computer Use: Source Edit → Edit Control → Back to Source Edit; trả về
      model Object, selection được khôi phục, nhân vật được frame đầy đủ.
- [x] Computer Use H/Alt-H: canonical mask 24E/0V → 0E/0V, mắt Hidden → On,
      giữ controller Edit; trả lại Source Edit đang dùng khi bắt đầu test cuối.
- [x] Bổ sung 13 nhóm front contour trên nhân vật live; giữ 37 definitions cũ
      và geometry. Cube giữ 6 definitions; không thêm topology vào model.

Bằng chứng/giới hạn: [báo cáo 0.2.3](../docs/testing/phase-02-edit-performance-report.md).

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
- [x] 0.2.1: Hide/Show Controls từng là display-only (đã thay bằng ADR-010 ở 0.2.3);
      Edit Control / Back to Model nhớ mode.
- [x] Overlay theo ngữ cảnh: Source-backed khi chọn model, controller-backed khi
      chọn proxy Object Mode, và highlight cyan trong Controller Edit Mode.
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
