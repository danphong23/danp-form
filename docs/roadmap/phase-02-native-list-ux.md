# Phase 2 — Sidebar gọn theo danh sách Blender

**Ưu tiên cập nhật 2026-09-26:** review mới xác định lỗi safety và tính nhất quán
visibility/selection. Thực hiện [cleanup tasks](../../tasks/addon-cleanup-review.md)
và đối chiếu [bằng chứng](../testing/2026-09-26-comprehensive-addon-review.md)
trước khi mở rộng viewport picker/Inspect; trạng thái triển khai lịch sử bên dưới
không thay gate cho những lỗi mới.

## Selection UX bổ sung — Phase 1

Đợt 1 bổ sung chọn nhiều control từ danh sách và trạng thái chọn suy ra trực
tiếp từ selection Edit Mode bằng persistent vertex IDs. Mỗi dòng có một nút
selection độc lập: click thay selection, Shift-click thêm membership; dòng được
nhấn trở thành active cho các thao tác chung. Bấm lại control đang chọn sẽ bỏ
chọn; Shift-bấm control đã chọn sẽ loại membership của nó khỏi vùng chọn.
Marker phân biệt đủ/một phần/rỗng,
cho phép nhiều control chồng lấp cùng hiện selected. Source Edit dùng membership
đã lưu; Controller Edit dùng effective membership sau Hide. Trạng thái chỉ là
projection UI và thao tác chọn không tạo bước Undo hình học.

Kiểm chứng và giới hạn được ghi trong [báo cáo selection UX Phase 1](../testing/selection-phase-1-report.md).

### Lộ trình selection UX

- [x] **Phase 1 — Chọn trong danh sách:** Shift-add; row marker FULL/PARTIAL/NONE;
  dùng persistent IDs; giữ một active row cho các thao tác quản lý.
- [ ] **Phase 2 — Chọn nhanh trong viewport:** rà soát shortcut pick control đang có,
  xác định hành vi khi chồng lấp/ẩn và bổ sung luồng chọn nhanh chỉ khi không cạnh
  tranh với Blender native selection. Không đổi solver, pivot hay topology.

**Trạng thái: UIList đã triển khai; lifecycle và controller cố định topology
trong 0.2.2 theo phản hồi ngày 2026-09-18.**

Bằng chứng và giới hạn kiểm tra: [báo cáo sidebar 0.2.1](../testing/phase-02-sidebar-performance-report.md).
Đợt bổ sung hiện tại: [báo cáo lifecycle 0.2.2](../testing/phase-02-controller-lifecycle-report.md).

Kế hoạch này thay thế bố cục sidebar và cách quản lý danh sách trong
[kế hoạch UX trước](phase-02-ux-upgrade.md). Giữ context theo active model, Source
là nguồn hình học, IDs ổn định, overlap-safe membership và canonical Hide/Reveal.
Không thêm phase chính; đây vẫn là công việc Phase 2 trước Phase 3.

## Mục tiêu và hiện trạng

Bản sidebar cũ có các box riêng cho từng đường, lặp Select/Rename/Delete/Hide và
hiện Display/Maintenance thường trực. Bản hiện tại dùng danh sách theo cách trình
bày của Vertex Groups/Shape Keys: dòng active,
tên sửa trực tiếp, con mắt, cột +/− và lên/xuống. Nút hiện theo object/mode.

Danh sách chứa **các đường/định nghĩa control của model hiện tại**, không phải danh
sách nhiều controller object. Mỗi Source vẫn có một controller object dùng chung.

## Bố cục duy nhất

```text
DANP Form
girl chibi 1
[Init DANP Form] [Remove DANP Form (đỏ)]   khi chọn model
[Edit Control / Back to Model] [Hide / Show Controls]
┌─────────────────────────┐  [+]
│ Đường trên           👁 │  [−]
│ Đường dưới           👁 │  [⋮]
│ Đường dọc            ◐ │  [↑]
│                         │  [↓]
└─────────────────────────┘
            [Sync]             chỉ hiện trong Source Edit Mode
```

- Dùng UIList native của Blender, có cuộn nội bộ, khoảng 5 dòng mặc định, hỗ trợ
  điều chỉnh chiều cao theo khả năng UIList. Mỗi dòng chỉ có tên và trạng thái mắt.
- Cột nút là thao tác trên dòng active. Tooltip giải thích chức năng; không lặp
  Select/Rename/Delete thành nút trên từng dòng.
- Tên Source là một nhãn gọn. Không hiện tên proxy, số effective, revision hoặc
  hộp status thành công thường trực. Lỗi dùng report Blender; hướng dẫn trống tối đa
  một dòng khi cần, ví dụ “Chọn cạnh rồi nhấn +”.
- Khi chọn model luôn có **Init DANP Form** và **Remove DANP Form** màu đỏ. Remove
  khóa trước khi khởi tạo. Init dùng lại controller hiện có hoặc dựng lại khi mất,
  giữ definitions/masks. Remove gỡ toàn bộ binding/definitions/masks/ID layers và
  controller, giữ hình học model và dữ liệu ngoài addon; giữ mode của Source.
- Không có khối Display/Maintenance. Edit Control / Back to Model và nút Hide/Show
  Controls nằm trên danh sách để điều hướng và Hide/Reveal toàn bộ nhanh (ADR-010).
  Khi chọn model, overlay màu lấy Source làm mốc để người dùng biết control nằm ở
  đâu. Khi chọn controller ở Object Mode, overlay đọc trực tiếp proxy mesh để đường
  màu trùng với từng điểm đang chỉnh. Trong Controller Edit Mode, lớp overlay phụ
  tắt để không chồng lên wire/vertex display thật của Blender. Các lệnh hiếm như Reveal All, Hide Whole, tùy
  chọn hiển thị nằm trong menu ⋮; không thêm menu nhiều tầng.
- Remove DANP Form khác −: Remove gỡ thiết lập addon; − chỉ bỏ một definition và
  giữ phần overlap thuộc definition khác. Cả hai thực hiện khi chọn model.

## Hành vi các thao tác

| Thao tác | Kết quả |
| --- | --- |
| Click tên/dòng | Highlight đường ngay; trong Edit Mode tự chọn điểm/cạnh tương ứng, Object Mode giữ mode/object |
| Nhấn đúp tên | Sửa tên trực tiếp tại dòng, Enter xác nhận, Escape hủy; không mở dialog UUID |
| + trong Source Edit Mode | Tạo định nghĩa mới từ Source selection, chọn dòng mới |
| − | Xóa định nghĩa active; giữ phần chung, Source topology và tọa độ |
| Sync trong Source Edit Mode | Thay membership của định nghĩa active bằng Source selection |
| ↑ / ↓ | Di chuyển định nghĩa active một dòng; giữ UUID và active item |
| Select trong menu | Chọn lại phần tương ứng khi cần; không dùng nút Select thường trực |
| Edit Control | Vào controller Edit Mode, chọn phần effective của đường active; khóa khi không còn control bật |
| Back to Model | Trở về Source và mode Object/Edit trước khi sửa control |
| Hide/Show Controls | Canonical Hide/Reveal toàn bộ; mọi con mắt đều Hidden/On, giữ object/mode; Show gồm cả phần đã ẩn riêng |
| Shift + Select | Thêm phần tương ứng vào selection hiện có |
| Con mắt | DANP Form Hide/Reveal toàn định nghĩa, theo trạng thái effective hiện tại |

Select mặc định thay selection trên mesh active. Face selection cũ không được để
lại khiến cả vùng bị chọn ngoài ý muốn; không sửa selection của mesh edit khác.
Điểm, cạnh, loop, tập rời và network đều là selection hợp lệ; không thêm loại role
front/side hay tính năng group mới.

**Sync ở đây là cập nhật nội dung đường**, không phải kéo tọa độ về template hay
chép vị trí proxy vào Source. Ví dụ đường A có cạnh 1–2–3: chọn 1–2–3–4 trên Source,
chọn dòng A trước, chỉnh selection thành 1–2–3–4 rồi Sync sẽ mở rộng A thành 1–2–3–4.
Chọn dòng sẽ tự chọn cả đường A trong Edit Mode. Selection rỗng khiến +/Sync bị khóa,
không xóa nội dung đường ngầm.

Sync giữ control UUID, tên và thứ tự. Recompute union từ tất cả definitions: phần
bỏ khỏi A vẫn tồn tại nếu B dùng; prune masks chỉ cho IDs không còn định nghĩa nào
dùng. Giữ masks của phần overlap còn tồn tại, không tự Reveal. Phần mới dùng vị trí
Source hiện tại và canonical masks đang có. Nếu membership không đổi thì là no-op.
Các lệnh cấu trúc validate trước ghi; lỗi không để metadata/proxy thay đổi dở dang.

Rename và reorder chỉ là metadata UX, không đổi masks, effective network, topology
partition hoặc network revision dùng cho deformation. Lưu thứ tự trên Source; UUID
quyết định identity, index chỉ dùng cho UI. Sau khi −, active item chuyển sang dòng
kề hợp lệ; sau reorder vẫn giữ cùng UUID. Có undo/redo cho tạo, xóa, Sync, đổi tên,
đổi thứ tự và Hide/Reveal; đổi dòng active không tạo undo cấu trúc.

## Sidebar theo context

| Active object/mode | Hiển thị và thao tác |
| --- | --- |
| Source chưa khởi tạo | Init, Remove đỏ bị khóa; giữ object/mode sau tạo |
| Source Object Mode | Init/Remove, danh sách, mắt, −, menu, ↑/↓, Edit Control, Hide/Show Controls; + bị khóa; không hiện Sync |
| Source Edit Mode | Init/Remove, danh sách và toàn bộ thao tác; +/Sync đọc selection Source BMesh |
| Controller Object Mode | Danh sách, mắt, menu, ↑/↓, Back to Model, Edit Control, Hide/Show; không +/−/Sync/Init/Remove |
| Controller Edit Mode | Danh sách tự chọn, mắt, menu, ↑/↓, Back to Model, Hide/Show; không +/−/Sync; chỉ chỉnh hình học hiện có |
| Mode khác, ví dụ Sculpt | Danh sách chỉ để đọc; khóa các thao tác ghi trạng thái để tránh ngắt workflow |
| Empty/unrelated object | Một dòng hướng dẫn chọn model/controller, không giữ danh sách model cũ |
| Binding lỗi/không chỉnh được | Một lý do ngắn; khóa thao tác, không đoán Source theo tên |

Muốn tạo/xóa đường hoặc thay membership thì Back to Model và dùng selection Source.
Controller không cho thêm/xóa vertex, edge hay face. Phím topology thường dùng bị
chặn theo context; lệnh menu/tool/MCP làm đổi IDs/connectivity được khôi phục về
topology và pose hợp lệ gần nhất, giữ Edit Mode và không ghi Source. Không bật
model Edit Mode ngầm khi click dòng. Modeling trên mesh thường vẫn hoạt động.

Các nút phụ thuộc selection/active definition: −/Sync/↑/↓ không có dòng active thì
khóa; ↑/↓ ở đầu/cuối khóa tương ứng. Source binding phải revalidate ở execute.
Multi-selection lấy active object làm context; multi-object Edit chỉ xử lý active
mesh. Mỗi Source nhớ active control UUID riêng để chuyển model không chọn nhầm dòng.

## Con mắt và overlap

On dùng mắt mở, Hidden dùng mắt đóng; Partial dùng mắt với dấu trạng thái phụ kín
đáo và tooltip “Một phần đường đang ẩn”. Không hiện ba nhãn trạng thái thành cột.
On click → Hide Whole; Hidden/Partial click → Reveal Whole. Menu vẫn có Hide Whole
cho dòng Partial. Đây là canonical masks chung, không phải cờ bật riêng mỗi dòng.

Ví dụ A và B cùng chứa cạnh 2–3: ẩn A có thể làm B thành Partial; xóa A vẫn giữ
cạnh 2–3 nếu B dùng. Whole edge Hide giữ junction được đường khác hỗ trợ; điểm rời
dùng node intent. Reveal chọn vị trí Source hiện tại. Mắt khác object/collection
visibility; display overlay không thay masks hoặc hiệu lực đường control.

## Cách triển khai và test

| Task | Kết quả | Test trước bàn giao |
| --- | --- | --- |
| NL2.1 — Backing list | Projection UIList theo Source, active UUID, rename/order | Chuyển model, tên trùng, rename cancel, reorder/save metadata, undo/redo; panel draw chỉ đọc |
| NL2.2 — +/−/Sync | Primitive chung trên Source; controller chỉ chỉnh | Source Edit, controller rejection, selection rỗng, overlap, prune masks, no-op/lỗi không ghi dở |
| NL2.3 — Panel native | Danh sách cuộn, cột icon, Select/Sync theo mode, menu gọn | Sidebar hẹp tên ưu tiên; 0/1/20 đường; thao tác chuột/đúp tên; không lặp nút mỗi dòng |
| NL2.4 — Bàn giao | Overlay/highlight và regression, package, báo cáo | CUA workflow thật; MCP assertions IDs/masks/geometry/context; install/reload; commit sau test đạt |

UIList và selection cache là projection của dữ liệu Source, không tạo nguồn metadata
thứ hai. Chọn CollectionProperty runtime hoặc migration storage theo nhu cầu triển
khai, giữ tương thích JSON definitions hiện có và tránh ghi Source trong draw.
UI callbacks và operator dùng chung primitives undo-safe; cache làm mới sau load,
undo/redo, change context và definition edits. Không tái dùng index thuộc Source cũ.

Test runtime theo hướng dẫn workspace, trên tiến trình và file Blender đang mở;
không chạy Blender riêng. Bảo toàn dữ liệu/selection và không lưu đè phiên dirty.
Test save/reopen cần bản sao an toàn và bảo toàn phiên; thiếu bằng chứng ghi NOT RUN.
Báo cáo live UX cũ không chứng minh native list mới đã đạt. Chỉ chuyển Phase 3 sau
Gate P2 và P2-UX, bao gồm các tiêu chí native list này.

Checklist: [Native list UX tasks](../../tasks/phase-02-native-list-ux.md).
