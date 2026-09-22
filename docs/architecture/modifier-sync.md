# Source và Controller: đồng bộ Modifier

## Quy tắc sở hữu

Source vẫn là nguồn hình học duy nhất. Controller là proxy vertex/edge có thể
dựng lại; nó không lưu một bản mesh thứ hai và không được dùng để khôi phục
Source sau khi modifier thay đổi.

Khi Source có modifier phù hợp với proxy, DANP sao chép modifier đó sang
Controller theo cùng thứ tự và thiết lập. Đây là bản sao được DANP đồng bộ,
không phải một liên kết datablock của Blender. `Ctrl-L > Copy Modifiers` của
Blender chỉ sao chép một lần; nó không cập nhật Controller khi Source đổi.

## Chính sách proxy

Controller không có mặt. Vì vậy không phải modifier nào của Source cũng có
nghĩa trên Controller. Phiên bản hiện tại chỉ cho phép `MIRROR`, gồm trục,
Mirror Object, Merge, Merge Distance và Clipping. `SUBSURF` và các modifier
cần mặt bị bỏ qua trên Controller nhưng vẫn giữ nguyên trên Source.

Mục tiêu của Mirror trên Controller là để Edit Mode native của Blender áp dụng
đúng Merge/Clipping tại mặt phẳng đối xứng. Mirror chỉ mở rộng phần hiển thị và
không tạo persistent ID mới; các vertex được chọn vẫn là vertex gốc của nửa
mesh Source.

## Đồng bộ vòng đời

```text
Init/Rebuild Controller
        │
        ├─ dựng vertex/edge proxy từ Source IDs
        └─ copy các modifier được cho phép

depsgraph thấy Source modifier đổi
        │
        └─ so sánh chữ ký RNA đầy đủ → đồng bộ Controller

Undo/Redo hoặc mở file
        │
        └─ dựng lại modifier Controller từ Source trước khi tiếp tục runtime
```

Chữ ký modifier bao gồm tên, loại, cờ hiển thị và các thuộc tính RNA của
modifier, nên đổi Clipping, Merge Distance, trục hoặc Mirror Object đều làm
Controller được cập nhật. Việc đồng bộ không chạy solver và không ghi tọa độ
Source.

`is_active` chỉ cho biết modifier nào đang được chọn trong giao diện của từng
object. Giá trị này không được sao chép hoặc so sánh: Source có thể đang chọn
Subdivision trong khi Mirror là modifier duy nhất của Controller. Một lần
đồng bộ không có thay đổi hình học phải giữ nguyên chính modifier Controller
và Edit Mode đang hoạt động.

## Ràng buộc đường giữa

Mirror trên Controller xử lý transform native trong Edit Mode. Phần DANP ghi
preview về Source phải tiếp tục tôn trọng mặt phẳng Mirror khi Clipping bật;
đây là lớp kiểm tra riêng của phép biến dạng, vì modifier của Controller không
thể tự bảo vệ một lần ghi tọa độ trực tiếp vào Source.

Writeback hiện áp dụng quy tắc này theo hệ tọa độ của Mirror: vertex vốn nằm
trên mặt phẳng được giữ ở mặt phẳng, vertex ngoài mặt phẳng không được vượt qua
trục khi Clipping bật, và vertex đi vào Merge Distance được snap về mặt phẳng
khi Merge bật.

Nếu test thực tế cho thấy patch ở đường giữa vẫn bị xem như đường hở, bước tiếp
theo là bổ sung đồ thị đối xứng ảo trong phép tính patch. Không tạo control
trái/phải và không Apply Mirror trong bước này.
