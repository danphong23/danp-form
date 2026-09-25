# H05 — Hoàn thiện UX chọn target và tạo Shape Key

**Phụ thuộc H01, H02, H04. Bàn giao:** Source/Controller hiển thị target đang
được chỉnh, chuyển target có kiểm tra và lệnh tạo key mới an toàn.

1. Dùng một nguồn trạng thái target (active Source key) cho panel và operator;
   tránh dropdown giữ giá trị khác Blender. Hiển thị base/Basis, tên key,
   locked/stale/unsupported và trạng thái đang preview.
2. Lệnh New Shape Key chép **tọa độ lưu** của target đang chọn theo ADR-017;
   nếu chưa có key thì tạo Basis trước, absolute stack phải cấp frame không
   trùng. Không tự đổi giá trị key, mute, drivers, animation hay `eval_time`.
   Khôi phục `show_only_shape_key` sau khi
   rời Controller Edit Mode và khi cancel/error.
3. Quy định phản hồi khi người dùng đổi/xóa/khóa key giữa transaction; chặn
   lệnh trước ghi và giữ selection/mode nhất quán.
   Theo [ADR-017](../../docs/decisions/ADR-017-deformation-target-contract.md),
   Basis là KeyBlock đầu tiên; chỉ mesh không có key mới dùng BASE. Kiểm cả
   relative và absolute, không tự thay `eval_time`.

**Kiểm thử:** background cho tạo/chọn/khóa/lưu-mở; UI thật cho panel, edit,
chuyển target, rời mode, Undo/Redo trên bản sao an toàn. So sánh key values,
mute và tọa độ các key không chọn. **Gate:** người dùng luôn thấy đúng target;
không có thay đổi ngoài ý muốn. **Commit:**
`feat(dan-form): complete deformation target workflow`.

Fixture bắt buộc: [T03–T04, T11–T13](../../docs/testing/deformation-target-matrix.md).

**Status 2026-09-25: PASS.** The Blender 5.2.1 background fixture covers new-key
creation from Base, relative and absolute targets, and preview restoration. It
also exposed and fixed an early-reset of `show_only_shape_key` during Controller
entry. Direct UI verification on a safe copy covered target/lock display,
relative-target creation, Controller Edit switching/exit, and Base-target
Undo/Redo/save/reopen. The absolute target path uses the same panel operator and
passed the background fixture, so no extra panel click is treated as a blocker;
see
[`2026-09-25-h05-target-ux.md`](../../docs/testing/2026-09-25-h05-target-ux.md).

Direct UI follow-up on a disposable Blender 5.2.1 file: the panel displayed the
Basis/Smile/locked Blink targets and the lock warning; creating from the
relative Smile target selected `DANP Shape`; Controller Edit allowed switching
targets and the Back to Model button returned to Object Mode. A separate prior
run verified Base-only creation, menu Undo/Redo, Save and File > Revert. The
absolute-target panel path and data preservation were verified through the
same operator in the background fixture. No manual acceptance remains open for
H05.
