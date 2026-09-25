# Hợp đồng phát triển

**Trạng thái: hướng dẫn triển khai 5 phase; tên file mã dưới đây là đề xuất.**

## Cấu trúc mã khi bắt đầu

```text
addon/dan_form/
  __init__.py                 đăng ký/hủy đăng ký extension
  core/                      identity, control network, patch, target, transaction, solve
  blender/                   mesh/BMesh, storage, proxy sync, operators, sidebar, overlay
  agent/                     facade chung primitives; triển khai khi phase 4/5 cần
tests/
  geometry/                  fixtures thuần dữ liệu, không phụ thuộc UI
  blender/                   đăng ký, mapping, lifecycle, undo và context
  reports/                   thông số môi trường và kết quả từng gate
```

Tạo module theo nhu cầu của phase, không tạo toàn bộ cây rỗng ngay từ đầu. Chọn phiên
bản Blender hỗ trợ đầu tiên ở P1.1 và ghi phiên bản thật vào báo cáo. Kiểm tra API từ
bản Blender/docs chính thức đó khi viết mã; tài liệu thiết kế không bảo đảm API cụ thể.

## Ranh giới trách nhiệm

| Thành phần | Trách nhiệm | Không sở hữu |
| --- | --- | --- |
| Source storage | Source UUID, persistent IDs, control definitions, masks, revisions | Proxy làm nguồn tọa độ thứ hai |
| Mesh adapter | Đọc/ghi base mesh đúng Object/Edit Mode, kiểm tra topology | Công thức nội suy |
| Proxy adapter | Dựng vertex/edge, parenting, selection map, hiển thị/sync | Bản lưu template độc lập |
| Core | Effective network, face patches, targets, P0, preview, validation | UI context và MCP transport |
| UI/agent facade | Chuyển thao tác thành primitive chung, trả lỗi/kết quả | Ghi Source bỏ qua transaction |
| Overlay | Màu/đường/nhãn patch và debug | Thay đổi topology, masks hoặc affected scope |

Giai đoạn đầu exact proxy: mỗi vertex hiển thị ánh xạ một Source vertex ID. Chưa làm
sparse. Chỉ `bpy`/adapter giữ object handle; core nhận IDs, connectivity, tọa độ và
buffer số. Trước ghi kiểm tra targets hữu hạn, identity/topology, revision/generation
và quyền chỉnh sửa. Không giữ index Blender làm identity lâu dài.

## Dữ liệu và cache

Lưu định nghĩa và trạng thái đủ để dựng lại proxy/patch sau mở file. Transaction,
buffer P0, preview, cache khoảng cách và overlay là runtime, không lưu như sự thật.
Cache partition phụ thuộc topology và effective network; cache khoảng cách/weights
còn phụ thuộc P0 và proportional. Đổi tên logical control không đổi lời giải.

Controller là con trực tiếp của Source và giữ cùng hệ tọa độ local, không thêm
offset/scale riêng. Transform object Source không phải biến dạng control. Quan hệ
parent là liên kết sở hữu duy nhất; UUID không được dùng để chọn Controller. Proxy
rebuild giữ định nghĩa/mask, không Reveal All. Mesh duplicate riêng lẻ ở trạng thái
chưa liên kết và Init với control mới; duplicate cả cặp nhận UUID mới và giữ định
nghĩa/ID cục bộ. Việc hòa giải duplicate dựa trên quan hệ trong scene, không dựa
vào thao tác Blender tạo object. Collision mơ hồ khi mở file phải chặn ghi. Các
generation/closed-operation checks phải có trước phase 4 ghi preview.

## Đồng bộ và thao tác

Ngoài transaction: nhận tín hiệu Source thay đổi → đánh dấu dirty → cập nhật proxy
nhẹ trong context an toàn. Thử cả BMesh khi đang Edit Mode. Không chạy solver trong
depsgraph handler. Mốc lệnh vẫn revalidate Source; tín hiệu UI không thay kiểm tra
identity. Loại event/timer cụ thể chọn bằng thử phase 2, ghi độ trễ đo được và giới hạn.

Trong transaction: resolve selection → chụp P0 và union các patch kề → sinh target
tuyệt đối từ đầu thao tác → solve/validate buffer → ghi preview Source → resync proxy.
Preview sau reset buffer về P0 trước khi solve scope hiện tại, để radius nhỏ lại hoặc
target quay về P0 không để lại biến dạng cũ. Confirm/cancel đóng handle và dọn runtime.

Các lệnh cấu trúc control/mask/rebuild khi đang thao tác trả `OPERATION_BUSY`.
Topology bị đổi ngoài dự kiến phải chặn tiếp tục, không rollback theo index cũ. Quy
tắc recovery đầy đủ nằm ở [errors-and-recovery.md](../architecture/errors-and-recovery.md).

## Bàn giao từng phase

Đợt hoàn thiện sau baseline dùng cùng mẫu báo cáo cho từng
[H01–H10](release-hardening-plan.md). Mỗi H là một phạm vi review và commit riêng;
phase phụ thuộc không được ghi PASS khi gate đầu vào còn FAIL/NOT RUN. Với
Shape Key phải ghi rõ target thực tế, mode và các key không được phép đổi; với
handler phải kiểm dữ liệu scene còn nguyên. Với UI modal phải thao tác thật,
không thay bằng kết quả background. Harness phải xét traceback trong log dù
Blender trả exit code 0.

Báo cáo gồm: commit/diff hoặc danh sách file, bản extension cài được, Blender/OS,
fixture và bước tái hiện, expected/actual, PASS/FAIL/BLOCKED, ảnh test phù hợp, lỗi
chưa sửa và tính năng chưa triển khai. Chưa chạy test phải ghi NOT RUN. Không lấy
ảnh giao diện làm bằng chứng selected/fixed/outside coordinates chính xác.

Phase 4/5 đo full preview median/P95, confirm và memory cùng kích thước Source,
affected verts, control samples; numerical-only tách riêng. Quyết định chất lượng
và mức hiệu năng phát hành phải có bằng chứng, không suy ra từ độ đầy đủ tài liệu.
