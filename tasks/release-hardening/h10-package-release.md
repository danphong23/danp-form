# H10 — Đóng gói và tài liệu phát hành

**Phụ thuộc H09. Bàn giao:** ZIP cài được, version/tài liệu/report khớp source,
không có file rác hoặc tuyên bố gate chưa qua.

1. Đồng bộ manifest, README, changelog/limitations, hướng dẫn Shape Key,
topology, ownership và API; rà relative links, specification và hashes.
2. Tạo ZIP từ commit đã pass, kiểm nội dung package, `__init__.py` ở root,
license/manifest, không có `__pycache__`, `.pyc`, fixture hoặc file riêng tư.
3. Cài/gỡ trên Blender hỗ trợ, mở fixture, kiểm register/unregister và lưu/mở;
đối chiếu checksum ZIP với commit và báo cáo gate. Không push/publish nếu người
dùng chưa yêu cầu hành động đó.

**Kiểm thử:** package validator, tài liệu validator, install/uninstall, smoke
Blender và hồi quy bắt buộc H09. **Gate:** gói có thể tái tạo, mọi giới hạn được
ghi đúng; không ghi “production ready” nếu một gate bắt buộc FAIL/NOT RUN.
**Commit:** `chore(dan-form): prepare verified release package`.
