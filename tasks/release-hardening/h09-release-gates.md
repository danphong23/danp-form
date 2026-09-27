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
and does not replace GPU/UI acceptance. Seven runs on the representative
1,698-vertex / 49-definition character copy measured 18.4–35.5 ms P95 after
four warm-ups; the background guardrail is set at 40 ms. Direct UI/GPU
measurements remain outstanding. See the
[2026-09-27 H09 benchmark report](../../docs/testing/2026-09-27-h09-large-preview-benchmark.md).
