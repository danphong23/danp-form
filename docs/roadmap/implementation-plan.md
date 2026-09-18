# Kế hoạch phát triển DANP Form

**Trạng thái: 5 phase đã thống nhất; đã có mã/bản cài Phase 1–2; bổ sung kế hoạch
nâng cấp UX Phase 2 trước Phase 3. Gate chỉ pass khi có bằng chứng test tương ứng.**

Mục tiêu là chỉnh model template qua các đường control nằm trên mesh thật. Các đường
đang bật chia patch và giữ phần không chọn đứng yên. Khi điều chỉnh control được chọn,
phần bên trong patch liên quan biến dạng theo hình dạng hiện tại và proportional.
Ẩn control giải phóng đường chia/ràng buộc; hiện lại ở vị trí mới của mesh.

## Lộ trình chính

| Phase | Kết quả có thể thử trong Blender | Task | Điều kiện hoàn thành |
| --- | --- | --- | --- |
| 1 — Khởi tạo | Cài extension, mở sidebar, chọn Source, tạo controller con của Source | [Bootstrap](../../tasks/phase-01-bootstrap.md) | Gate P1 |
| 2 — Control và đồng bộ | Tạo đường từ vertex/edge Source, controller trùng mesh, Hide/Reveal; sidebar native list theo model/mode, giữ Edit Mode và màu đường | [Controls](../../tasks/phase-02-controls-and-sync.md), [Native list UX](../../tasks/phase-02-native-list-ux.md) | Gate P2 và P2-UX |
| 3 — Hiển thị patch | Thấy các patch thật và bật/tắt lớp hiển thị để kiểm tra vùng | [Patch UX](../../tasks/phase-03-patch-visualization.md) | Gate P3 |
| 4 — Biến dạng | Edit Mode controller: chọn điểm/dải/cạnh/loop, G/R/S với proportional, commit/cancel/undo | [Deformation](../../tasks/phase-04-deformation.md) | Gate P4 và B/C/D |
| 5 — Kiểm chứng thực tế | Người dùng và agent qua MCP tạo control, chỉnh model fit ảnh front/side, so sánh kết quả | [User and agent validation](../../tasks/phase-05-user-agent-validation.md) | Gate P5 và F |

Mỗi phase cung cấp một bản thử được, ghi rõ tính năng đã hoạt động và giới hạn còn
lại. Không đánh dấu phase hoàn thành chỉ vì đã có giao diện hoặc tài liệu.

Đợt tiếp theo là [sidebar native list Phase 2](phase-02-native-list-ux.md), thay bố
cục box/nhiều nút của bản UX hiện có; chưa chuyển Phase 3. Task NL2.1–NL2.4 có test
và commit sau khi hoạt động. Báo cáo UX trước không xác nhận task mới đã pass.

## Những quy tắc đã chốt

1. **Một nguồn hình học:** Source giữ tọa độ, định nghĩa control, IDs và trạng thái ẩn.
   Controller là mesh vertex/edge không face, có thể dựng lại. Đường nhìn ở front/side
   vẫn là đường trong không gian 3D, không phải bản sao 2D độc lập.
2. **Object controller là con của Source:** di chuyển/xoay/scale object Source kéo
   controller theo, không nhân transform hai lần. Đây là quan hệ object Blender,
   không phải quan hệ cha/con giữa các đường control.
3. **Đồng bộ có hướng rõ ràng:** ngoài thao tác DANP Form, Source cập nhật controller.
   Trong thao tác phase 4, controller cung cấp target; core cập nhật Source rồi
   đồng bộ controller từ Source. Không để hai object tự ghi qua lại.
4. **Bật là ràng buộc, ẩn là giải phóng:** mọi vertex control đang bật không được
   chọn giữ nguyên trong phép biến dạng. Vertex giao nhau được chọn vẫn di chuyển.
   Hide/Reveal theo mask nguồn, không cần thêm deactivate hay lồng control.
5. **Patch theo topology:** các face liên thông qua cạnh không bị control đang bật
   cắt tạo thành patch. Đường mở không nhất thiết chia được patch.
6. **Ảnh hưởng theo kết nối:** một vertex control có thể tác động lên tập vertex
   nối tới nó qua edge trong patch kề, tùy proportional và ràng buộc. Tập này có
   thể phân nhánh, không có quy tắc một control vertex sở hữu một chuỗi duy nhất.
7. **Nền mỗi thao tác là mesh hiện tại:** snapshot P0 bất biến cho mọi preview;
   cancel khôi phục, confirm ghi mesh thật. Không kéo về template lịch sử.
8. **Chốt nội suy ở phase 4 bằng thử nghiệm:** dùng candidate đơn giản để đo hành
   vi, so sánh proportional và chất lượng. Không bắt buộc solver phức tạp trước.

## Phân lớp triển khai

[Hợp đồng phát triển](development-contract.md) mô tả cấu trúc mã, trạng thái lưu,
luồng cập nhật và báo cáo bàn giao. API Blender/UI chỉ thu nhận selection/target,
core tính patch và biến dạng trên buffer, adapter mới ghi mesh. Human và agent dùng
chung primitive; không duy trì một solver khác cho MCP.

Phase 1 dựng shell và đăng ký; phase 2 hoàn thiện identity/control/proxy; phase 3
cung cấp patch graph và overlay; phase 4 thêm selection/transaction/proportional/
solve và facade số tối thiểu; phase 5 kiểm chứng facade đó qua MCP. Hạ tầng cần cho
phase sau chỉ làm khi task hiện tại sử dụng được, tránh scaffold tính năng tương lai.

## Quy trình cho mỗi phase

1. Đọc task và các tài liệu bắt buộc, xác nhận các gate trước đã có bằng chứng.
2. Triển khai theo work package trong task; giữ mỗi thay đổi có thể kiểm tra riêng.
3. Chạy fixture thuần hình học cho quy tắc liên quan, rồi kiểm tra tích hợp Blender.
4. Test tích hợp/UI trên tiến trình và file Blender đang mở theo yêu cầu người dùng
   và hướng dẫn workspace. Dùng fixture tạm có phạm vi rõ; không chạy script dựng/
   xóa scene để thử kết nối. Test save/reopen cần bản sao an toàn và bảo toàn phiên
   đang làm việc; không lưu đè file dirty, không mở Blender riêng.
5. Bàn giao mã, bản cài, kết quả test, ảnh/video phù hợp, lỗi còn lại và hướng dẫn
   thử. Gate thất bại phải có reproduction; sửa rồi kiểm tra lại phần bị ảnh hưởng.

Các gate và hợp đồng đo nằm ở [acceptance-gates.md](../testing/acceptance-gates.md),
[geometry-cases.md](../testing/geometry-cases.md) và
[blender-integration-cases.md](../testing/blender-integration-cases.md).

## Sau 5 phase

Sparse simplify/refine, solver nâng cao, tự động phân tích ảnh/calibration/fit và
tăng tốc native là mở rộng tùy bằng chứng. G7/G8 và Gate E chỉ bắt buộc khi phát hành
sparse. Phase 5 dùng ảnh tham chiếu để người/agent quyết định target, không đòi hỏi
extension tự hiểu ảnh. Chưa hứa lịch phát hành hoặc hiệu năng khi chưa đo fixture thật.
