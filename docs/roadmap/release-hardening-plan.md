# DANP Form — Lộ trình hoàn thiện trước phát hành

**Trạng thái: H01–H03 pass theo phạm vi phase 2026-09-25; H04–H10 chưa pass.** Đây là đợt hardening sau baseline 5 phase của
[ADR-009](../decisions/ADR-009-five-phase-development.md), không viết lại lịch sử
P1–P5 và không có nghĩa các gate cũ đã pass. Mỗi hàng dưới đây là **một phase,
một phạm vi bàn giao và một commit riêng**. Xem [task tương ứng](../../tasks/README.md)
để triển khai. H01 được chốt bằng [ADR-017](../decisions/ADR-017-deformation-target-contract.md)
và [ma trận target](../testing/deformation-target-matrix.md); H02/H03 có báo cáo
runtime riêng, còn H04–H10 vẫn chờ gate của chúng.

## Căn cứ và ranh giới

- Mã hiện tại đã có target Shape Key đang active, P0 theo target và UI chọn key.
  [ADR-015](../decisions/ADR-015-shape-key-edit-target.md) chấp nhận cả
  relative và absolute; H01 giữ nguyên phạm vi này trong ADR-017. Đề xuất
  bên ngoài về `Deformation Target` là đầu vào thiết kế, không phải đặc tả
  tự động thay thế ADR.
- Baseline audit phát hiện target I/O Edit Mode chưa tôn trọng key tường minh
  và handler có thể xóa object stale. H02/H03 đã sửa các đường đó; xem báo cáo
  H02/H03 để biết phần đã kiểm và các case UI còn chờ.
- [Audit Scale](../testing/2026-09-25-all-control-scale-audit.md) đã xác minh
  phép tính và fixture nền, nhưng chưa xác minh transform modal bằng chuột trên
  phiên Blender mở. Bộ selection lịch sử và overlay cần cập nhật gate.
- Manifest hiện là 0.5.31. Không suy ra mức sẵn sàng phát hành từ số phiên bản,
  test thuần Python hoặc ảnh chụp.

## Thứ tự và phụ thuộc

| Phase | Kết quả độc lập có thể review | Phụ thuộc bắt buộc | Commit đề xuất |
| --- | --- | --- | --- |
| [H01](../../tasks/release-hardening/h01-target-contract.md) — PASS tài liệu | Hợp đồng target và ADR giải quyết relative/absolute, Basis, target ID, thao tác đổi target | Không | `docs(dan-form): settle deformation target contract` |
| [H02](../../tasks/release-hardening/h02-target-io-undo.md) — PASS runtime | Đọc/ghi đúng target ở Object/Edit Mode và Undo/Redo | H01 | `fix(dan-form): route target io and undo safely` |
| [H03](../../tasks/release-hardening/h03-owned-object-safety.md) — PASS lifecycle | Lifecycle không tự xóa dữ liệu mồ côi trong scene | Không; có thể song song H01/H02 | `fix(dan-form): make ownership recovery non-destructive` |
| [H04](../../tasks/release-hardening/h04-native-transform.md) | G/R/S modal ổn định, gồm Scale toàn control | H02, H03 | `fix(dan-form): stabilize native transform transactions` |
| [H05](../../tasks/release-hardening/h05-target-ux.md) | UI target rõ ràng, tạo Shape Key mới an toàn | H01, H02, H04 | `feat(dan-form): complete deformation target workflow` |
| [H06](../../tasks/release-hardening/h06-agent-parity.md) | Agent API target đạt parity với UI | H01, H02, H05 | `feat(dan-form): expose target-aware agent operations` |
| [H07](../../tasks/release-hardening/h07-topology-recovery.md) | Chính sách thay topology và phục hồi tường minh | H01, H03; có thể triển khai song song H05/H06 | `feat(dan-form): make topology recovery explicit` |
| [H08](../../tasks/release-hardening/h08-runtime-architecture.md) | Handler, cache, lỗi và module boundaries được làm cứng | H03, H04, H07 | `refactor(dan-form): harden runtime boundaries` |
| [H09](../../tasks/release-hardening/h09-release-gates.md) | Test/release gate tự lặp và có bằng chứng trên Blender | Có thể dựng harness sớm; chỉ đóng gate sau H02–H08 | `test(dan-form): establish reproducible release gates` |
| [H10](../../tasks/release-hardening/h10-package-release.md) | Gói cài, tài liệu, manifest và báo cáo phát hành khớp mã | H09 | `chore(dan-form): prepare verified release package` |

Đường găng là H01 → H02 → H04 → H05 → H06 → H09 → H10. H03 có thể
bắt đầu ngay; H07 có thể chạy sau H01/H03. Công việc thiết kế fixture và
harness của H09 có thể bắt đầu sớm nhưng phase chỉ hoàn tất khi các chức năng
phụ thuộc đã qua gate. Nếu phase trước đổi hợp đồng, phase sau phải cập nhật
test theo hợp đồng mới, không lách gate.

## Quy tắc cho từng phase

1. Bắt đầu từ checkout sạch; ghi commit gốc, phiên bản Blender, fixture và
   tiêu chí pass. Giữ thay đổi trong phạm vi phase. Thay đổi kiến trúc/ngữ nghĩa
   cần ADR trước mã; không sửa ADR đã accepted một cách ngầm định.
2. Thực hiện unit/fixture, Blender background và UI trực tiếp theo task. Test
   nào không chạy ghi `NOT RUN`; lỗi ghi bước tái hiện và `FAIL`. Không coi
   exit code 0 là pass nếu log có traceback. UI trực tiếp không được thay bằng
   background fixture khi gate yêu cầu thao tác modal thật.
3. Ghi bằng chứng expected/actual, bản Blender/OS, mesh/key/mode, kết quả
   cancel/undo/save/reopen khi liên quan, cùng số đo median/P95 full preview
   và peak memory theo [hợp đồng](development-contract.md).
4. Chỉ commit phase sau khi gate của chính phase pass; commit message đề xuất
   ở bảng. Nếu bị chặn, giữ báo cáo `BLOCKED` hoặc `NOT RUN` và không tuyên bố
   hoàn tất. H10 chỉ chạy khi mọi gate bắt buộc và [acceptance gates](../testing/acceptance-gates.md)
   có bằng chứng.

## Ngoài phạm vi đợt này

`Save As Shape Key`, tự lan biến dạng Basis sang tất cả key, driver/corrective
key, multi-object transaction, tự động fit ảnh, solver mới và sparse control
không nằm trong H01–H10. Chỉ bổ sung bằng ADR và phase mới nếu có nhu cầu cùng
fixture chứng minh. Topology recovery H07 không được âm thầm đoán lại mapping
ID mơ hồ.
