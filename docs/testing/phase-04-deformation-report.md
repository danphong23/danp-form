# Phase 4 — Báo cáo biến dạng và fit tham chiếu

## Phạm vi

Phase 4 bổ sung primitive transaction dùng chung cho thao tác controller:
capture Operation Rest, resolve vertex/edge selection, preview từ cùng P0,
proportional theo khoảng cách trên graph của patch, commit và cancel. Control
đang bật nhưng không chọn vẫn là ràng buộc đứng yên; target đã chọn được ghi
chính xác vào Source rồi đồng bộ lại controller.

Candidate hiện có gồm `LINEAR`, `SMOOTH`, `UNIFORM` và Whole Patch khi radius
bằng 0. Đây là baseline có thể thay thế; chưa đóng băng solver nâng cao.

## Kiểm tra trực tiếp

File đang mở: `Project/2. toon/girl_chibi_1.blend`, Blender 5.2.1 LTS,
MCP kết nối đúng phiên. File đã dirty từ trước; không lưu đè.

- Chọn `Arm.Shoulder.L`: 8 vertex control được chọn, transaction scope 203
  vertex; preview Smooth radius 4 làm đổi 56 vertex.
- Target control đạt đúng vị trí (`max error < 1e-6`). Cancel khôi phục chính xác
  toàn bộ Source (`restored_exact = true`).
- Fit front không chỉ scale một chiều: dùng ảnh `REF_BASE_FRONT` (896×1200),
  chuyển viewport sang Front Orthographic và chỉnh theo silhouette nhìn thấy.
  - `Front.Outline.All`: khớp khung ngang ảnh, 494 vertex nhận target chính xác;
    1,348 vertex trong scope được nội suy.
  - 16 control vai, khuỷu, cẳng tay, cổ tay và bàn tay: đưa đường tay lên đúng
    mốc ngang trong ảnh với delta world Z khoảng 0.58; 370 vertex nhận target,
    869 vertex trong patch scope thay đổi.
  - 19 control thân, hông, đùi, gối, bắp chân, cổ chân và bàn chân: mở rộng
    silhouette ngang theo ảnh với hệ số 1.12; 248 vertex nhận target,
    611 vertex trong patch scope thay đổi.
  Cả ba nhóm đều có `max_target_error = 0` trong Source local space. Screenshot
  Front Orthographic sau thao tác cho thấy tay, thân và chân chồng lên silhouette
  ảnh; trạng thái cuối là `Front reference silhouette fit applied`.

- Kiểm tra lại theo đúng quy trình fit thủ công bằng ẩn/hiện control trên file đang
  mở. Trước mỗi bước, toàn bộ control được ẩn rồi chỉ bật nhóm cần chỉnh, đi từ
  đầu xuống chân:
  - Bật nhóm đầu (`Head.*`, outline đầu/tai): 139 effective vertices, 772 edge
    của controller vẫn ẩn.
  - Bật thêm cổ, ngực, hai vai và tay: 632 effective edges, còn 292 edge ẩn.
  - Bật tiếp eo, hông, chân và bàn chân: toàn bộ 924 edge cần dùng hiện lên.
  Sau mỗi bước, viewport được kiểm tra ở Front Orthographic với
  `REF_FRONT_CENTERED`; cuối bước front các control được hiện lại đầy đủ.
- Kiểm tra side được thực hiện riêng: ẩn ảnh front, hiện `REF_SIDE_CENTERED`,
  chuyển sang Right Orthographic rồi chỉnh lần lượt đầu, thân và phần chân.
  Nhóm đầu dùng 139/139 vertex control đúng (không lẫn selection cũ), đổi 389
  vertex trong scope; nhóm thân chọn 42 vertex và đổi 250 vertex; nhóm chân chọn
  108 vertex và đổi 272 vertex. Các transaction đều báo
  `max_target_error = 0` trong Source local space.
- Có một lỗi trong lần thử đầu của bài test side: edge selection cũ còn giữ sau
  khi rebuild proxy nên resolver nhận toàn bộ controller. Test harness đã phát
  hiện, hoàn tác phép scale Y thử nghiệm và chạy lại sau khi clear cả vertex lẫn
  edge selection. Đây là điều kiện bắt buộc của quy trình test chọn control, không
  phải target fit mới.
- Kết thúc kiểm tra: viewport quay lại Front Orthographic, ảnh front hiện, ảnh
  side ẩn, tất cả control hiện (`hidden_edges = 0`), Source đang ở Object Mode và
  scene hiển thị trạng thái `Reference fit complete: front and side checked`.
  File vẫn dirty và không được lưu đè.

## Hiệu chỉnh lại sau kiểm tra người dùng

Báo cáo trước đã kết luận quá sớm vì chỉ kiểm tra trạng thái transaction và dùng
viewport perspective, trong đó mesh đặc che phần lớn ảnh. Kiểm tra lại trên cùng
file đã chuyển sang Front/Right Orthographic, đặt Source thành wireframe và tăng
độ rõ ảnh để so silhouette trực tiếp.

- Front: thu đầu theo nhóm `Head.*` và outline đầu/tai; chỉnh lại bề rộng nhóm
  cổ, ngực, eo, hông; kéo dài và mở bề rộng hai chân; chỉnh nhẹ hai tay và bàn
  tay. Các phép này đi qua `dan_form.deform`, lần lượt tác động 389, 357, 72,
  365 và 828 vertex theo scope transaction.
- Side: ẩn ảnh front, hiện ảnh side, thu chiều sâu đầu; mở chiều sâu chân và
  bàn chân; phần hông được nới theo profile side. Các phép vẫn dùng control
  tương ứng và giữ controller đồng bộ với Source.
- Ảnh overlay cuối cho thấy viền đầu, hai tay, thân, hông, chân và bàn chân đã
  nằm cùng vùng silhouette tham chiếu ở cả hai hướng. Trạng thái scene cuối là
  `Reference fit applied: front and side silhouette checked`; Source vẫn ở
  wireframe để người dùng tiếp tục quan sát, controller đang được chọn, toàn bộ
  924 control edge hiện.

Đây là fit thủ công có kiểm soát theo các nhóm control và landmark ảnh, chưa phải
solver tự động suy ra toàn bộ target từ pixel ảnh.

## Giới hạn còn lại

Fit hiện nhận các mốc/target từ facade số; chưa tự đọc toàn bộ silhouette ảnh thành
target tự động. Modal chuột G/R/S
đầy đủ và rotation/scale pivot UI sẽ được hoàn thiện sau khi baseline này được
review trên các fixture limb hai loop và các trường hợp junction/ẩn-reveal.
