# Task phát triển DANP Form

Ưu tiên hiện tại là [cleanup sau comprehensive review](addon-cleanup-review.md).
Các lỗi mới có bằng chứng phải được sửa trước phát hành và trước Inspect/hover.

Lộ trình baseline ban đầu có đúng 5 phase, theo [kế hoạch](../docs/roadmap/implementation-plan.md).
Hoàn thành gate của phase hiện tại trước khi chuyển phase tiếp theo. Đợt hoàn thiện
trước phát hành gồm [H01–H10](../docs/roadmap/release-hardening-plan.md), mỗi
công việc là một phase và một commit có kiểm thử riêng. Các phase H không thay
thế ADR-009 hoặc biến các gate P1–P5 chưa kiểm thành PASS.

1. [Phase 1 — Khởi tạo add-on](phase-01-bootstrap.md).
2. [Phase 2 — Control và đồng bộ](phase-02-controls-and-sync.md).
3. [Phase 3 — Hiển thị patch](phase-03-patch-visualization.md).
4. [Phase 4 — Biến dạng và proportional](phase-04-deformation.md).
5. [Phase 5 — Test người dùng và agent](phase-05-user-agent-validation.md).

## Phase hoàn thiện trước phát hành

Theo [sơ đồ phụ thuộc H01–H10](../docs/roadmap/release-hardening-plan.md):

1. [H01 — Hợp đồng Deformation Target](release-hardening/h01-target-contract.md).
2. [H02 — Target I/O và Undo](release-hardening/h02-target-io-undo.md).
3. [H03 — An toàn object mất liên kết](release-hardening/h03-owned-object-safety.md).
4. [H04 — G/R/S modal ổn định](release-hardening/h04-native-transform.md).
5. [H05 — UX Shape Key target](release-hardening/h05-target-ux.md).
6. [H06 — Agent API parity](release-hardening/h06-agent-parity.md).
7. [H07 — Topology recovery](release-hardening/h07-topology-recovery.md).
8. [H08 — Runtime architecture](release-hardening/h08-runtime-architecture.md).
9. [H09 — Release gates tái lập](release-hardening/h09-release-gates.md).
10. [H10 — Gói và tài liệu phát hành](release-hardening/h10-package-release.md).

Trước Phase 3, thực hiện [native list UX thuộc Phase 2](phase-02-native-list-ux.md):
sidebar kiểu Vertex Groups, +/−, Sync membership, reorder, inline rename và con mắt
theo active object/mode. Kế hoạch mới thay bố cục của [đợt UX trước](phase-02-ux-upgrade.md);
giữ context, Edit Mode và Source-backed overlay. Cần Gate P2 và P2-UX pass.

Đọc [hợp đồng phát triển](../docs/roadmap/development-contract.md) và
[acceptance gates](../docs/testing/acceptance-gates.md) khi bắt đầu. Mỗi task chỉ rõ
đầu vào, work package, test và điều kiện bàn giao. Không tự chốt công thức nội suy
từ ví dụ định tính. Các phase cũ 0–8 đã được thay thế; sparse và auto fitting là
mở rộng sau lộ trình chính.
