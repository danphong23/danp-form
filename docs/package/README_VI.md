# DANP Form 0.5.36

DANP Form là Blender extension giúp chỉnh Source Mesh bằng một Controller con
có các đường điều khiển thưa. Add-on dùng selection vertex/edge và các phím G/R/S
của Blender, sau đó truyền chuyển động control lên bề mặt Source.

## Cài đặt

Trong Blender Preferences, chọn **Install from Disk** và mở ZIP DANP Form này.
Bật extension, rồi mở sidebar (`N`) trong 3D View và chọn **DANP Form**.

## Bắt đầu

1. Chọn mesh làm Source.
2. Trong panel DANP Form, khởi tạo Controller.
3. Edit Controller, chọn vertex hoặc edge trên Source và tạo control.
4. Chọn handle Controller rồi dùng các phím **G**, **R** hoặc **S** như bình
   thường.
5. Dùng các nút hiển thị trong panel để ẩn, hiện hoặc quản lý đường control.

Mỗi Source sở hữu Controller con riêng. Sao chép mesh không làm hai model dùng
chung control; hãy khởi tạo riêng cho bản sao. Thay đổi Shape Key target được
thực hiện tường minh trong panel.

## Topology và phục hồi

Thay đổi topology Source có thể làm mapping control cũ không còn hợp lệ. DANP
Form sẽ tạm dừng biến dạng khi phát hiện mapping lỗi. Hãy Undo thao tác topology
để trở về mapping cũ, hoặc dùng Validate/Repair hay Reset DANP Controls để tạo
mapping mới theo topology hiện tại. **Reset Model** đưa mesh về dáng Init đã lưu
và là thao tác riêng có thể Undo.

Đây là bản chức năng có thể cài để kiểm thử. Kiểm thử UI trực tiếp cho phím tắt,
visibility Undo/Redo/save-reopen, overlay GPU, hiệu năng UI và thông tin chủ thể
bản quyền vẫn còn mở; chưa phải chứng nhận phát hành.

## Giấy phép

DANP Form dùng giấy phép GPL-3.0-or-later; gói có toàn văn giấy phép và thông
báo thư viện bên thứ ba về NumPy tùy chọn.
