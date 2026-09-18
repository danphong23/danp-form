# Phase 2 cuối — Control Edit dễ nhìn

**Trạng thái: đang triển khai trong goal chốt Phase 2.**

## Vấn đề và kết quả cần đạt

Ảnh người dùng cung cấp cho thấy control chưa chọn lẫn vào wire của Source.
0.2.3 đặt màu controller nhưng `_overlay_mode` trả `controller_edit_hidden` và
draw bỏ qua Controller Edit. Giả định native wire đủ rõ chưa đạt ở tình huống này;
phần triển khai cuối chuyển sang overlay BMesh trực tiếp.

Khi vào Controller Edit, người dùng phải phân biệt ngay geometry control đang bật,
selection thực tế, và mesh nền. Lớp màu phải trùng với BMesh controller hiện tại,
đi theo cả preview transform và cancel, không đọc vị trí Source để vẽ Edit proxy.
Không tạo thêm object/geometry hay đổi theme Blender để làm nổi control.

## RE2.1 — Màu geometry đang bật

- [x] Bật highlight mặc định cho Controller Edit qua tùy chọn Control Overlay có
      sẵn; không thêm khối cài đặt vào sidebar.
- [x] Cạnh control chưa chọn có màu cyan và độ dày vừa đủ để khác wire nền.
- [x] Selection lấy từ BMesh thực tế, không lấy từ tên active trong danh sách.
      Không phủ cyan lên cạnh/điểm được chọn; bảo đảm màu selection native rõ.
- [x] Chỉ tô effective geometry còn tồn tại trong proxy. Hidden canonical không
      xuất hiện như handle đang bật. Show Hidden không biến nó thành handle Edit;
      việc xem phần ẩn tiếp tục ở Source.
- [x] Kiểm tra các điểm đơn lẻ và vertex-selection mode. Nếu native điểm chưa
      đủ rõ, thử chấm nhỏ cho điểm chưa chọn; tránh cụm chấm đặc ở ngón tay.
- [x] Mặc định tôn trọng che khuất; dùng X-Ray hiện có khi người dùng cần xuyên
      model. Kiểm tra đường front/back và depth để tránh nhấp nháy hay lệch viền.

## RE2.2 — Theo kịp thao tác, giữ hiệu năng

- [x] Đọc tọa độ/connectivity/selection từ BMesh controller trong Edit; world
      transform chỉ áp dụng một lần. Không giữ BMesh handle qua callback.
- [ ] Chứng minh highlight theo kịp G/R/S preview, confirm và Esc/cancel. Chọn
      cơ chế invalidation sau benchmark; không giả định depsgraph luôn đủ cho
      mọi thay đổi selection hoặc modal preview.
- [x] Idle redraw dùng buffer đã có. Selection chỉ làm mới phần màu cần thiết;
      chuyển góc nhìn không rebuild connectivity. Không resolve từng Source ID
      hoặc tính lại toàn bộ union trong mỗi redraw.
- [x] H/Alt-H, mắt từng dòng và Hide/Show All cập nhật màu cùng proxy, không còn
      nét cũ sau rebuild. Cạnh chung vẫn theo mask canonical ADR-008/ADR-010.
- [x] Benchmark idle và thao tác selection/transform trên nhân vật 50 nhóm và
      Cube. Báo riêng CPU xây buffer, cached draw và độ trễ quan sát; không gọi
      thời gian truy vấn Python là FPS. So sánh bật/tắt highlight cùng điều kiện.

## RE2.3 — Gate live và bàn giao

- [x] MCP: BMesh đổi tọa độ/selection, shared junction, partial Hide, All Hidden,
      Reveal current Source, parent transforms, chuyển context/mode, cleanup.
- [x] Computer Use: vào Edit, bỏ selection vẫn thấy control cyan; chọn một
      điểm/đoạn/loop thấy selection rõ; kiểm tra Ctrl+Alt+Click và Shift cộng đoạn
      nếu công cụ hỗ trợ chord chuột; báo NOT RUN nếu chưa thực hiện được.
- [ ] Computer Use: G/R/S preview và cancel trên fixture thuộc test; không dùng
      biến dạng Source làm tiêu chí, vì writeback/deformation thuộc phase 4.
- [x] Test H/Alt-H, mắt Partial/Hidden/On, Hide/Show All, Back to Model. Chụp
      trước/sau ở front và góc nghiêng, vertex và edge mode, X-Ray bật/tắt.
- [ ] Test undo/redo thật sau Hide/Reveal; xác nhận không có handler/keymap trùng
      sau reload. Test trên file Blender đang mở, không dùng tiến trình riêng.
- [x] Các fixture được dọn; geometry/transform Source nhân vật và Cube không
      thay đổi. Khôi phục mode/selection/trạng thái người dùng, không tự lưu blend.
- [x] Cập nhật interaction contract và regression cũ đang yêu cầu Controller Edit
      không vẽ overlay: thay bằng kiểm tra highlight live, đúng selection/mask,
      không nét đứng im và không rebuild idle. Không xóa coverage hiệu năng cũ.
- [ ] Chạy regression liên quan, validate docs/package; nạp bản đã test. Commit
      riêng từng RE2.1/RE2.2/RE2.3 khi phần đó đã có bằng chứng hoạt động.

## Điều kiện kết thúc

Nhìn được control bật ngay cả khi chưa chọn, selection nổi rõ, ẩn/hiện nhìn thấy
đúng kết quả, transform không có nét màu đứng im, và không tái xuất hiện lag do
đọc mesh/dựng buffer mỗi redraw. Gate chưa thử phải ghi rõ, không tuyên bố toàn
phase 2 hoàn tất chỉ từ các kiểm tra chức năng trước đây.
