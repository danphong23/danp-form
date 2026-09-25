# H02 — Đọc/ghi target và Undo đúng key

**Trạng thái: PASS runtime và người dùng xác nhận ổn định trên Blender 0.5.34,
2026-09-25.** Bằng chứng ở
[báo cáo H02](../../docs/testing/2026-09-25-h02-target-io-undo.md).

**Follow-up sau kiểm thử người dùng:** controller idle phải theo bề mặt Source
đang hiển thị sau đánh giá Shape Key, không theo tọa độ lưu của key đang chọn.
Undo history chỉ lưu identity dạng scalar rồi resolve lại key sống; không giữ
KeyBlock RNA qua native Undo. Bản sửa và fixture bổ sung nằm trong
[báo cáo đồng bộ/Undo](../../docs/testing/2026-09-25-h02-evaluated-sync-undo.md).
Sau lỗi đồng bộ khi kéo Shape Key 0 → 1, gói 0.5.34 đã được cài và kiểm tra
trực tiếp qua MCP trên model hiện tại. Người dùng sau đó xác nhận thao tác trên
Blender hoạt động ổn định; xem báo cáo để phân biệt kiểm tra do agent quan sát
và nghiệm thu do người dùng xác nhận.

**Phụ thuộc H01. Bàn giao:** adapter đọc/ghi duy nhất cho base/Basis/Shape Key,
gồm Source Object/Edit Mode, preview, cancel và native Undo/Redo.

1. Tách API `read_positions(target)`, `write_positions(target, positions)` và
   kiểm tra mode/key/lock/count. Đường explicit target không được rơi về
   BMesh của active key khác. Trong Edit Mode, hoặc chuyển context có kiểm soát
   và khôi phục đầy đủ, hoặc từ chối trước khi ghi với lỗi rõ ràng.
2. Đưa sync controller, P0, restore và reset qua cùng adapter; chặn stale target
   trước khi đụng Source. Đảm bảo một preview không đổi target giữa chừng.
3. Thu hẹp nhánh writeback/Undo cũ; không để hai đường ghi tọa độ cạnh tranh.
   Áp dụng [ADR-017](../../docs/decisions/ADR-017-deformation-target-contract.md):
   kiểm owner/KeyBlock identity, name/index/mode/count/topology guards; Reset Model
   chỉ ghi khi chứng minh được provenance snapshot, không chỉ trùng tên key.

**Kiểm thử:** fixture riêng cho mesh không key, Basis, hai key A/B khi active A
nhưng lịch sử Undo yêu cầu B, key khóa, đổi/xóa target giữa transform, Object/Edit
Mode; so sánh tọa độ từng key trước/sau, cancel và redo. Chạy Blender background
và case UI theo H01. **Gate:** không key nào ngoài target thay đổi; không có
partial write/traceback. **Commit:** `fix(dan-form): route target io and undo safely`.

Fixture bắt buộc: [T01–T10, T15–T16](../../docs/testing/deformation-target-matrix.md),
bao gồm absolute stack và Undo khi Source Edit Mode đang ở key khác.

## Kết quả triển khai

- `blender.mesh._resolve_shape_key` xác thực owner và KeyBlock; đọc/ghi Object
  Mode dùng `KeyBlock.data`, còn Edit Mode truy cập đúng BMesh shape layer theo
  tên key. Mọi ID, số điểm, trạng thái khóa và tọa độ đều được xác thực trước
  khi ghi.
- Preview/cancel giữ target sống đã capture trong thời gian thao tác. Undo
  history ghi descriptor scalar (owner/key pointer/name/index), resolve lại
  trên stack hiện hành rồi mới đọc/ghi; target không chứng minh được thì fail
  closed. Đổi target, khóa key hoặc đổi signature dừng thao tác trước khi ghi.
- Controller idle đọc pose Source theo ID đỉnh. Nếu modifier thay topology,
  Blender trộn Shape Key trên mesh Source tạm độc lập trước khi copy về proxy;
  Controller theo value, blend, mute và show-only-key. Khi vào Controller Edit, mesh
  preview key được cô lập và proxy đồng bộ lại từ bề mặt đang hiển thị.
- Reset lưu loại target `BASE`/`KEY`. Blender 5.2.1 không cho KeyBlock dùng
  IDProperty, nên DANP giữ bằng chứng runtime theo phiên và theo dõi cấu trúc
  stack. Sau load hoặc khi không còn chứng cứ, reset key cũ từ chối an toàn.
- Fixture Blender 5.2.1 kiểm tra Basis, expression, absolute stack, Object/Edit
  Mode, cancel, khóa, đổi/đổi tên target, Reset cùng key và key thay thế cùng
  tên; kiểm thử Undo/Redo bridge đặt Source ở Edit Mode trên Basis và kiểm thử
  Undo/Redo của absolute key.
- Không chạy được kiểm thử `pytest` vì môi trường không có pytest; 59 hàm test
  tĩnh được gọi trực tiếp và đều qua. Agent không trực tiếp gửi phím Undo native
  vào Blender UI; người dùng đã xác nhận build 0.5.34 ổn định sau kiểm thử.
  Key reorder trong lúc modal transform vẫn là NOT RUN.
