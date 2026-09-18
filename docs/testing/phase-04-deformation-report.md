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
- Fit front bằng `Front.Outline.All` và ảnh `REF_BASE_FRONT` (896×1200). Chiều
  rộng ảnh quy đổi là 3.173333; control viền sau fit đạt 3.1733334, sai số dưới
  1e-6. 494 vertex control nhận target; 1,348 vertex trong scope được cập nhật
  theo patch. Trạng thái cuối là `Front reference fit applied`.

## Giới hạn còn lại

Fit hiện nhận target từ facade số; chưa tự đọc silhouette ảnh. Modal chuột G/R/S
đầy đủ và rotation/scale pivot UI sẽ được hoàn thiện sau khi baseline này được
review trên các fixture limb hai loop và các trường hợp junction/ẩn-reveal.
