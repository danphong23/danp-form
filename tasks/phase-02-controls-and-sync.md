# Phase 2 — Đường control và đồng bộ Source/controller

**Đầu vào:** Gate P1 pass. **Đầu ra:** chọn vertex/edge Source tạo control exact;
đường trùng Source và Hide/Reveal hoạt động. Gate P2; chưa nội suy biến dạng.

Trước khi chuyển Phase 3, hoàn thành thêm [Phase 2 native list UX](phase-02-native-list-ux.md)
và Gate P2-UX. Task nền này vẫn là yêu cầu mapping/masks/lifecycle; bản triển khai
có UI không có nghĩa toàn bộ gate đã pass.

## Đọc bắt buộc

[Control model](../docs/core/control-model.md),
[mapping/sync](../docs/architecture/mapping-and-sync.md),
[ADR-008](../docs/decisions/ADR-008-hide-releases-control.md),
[data model](../docs/architecture/data-model.md),
[interaction](../docs/blender/interaction.md).

## Work packages

- **P2.1 — Persistent IDs:** cấp vertex/edge IDs ổn định, monotonic counters và
  fingerprint connectivity có face. Đọc đúng BMesh khi Source Edit Mode. Phân biệt
  đổi tọa độ với đổi topology; kiểm tra referenced ID mất/đúp/ambiguous.
- **P2.2 — Create/remove definitions:** nhận selection điểm, dải cạnh, loop hoặc
  network giao nhau; lưu Source-backed definitions. Logical names chỉ để chọn/UX.
  Overlap dùng chung Source IDs, không tạo vertex proxy trùng. Remove prunes obsolete
  masks nhưng giữ trạng thái các định nghĩa overlap còn tồn tại.
- **P2.3 — Exact proxy:** dựng vertex/edge không face theo union định nghĩa. Mỗi
  visible vertex trùng vị trí Source local, mapping hai chiều IDs. Create thêm đường
  cập nhật controller hiện có. Rebuild không đổi hình học hay Reveal All.
- **P2.4 — Hide/Reveal:** cả đường edge-backed dùng edge intent; explicit node Hide
  dùng vertex intent; đoạn/selection mixed theo canonical masks. Shared junction
  vẫn bật nếu được đường khác hỗ trợ. Reveal edge xóa edge masks của nó và node
  masks endpoint; các edge-hidden khác vẫn ẩn. Lặp lệnh unchanged không tăng revision.
- **P2.5 — Live display sync:** Source chỉnh tọa độ, controller cập nhật khi đang
  xem/đổi mode, không phải đợi đến lệnh deformation. Thử event/dirty refresh nhẹ trong
  context an toàn; revalidate ở mốc lệnh. Source transform vẫn chỉ qua parenting.
  Chặn/khôi phục coordinate edits trên controller ở phase này với thông báo chưa
  hỗ trợ; không ghi mesh từ hai phía trước khi có transaction phase 4.
- **P2.6 — Persistence/recovery:** save/reopen, proxy delete/rebuild, external
  topology change, duplicate Source. Masks/definitions lưu trên Source; corruption
  trả lỗi và cho validation/repair tường minh, không đoán ID.

## Test và bàn giao

Grid và cylinder có 2 loop + đường dọc; create overlap; point độc lập; branch;
Hide cả đường dọc giữ junction của loop, node Hide giải phóng edges giáp nó, Hide
một đoạn rồi Reveal; create trên vùng đang ẩn không tự hiện. Kiểm tra effective
network qua IDs, không chỉ nhìn màn hình. Dùng assertions state của G18/G21, còn
assertions deformation của chúng kiểm tra ở phase 4.

Đổi tọa độ Source trong Object/Edit Mode, save/load/rebuild và undo/redo create/
hide/remove đều giữ mapping và trùng vị trí. Record độ trễ sync/refresh, không tuyên
bố mọi frame tức thời nếu chưa đo. Topology đổi giữ counts vẫn bị phát hiện.

Gate P2 pass khi đường/masks/IDs/persistence đúng và Source không biến dạng bởi
create/hide/reveal/rebuild. Không có deactivate riêng; ẩn DANP Form khác visibility
object/collection thông thường. Bàn giao demo và state assertions; hoàn tất NL2.1–NL2.4
và Gate P2-UX trước P3.1.
