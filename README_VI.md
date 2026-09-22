# DANP Form

DANP Form là add-on Blender giúp người dùng hoặc AI chỉnh một model template bằng mạng đường control thưa nằm trên topology thật của Source Mesh.

```text
Source Mesh + control
        ↓
patch theo topology
        ↓
G / R / S control
        ↓
nội suy chuyển động trên patch hiện tại
        ↓
ghi trực tiếp vào Source Mesh
```

Điểm cốt lõi: **hình dạng hiện tại của patch trước mỗi thao tác là nền hình học**.
Biến dạng dựa vào chuyển động control và proportional; không dựng lại patch chỉ từ vài
điểm control và không kéo mesh về template ban đầu. Cộng displacement là phương pháp
prototype cần thử, chưa phải công thức bắt buộc của sản phẩm.

Control đang bật chỉ đổi qua phần được chọn; phần không chọn giữ nguyên. Ẩn control
hoặc một đoạn sẽ bỏ ràng buộc và đường chia patch, cho phép nó đi theo mesh. Hiện lại
lấy vị trí mới từ Source, không quay về vị trí cũ. Vertex giao nhau được chọn sẽ đi
theo thao tác dù cũng thuộc đường khác. Không cần cha/con giữa các đường control
hay deactivate riêng.

Bộ này gồm specification và addon prototype Phase 1–4. Bản 0.5.17 dùng tên DANP
Form; model có Init/Remove, controller giữ topology cố định. Patch chỉ có một
control biên nhận toàn bộ G/R/S; patch có nhiều control blend transform với các
control không chọn làm neo đứng yên. Lộ trình kiểm chứng agent và release vẫn
thuộc Phase 5.

Controller Edit: Ctrl+Alt+Click chọn đoạn giữa giao điểm; Shift để chọn thêm.
H ẩn phần chọn, Alt-H hiện tất cả; Hide/Show Controls đồng bộ toàn bộ con mắt.

Source vẫn có thể chỉnh topology bằng Edit Mode hoặc Apply Modifier. Khi topology
thay đổi, DANP tạm dừng để không ghi theo ID cũ; dùng Undo để quay lại mapping
trước đó hoặc chọn **Manage → Reset DANP Controls** để tạo mapping mới trên mesh hiện tại.
Modifier chưa Apply chỉ thay đổi hình hiển thị; mapping vẫn theo Source base.

Khi Init lần đầu, DANP lưu một snapshot tọa độ theo ID của Source. **Reset Model**
đưa mesh về đúng dáng đó và có thể Undo; **Reset DANP Controls** chỉ tạo lại mapping trên
topology hiện tại và dùng dáng hiện tại làm snapshot mới.

Khi Source đã có DANP, thanh trên chỉ hiện **Reset Model** và **Manage**;
Manage chứa lệnh tạo lại control và gỡ DANP. Với Radius = 0, vùng giữa hai
đường control nội suy theo chiều dài cạnh của Source ở đầu thao tác, nên các
vòng hình trụ giữ tỉ lệ khoảng cách ban đầu khi hai đầu tiến lại gần nhau.
Nếu model đã bị biến dạng không đều ở các thao tác trước, dùng Reset Model
trước khi thử lại; lệnh transform mới không tự thay đổi lịch sử hình học.

Trong Controller Edit, DANP so sánh toàn bộ tọa độ proxy trước và sau mỗi mẫu
G/R/S. Vì vậy Blender Proportional Editing có thể kéo cả các điểm không được
chọn; mọi điểm thực sự đổi tọa độ đều được xem là mục tiêu, còn vùng chọn chỉ
dùng để bắt đầu và phân định thời điểm chuyển sang thao tác khác.

1. Khởi tạo add-on, sidebar, chọn Source, tạo controller con của Source.
2. Tạo đường control từ vertex/edge, đồng bộ vị trí, Hide/Reveal và lưu/dựng lại.
3. Tính patch theo topology và bật/tắt lớp hiển thị patch.
4. Edit Mode controller, G/R/S và proportional; thử/chốt nội suy, cancel/undo.
5. Test người dùng và agent ngoài qua MCP, tạo control và chỉnh fit ảnh front/side.

[Kế hoạch chi tiết](docs/roadmap/implementation-plan.md) và [task từng phase](tasks/README.md)
đã có bước triển khai, test và điều kiện hoàn thành. Sparse và auto fitting là mở
rộng sau lộ trình này. Controller con là quan hệ object Blender; không lồng các
đường control. Bật/tắt hiển thị patch chỉ đổi UX.

Đọc theo thứ tự: `docs/product/product-definition.md` → `docs/core/invariants.md` → `docs/core/control-model.md` → `docs/core/patch-model.md` → `docs/core/selection-and-targets.md` → `docs/core/interpolation-baseline.md` → `docs/testing/prototype-plan.md`.
