# Kế hoạch nâng cấp DANP Form: Source là hình học duy nhất

**Trạng thái:** Đang hoàn thiện semantics selection-intent và moved-target, 2026-09-23. Người dùng đã xác nhận kiến trúc Source-backed, overlap-safe control và quy tắc giữ lại vùng selection khi một số điểm không đổi trong Scale.

### Tiến độ giai đoạn 1–4

- **Giai đoạn 1:** Đã sửa handoff khi đổi selection giữa hai native G/R/S, lưu nhiều bản ghi Undo/Redo và xử lý confirm/cancel theo tập target của phiên cũ. Ranh giới kết thúc đọc `Window.modal_operators`; không còn commit theo số nhịp yên lặng.
- **Giai đoạn 2:** Đã gom invalidation runtime cho proxy, overlay, patch và face cache ở Undo/Redo/load; Source edit vẫn là đầu vào để đồng bộ proxy. Cần tiếp tục kiểm tra modifier evaluated cage và chuỗi thao tác UI đầy đủ.
- **Giai đoạn 3:** Đã kiểm chứng Box Select native của Blender trên Controller Edit. Vì Controller là loose wire mesh không có face, chọn cả phần sau là hành vi native hợp lệ; không override phím `B`. Click/Pick riêng của DANP vẫn giữ chính sách Source occlusion.
- **Giai đoạn 4:** Đã chuyển trạng thái hide/enabled sang từng ControlDefinition, thêm migration schema 2 → 3 và giữ union hiệu dụng khi control chồng lấn. Hide/delete một definition không xóa phần Source mà definition khác còn giữ.

Các mục trên là phần triển khai có kiểm chứng bước đầu, chưa phải cổng nghiệm thu cuối của toàn bộ ma trận test ở cuối tài liệu.

## 1. Mục tiêu và phạm vi

Giữ bố cục sidebar, các thao tác quen thuộc và Edit Mode của Blender. Làm sạch quyền sở hữu dữ liệu và luồng thao tác để:

1. Source Mesh giữ topology, ID và tọa độ duy nhất. Controller là input proxy có thể dựng lại; overlay là hiển thị dẫn xuất.
2. Mục trong danh sách là tập membership Source vertex/edge và phím chọn nhanh. Tên, thứ tự, số mục trùng nhau không ảnh hưởng lời giải.
3. Mạng hiệu dụng là hợp phần hình học của các mục đang bật. Ẩn/xóa một mục chỉ bỏ phần mục đó đóng góp; phần trùng do mục khác giữ vẫn tồn tại. Không bao giờ xóa Source vertex/edge chỉ vì xóa control.
4. Mỗi thao tác giữ riêng `selection_intent` lúc bắt đầu và `moved_targets` đo từ tọa độ Controller. Hợp hai tập là biên đang biến đổi; điểm đã chọn nhưng tình cờ không đổi vẫn ở phía này với target P0. Vertex control ngoài hợp hai tập là mốc đứng yên. Patch bắt nguồn từ topology và các cạnh đang bật, không từ tên mục.
5. G/R/S có điểm bắt đầu, confirm và cancel rõ ràng; một thao tác tạo một bước Undo. Không suy đoán confirm bằng timer.
6. Click/Pick của DANP áp dụng chính sách che khuất theo Source; Box Select giữ hành vi native của Blender khi Controller không có face.
7. Giữ chất lượng biến dạng bề mặt hiện người dùng thấy ổn, nhưng chỉ chốt thuật toán số sau kiểm chứng hình học, proportional và hiệu năng.

Ngoài phạm vi đợt này: sparse control, tự khớp ảnh, solver nâng cao khi chưa có fixture thất bại, và thay đổi topology Source tự động.

**Nguyên tắc bảo toàn:** Controller hiện đã dùng Edit Mode thật của Blender cho chọn vertex/edge và G/R/S; Source hiện đã biến dạng hợp lý trong nhiều ca một điểm, nhiều điểm và vùng chọn rời nhau. Ghi lại kết quả những ca này trước khi sửa. Ưu tiên sửa phiên transform liên tiếp, Box Select và đồng bộ undo/overlay bằng thay đổi nhỏ có kiểm chứng. Không viết lại bộ giải hoặc thay toàn bộ tương tác Edit Mode chỉ vì cấu trúc mã hiện tại phức tạp. Mọi thay đổi core phải chứng minh bất biến mới và không thoái lui các ca đang chạy tốt.

### Hiện trạng mã và phần cần nâng cấp

| Khu vực hiện tại | Bằng chứng trong mã | Nâng cấp cần làm |
| --- | --- | --- |
| G/R/S và phiên thao tác | `registration.py` để G/R/S native; `lifecycle.py` quan sát depsgraph và trạng thái modal thật; `transform_session.py` giữ `last_targets` và cờ `had_delta`. | Chỉ có một chủ sở hữu Begin/Preview/Confirm/Cancel. Kết thúc phiên trước khi selection mới được dùng; phép kiểm tra delta dựa trên đúng tập ID; không dùng timeout để đoán confirm. |
| Undo/Redo | `NATIVE_UNDO_RECORDS` là dict theo Source pointer, mỗi commit thay bản ghi trước; handler sửa lại Source sau Undo/Redo bằng timer. | Thiết kế lịch sử nhiều bước gắn với chính Undo của Blender, kiểm chứng không ghi đè trạng thái cũ; invalidation và resync theo thứ tự rõ ràng. Không xóa cơ chế cũ trước khi thay thế qua test live. |
| Control, hide và overlap | `storage.py` lưu JSON definitions nhưng `HIDDEN_VIDS_KEY`/`HIDDEN_EIDS_KEY` là mask chung; `workflows.py` hide một mục bằng cách ghi vào mask chung. | Tách membership và trạng thái ẩn của từng định nghĩa; effective network là hợp các phần đang bật. Xóa/ẩn A không lấy đi phần B còn giữ; migration từ mask chung phải giữ hình dạng cũ lúc mở file. |
| Patch và biến dạng | Core nhận measured targets và stationary set, nhưng trước đây không nhận selection intent riêng. | Giữ selection intent và moved targets riêng; đo Scale X/Y/Z khi điểm trên trục không đổi, Proportional, nhiều control neo và control chồng lấn. Không đổi phương pháp nội suy ngoài khác biệt phát sinh từ biên patch. |
| Source, proxy, overlay | `proxy.py` đồng bộ tọa độ theo Source ID; `overlay.py` vẽ từ Source khi active Source nhưng đọc proxy trực tiếp khi active Controller; cache overlay dùng nhiều token và callback lỗi bị nuốt. | Ngoài phiên transform, proxy và overlay phải hội tụ về Source. Trong lúc kéo, pose Controller và selection ban đầu là input; Source là hình học được ghi. Tập trung quy tắc invalidation cho Source edit, mode switch, hide, undo/redo, modifier, load; báo lỗi kiểm chứng thay vì để overlay lệch âm thầm. |
| Chọn và X-Ray | Click/pick có `_pick_point_visible` kiểm tra Source che khuất; `Box Select` native của Blender chỉ xét geometry của Controller. Controller không có face nên không có occluder nội bộ. | Giữ native Box Select làm mặc định; chỉ thêm công cụ chọn theo Source nếu sau này người dùng yêu cầu một chế độ riêng. Không thay đổi Edit Mode chuẩn. |
| Ranh giới module | `operators.py` khoảng 1.768 dòng gồm model mutation, pick, transform macro cũ, keymap và panel; `__init__.py` export nhiều tên private; `bind(api)` chép tên vào global của các module. | Tách theo nghiệp vụ thực và dependency tường minh, đặt registration/handler/keymap ở một nơi, bỏ alias và code chết sau khi test thay thế. Tránh tạo cây thư mục mới chỉ để chuyển vị trí mã. |
| Dữ liệu và lỗi | `json_get` trả mặc định nếu JSON hỏng; `source_uuid` gán schema hiện tại; nhiều handler bắt lỗi rồi bỏ qua để không làm Blender crash. | Schema có validate/migration rõ; không mặc định dữ liệu hỏng là danh sách rỗng rồi ghi lại. Handler vẫn an toàn với Blender nhưng lưu lỗi có thể chẩn đoán và dừng trước khi ghi sai Source. |
| Kiểm thử | Có test core/static và nhiều script live; kết quả hiện hữu chưa thay thế được chuỗi thao tác của người dùng, nhiều bước Undo và modifier. | Chụp fixture Source theo ID trước/sau, kiểm tra G/R/S liên tiếp, box mặt sau, overlay sau Undo/Redo và overlap; đo full path trước/sau dọn. |

Các dòng trên là đánh giá mã hiện tại, không khẳng định mọi rủi ro đã xảy ra trong UI. Lỗi reset khi đổi vùng chọn, Box Select lấy mặt sau và overlay đôi lúc lệch là quan sát của người dùng; các rủi ro khác cần fixture để xác nhận mức ảnh hưởng.

## 2. Các bất biến không được phá

| Mã | Bất biến | Cách kiểm chứng |
| --- | --- | --- |
| I1 | Ngoài phiên G/R/S, mọi vertex proxy ánh xạ đúng tọa độ Source theo ID | So sánh toàn bộ ID sau edit, hide, undo, load |
| I2 | Overlay lấy tọa độ Source hiện tại hoặc hình học hiển thị được đánh giá từ Source | Đối chiếu vị trí đường với mesh ở Object/Edit và modifier cage |
| I3 | Trong phiên G/R/S, biên biến đổi là selection-intent hợp measured moved-targets; các điểm được chọn nhưng không đổi vẫn nhận P0; control ngoài biên giữ đúng P0 | Kiểm tra tọa độ từng ID, kể cả junction, proportional và phần trùng |
| I4 | Cùng Source, mạng hiệu dụng, selection-intent, moved-targets và thiết lập cho cùng output dù đổi tên/thứ tự/thêm mục trùng | Fixture bất biến theo membership |
| I5 | Mỗi preview tính từ cùng `P0` là Source ở đầu thao tác; không tích lũy preview | Kéo qua lại, target trở về `P0`, thu radius |
| I6 | Không ghi vertex ngoài union patch liên quan đã chụp | So sánh từng ID ngoài scope |
| I7 | Ẩn/xóa mục A không loại phần vẫn do B giữ; Reveal lấy vị trí Source hiện tại | Fixture trùng node/cạnh và save/load |
| I8 | Confirm/cancel/undo/redo không để phiên, proxy hay overlay ở trạng thái cũ | Hai G/R/S liên tiếp và nhiều bước Undo/Redo |
| I9 | Box Select native tuân theo quy tắc visibility của chính Controller; Source occlusion chỉ áp dụng cho click/Pick của DANP | Perspective/orthographic, loose edge Controller và X-Ray |
| I10 | Kết quả agent và UI đi qua cùng target và solver | So sánh buffer theo ID |

`P0` là Source hiện tại khi bắt đầu thao tác. Template ban đầu, nếu sau này cần để đo sai lệch, chỉ là tham chiếu chẩn đoán; không tự kéo mesh về dáng cũ.

## 3. UI giữ lại và chỉnh hành vi

| UI hiện có | Hành vi sau nâng cấp |
| --- | --- |
| `Init DANP Form`, `Remove DANP Form` | Giữ vị trí. Init gắn Source và tạo proxy; Remove tháo dữ liệu add-on theo xác nhận riêng, không tự xóa Source geometry. |
| `Edit Control`, `Back to Model` | Giữ vị trí, mode và selection được khôi phục theo ID. Rời Edit Control khi đang G/R/S chỉ được sau confirm/cancel rõ ràng. |
| `Hide Controls` / `Show Controls` | Bật/tắt tất cả định nghĩa; đây là thay đổi mạng hiệu dụng, không phải công tắc vẽ. Tooltip/status nói rõ. Trạng thái ẩn một phần của từng mục được giữ khi bật lại hàng loạt. |
| `Overlay`, `Patches`, `Preview Hidden` | Chỉ thay đổi hiển thị. Preview Hidden không làm phần ẩn chọn được hoặc trở lại làm ràng buộc. |
| `X-Ray` | Điều khiển hiển thị, click/Pick của DANP và các công cụ có policy riêng; Box Select native vẫn theo Blender. |
| Bộ Pick/Clear/All Controls/Add to Selection | Bỏ khỏi sidebar và keymap. Controller Edit dùng trực tiếp Box/Circle/Lasso/click/Shift/Ctrl native của Blender; UIList vẫn là lối tắt chọn control. |
| UIList: hàng, mắt, đổi tên, `+`, `−`, lên/xuống, `Sync` | Giữ giao diện. Click hàng chọn membership đang bật; mắt bật/tắt đóng góp của mục; `+` và Sync chỉ trong Source Edit; `−` xóa định nghĩa và phần chỉ nó giữ khỏi proxy; lên/xuống và đổi tên không đổi hình học. |
| `Profile`, `Radius` | Giữ trong nhóm G/R/S. `Radius = 0` hiển thị rõ là ảnh hưởng toàn patch; Profile mờ đi khi không có tác dụng. Chưa đổi mặc định trước khi so sánh chất lượng. |

Trạng thái mắt của một mục: **On** (toàn bộ membership có hiệu lực), **Partial** (một phần đang ẩn), **Hidden** (mục tắt hoặc không còn phần hiệu lực). Bấm mắt ở mục đang Partial tắt mục; bấm lần nữa khôi phục đúng trạng thái Partial trước đó. `Alt-H` hiện lại các phần đã ẩn; `Show Controls` chỉ bật các mục, không tự xóa trạng thái ẩn một phần.

Đề xuất giữ `H` trong Controller Edit để ẩn **membership được chọn thuộc mục active trong danh sách**; phần trùng do mục khác giữ vẫn hiệu lực. Nếu vùng chọn không thuộc mục active, lệnh không làm gì và nêu rõ lý do. Đây là quy tắc UX cần xác nhận khi thử live, vì hiện tại H sử dụng mask chung cho mọi mục.

Trong lúc transform, các thao tác sửa định nghĩa, mắt, Sync, H/Alt-H và dựng lại proxy bị khóa với thông báo ngắn; không âm thầm đổi selection hoặc Source.

## 4. Dữ liệu lưu và mạng hiệu dụng

Source giữ persistent ID của vertex/edge và một schema có phiên bản. Mỗi `ControlDefinition` lưu `uuid`, tên, tập vertex/edge ID, `enabled`, và tập ID ẩn một phần **trong chính định nghĩa đó**. Không lưu tọa độ control. UIList active row và selection là trạng thái tương tác, không là nguồn hình học.

```
effective_edges = hợp cạnh đang bật của mọi định nghĩa
effective_vertices = các đầu mút effective_edges
                   ∪ các điểm đứng riêng đang bật
```

Một node ẩn trong một định nghĩa làm các cạnh của định nghĩa đó tại node mất hiệu lực; định nghĩa khác vẫn có thể giữ node/cạnh ấy. Hiding toàn bộ mục không xóa partial masks; Reveal dùng tọa độ Source mới. Xóa mục bỏ record rồi tính lại hợp tập, không can thiệp mesh Source. Dựng lại proxy chỉ dùng Source ID, Source tọa độ và mạng hiệu dụng; selection cũ được giữ theo giao các ID còn tồn tại. Không giữ pose proxy cũ như nguồn tọa độ thay thế.

### Di chuyển dữ liệu cũ

Schema hiện tại dùng mask vertex/edge chung trên Source. Khi nâng schema:

1. Đọc file cũ một lần, kiểm tra ID và topology trước khi chuyển.
2. Chiếu mỗi ID đang bị mask chung vào mọi định nghĩa chứa ID đó. Nhờ vậy trạng thái nhìn thấy ngay sau mở file vẫn giống bản cũ, kể cả phần trùng.
3. Tạo `enabled` và partial masks theo từng định nghĩa; kiểm tra mạng hiệu dụng trước/sau migration bằng ID.
4. Lưu schema mới chỉ sau khi qua kiểm tra. Nếu lỗi, không sửa Source; báo lỗi kèm ID để phục hồi.
5. Runtime chỉ dùng schema mới. Adapter migration được cô lập; không duy trì hai luồng solver, hai loại mask hoặc fallback âm thầm.

Thử migration trên **bản sao** `.blend`, gồm file hiện tại có 26 định nghĩa và phần hình học trùng. Không ghi đè bản autosave hoặc dữ liệu đang dirty của người dùng trong quá trình phát triển.

## 5. Core: selection, patch và biến dạng

### Selection

Selection chuẩn là tập Source ID lấy từ Controller Edit BMesh. Click/Pick của DANP lọc theo bề mặt Source khi X-Ray tắt; Box Select, Circle và Lasso giữ quy tắc native của Blender đối với geometry Controller. Giữ thao tác Shift thêm, Ctrl bỏ, góc nhìn perspective/orthographic và vertex/edge mode của Blender.

### Patch

Tính các thành phần mặt liên thông khi không đi xuyên qua effective control edges. Đường hở không tách mặt thì không được giả tạo patch mới. `S` và `U` là điều kiện biên trong các patch liên quan; chúng không tạo thêm loại control hay trọng số theo tên. Scope chụp ở đầu thao tác là hợp patch chạm `S`; không ghi ra ngoài scope.

### Solver

Đầu vào thuần dữ liệu: topology/patch, `P0`, `S`, `U`, target tuyệt đối `Q`, proportional settings. Đầu ra: tọa độ mới theo Source ID trong scope và thống kê. Ràng buộc cứng: `output[S]=Q`, `output[U]=P0[U]`, ngoài scope không đổi; no-op trả `P0` chính xác. Junction chung được giải một lần theo Source ID.

Trước tiên đo và giữ output của solver hiện tại với các fixture một điểm, nhiều điểm, vòng, hai vùng rời nhau, junction, G/R/S và patch có một/nhiều biên. Chỉ sửa phần phụ thuộc số lượng/định nghĩa `control_uuid` bằng thay đổi nhỏ nhất đáp ứng bất biến I4; kiểm tra kết quả với fixture thêm mục trùng. Nếu việc tách khỏi định nghĩa không thể thực hiện mà vẫn giữ chất lượng, lúc đó thử ứng viên transform field từ **nhóm liên thông hình học của selection trên mạng hiệu dụng**. Solver nằm sau cùng một hợp đồng dữ liệu để có thể thay mà không đổi UI/transaction; không mở rộng solver chỉ vì muốn tái cấu trúc mã.

Proportional chỉ tác động lên vertex tự do trong patch, một lần. `Radius = 0` trước mắt giữ hành vi toàn patch hiện dùng. Các profile/radius khác có bảng so sánh hình dạng và hiệu năng trước khi quyết định mặc định cuối.

## 6. Một chủ sở hữu cho G/R/S và Undo

Trạng thái tối thiểu: `IDLE → ACTIVE → COMMITTED` hoặc `IDLE → ACTIVE → CANCELLED`. Một Source chỉ có một phiên ACTIVE. Đầu phiên chụp Source UUID, topology/network/proxy generation, object transform, `P0`, `S/U`, scope và proxy selection. Không tạo P0 mới giữa các preview.

Mỗi sự kiện kéo đọc target tuyệt đối của `S`, kiểm tra finite/ID/generation, giải từ P0 và ghi preview Source. Controller lúc đang kéo là input tạm; sau confirm/cancel nó đồng bộ từ Source. Confirm/cancel lấy từ sự kiện của chính transform đang chạy. Lỗi trước ghi không đổi Source; lỗi có preview hợp lệ nhưng phải hủy thì phục hồi P0. Đổi mode/selection/định nghĩa giữa phiên bị chặn hoặc kết thúc phiên tường minh.

Trước khi viết lại, làm một thử nghiệm nhỏ trên Blender 5.1/5.2 để chọn **một** cơ chế sở hữu native G/R/S có thể bắt đúng Begin, Confirm, Cancel và một bước Undo. Có thể dùng macro/wrapper nếu thử nghiệm chứng minh đủ các sự kiện; không giữ observer và macro song song. Bỏ timeout 20 lần kiểm tra để commit, cờ `had_delta` suy từ tập target sai, và bản ghi undo runtime chỉ chứa một thao tác mỗi Source.

Undo/Redo nhiều bước phải khôi phục Source, định nghĩa/visibility, selection có thể khôi phục, proxy và overlay đúng thứ tự. Sau `undo_post`/`redo_post`, chỉ đánh dấu cache cũ vô hiệu và chạy resync trong context an toàn; không ghi edit BMesh bên trong handler. Lưu/mở file phải dựng lại proxy/caches từ Source, không lưu transaction runtime.

## 7. Đồng bộ và overlay

- Source Edit/Object coordinate change: đánh dấu tọa độ đã đổi; proxy cập nhật từ Source trong context an toàn. Object transform của Source được áp qua parenting/matrix đúng một lần.
- Proxy Edit ngoài phiên hợp lệ: không ghi ngược Source; resync hoặc báo lỗi. Trong phiên hợp lệ, chỉ `S` sinh target ngược.
- Overlay: lấy ID và tọa độ từ Source; đối với modifier/cage, dùng hình học hiển thị được đánh giá từ Source với mapping được kiểm tra. Nếu mapping không đáng tin, dùng fallback có cảnh báo thay vì vẽ một đường có vẻ chính xác nhưng lệch mesh.
- Cache partition chỉ phụ thuộc topology và mạng hiệu dụng. Cache vị trí/GPU phụ thuộc Source geometry, object transform, modifier và mode/selection phù hợp. Source edit, confirm/cancel, hide/reveal, undo/redo, load, duplicate và rebuild đều vô hiệu đúng cache rồi yêu cầu redraw.
- Draw callback chỉ vẽ; depsgraph handler chỉ phát hiện/đánh dấu thay đổi. Không chạy solver hay sửa geometry bên trong callback vẽ.

## 8. Ranh giới mã sau nâng cấp

```
model/          schema, ID, định nghĩa, migration, validation
core/network/   hợp membership, effective edges/vertices, patch topology
core/solve/     P0 + S/U/Q + patch -> tọa độ Source mới
blender/mesh/   đọc/ghi Mesh và Edit BMesh theo persistent ID
blender/proxy/  dựng và đồng bộ controller từ Source
interaction/    selection, depth policy, phiên G/R/S, Undo
ui/             sidebar hiện tại, overlay, thông báo trạng thái
agent/          chuyển lệnh thành cùng selection/target/operation
```

Đây là ranh giới trách nhiệm, không bắt buộc tạo đúng từng thư mục như sơ đồ. Dọn `operators.py` lớn thành nhóm chức năng; bỏ `bind(api)` sao chép toàn bộ tên private của facade, alias runtime dư, hai đường biến dạng và các nhánh compatibility chỉ còn phục vụ mã cũ. Các ngưỡng số, pixel tolerance và đơn vị radius phải có tên, lý do và test; không nhánh theo tên nhân vật/scene/control.

## 9. Thứ tự thực hiện và cổng nghiệm thu

| Chặng | Việc làm | Bàn giao / điều kiện qua |
| --- | --- | --- |
| 0. Chốt hợp đồng | Ghi ADR mới thay quy tắc mask chung và ownership theo định nghĩa; cập nhật invariants, data model, selection, operation, acceptance gates. Chụp baseline file và UI hiện tại. | Tài liệu không còn hai quy tắc đối nghịch; có danh sách fixture và số liệu Source/proxy ban đầu. |
| 1. Phiên G/R/S | Tái hiện lỗi hai control liên tiếp; chọn một integration native; sửa lifecycle Begin/Preview/Confirm/Cancel và một bước Undo mà giữ nguyên selection và solver hiện có. | G/R/S một/nhiều/rời nhau giữ chất lượng cũ; chốt rồi chọn vùng khác ngay không reset; cancel và nhiều Undo/Redo đúng từng vertex. |
| 2. Đồng bộ/overlay | Source → proxy và Source → overlay; invalidation sau edit, undo/redo/load, modifier và mode. | Không có overlay/proxy lệch sau chuỗi thao tác; kiểm tra base và evaluated cage. |
| 3. Selection UX | Kiểm chứng và giữ native Box Select; không override vì Controller loose edge không có mặt. | Box Select hoạt động đúng theo Blender; click/Pick vẫn lọc Source khi policy DANP được dùng. |
| 4. Schema và mạng | Tạo per-definition membership/visibility, migration, effective union, overlap-safe delete/hide/reveal; proxy dựng từ Source. | Fixture trùng node/cạnh, partial hide, delete, save/load/undo; Source geometry không đổi khi sửa định nghĩa. |
| 5. Bất biến solver | Đo và giữ baseline hiện tại; bỏ phụ thuộc số mục trùng bằng thay đổi nhỏ nhất; sửa X/Y rotation và WORLD target conversion. Chỉ thay phương pháp nội suy nếu fixture cho thấy cần thiết. | I3–I7/I10, no-op, scope, G/R/S; thêm mục trùng không đổi output; chất lượng cũ được giữ. |
| 6. Proportional và tối ưu | Đo profile/radius, hình dạng và full-path latency; tối ưu cache/solver ở điểm có bằng chứng. | Chất lượng mặc định ít nhất không thoái lui; số đo median/P95, confirm, memory trên fixture nhỏ/lớn. |
| 7. Dọn và phát hành thử | Xóa runtime legacy, cập nhật docs/help, đóng gói extension, migration test trên bản sao, cài và test live. | Không còn hai đường nghiệp vụ; test sạch; gói cài được; báo cáo PASS/FAIL và giới hạn còn lại. |

Không cập nhật extension đang cài trong Blender ở giữa các chặng chưa qua gate. Làm trên nhánh/copy thử; chỉ đưa vào phiên đang dùng khi luồng liên quan đã qua test.

## 10. Ma trận kiểm thử bắt buộc

1. **Tập hợp/overlap:** A và B trùng node, trùng cạnh, giao nhau; ẩn A, xóa A, bật lại, partial H; phần B giữ không đổi.
2. **Tính độc lập danh sách:** đổi tên/thứ tự, tách một mục thành hai mục, thêm mục trùng; cùng mạng/S/U/Q cho cùng output.
3. **G/R/S nối tiếp:** G → LMB → chọn vùng khác → R/S/G ngay, không cần chờ; vùng trước không reset. Lặp với chọn từ list, click và Box Select.
4. **Cancel:** Esc/RMB trước và sau preview; Source/proxy về P0/C0, không tạo bước Undo có nghĩa.
5. **Undo/Redo:** ít nhất ba biến dạng liên tiếp, hide/reveal xen giữa, trở đi và trở lại từng bước; overlay/proxy khớp sau mỗi bước.
6. **Selection/X-Ray:** vertex trước/sau cùng vùng màn hình, perspective/orthographic, Box Select native trên loose Controller, Shift/Ctrl, vertex/edge mode; click/Pick kiểm tra Source occlusion.
7. **Source trực tiếp:** edit vertex Source ở Edit Mode, object transform, mode switch, save/reopen; proxy và overlay theo Source.
8. **Solver:** một vertex, span, loop, hai vùng chọn rời nhau, junction, patch một/nhiều biên, open chain, target no-op, radius đổi, ngoài scope giữ nguyên.
9. **Lỗi và dữ liệu:** topology đổi giữa phiên, ID thiếu/trùng, duplicate Source, hai Source cùng scene, xóa proxy và dựng lại, migration file cũ; lỗi chặn trước ghi.
10. **Agent parity và hiệu năng:** cùng target cho cùng Source output qua UI/agent; đo toàn bộ đường preview trên file thật 1698 Source vertex/264 proxy vertex và fixture lớn hơn.

Static tests hiện tại chỉ là kiểm tra bước đầu; các bài thử live phải xác nhận tọa độ theo ID, không chỉ chụp ảnh. Mỗi chặng có báo cáo Blender version, fixture, expected/actual, thay đổi file, PASS/FAIL/NOT RUN và lỗi còn lại.

## 11. Định nghĩa hoàn thành

Bản nâng cấp chỉ được coi là xong khi người dùng làm liên tục từ tạo control → chọn bằng click/box/list → G/R/S → hide/reveal/delete → sửa Source trực tiếp → Undo/Redo → save/reopen mà Source, proxy và overlay luôn khớp theo các bất biến trên; test live và migration qua; chất lượng patch mặc định không thoái lui; runtime chỉ còn một schema, một đường transform và một đường solver được dùng thật.
