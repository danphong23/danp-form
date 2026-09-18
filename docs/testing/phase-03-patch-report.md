# Phase 3 — Patch graph và hiển thị patch

## Kết quả

Phase 3 đã có partition runtime theo face graph của Source. Mỗi patch là một
component của các face liên thông sau khi bỏ adjacency qua edge control đang bật.
Edge control được lookup qua các patch mà nó nằm trên biên; point control được
lookup qua patch chứa vertex. Đây là dữ liệu runtime để Phase 4 capture scope,
không phải một mesh hay ownership mới.

Lớp màu patch dùng triangle batches từ chính face Source, theo transform hiện tại.
Nó chỉ hiển thị, không sửa Source, không đổi mask/network revision và không tham
gia chọn chuột. Hide/Reveal control làm thay đổi partition; bật/tắt Show Patches
chỉ làm thay đổi lớp màu.

## Các trường hợp đã kiểm tra

Fixture lưới hai quad có một edge chung đạt 13 kiểm tra:

- edge control nội bộ tạo hai patch và được lookup ở cả hai phía;
- boundary edge không tự tách patch và chỉ lookup patch chứa biên đó;
- point control không tạo cut;
- partition giữ cache khi topology/network không đổi;
- overlay tạo một batch cho mỗi patch;
- tắt overlay không đổi tọa độ hoặc network revision;
- Hide edge cut gộp hai patch, Reveal khôi phục hai patch;
- Hide boundary edge không làm thay đổi partition nội bộ.

Kiểm tra trên file Blender đang mở `Project/2. toon/girl_chibi_1.blend`:

- Blender 5.2.1 LTS, cùng phiên người dùng, không mở tiến trình Blender phụ;
- Source `girl chibi 1`: 1696 face, 50 control definition;
- partition hiện tại: 104 patch, bao phủ đủ 1696 face;
- 50/50 control có lookup patch không rỗng;
- thử Hide một edge rồi Reveal: 104 → 103 → 104 patch;
- overlay tạo 104 batch;
- hidden vertex/edge mask cuối cùng rỗng, không còn fixture test;
- context được khôi phục về `DANPFORM_CTRL_girl chibi 1` / Controller Edit.

Năm suite hồi quy Phase 1/2 vẫn đạt 197 checks: lifecycle 37, sidebar 34,
Edit/performance 38, segment/visibility 43 và pick UX 45. Test patch graph
được chạy thêm trực tiếp qua MCP trên file live.

## Giới hạn còn lại

Patch display hiện dùng palette lặp theo thứ tự patch, phù hợp để kiểm tra vùng
nhưng chưa phải hệ màu semantic. Chưa có thao tác biến dạng, proportional hay
chọn patch để thao tác; đó là Phase 4. Patch graph vẫn giả định manifold mesh làm
baseline và chưa biến non-manifold thành một quy tắc tự động.
