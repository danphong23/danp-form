# H09 — Bộ kiểm thử phát hành có thể lặp

**Bắt đầu dựng harness song song; chỉ đóng phase sau H02–H08. Bàn giao:** một
lệnh/hướng dẫn chạy lại được với báo cáo kết quả và bằng chứng UI riêng.

1. Sửa/thay bộ selection lịch sử gọi operator không còn đăng ký; dựng fixture
độc lập cho no-key/Basis/relative/absolute theo H01, duplicate, ownership,
topology, G/R/S, overlay, undo/save/load và agent parity.
2. Harness kiểm exit code **và** traceback/assertions/result marker trong log;
không chuyển lỗi thành pass. Ghi phiên bản Blender, add-on, OS, commit và fixture.
3. Lập gate UI trực tiếp cho modal G/R/S, panel, overlay, nhiều model và MCP;
background không thay thế GPU/UI. Đo median/P95 full preview, confirm, peak memory
trên fixture đại diện; ghi ngưỡng được chọn sau đo.

**Kiểm thử:** cố ý tạo một test fail để chứng minh harness trả FAIL; chạy sạch
mọi suite bắt buộc, chạy test UI trên bản sao file an toàn, ghi NOT RUN nếu không
thực hiện. **Gate:** Gate A–F liên quan và H01–H08 có bằng chứng; không stale test,
không traceback bị bỏ qua. **Commit:**
`test(dan-form): establish reproducible release gates`.

**Progress 2026-09-25:** operational gate passes: 9 static suites / 60 checks,
8 Blender suites / 169 assertions, H04–H07 UI acceptance evidence, and an
intentional-failure self-test. The full runner correctly reports `INCOMPLETE`
because GPU overlay fault review and a fresh combined large-mesh P95/peak-memory
run were not performed. See the
[H09 report](../../docs/testing/2026-09-25-h09-release-gates.md). H10 may build
and install a functional candidate, but it must not claim performance-certified
production readiness.

**Progress 2026-09-27:** added an optional NumPy path for the large all-control
affine preview. The dependency-free implementation remains the fallback and a
parity regression compares both paths in Blender's bundled Python. A guarded
background benchmark now accepts only an unsaved copy in the system temp
directory, reports full preview median/P95, confirm commit and process memory,
and does not replace GPU/UI acceptance. Nine recorded runs on the representative
1,698-vertex / 49-definition character copy measured 18.4–35.5 ms P95 after
four warm-ups; the background guardrail is set at 40 ms. The post-commit runner
passed 9/9 static suites, 11/11 Blender suites and the representative benchmark.
Release remains `INCOMPLETE`: direct C02 UI Undo/Redo/save-reopen, H08 GPU,
native UI performance and maintainer attribution are outstanding. See the
[2026-09-27 H09 benchmark report](../../docs/testing/2026-09-27-h09-large-preview-benchmark.md).

**Post-overlay diagnostics regression, 2026-09-27:** the runner was repeated
against source commit `4703f2f` after adding visible/throttled GPU overlay error
reporting. All 10 static suites and all 11 Blender 5.2.1 background suites
passed. This run did not include the large-mesh benchmark or GPU/UI checks;
the report remains `INCOMPLETE` and is recorded at
[`2026-09-27-post-overlay-diagnostics-gates.json`](../../docs/testing/2026-09-27-post-overlay-diagnostics-gates.json).

**Package-hygiene regression, 2026-09-27:** after curated packaging and report
path redaction, source commit `2df8bdd` passed all 10 static suites and 11/11
Blender 5.2.1 background suites. The runner report is
[`2026-09-27-release-gates-package-hygiene.json`](../../docs/testing/2026-09-27-release-gates-package-hygiene.json).
The result remains `INCOMPLETE`; direct UI/GPU/performance gates and maintainer
attribution are still explicitly unrun.

The same revision was then measured on a disposable multi-scene character copy.
The benchmark now activates the scene owning the Source/Controller pair before
selection, so it supports a valid pair outside the file's initially active scene.
On 1,698 Source vertices, 49 definitions, and 726 effective handles, 30 preview
samples after four warm-ups measured 19.65 ms median / 28.73 ms P95; confirm
commit was 3.70 ms, with a 40 ms background P95 guardrail. H08 also now injects
a failure in the overlay callback and verifies cache clearing, contextual
traceback capture, and log throttling in Blender background mode. This is not
native UI, viewport, or actual GPU rendering evidence. The complete report is the
[`2026-09-27 package-hygiene gate report`](../../docs/testing/2026-09-27-release-gates-package-hygiene.json).

**Final cleanup audit, 2026-09-27:** reran the complete runner on documentation
revision `b1323d0` with the disposable multi-scene character copy. All 10 static
and 11 Blender background suites passed. Thirty warmed preview samples measured
16.74 ms median / 17.28 ms P95; confirm was 1.58 ms and the process peak working
set was 285.02 MB. The benchmark copy was not saved. The run remains
`INCOMPLETE`: native UI/GPU performance, the C02 keymap/visibility Undo/Redo and
save/reopen sequence, actual GPU overlay review, and maintainer attribution are
still open. See
[`2026-09-27 cleanup audit`](../../docs/testing/2026-09-27-cleanup-audit.json).
