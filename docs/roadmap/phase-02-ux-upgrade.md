# Phase 2 — Nâng cấp UX trước Phase 3

**Trạng thái: kế hoạch triển khai, 2026-09-18; chưa triển khai/test đợt nâng cấp.**

Đây là phần bổ sung của Phase 2, không tạo thêm phase chính. Hoàn thành Gate P2
và P2-UX trước khi chuyển sang hiển thị patch. Yêu cầu của người dùng là sidebar
theo model đang chọn, tạo đường liên tục trong Edit Mode, thấy đường rõ trên Source
và quản lý các đường bằng danh sách. Chi tiết bố cục dưới đây là đề xuất triển khai.

## Hiện trạng đã kiểm tra trong mã

Trong `dan_form/__init__.py`, panel và operator dùng `scene.dan_form_source` được
chọn thủ công. Make Control gọi chuyển Object Mode rồi chọn controller. Sidebar chỉ
hiện số control; chưa có danh sách, chọn nguyên định nghĩa, đổi tên hay xóa từng
định nghĩa. Controller dùng wire mặc định, chưa có lớp vẽ màu trên Source.

Định nghĩa đã có UUID và Source vertex/edge IDs; masks đang lưu chung trên Source.
Có thể dùng nền dữ liệu này, nhưng phải hoàn thiện thao tác Edit Mode, union overlap,
sync nhiều model và lifecycle trước khi coi nâng cấp UX là hoàn tất. Kiểm tra mã
không chứng minh các gate runtime đã pass.

## 1. Sidebar theo đối tượng đang thao tác

Một resolver dùng chung cho panel và operator xác định Source từ **active object**:

| Active object | Sidebar |
| --- | --- |
| Mesh chưa khởi tạo | Tên mesh và nút Initialize; chưa hiện quản lý control |
| Source đã khởi tạo | Danh sách và trạng thái của chính Source đó |
| Controller DAN Form | Resolve Source qua identity binding và parent; cùng danh sách như Source |
| Không chọn / object khác | Hướng dẫn ngắn chọn mesh hoặc controller; không giữ thao tác trên model cũ |
| Mapping thiếu, UUID trùng hoặc parent sai | Báo lỗi binding và hướng phục hồi; không đoán Source theo tên |

Nhiều object được chọn thì active object quyết định context. Trong multi-object Edit
Mode chỉ đọc selection của Source active; không sửa các mesh khác. Source không đủ
điều kiện chỉnh sửa có lý do cụ thể và nút thao tác bị khóa.

Không dùng dropdown Source làm luồng chính. Scene pointers cũ chỉ có thể là cache
tương thích, không phải nguồn quyết định context. Panel draw không tạo IDs, ghi
metadata hay rebuild. Các lệnh revalidate binding trước khi ghi; không dùng context
đã cache từ model trước. Sync phải theo dõi các Source có controller, kể cả khi người
dùng vừa chuyển sang model khác.

## 2. Tạo đường mà không ngắt thao tác modeling

Luồng chính: chọn Source → Edit Mode → chọn điểm/cạnh/dải/loop → **Make Control** →
đường được tô rõ và danh sách thêm một dòng → tiếp tục chọn đường kế tiếp ngay.

- Kết thúc thành công vẫn là Source active, Edit Mode, giữ selection và selection
  mode; không chọn controller thay người dùng. Lỗi cũng không làm mất context.
- Đọc IDs, topology và tọa độ từ BMesh đang edit; không ép Object Mode chỉ để đọc
  `mesh.data`. Cập nhật proxy khác object qua adapter an toàn.
- Validate toàn bộ trước khi ghi định nghĩa/masks. Lỗi rebuild không được để lại
  định nghĩa đã ghi một nửa hoặc metadata sai; phục hồi trạng thái nhất quán.
- Một lần tạo là một bước undo. Overlap một phần hoặc toàn bộ được phép: mỗi dòng
  có UUID riêng nhưng union proxy chỉ chứa một bản mỗi Source vertex/edge.
- Tạo đường trên vùng đang DAN Form-hidden giữ nguyên masks, không tự Reveal.
- Hide/Reveal/xóa trong Edit Mode cũng giữ object/mode khi object đó còn tồn tại.
  Khi rebuild proxy đang edit, khôi phục selection bằng Source IDs của phần còn
  hiệu lực, không dùng proxy indices cũ.

## 3. Danh sách control là công cụ quản lý selection

Mỗi dòng đại diện một định nghĩa người dùng tạo: tên có thể đổi, trạng thái,
**Select**, **Hide/Reveal**, **Delete**. Định danh lệnh là Source UUID + control UUID,
không phải tên hoặc vị trí dòng. Đổi tên chỉ đổi nhãn, không đổi network revision
hay masks. Tên mặc định không bị tái sử dụng gây nhầm sau khi xóa.

Click dòng chỉ chọn dòng quản lý, không ngầm đổi mode hay bật đường. Nút Select:

| Context | Hành vi Select |
| --- | --- |
| Source Edit Mode | Chọn đúng vertex/edge của định nghĩa trên Source, giữ Edit Mode |
| Controller Edit Mode | Chọn phần effective tương ứng trên proxy, giữ Edit Mode |
| Object Mode | Nút ghi rõ Edit Source & Select; vào Source Edit Mode và chọn định nghĩa |

Select mặc định thay selection trong mesh đang thao tác; tùy chọn Add to Selection
cho phép gom nhiều dòng. Không cần thêm hệ thống group hay multi-owner control.
Định nghĩa hidden vẫn chọn được trên Source để kiểm tra; trên proxy chỉ chọn phần
effective. Nếu phần đó rỗng, báo đường đang ẩn, không tự Reveal.

**Trạng thái dòng là kết quả hình học, không phải cờ on/off độc lập:**

- On: toàn bộ hình học định nghĩa đang effective.
- Partial: chỉ một phần đang effective.
- Hidden: không còn phần effective của định nghĩa.

Hiện số cạnh/điểm đang bật so với tổng khi cần giải thích Partial. Với Partial, hành
động chính là Reveal Whole; menu dòng vẫn có Hide Whole. Không dùng checkbox nhị
phân khiến người dùng hiểu nhầm mỗi dòng sở hữu trạng thái riêng.

Hide Whole dùng edge intent cho các thành phần có cạnh, node intent cho các thành
phần điểm độc lập. Một định nghĩa vừa có cạnh vừa có điểm rời phải giữ cả hai ý
định, không bỏ điểm rời chỉ vì danh sách edge không rỗng. Hide Selected cũng phân
biệt node intent với endpoint flags khi chọn cạnh. Reveal tuân canonical masks.

Ví dụ A chứa cạnh 1–2, 2–3; B chứa 2–3, 3–4:

- Hide A làm cạnh 2–3 ẩn chung; B hiển thị Partial nếu 3–4 còn bật. Vertex 3 còn
  được cạnh 3–4 hỗ trợ. Tooltip nói rõ thao tác ảnh hưởng phần trùng của dòng khác.
- Xóa A giữ cạnh 2–3, 3–4 của B; giữ masks trên phần còn định nghĩa. Chỉ xóa hình
  học proxy không còn được định nghĩa nào dùng, và prune masks tương ứng.
- Xóa B cuối cùng làm proxy rỗng; Source vẫn giữ nguyên mọi vertex, edge, face và
  tọa độ. Controller rỗng vẫn có thể nhận đường mới.

Delete từng dòng có undo; không cần hộp xác nhận cho từng lần xóa. Remove Controller
là thao tác khác, đặt trong Maintenance và ghi rõ định nghĩa Source vẫn được giữ.

## 4. Đường màu rõ trên Source

Ưu tiên lớp overlay vẽ union control trên Source, dùng màu tương phản dễ nhìn; dòng
đang chọn có highlight riêng. Không sơn vertex colors, thay material hoặc thêm edge
vào Source chỉ để hiển thị. Các đường overlap không vẽ nhiều lần chồng màu.

- Mặc định vẽ đường effective với độ dày dễ đọc, xử lý độ sâu để đường trên mặt
  mesh không nhấp nháy. Điểm độc lập có marker rõ.
- Đọc tọa độ BMesh khi Source Edit Mode; Object Mode đọc base mesh. Transform
  Source được áp dụng đúng một lần; màu/highlight không làm sai parenting proxy.
- Show Control Overlay chỉ bật/tắt hiển thị; **khác DAN Form Hide/Reveal**. X-Ray
  là tùy chọn hiển thị khi cần nhìn qua bề mặt.
- Có thể bật Show Hidden Controls để thấy phần hidden bằng kiểu đường/màu phụ,
  mặc định tắt. Hiển thị này không khôi phục ràng buộc hay cho chọn handle ẩn.
- Chỉ overlay cho context Source hiện tại. Cache đánh dấu dirty theo coordinates,
  topology, masks và selection; không rebuild network mỗi lần panel draw.
- Draw handlers/cache được dọn khi unregister, load và thay context; reload không
  tạo overlay kép. Nếu unsupported modifier làm base mesh khác hình nhìn thấy,
  thông báo giới hạn, không hứa bám evaluated surface khi chưa có mapping.

Đây là màu **đường control**, không phải màu các patch của Phase 3.

## 5. Bố cục sidebar đề xuất

```text
DAN Form
Model: girl chibi 1                 [Edit Source] [View Controller]

Controls
[Make Control from Selection]
State      Name                    Select   Hide/Reveal   Delete
On         Control 1                 ↗          …           ×
Partial    Control 2                 ↗          …           ×
Hidden     Control 3                 ↗          …           ×
[Hide Selected] [Reveal All]
Thông báo ngắn / hướng dẫn theo context

▸ Display       overlay, X-Ray, show hidden, màu/độ dày
▸ Maintenance   validate/sync/rebuild, remove controller
```

Mesh mới chỉ hiện Initialize và giải thích bước kế tiếp. Nút không dùng được có
tooltip chỉ cách tiếp tục: ví dụ Make Control yêu cầu chọn điểm/cạnh của Source
trong Edit Mode. Không hiện thuật ngữ solver, JSON IDs, schema hay generation trong
luồng chính. View Controller ở Phase 2 giải thích mới hỗ trợ xem/chọn, chưa có biến
dạng G/R/S lên Source. Thông báo thành công/lỗi phải thuộc Source hiện tại.

## Thứ tự triển khai và kiểm chứng

| Task | Kết quả | Test cần pass trước commit |
| --- | --- | --- |
| UX2.1 — Resolve context | Panel/operators/sync dùng binding nhất quán cho nhiều model | Chuyển Source A/controller A/Source B/controller B; mesh mới; empty; binding lỗi; không ghi nhầm model |
| UX2.2 — Edit Mode adapter | Make liên tục, structural actions giữ context, validation trước ghi | Tạo nhiều đường không thoát Edit; giữ selection; lỗi không ghi dở; Object/Edit sync; mixed point/edge |
| UX2.3 — Definition list | List, rename/select, Hide/Reveal, delete overlap-safe | Overlap một phần/toàn bộ; Partial; shared node; delete cuối; undo/redo; masks không tự bật |
| UX2.4 — Source overlay | Control/point dễ nhìn, highlight, display toggles | Front/side/perspective; live Source edits; translation/rotation/nonuniform scale; overlap không vẽ kép; hide khác display |
| UX2.5 — Hoàn thiện và regression | Sidebar gọn, bản cài và báo cáo P2/P2-UX | Chuỗi thao tác người dùng; install/reload; proxy rebuild; lifecycle; không rò handler; các gate P2 còn thiếu |

Tách phần resolver, Edit Mode adapter, definition actions và overlay khi cần; không
đổ thêm toàn bộ vào panel hoặc depsgraph handler. UI và lệnh gọi chung primitive
Source-backed để MCP sau này không cần đường logic riêng.

Các ca union/masks dùng assertions hành vi, không chỉ kiểm tra có tên hàm. Test
tích hợp/UI chạy **trên tiến trình Blender và file đang mở**, qua MCP hoặc Computer
Use theo hướng dẫn workspace; không mở tiến trình Blender riêng. Trước test đọc
scene hiện tại, dùng fixture tạm có phạm vi rõ và phục hồi sau test, không chạy
script dựng/xóa scene. Ghi Source coordinates/topology, mode/selection trước/sau.
Save/reopen chỉ kiểm tra bằng bản sao an toàn trong cùng tiến trình, sau khi có
cách bảo toàn phiên đang làm việc; không tự lưu đè file dirty. Nếu chưa thực hiện
được thì ghi NOT RUN và gate chưa pass.

Mỗi task bàn giao expected/actual, PASS/FAIL/NOT RUN, ảnh UI thích hợp và commit sau
khi các test liên quan pass. Task cuối đồng bộ phiên bản manifest/package, cài bản
ZIP và kiểm tra lại workflow. Không coi báo cáo Phase 2 trước đây là bằng chứng
tự động cho các ca mới hoặc các ca lifecycle chưa chạy.

Chi tiết task: [Phase 2 UX upgrade](../../tasks/phase-02-ux-upgrade.md).
Điều kiện sang Phase 3: [Gate P2-UX](../testing/acceptance-gates.md).
