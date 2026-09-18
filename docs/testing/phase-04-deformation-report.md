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

## Giới hạn còn lại

Fit hiện nhận các mốc/target từ facade số; chưa tự đọc toàn bộ silhouette ảnh thành
target tự động. Modal chuột G/R/S
đầy đủ và rotation/scale pivot UI sẽ được hoàn thiện sau khi baseline này được
review trên các fixture limb hai loop và các trường hợp junction/ẩn-reveal.
