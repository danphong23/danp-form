# H08 — Làm cứng handler và ranh giới module

**Phụ thuộc H03, H04, H07. Bàn giao:** đường sự kiện dễ kiểm soát, lỗi quan sát
được và không có ghi Source ngoài transaction đã xác nhận.

1. Rà soát depsgraph/load/undo callbacks, timer, global state, cache invalidation
và import vòng. Handler chỉ đánh dấu dirty/lên lịch công việc an toàn; giới hạn
re-entry và tránh solver/nặng dữ liệu trong callback.
2. Thay broad exception im lặng bằng lỗi có context và trạng thái phục hồi được;
   vẫn không để exception phá Blender UI. Gom các đường đọc/ghi target về adapter,
   loại code trùng và hardcode tình huống model cụ thể.
3. Đo hiệu năng full path và bộ nhớ với mesh nhỏ/lớn, nhiều control/key; tách
numerical-only để tìm bottleneck thật. Giữ tương thích operator/storage IDs.

**Kiểm thử:** fixture handler lặp/re-entry, load/undo/redo, multi-Source,
register/unregister nhiều lần, cache invalidation, lỗi cố ý; Blender UI và
background. **Gate:** không dữ liệu bị ghi/xóa ngoài transaction; không lỗi bị
nuốt; số đo và giới hạn được ghi. **Commit:**
`refactor(dan-form): harden runtime boundaries`.

**Progress 2026-09-25:** handler/cache lifecycle fixture passes 12 checks over
repeated register/unregister, handler uniqueness, undo/load invalidation and
overlay teardown. Source writes were reviewed against the shared transaction
workflow and deferred Undo restoration. Scoped performance baselines are linked
in the [H08 report](../../docs/testing/2026-09-25-h08-runtime-architecture.md);
large-mesh peak-memory and GPU error injection remain H09 release gates.
