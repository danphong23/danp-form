# Phase 2 bổ sung — UX control và sidebar

**Trạng thái: kế hoạch; các task dưới đây chưa được đánh dấu PASS.**

Đọc [kế hoạch UX](../docs/roadmap/phase-02-ux-upgrade.md),
[Phase 2 nền](phase-02-controls-and-sync.md),
[interaction](../docs/blender/interaction.md),
[control model](../docs/core/control-model.md),
[mapping/sync](../docs/architecture/mapping-and-sync.md),
[development contract](../docs/roadmap/development-contract.md).

## UX2.1 — Context tự động

- [ ] Resolve active Source/controller bằng identity; xử lý mesh mới, empty và binding lỗi.
- [ ] Panel, poll, execute và navigation dùng resolver chung; draw chỉ đọc.
- [ ] Status/list không lưu lẫn giữa Source; sync theo dõi nhiều Source/controller.
- [ ] Test hai model, các đường chuyển context, multi-selection và binding ambiguous;
      xác nhận lệnh không sửa Source khác. Ghi báo cáo và commit khi pass.

## UX2.2 — Giữ Edit Mode

- [ ] Adapter đọc Source BMesh IDs/topology/coordinates mà không thoát Edit Mode.
- [ ] Make Control liên tục giữ Source active, mode và selection; overlap toàn phần cho phép.
- [ ] Validate trước ghi và phục hồi nếu lỗi; structural actions giữ context;
      rebuild proxy edit khôi phục selection qua Source IDs.
- [ ] Test nhiều lần tạo, thất bại có kiểm soát, mixed point/edge, Source sync cả
      Object/Edit; geometry không đổi và undo/redo đúng. Báo cáo và commit khi pass.

## UX2.3 — Danh sách và hành động

- [ ] List theo Source; UUID ổn định; đổi tên chỉ đổi nhãn; tên mặc định không gây nhầm.
- [ ] Select/Add to Selection theo context, không implicit Reveal; Object Mode có
      hành động Edit Source & Select được ghi rõ.
- [ ] On/Partial/Hidden suy ra từ effective network; Hide Whole/Reveal Whole gọi
      canonical masks, tooltip giải thích ảnh hưởng overlap.
- [ ] Delete definition giữ union và masks được định nghĩa khác dùng; Source không
      bị xóa; prune dữ liệu obsolete; undo/redo đầy đủ.
- [ ] Test A=1–2–3, B=2–3–4; overlap toàn phần; điểm rời + cạnh; node junction;
      hide rồi tạo overlap; reveal không về vị trí cũ; delete cuối. Báo cáo/commit.

## UX2.4 — Hiển thị đường trên Source

- [ ] Overlay màu union edges/points và highlight định nghĩa được chọn.
- [ ] Live BMesh coordinates, depth handling và Source transforms chính xác.
- [ ] Show Overlay/X-Ray/Show Hidden là display-only; không sửa materials/geometry/masks.
- [ ] Dirty refresh và cleanup handlers/cache khi load/unregister/reload.
- [ ] Test front/side/perspective, Source Edit, nonuniform scale, đường trùng,
      masks so với display; ảnh đủ nhìn rõ; đo refresh thực tế. Báo cáo/commit.

## UX2.5 — Bàn giao trước Phase 3

- [ ] Sidebar theo wireframe kế hoạch: thao tác thường dùng ở trên, Display và
      Maintenance thu gọn; tooltip/empty/error đúng context.
- [ ] Chạy end-to-end: chọn model → Initialize → tạo liên tiếp → chọn qua list →
      Hide/Reveal → xóa overlap → undo/redo → đổi model → rebuild.
- [ ] Hoàn tất regression P2: mapping, topology validation, persistence/save/reopen,
      proxy delete/rebuild, unsupported input; ca thiếu bằng chứng ghi NOT RUN.
- [ ] Test trên phiên/file Blender đang mở theo hướng dẫn workspace; không chạy
      Blender riêng, không lưu đè file đang dirty. Fixture tạm được dọn/khôi phục.
- [ ] Version code/manifest/ZIP nhất quán; cài ZIP thật, kiểm tra lifecycle và handler.
- [ ] Báo cáo [P2 và P2-UX](../docs/testing/acceptance-gates.md), commit sau test pass.

## Điều kiện bàn giao

Không sửa mesh Source qua thao tác quản lý control; proxy luôn là cache Source-backed.
Không thêm cờ deactivate riêng, control parenting hoặc nội suy Phase 4. Phase 3 chỉ
bắt đầu khi P2 và P2-UX có bằng chứng pass. Kế hoạch tài liệu không phải báo cáo test.
