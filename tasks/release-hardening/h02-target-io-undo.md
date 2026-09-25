# H02 — Đọc/ghi target và Undo đúng key

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
