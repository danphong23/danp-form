# Phase 1 — Khởi tạo add-on và controller

**Đầu vào:** specification; chưa có add-on production. **Đầu ra:** extension cài và
mở sidebar được, bind Source và tạo controller con. Gate P1; chưa biến dạng mesh.

## Đọc bắt buộc

[Development contract](../docs/roadmap/development-contract.md),
[Source truth](../docs/decisions/ADR-001-source-truth.md),
[data model](../docs/architecture/data-model.md),
[Blender integration](../docs/blender/integration.md),
[lifecycle](../docs/blender/storage-and-lifecycle.md).

## Work packages

- **P1.1 — Extension shell:** xác nhận Blender mục tiêu; tạo namespace `dan_form`,
  manifest/package, register/unregister classes và sidebar DAN Form. Cài, disable,
  enable lại không nhân đôi handler/keymap/class. Thông báo phiên bản/feature không
  hỗ trợ bằng lỗi rõ ràng.
- **P1.2 — Bind Source:** chọn mesh hợp lệ; tạo Source UUID và metadata version.
  Kiểm tra quyền chỉnh sửa và các giới hạn prototype trước ghi. Cùng Source gọi
  Initialize lại không tạo controller thứ hai. Chưa cần cấp ID mọi face/edge nếu
  bước này chưa dùng chúng.
- **P1.3 — Controller object:** tạo mesh vertex/edge rỗng không face, link collection
  hợp lệ, bind Source UUID, parent trực tiếp Source. Giữ hệ tọa độ local trùng Source;
  transform Source kéo object con đi một lần. Không dùng constraint/modifier để
  tạo biến dạng ở phase này.
- **P1.4 — Sidebar và lifecycle:** hiện Source/controller, nút Initialize và chọn
  controller; báo trạng thái chưa có control. Xử lý đổi selection, object bị xóa,
  file reload và unregister; không crash từ stale pointer.
- **P1.5 — Package và test:** chạy `scripts/package-extension.ps1` để tạo ZIP có
  `blender_manifest.toml` và `__init__.py` ở package root, cài bằng Blender Extension
  Manager, bật/tắt package và ghi cách chạy trên file test; lưu/mở lại vẫn bind đúng,
  undo Initialize khôi phục đúng trạng thái trước.

## Test và bàn giao

Thử mesh hợp lệ; không selection; camera/light; Source read-only/feature không hỗ
trợ; Initialize lặp; hai Source; move/rotate/scale object Source, gồm scale không đều;
save/reopen; disable/enable. So sánh tọa độ/topology Source trước/sau Initialize:
không thay hình học. Xóa controller và Initialize lại không đổi Source UUID hợp lệ.

Gate P1 chỉ pass khi cài và thao tác sidebar thật thành công, Source không bị thay
đổi hình học, quan hệ parent đúng và unregister sạch. Bàn giao bản cài, kết quả và
giới hạn; bước tiếp theo P2.1. Chưa hiển thị đường/patch và chưa hỗ trợ G/R/S control.
