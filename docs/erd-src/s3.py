# Sơ đồ tuần tự phần 3: Kho, R&D, Chất lượng, Tài sản, Nhân sự, Kế toán
from s2 import F

F('kho', 'KH1', 'Chuyển kho giữa kho, giữa 2 công ty', 'Có vị trí đang vận chuyển; chuyển khác công ty thì sinh giao dịch nội bộ.', """
sequenceDiagram
  autonumber
  actor A as Kho đi
  participant HT as Hệ thống
  actor B as Kho đến
  A->>HT: Tạo phiếu chuyển kho, hàng, lô, SL, kho đến
  HT->>HT: Kiểm tra tồn khả dụng theo lô
  A->>HT: Quét mã, xác nhận xuất
  HT->>HT: Chuyển tồn sang vị trí đang vận chuyển
  B->>HT: Quét mã, xác nhận nhận
  opt Lệch số lượng
    HT-->>B: Ghi chênh lệch, tạo phiếu xử lý hao hụt
  end
  HT->>HT: Cộng tồn vị trí đến
  opt Nhà máy chuyển cho Văn phòng
    HT->>HT: Sinh giao dịch nội bộ, hóa đơn bán và mua nội bộ
  end
""")

F('kho', 'KH2', 'Kiểm kê kho', 'Chụp số sổ sách, đếm bằng máy quét, duyệt chênh lệch rồi mới điều chỉnh.', """
sequenceDiagram
  autonumber
  actor KK as Tổ kiểm kê
  participant HT as Hệ thống
  actor KTT as Kế toán trưởng
  participant SC as Sổ cái
  KK->>HT: Tạo đợt kiểm kê theo kho, vị trí
  HT->>HT: Chụp số tồn sổ sách lúc bắt đầu
  loop Mỗi vị trí
    KK->>HT: Quét mã hàng và lô, nhập SL thực tế
  end
  HT->>HT: Tính chênh lệch từng dòng
  HT-->>KTT: Bảng chênh lệch và giá trị
  KTT->>HT: Duyệt
  HT->>HT: Điều chỉnh tồn
  HT->>SC: Ghi thừa thiếu vào tài khoản chờ xử lý
""")

F('rd', 'R1', 'Phát triển sản phẩm mới (R&D tách riêng)', 'Chỉ nhóm R&D và Giám đốc thấy; kế toán không truy cập công thức.', """
sequenceDiagram
  autonumber
  actor RD as Nhân viên R&D
  actor GD as Giám đốc
  participant HT as Hệ thống
  RD->>HT: Tạo dự án, nhập công thức phiên bản 1
  HT->>HT: Kiểm tra quyền, chặn mọi nhóm ngoài R&D và Giám đốc
  loop Mỗi lần thử
    RD->>HT: Ghi mẫu thử và kết quả đánh giá
    opt Cần sửa
      RD->>HT: Tạo phiên bản công thức mới, giữ phiên bản cũ
    end
  end
  RD->>GD: Trình công thức đạt
  GD->>HT: Duyệt chốt công thức
  HT->>HT: Khóa phiên bản, ghi nhật ký người duyệt
""")

F('cl', 'Q1', 'Truy xuất lô và thu hồi sản phẩm', 'Yêu cầu của ISO 22000: biết lô lỗi đến từ đâu và đã đi đến đâu.', """
sequenceDiagram
  autonumber
  actor QA as Nhân viên QA
  participant HT as Hệ thống
  actor BH as Phòng bán hàng
  QA->>HT: Nhập số lô nghi lỗi
  HT->>HT: Truy ngược lô nguyên liệu, nhà cung cấp, phiếu nhận
  HT->>HT: Truy xuôi lô thành phẩm, phiếu giao, khách hàng
  HT-->>QA: Cây truy xuất, SL còn trong kho, SL đã giao
  QA->>HT: Mở lệnh thu hồi
  HT->>HT: Khóa tồn các lô liên quan
  HT-->>BH: Danh sách khách cần thu hồi
  BH->>HT: Ghi nhận hàng trả về theo lô
  HT->>HT: Chuyển vị trí cách ly, lập biên bản hủy
""")

F('ts', 'T1', 'Ghi tăng tài sản cố định', 'Bản chạy thử 4 sheet hiện tại đã làm được phần này.', """
sequenceDiagram
  autonumber
  actor KT as Kế toán tài sản
  participant HT as Hệ thống
  participant SC as Sổ cái
  KT->>HT: Chọn dòng chứng từ mua hoặc đơn mua là tài sản
  HT->>HT: Tạo tài sản nháp, nguyên giá bằng thành tiền, gợi ý TK 211, 214 theo loại
  KT->>HT: Đơn vị sử dụng, thời gian sử dụng theo tháng hoặc năm
  HT->>HT: Lập lịch khấu hao, tháng cuối nhận phần làm tròn
  KT->>HT: Xác nhận
  HT->>SC: Nợ 211, Có 331 hoặc 241
""")

F('ts', 'T2', 'Khấu hao cuối tháng và thanh lý', 'Chạy tự động, ghi chi phí khấu hao vào đúng khoản mục.', """
sequenceDiagram
  autonumber
  participant LICH as Lịch chạy tự động
  participant HT as Hệ thống
  participant SC as Sổ cái
  actor KT as Kế toán tài sản
  LICH->>HT: Ngày cuối tháng
  loop Mỗi tài sản đang khấu hao
    HT->>HT: Lấy dòng lịch khấu hao của kỳ
    HT->>SC: Nợ TK chi phí theo khoản mục, Có 214
  end
  HT-->>KT: Bảng khấu hao kỳ
  opt Thanh lý
    KT->>HT: Ngày thanh lý, giá bán
    HT->>HT: Dừng lịch, tính giá trị còn lại
    HT->>SC: Ghi giảm nguyên giá, hao mòn, lãi lỗ thanh lý
  end
""")

F('ts', 'T3', 'Bảo trì thiết bị và chi phí xe', 'Chi phí thuê ngoài đi qua chứng từ mua dịch vụ nên cũng có phiên bản.', """
sequenceDiagram
  autonumber
  actor VH as Tổ bảo trì, đội xe
  participant HT as Hệ thống
  participant CT as Chứng từ mua dịch vụ
  HT->>VH: Nhắc bảo trì theo lịch hoặc số km
  VH->>HT: Tạo yêu cầu bảo trì hoặc nhập chi phí xe
  opt Thuê ngoài
    VH->>CT: Lập chứng từ mua dịch vụ, khoản mục Bảo dưỡng xe hoặc Sửa chữa CCDC
  end
  VH->>HT: Hoàn thành, ghi thời gian dừng máy
  HT-->>VH: Chi phí theo thiết bị, theo xe, theo vùng MN và MB
""")

F('hr', 'H1', 'Chấm công đến bút toán lương', 'Chi phí lương đi vào khoản mục Lương trực tiếp nhà máy hoặc Lương khối Back Office.', """
sequenceDiagram
  autonumber
  actor PNS as Phòng nhân sự
  participant HT as Hệ thống
  actor KTT as Kế toán trưởng
  participant SC as Sổ cái
  HT->>HT: Tổng hợp chấm công và nghỉ phép trong kỳ
  PNS->>HT: Tạo bảng lương kỳ
  loop Mỗi nhân viên
    HT->>HT: Lương theo hợp đồng, công, phụ cấp, BHXH, thuế TNCN
  end
  PNS->>HT: Kiểm tra, trình duyệt
  KTT->>HT: Duyệt
  HT->>SC: Nợ chi phí lương theo khoản mục, Có 334, 338, 3335
  HT-->>PNS: Gửi phiếu lương cho nhân viên
""")

F('hr', 'H2', 'Đề nghị thanh toán', 'Nhân viên chi hộ rồi xin hoàn tiền.', """
sequenceDiagram
  autonumber
  actor NV as Nhân viên
  participant HT as Hệ thống
  actor QL as Quản lý
  actor KT as Kế toán
  participant SC as Sổ cái
  NV->>HT: Tạo đề nghị, chụp hóa đơn, chọn khoản mục
  HT->>HT: Kiểm soát ngân sách
  NV->>HT: Gửi
  QL->>HT: Duyệt hoặc trả lại
  KT->>HT: Kiểm tra chứng từ, ghi sổ
  HT->>SC: Nợ chi phí theo khoản mục, Có 141 hoặc 334
  KT->>HT: Chi tiền
""")

F('kt', 'KT1', 'Tự động hạch toán từ nghiệp vụ', 'Người dùng không định khoản tay; kỳ đã khóa thì không ghi được.', """
sequenceDiagram
  autonumber
  participant NV as Nghiệp vụ gốc
  participant CH as Cấu hình hạch toán
  participant KY as Kỳ kế toán
  participant SC as Sổ cái
  NV->>CH: Loại nghiệp vụ, sản phẩm, đối tác, khoản mục, thuế
  CH-->>NV: TK nợ, TK có theo nhóm sản phẩm, đối tác, thuế
  NV->>KY: Ngày hạch toán thuộc kỳ nào
  alt Kỳ đã khóa
    KY-->>NV: Từ chối, chọn ngày trong kỳ đang mở
  else Kỳ mở
    NV->>SC: Tạo bút toán, gắn chứng từ nguồn
    SC->>SC: Kiểm tra tổng nợ bằng tổng có
    SC-->>NV: Số bút toán
  end
""")

F('kt', 'KT2', 'Khóa sổ cuối kỳ và chốt báo cáo', 'Sau bước chốt, báo cáo kỳ đó không đổi nữa.', """
sequenceDiagram
  autonumber
  actor KTT as Kế toán trưởng
  participant HT as Hệ thống
  participant SC as Sổ cái
  participant BC as Báo cáo
  KTT->>HT: Mở danh sách việc khóa sổ tháng
  HT->>SC: Chạy khấu hao
  HT->>SC: Phân bổ chi phí sản xuất chung vào giá thành
  HT->>SC: Đánh giá chênh lệch tỷ giá
  HT->>HT: Kiểm tra đối soát ngân hàng, hàng nhận chưa có hóa đơn, chứng từ Chờ duyệt
  alt Còn việc dở dang
    HT-->>KTT: Danh sách cần xử lý
  else Đủ điều kiện
    HT->>SC: Kết chuyển doanh thu, chi phí, xác định kết quả
    KTT->>BC: Chốt báo cáo kỳ
    BC->>BC: Lưu giá trị từng chỉ tiêu vào báo cáo đã chốt
    KTT->>HT: Khóa kỳ
  end
""")

F('kt', 'KT3', 'Xem báo cáo và truy ngược', 'Từ chỉ tiêu xuống sổ chi tiết xuống chứng từ gốc.', """
sequenceDiagram
  autonumber
  actor BGD as Ban giám đốc
  participant BC as Báo cáo
  participant SC as Sổ cái
  BGD->>BC: Chọn B01, B02, B03, phân tích chi phí hoặc lãi gộp theo nhãn hàng
  BGD->>BC: Chọn công ty, kỳ, so với kỳ trước hoặc ngân sách
  BC->>SC: Tổng hợp theo công thức chỉ tiêu
  BC-->>BGD: Bảng và biểu đồ
  BGD->>BC: Bấm một chỉ tiêu
  BC-->>BGD: Sổ chi tiết tài khoản
  BGD->>BC: Bấm một dòng
  BC-->>BGD: Chứng từ gốc
  opt Xuất
    BGD->>BC: Xuất Excel hoặc PDF
  end
""")

F('kt', 'KT4', 'Hợp nhất Văn phòng và Nhà máy', 'Loại trừ mua bán nội bộ để ra số của cả tập đoàn.', """
sequenceDiagram
  autonumber
  participant NM as Công ty Nhà máy
  participant VP as Công ty Văn phòng
  participant HT as Hệ thống
  actor KTT as Kế toán trưởng
  NM->>HT: Hóa đơn bán nội bộ cho Văn phòng
  HT->>VP: Tự tạo hóa đơn mua tương ứng
  HT->>HT: Ghi giao dịch nội bộ nối 2 bút toán
  KTT->>HT: Chạy hợp nhất kỳ
  HT->>HT: Cộng báo cáo 2 công ty
  HT->>HT: Loại trừ doanh thu, giá vốn, công nợ nội bộ
  HT->>HT: Loại trừ lãi chưa thực hiện trong tồn kho cuối kỳ
  HT-->>KTT: Báo cáo hợp nhất và bảng loại trừ
""")

F('ch', 'CH1', 'Cập nhật tham số khi luật thay đổi', 'Ví dụ lương cơ sở tăng từ 01/7/2026. Không sửa code, không sửa đè số cũ.', """
sequenceDiagram
  autonumber
  actor KT as Kế toán
  actor KTT as Kế toán trưởng
  participant CH as Cấu hình pháp lý
  participant MP as Mô phỏng
  participant NV as Nghiệp vụ tính toán
  CH-->>KT: Nhắc rà soát trước mốc 01/7
  KT->>CH: Thêm văn bản mới, số hiệu, ngày hiệu lực, tệp
  KT->>CH: Thêm giá trị mới 2.530.000 từ 01/7/2026 cho LUONG_CO_SO
  CH->>MP: Tính thử bảng lương tháng 7 với giá trị nháp
  MP-->>KT: Nhân viên nào đổi số tiền bảo hiểm, chênh lệch bao nhiêu
  KT->>CH: Trình duyệt
  alt Từ chối
    KTT->>CH: Trả lại kèm lý do
  else Duyệt
    KTT->>CH: Duyệt
    CH->>CH: Dòng cũ tự có ngày kết thúc 30/6/2026, dòng mới đang áp dụng
  end
  NV->>CH: Bảng lương tháng 7 hỏi lương cơ sở tại ngày 31/7/2026
  CH-->>NV: 2.530.000
  NV->>CH: Bảng lương tháng 6 tính lại hỏi tại ngày 30/6/2026
  CH-->>NV: 2.340.000
  Note over NV: Kỳ đã khóa sổ không bị tính lại
""")
