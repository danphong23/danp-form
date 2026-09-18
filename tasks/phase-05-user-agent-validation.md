# Phase 5 — Test người dùng và agent ngoài qua MCP

**Đầu vào:** Gate P4/B/C/D pass và facade chung. **Đầu ra:** bằng chứng workflow
modeling thực tế, parity và lỗi đã khắc phục. Gates P5/F; chưa cần auto-fit extension.

## Đọc bắt buộc

[Agent API](../docs/agent/api-contract.md),
[shared primitives](../docs/agent/shared-primitives.md),
[acceptance gates](../docs/testing/acceptance-gates.md),
[reference extension](../docs/extensions/reference-fitting.md).
Trước kiểm tra Blender đang mở/MCP/Computer Use đọc hướng dẫn test tại workspace
`.agents/blender-testing.md`; dùng skill Computer Use khi thực sự test UI.

## Work packages

- **P5.1 — Môi trường test:** xác nhận Blender/extension/MCP hiện có, handshake
  read-only, file test riêng có model chân/grid và ảnh reference được phép dùng.
  Ghi addon/MCP versions, tên file, Source IDs và trạng thái scene. Không dựng/xóa/
  lưu đè scene của người dùng để thử kết nối. Thiếu transport ghi BLOCKED của test
  đó, không thay bằng tuyên bố PASS.
- **P5.2 — Test người dùng:** tạo 2 loop + đường dọc và thêm đường theo viền front/
  side; select điểm/đoạn/loop G/R/S; so sánh profiles; Hide đường/đoạn để gộp vùng,
  chỉnh lại, Reveal; confirm/cancel/undo và save/reopen. Ghi dễ chọn, dễ dự đoán,
  lỗi hình dạng và bước tái hiện. Viền view là đường do người dùng tạo bình thường.
- **P5.3 — Agent qua MCP:** agent đọc state/control/patch queries, tạo definitions
  và set numeric targets bằng facade chung. Có thể MCP gọi Python/operator facade
  qua capability hiện có; không sửa raw Source coords để giả lập DANP Form.
  Agent xem ảnh/reference và quyết định target, không yêu cầu core tự phân tích ảnh.
- **P5.4 — Parity:** từ cùng fixture/P0 chạy human numeric targets và equivalent
  agent targets, cùng pivot/space/profile/radius. So tọa độ, selected/fixed/outside,
  effective network, Hide/Reveal, cancel/no-op. Bài fit ảnh tự do là quality workflow,
  không dùng để đòi numerical parity hai hành động khác nhau.
- **P5.5 — Robustness và sửa lỗi:** stale revision, closed token, busy operation,
  proxy rebuild, partial visibility, unsupported feature, Source khác, interruption;
  retry không cộng dồn displacement. Sửa lớp chung, thêm regression cho lỗi thực,
  rerun gates liên quan. Ghi throughput/latency toàn đường MCP riêng với core time.
- **P5.6 — Bàn giao:** hướng dẫn cài/sử dụng, public callable facade examples theo
  API thực, demo fit ảnh before/after, bảng PASS/FAIL/NOT RUN/BLOCKED, quality review
  và known limitations. Cập nhật hướng dẫn agent test workspace nếu quy trình thực
  khác, tránh lưu assumption như bằng chứng scene tương lai.

## Điều kiện hoàn thành

Gate F pass trên equivalent numerical inputs, workflow người dùng và external
agent đều tạo control/chỉnh Source qua DANP Form thành công. Fit reference có review
của người dùng hoặc tiêu chí được ghi trước; ảnh đẹp không thay checks constraints.
Không còn lỗi ngăn core workflow và mọi gate bắt buộc có evidence. Production chỉ
được tuyên bố sau quality/lifecycle/performance review trong acceptance gates.

Sparse, automatic image extraction/calibration và advanced solver chưa phải đầu ra
phase 5. Đề xuất mở rộng chỉ dựa trên lỗi/hạn chế đã quan sát được ở báo cáo này.
