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

**Operational scope:** ship an installable, version-consistent functional
candidate. Keep the H09 GPU-overlay and combined large-mesh P95/peak-memory
items explicitly listed; do not describe this archive as performance-certified.

**Progress 2026-09-25:** manifest and `bl_info` are aligned at 0.5.35; English
and Vietnamese guides were refreshed. Documentation links and hashes validate.
The 131-file archive passes package validation and a Blender 5.2.1 extract,
import, register, and unregister smoke test. See the
[H10 package report](../../docs/testing/2026-09-25-h10-package-candidate.md).

**0.5.36 follow-up:** Source Edit Mode Init now builds a direct Controller child
without leaving partial state on failure. The sidebar and English messages were
reviewed with the [Edit Mode Init report](../../docs/testing/2026-09-25-init-edit-mode.md).

**2026-09-26 package follow-up:** `THIRD_PARTY_NOTICES.md` is included at the
extension root. The release runner passes 9/9 static and 11/11 Blender
background suites. The current 0.5.36 archive passed isolated Blender 5.2.1
extract/import/register/unregister smoke; see
`docs/testing/2026-09-26-h10-package-candidate.json` for checksum and report.
H08 GPU, representative performance, C02 UI regression, and copyright-holder
attribution remain open; this is not release certification.

**Superseded 2026-09-27 candidate:** the earlier 147-member source/docs archive
passed its historical validator and Blender smoke test, as recorded in
`docs/testing/2026-09-27-h10-package-candidate.json`. It was removed from `dist/`
after the package was narrowed to user-facing install files. Use the curated
candidate below for testing.

**2026-09-27 curated package:** source commit `bae32be` produces a 39-member ZIP
containing the runtime, manifest/license/notices and purpose-written EN/VI user
guides only. Developer tasks, test reports, caches and local machine paths are
excluded. Package validation and isolated Blender 5.2.1 extract/import/register/
unregister smoke pass. The current runner passes 10/10 static and 11/11
background suites but remains `INCOMPLETE`; the package is not release-certified.
See [`2026-09-27-h10-curated-package-candidate.json`](../../docs/testing/2026-09-27-h10-curated-package-candidate.json).
