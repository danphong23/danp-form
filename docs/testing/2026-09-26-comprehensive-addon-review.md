# DANP Form — Review tổng quát và làm sạch ngày 2026-09-26

**Kết luận: chưa đủ điều kiện đóng gói phát hành.** Các gate cũ vẫn pass trong
phạm vi của chúng, nhưng audit bổ sung tái hiện lỗi về transaction ownership,
target validation, atomicity và trạng thái tương tác. Đây là kết luận mới trên
baseline `f8dbcaac9d62bb7755d7722103aa2b332d8ed3d4`, phiên bản 0.5.36;
không ghi đè bằng chứng kiểm thử lịch sử.

## Phạm vi và phương pháp

- Khảo sát 25 module runtime, 7.582 dòng Python tại baseline; `operators.py`
  chiếm 2.480 dòng. Đối chiếu core, storage/migration, ownership, mesh/Shape Key,
  proxy, transaction, lifecycle/cache, operator/sidebar, overlay, agent API,
  registration, test runner, package builder và tài liệu chuẩn.
- Đọc và phân tích AST toàn bộ runtime; đối chiếu classes với `CLASSES`, các
  properties/keymaps với đường gọi, và manifest/package inventory.
- Tại thời điểm review ban đầu, release runner trên Blender 5.2.1 LTS,
  Windows 11 đạt 9/9 static suites và 10/10 background suites. Checkpoint C01
  mới nhất đạt 9/9 static và 11/11 background; runner vẫn `INCOMPLETE` do
  GPU/P95/memory chưa được kiểm.
- Chạy [audit probes](../../tests/audit_state_consistency.py) trong tiến trình
  background riêng với scene factory chưa lưu. Không mở, chỉnh hay lưu file
  Blender của người dùng. Observer bị guard trong các probe để kiểm riêng
  ngữ nghĩa lệnh; probe native ownership gọi trực tiếp cầu nối native.
- 11 probe thất bại trước làm sạch; checkpoint C01 mới nhất có 8 PASS và 3 FAIL.
  Ba lỗi còn lại thuộc visibility/selection. Đây là các ca tái hiện riêng,
  không phải 11 nguyên nhân độc lập đã bao phủ mọi tổ hợp giao diện.

## Phát hiện có bằng chứng thực thi

| ID | Mức | Phát hiện và bằng chứng | Trạng thái sau làm sạch |
| --- | --- | --- | --- |
| R01 | P1 | Một transaction agent đang có preview 0,25 đơn vị. Caller thứ hai trước đây hủy transaction gốc. Guard hiện chỉ rollback transaction do operator đó mở; audit giữ transaction và preview (0 displacement loss). Blender background đôi khi chặn dispatch báo transform đang chạy, nên UI feedback trên phiên tương tác chưa được kiểm lại. | FIXED; UI dispatch detail pending |
| R02 | P1 | `transform_session.begin` trước đây tái sử dụng transaction của agent. Native bridge hiện từ chối bằng `OPERATION_BUSY`; regression xác nhận owner và preview giữ nguyên. | FIXED; timer-race matrix pending |
| R03 | P1 | `targets_json` trước đây nhận target cho Source vertex ngoài controller mapping và di chuyển ~0,300000006. Workflow hiện kiểm mapping đã chụp trước solve/writeback. | FIXED; malformed payload matrix pending |
| R04 | P1 | Structural control operations hiện snapshot/rollback definitions, masks, revision và proxy; Reset và Repair còn khôi phục Source ID layers/ownership. Fault injection hiện bao phủ Create/Sync/Hide/eye/Reveal/Delete/Reset/Repair. | FIXED; verify all gates on latest commit |
| R05 | P2 | Native Hide Unselected làm ẩn 2 controller vertices trong khi trạng thái definition vẫn On. DANP Reveal trả FINISHED nhưng cả 2 vẫn ẩn. | OPEN |
| R06 | P2 | H với 4 đỉnh thuộc A/B đang chọn chỉ xử lý A active; 2 đỉnh của B vẫn effective. | OPEN |
| R07 | P2 | Chọn B rồi click mắt ẩn A: selection của B bị thay bằng rỗng dù B không bị ẩn. | OPEN |
| R08 | P2 | Reader selection ngoài Edit Mode trả `set()` thay vì cặp vertex/edge sets. | FIXED, PASS |
| R09 | P2 | WORLD transform trước đây chấp nhận matrix singular qua `inverted_safe`; hiện dùng phép nghịch đảo có kiểm lỗi và kiểm tra giá trị hữu hạn. Static regression từ chối matrix singular. | FIXED; Blender Matrix edge cases pending |
| R10 | P2 | `bind()` chép dunder từ facade sang module: `dan_form.operators.__name__` và spec name đều thành `dan_form`. Metadata cho reload bị thay sai. | FIXED, PASS |
| R11 | P2 | Unregister trước đây để transaction agent mở trong registry. Hiện preview được rollback về Operation Rest và registry được dọn; mid-register failure cũng rollback class/property/handler/overlay/keymap. Background regressions xác nhận. | FIXED; timer race cleanup pending |

P1 là lỗi về quyền ghi/transaction hoặc trạng thái dữ liệu dở dang. P2 là lỗi
đúng đắn/tương tác hoặc lifecycle. Một lỗi được inject để kiểm failure atomicity
không có nghĩa mọi lần Delete bình thường đều lỗi. Busy preview loss được kiểm
trong process riêng, không phải báo cáo mất dữ liệu đã xảy ra trên model live.

### Các đường mã cần sửa

- R01: [operator Deform](../../dan_form/operators.py), phần bắt lỗi của
  `DANFORM_OT_deform.execute`. Chỉ rollback transaction do chính lời gọi đó mở;
  từ chối busy phải giữ operation của chủ sở hữu.
- R02: [native bridge](../../dan_form/blender/transform_session.py), hàm `begin`.
  Ownership của operation phải tường minh; không tái sử dụng transaction chỉ vì
  có cùng Source pointer. Review cả observer/timer và finalization.
- R03: [workflow Deform](../../dan_form/blender/workflows.py), `deform_update`,
  và parser `targets_json`. Kiểm tập ID thuộc captured controller mapping,
  quyền chọn/di chuyển, cấu trúc và finite values trước cập nhật scope/writeback.
  Giữ hỗ trợ các enabled vertices được Blender Proportional thực sự di chuyển.
- R04: [structural operators](../../dan_form/operators.py), trước hết Delete,
  rồi Create/Sync/Hide/Reset. Validate trước ghi, prepare rồi commit, hoặc rollback
  metadata và proxy nếu bước sau thất bại. Probe hiện xác minh Delete; các lệnh
  khác là đường cần kiểm tiếp, chưa khẳng định đều có cùng lỗi đã tái hiện.
- R05–R07: [selection adapters](../../dan_form/blender/selection.py),
  keymaps/operators và [visibility workflows](../../dan_form/blender/workflows.py).
  Native hide flags và definitions không được trở thành hai trạng thái DANP
  không hòa giải được; lệnh mắt không được ghi đè unrelated selection.
- R09: [operation inputs](../../dan_form/core/operation.py),
  `targets_from_transform`: reject singular/non-finite frames trước biến đổi.
- R11: [registration lifecycle](../../dan_form/registration.py): chốt cách
  kết thúc operation khi disable/reload rồi dọn transaction/timer/provenance.
  Không chỉ xóa dictionary rồi bỏ mặc một Source preview chưa được đóng.

## Review kiến trúc, hiệu năng và tài liệu

Các mục dưới đây là phát hiện từ mã/tài liệu hoặc rủi ro cần kiểm thêm;
không gán PASS/FAIL thực thi khi chưa có ca đo tương ứng.

1. **Hợp đồng visibility lệch triển khai.** Schema 3 dùng `enabled` và masks theo
   definition. [Control model](../core/control-model.md),
   [invariants](../core/invariants.md), ADR-008 và một số kế hoạch sidebar vẫn mô
   tả masks chung theo Source IDs. Test core mới lại chấp nhận per-definition
   overlap. Cần ADR đối chiếu hợp đồng đang dùng, migration và tài liệu;
   không downgrade hoặc migrate dữ liệu ngầm trong đợt review.
2. **Mã tương tác lịch sử trong runtime.** Có 5 operator classes không được
   đăng ký: pick-selection tool, select-control-at-cursor, select-segment,
   clear-selection và select-all-controls. Đường pick còn đọc
   `dan_form_add_to_selection` chưa được đăng ký. README/tests đã ghi chúng là
   historical. Review dependency rồi bỏ khỏi runtime hoặc triển khai lại như
   tính năng có gate; giữ bằng chứng lịch sử trong `tests/history`.
3. **Ranh giới module còn mờ.** Operators chứa lifecycle, structural mutation,
   picking, selection, visibility, Shape Key UX và sidebar. Bind qua toàn bộ tên
   underscore che dependency, dù lỗi dunder đã được sửa. Nên tách theo trách
   nhiệm và chuyển dần sang dependencies tường minh sau khi có regression bảo vệ.
4. **Cache/Undo cần state contract chung.** UI token không xét native hide;
   selection readers khác quy tắc lọc hide. Reader selection và lệnh selection
   cần thống nhất cách vertex/edge/face flags được flush. Kiểm restore cache,
   context, selection và definitions theo từng chuỗi Undo/Redo.
5. **Chi phí cần đo trước tối ưu.** Mỗi commit lưu full Source pre/post và proxy
   pre/post vào runtime history không có giới hạn/pruning rõ theo Blender undo
   budget. Ownership lookup lặp scan scene; graph/distance có thể dựng lại theo
   patch/sample. Đây là rủi ro scaling, chưa phải kết luận về P95 hay memory.
6. **Agent context/parity chưa kín.** Một số facade nhận `context` nhưng gọi
   `bpy.ops` theo context toàn cục mà không override. Cần hoặc hỗ trợ context đã
   nhận, hoặc kiểm và từ chối context khác. R01/R02 cho thấy dùng chung primitive
   chưa đủ để chứng minh ownership/parity.
7. **Error/disabled-state contract chưa kín.** Empty selection là tình huống
   bình thường; thông báo raw `NO_PROXY_SELECTION` và việc đổi active row/mode
   trước khi nhận ra control không có handles gây UX khó hiểu. Row quản lý
   definition phải tách rõ với selection hình học, kể cả khi definition bị ẩn.
8. **Registration failure atomicity chưa chứng minh.** `register` đăng ký từng
   class/property/handler nhưng chưa có rollback nếu bước giữa lỗi. Bộ test hiện
   kiểm happy register/unregister cycles; cần thêm lỗi đăng ký giữa chừng.
9. **Gate không kiểm freshness của UI evidence.** Runner trả các chuỗi PASS từ
   nghiệm thu H04/H05/H07 lịch sử cho mọi lần chạy mới. Chúng là tham chiếu lịch
   sử, không phải thao tác UI vừa được chạy trên commit này. Các invariant từ
   audit phải được chuyển vào regression suite trước nghiệm thu mới.
10. **Packaging/license note cũ.** `LICENSE.md` vẫn nói không có production code,
    trong khi manifest khai báo GPL-3.0-or-later và package chứa runtime. Cần
    thay bằng nội dung license tương ứng đã chọn, thống nhất README/manifest và
    kiểm dependency notices. Review không đổi lựa chọn license trong đợt này.

Không thấy đường dẫn máy người dùng, tên Girl Chibi, giải phẫu L/R/front/side,
network transport hoặc thực thi shell hard-code trong runtime. `side/region`
là metadata. Màu UI, ngưỡng số và iteration caps là implementation constants;
cần giải thích/kiểm số học, không coi mọi hằng số là hard-code model. Solver
hiện có affine fit và harmonic displacement solve; giữ baseline đã có bằng
chứng, không thay thuật toán chỉ để làm mã trông đơn giản hơn.

## Làm sạch đã thực hiện

- Bảo toàn dunder metadata trong bind của operators, lifecycle và overlay.
- Chuẩn hóa selection reader luôn trả cặp sets cho context không hỗ trợ.
- Bỏ snapshot `control_groups` và đường truyền snapshot đó ở workflow: solver
  hiện không đọc nó. Giữ tham số core tùy chọn để không phá call compatibility.
  Không tuyên bố cải thiện tốc độ khi chưa đo.
- Thêm regression runtime cho metadata module và return contract; suite
  `live_runtime_boundaries.py` đạt 20 checks sau bổ sung.
- Dọn 4 thư mục bytecode cache phát sinh. Không thấy ZIP/build/`.blend`/log/cache
  được Git tracking; `.gitignore` và package allowlist đã loại cache. Inventory
  baseline package có 134 members, không có bytecode/cache member.
- Giữ docs/tests/history có liên kết và bằng chứng; chúng không phải rác chỉ vì
  cũ. Cập nhật trạng thái phát hành để không dùng PASS lịch sử che lỗi mới.

## Chạy lại bằng chứng

```powershell
python -B tests/run_release_gates.py --blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --report "$env:TEMP\danp-review-gates.json"
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --factory-startup --background --python tests/audit_state_consistency.py -- "$env:TEMP\danp-review-probes.json"
```

Audit script từ chối UI process hoặc scene có filepath. Nó báo
`DEFECTS_FOUND`; exit code 0 chỉ có nghĩa script đã thu thập xong observations.
Traceback của rebuild là lỗi được chủ động inject, không phải bằng chứng PASS.
Không thêm script này vào release runner như một suite PASS giả; chuyển từng
case đã sửa thành regression gates thông thường.

## Thứ tự xử lý

Theo [cleanup tasks](../../tasks/addon-cleanup-review.md): sửa safety/atomicity
trước, thống nhất visibility/selection tiếp theo, rồi tối ưu đo được và hoàn
thiện package/docs. Inspect/hover và batch UX mới chỉ triển khai sau khi các
đường tương tác nền đạt gate. Các việc còn mở không được coi là đã sửa chỉ vì
đã có kế hoạch hoặc vì bộ test cũ pass.

## Addendum — trạng thái sau khi hoàn tất C01

Addendum này cập nhật trạng thái triển khai sau các thay đổi tiếp theo; các phát
hiện R05–R07 và giới hạn release ban đầu ở trên cần được đối chiếu với gate mới
nhất.

- C01 hoàn tất tại revision `5f7fbc2`: lifecycle timer được hủy đúng lúc,
  callback exception và lỗi đăng ký timer được fault-inject, operator được tách
  theo miền trách nhiệm, UI panel có module riêng, và picker không đăng ký cùng
  state preview dư thừa đã được gỡ khỏi runtime.
- Release runner ở revision này đạt 9/9 static suites và 11/11 Blender 5.2.1
  background suites. Chi tiết và giới hạn nằm trong
  [runner report](2026-09-26-release-gates-c01-cleanup.json) và
  [C01 checkpoint](2026-09-26-c01-operation-safety.md).
- Consistency audit đã được chạy lại trên Blender 5.2.1 factory scene sau refactor:
  8 PASS, 3 FAIL. R05 native Hide/Reveal chưa hòa giải với definition state;
  R06 multi-control Hide chưa xử lý toàn bộ control liên quan; R07 thao tác mắt
  có thể xóa selection không liên quan. Fault injection Delete được cập nhật để
  nhắm đúng module operator sau khi tách mã và hiện PASS. Xem
  [C02 audit baseline](2026-09-26-c02-audit-baseline.json).
- Overall release runner hiện `INCOMPLETE`: H08 GPU overlay review và P95/peak
  memory measurement chưa được thực hiện. Bản quyền còn placeholder; chưa được
  coi là sẵn sàng đóng gói/phát hành công khai.
- Các kết quả UI cũ trong review vẫn là bằng chứng lịch sử, không chứng minh
  hành vi Blender UI/MCP đã được kiểm trên revision `5f7fbc2`.
