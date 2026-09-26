# DANP Form — Làm sạch sau comprehensive review

**Trạng thái: C01 đang triển khai; checkpoint safety đầu tiên đã kiểm chứng. C02 còn mở.**
Baseline: `f8dbcaa`, version 0.5.36. Bằng chứng:
[review ngày 2026-09-26](../docs/testing/2026-09-26-comprehensive-addon-review.md).
Các mục dưới đây là cleanup của hợp đồng hiện có; preview/hover mới chờ các gate.

## Đã hoàn tất trong đợt review

- [x] Inventory runtime, đăng ký operator, package và tracked artifacts.
- [x] Chạy release suites trên tiến trình riêng và audit các đường gọi chéo.
- [x] Sửa bind ghi đè module metadata, sửa empty selection return contract.
- [x] Bỏ control-group snapshot không còn được solver dùng; giữ core API compatibility.
- [x] Thêm regression cho hai lỗi nền; dọn bytecode cache.
- [x] Ghi lỗi đã tái hiện và giới hạn nghiệm thu lịch sử.

## C01 — Safety, lifecycle và ranh giới mã

Tiến độ checkpoint 2026-09-26:

- [x] R01/R02: busy caller không mượn hoặc hủy transaction của owner; native
  bridge từ chối operation khác đang mở.
- [x] R03/R09: target giới hạn vào mapping chụp đầu operation; matrix WORLD
  suy biến/non-finite bị từ chối.
- [x] R04 Create/Sync/Hide/eye/Reveal/Delete/Reset/Repair: failure sau mutation
  nhưng trước proxy rebuild rollback state nguồn, revision và proxy; fault
  injection được thêm vào Blender background suites.
- [x] R11 unregister: preview đang mở được hủy về Operation Rest và dọn registry.
- [x] Registration failure giữa lúc đăng ký class rollback class/property/handler/
  overlay/keymap đã tạo một phần.
- [x] Unregister timer handles for native transform and Undo/Redo; repeated
  enable/disable regression confirms callbacks cancel and runtime handles clear.
- [ ] Deeper timer race/exception matrix; historical operator removal; module
  split.

Bằng chứng và giới hạn hiện tại ở
[checkpoint C01](../docs/testing/2026-09-26-c01-operation-safety.md).

Triển khai tuần tự; commit các phạm vi sửa có thể kiểm chứng độc lập.

1. **Transaction ownership (R01/R02).** Gắn owner/operation identity; một caller
   chỉ update/commit/cancel operation của mình. Busy rejection không đổi Source,
   Controller hoặc transaction của caller trước. Native observer không tái sử
   dụng agent transaction. Kiểm cả exception/finalize và timer race.
2. **Target validation (R03/R09).** Validate captured mapping, selected/moved IDs,
   finite coordinates, payload shape và invertible frame trước scope/writeback.
   Native proportional-moved enabled handles vẫn hợp lệ. Agent/UI cùng rules.
3. **Structural atomicity (R04).** Prepare/validate rồi ghi một lần hoặc có
   rollback cả definitions/masks/revision/proxy/context. Test inject lỗi ở từng
   bước của Create/Delete/Sync/Hide/Reset; no-op giữ revision.
4. **Lifecycle cleanup (R11).** Chốt finish/cancel khi disable/reload; dọn
   transaction, timers và stale RNA references sau khi kết thúc hợp lệ.
   Register failure rollback, repeated enable/disable và timer cancellation khi
   unregister đã có regression; bổ sung matrix race/exception trước khi chốt.
5. **Mã lịch sử và module boundaries.** Bỏ picker classes/helpers không đăng ký
   sau dependency review; giữ historical fixtures/report. Tách operator theo
   selection/visibility, structure/lifecycle, target UX và panel. Dependencies
   tường minh; không đổi solver hoặc IDs/schema để làm refactor.

Gate C01:

- [ ] Audit R01/R02/R03/R04/R09/R11 trở thành regression PASS.
- [ ] Caller bị reject không ảnh hưởng preview của owner.
- [ ] Không có write ngoài captured controller targets/scope.
- [x] Failure injection không để metadata/proxy/Source ID ghi dở trong các
  structural paths đã liệt kê; no-op giữ revision.
- [ ] Shape Key/duplicate/topology/transform suites tiếp tục pass.
- [ ] Mỗi commit ghi đúng fixture, actual result và giới hạn UI còn chưa chạy.

## C02 — Một hợp đồng tương tác, kiểm thử UX và package

Phụ thuộc C01 cho các đường ghi. Có thể rà docs/keymaps trước, nhưng không nghiệm
thu C02 khi safety gate còn FAIL.

1. **ADR visibility.** Đối chiếu schema 3 per-definition state với tài liệu masks
   chung; chốt intent cho H/Shift-H/Alt-H, mắt và overlap. Migration bảo toàn dữ
   liệu, không đoán hoặc downgrade từ tên. Cập nhật normative docs cùng quyết định.
2. **Shared selection/visibility service (R05/R06/R07).** UI/keymap/menu/MCP gọi
   cùng primitive. Có xử lý lệnh native không đi qua keymap; giữ unrelated
   selection qua rebuild. BMesh readers/writers cùng hide và flush rules.
3. **List state.** Mesh selection là nguồn FULL/PARTIAL/NONE. Active row và nhóm
   definitions để quản lý có semantics tường minh; hidden definitions vẫn quản
   lý được. “−”, mắt và bulk actions có scope/tooltip rõ, một thao tác một Undo.
4. **Errors và context.** Empty selection/no-op là kết quả dự kiến. Validation
   trước thay mode/active selection. Facade hỗ trợ context đã nhận hoặc từ chối
   context khác trước mutation.
5. **Hiệu năng có số đo.** Đo history memory, scene ownership lookup, preview P95
   và graph/cache rebuild. Giới hạn/prune history theo undo policy; tối ưu chỗ đo
   được. Không đổi thuật toán do kích thước file lớn hay số lượng hằng số.
6. **Gate freshness và phát hành.** Chuỗi UI mới có provenance commit/version;
   PASS cũ chỉ là historical reference. Đồng bộ license text/manifest/README,
   docs nguồn và bản tổng hợp; ZIP sạch, install/restart/reload đúng bản.

Gate C02:

- [ ] Chọn nhiều → H/Shift-H → Alt-H → mắt → Undo/Redo đạt expected state.
- [ ] Kiểm Vertex/Edge/Face, partial/hidden/overlap/empty, đổi Source/controller,
      đổi mode, save/reopen và các đường UI/MCP.
- [ ] MCP kiểm IDs, masks, flags, coordinates, context; Computer Use kiểm mouse,
      keymaps, list scroll và feedback thật trên bản sao an toàn.
- [ ] Không raw internal errors cho tình huống bình thường, không thay selection
      ngoài scope lệnh, không auto-reveal khi chỉ chọn.
- [ ] Release runner và audit mới đều đạt; GPU/performance có bằng chứng riêng.
- [ ] Chỉ sau gate nền mới triển khai Inspect/hover và batch preview đã đề xuất.

Không coi checkbox trong kế hoạch này là PASS chỉ vì task đã được mô tả. Review
không chứng minh mọi tổ hợp Blender native tools/modifiers đã được thử.
