# Task phát triển DAN Form

Lộ trình chính có đúng 5 phase, theo [kế hoạch](../docs/roadmap/implementation-plan.md).
Hoàn thành gate của phase hiện tại trước khi chuyển phase tiếp theo.

1. [Phase 1 — Khởi tạo add-on](phase-01-bootstrap.md).
2. [Phase 2 — Control và đồng bộ](phase-02-controls-and-sync.md).
3. [Phase 3 — Hiển thị patch](phase-03-patch-visualization.md).
4. [Phase 4 — Biến dạng và proportional](phase-04-deformation.md).
5. [Phase 5 — Test người dùng và agent](phase-05-user-agent-validation.md).

Trước Phase 3, thực hiện [native list UX thuộc Phase 2](phase-02-native-list-ux.md):
sidebar kiểu Vertex Groups, +/−, Sync membership, reorder, inline rename và con mắt
theo active object/mode. Kế hoạch mới thay bố cục của [đợt UX trước](phase-02-ux-upgrade.md);
giữ context, Edit Mode và Source-backed overlay. Cần Gate P2 và P2-UX pass.

Đọc [hợp đồng phát triển](../docs/roadmap/development-contract.md) và
[acceptance gates](../docs/testing/acceptance-gates.md) khi bắt đầu. Mỗi task chỉ rõ
đầu vào, work package, test và điều kiện bàn giao. Không tự chốt công thức nội suy
từ ví dụ định tính. Các phase cũ 0–8 đã được thay thế; sparse và auto fitting là
mở rộng sau lộ trình chính.
