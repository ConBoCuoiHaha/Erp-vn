# Sơ đồ tuần tự phần 2: Nền tảng, Mua hàng, Ngân sách, Bán hàng
from s1 import S

FLOWS = {}  # module code -> list


def F(mod, *a):
    S(FLOWS.setdefault(mod, []), *a)


F('nen', 'N1', 'Đăng nhập, chọn công ty, tìm kiếm nhanh', 'Người dùng chỉ thấy menu và dữ liệu mà nhóm quyền cho phép.', """
sequenceDiagram
  autonumber
  actor ND as Người dùng
  participant UI as Ứng dụng
  participant AU as Xác thực
  participant DB as Cơ sở dữ liệu
  ND->>UI: Tên đăng nhập, mật khẩu
  UI->>AU: Xác thực
  alt Sai hoặc tài khoản bị khóa
    AU-->>UI: Từ chối, đếm số lần sai
    UI-->>ND: Báo lỗi
  else Đúng
    AU->>DB: Đọc nhóm quyền, các công ty được phép
    AU-->>UI: Phiên làm việc
    ND->>UI: Chọn công ty Văn phòng hoặc Nhà máy
    UI->>DB: Nạp menu và dữ liệu theo quyền
    UI-->>ND: Trang chủ theo vai trò
  end
  opt Tìm kiếm nhanh
    ND->>UI: Gõ số chứng từ, tên đối tác, mã hàng hoặc số lô
    UI->>DB: Tìm trên mọi đối tượng có quyền đọc
    UI-->>ND: Kết quả nhóm theo loại, mở thẳng bản ghi
  end
""")

F('nen', 'N2', 'Luồng duyệt nhiều cấp theo hạn mức', 'Dùng chung cho chứng từ mua dịch vụ, đơn mua, ngân sách, đề nghị thanh toán, tín dụng.', """
sequenceDiagram
  autonumber
  actor NG as Người gửi
  participant DY as Luồng duyệt
  actor C1 as Duyệt cấp 1
  actor C2 as Duyệt cấp 2
  participant DB as Cơ sở dữ liệu
  NG->>DY: Gửi chứng từ
  DY->>DB: Tìm quy trình theo loại chứng từ, công ty, khoảng tiền
  DB-->>DY: Các bước duyệt
  DY->>DB: Tạo yêu cầu duyệt, Chờ duyệt
  DY-->>C1: Thông báo
  alt Cấp 1 từ chối
    C1->>DY: Từ chối kèm ý kiến
    DY-->>NG: Trả về Nháp
  else Cấp 1 duyệt
    C1->>DY: Duyệt
    opt Còn bước tiếp
      DY-->>C2: Thông báo
      C2->>DY: Duyệt hoặc từ chối
    end
    DY->>DB: Đủ bước bắt buộc thì Đã duyệt
    DY-->>NG: Chứng từ đi tiếp
  end
  Note over DB: Mỗi lượt duyệt lưu người, kết quả, ý kiến, thời điểm
""")

F('mh', 'M1', 'Yêu cầu mua đến đơn mua', 'Từ nhu cầu của phòng ban tới đơn gửi nhà cung cấp.', """
sequenceDiagram
  autonumber
  actor PB as Phòng ban
  actor NVM as Nhân viên mua hàng
  participant HT as Hệ thống
  actor NCC as Nhà cung cấp
  PB->>HT: Tạo yêu cầu mua, hàng, SL, ngày cần, khoản mục
  HT->>HT: Kiểm soát ngân sách, trình duyệt
  HT-->>NVM: Yêu cầu đã duyệt
  NVM->>HT: Tạo đề nghị báo giá cho một hoặc nhiều nhà cung cấp
  HT->>HT: Gợi ý giá từ bảng giá NCC và hợp đồng khung
  HT-->>NCC: Gửi đề nghị báo giá
  NCC-->>NVM: Báo giá
  NVM->>HT: Chọn báo giá tốt nhất, xác nhận đơn mua
  opt Vượt hạn mức
    HT->>HT: Trình duyệt đơn mua
  end
  HT->>HT: Tạo phiếu nhập kho dự kiến
  HT-->>NCC: Gửi đơn mua đã xác nhận
""")

F('mh', 'M2', 'Nhận hàng vào kho theo lô', 'Quét mã vạch, ghi lô và hạn sử dụng, kiểm tra chất lượng trước khi nhập.', """
sequenceDiagram
  autonumber
  actor TK as Thủ kho
  participant MQ as Máy quét mã vạch
  participant HT as Hệ thống
  participant CL as Chất lượng
  participant SC as Sổ cái
  TK->>MQ: Quét mã phiếu nhập
  MQ->>HT: Mở phiếu nhập theo đơn mua
  loop Mỗi mặt hàng
    TK->>MQ: Quét mã hàng, nhập SL thực nhận
    TK->>HT: Số lô, ngày sản xuất, hạn sử dụng
  end
  HT->>CL: Tạo phiếu kiểm tra theo điểm kiểm tra nhập mua
  alt Không đạt
    CL->>HT: Mở cảnh báo, chuyển hàng sang vị trí cách ly
  else Đạt
    CL->>HT: Cho phép nhập
  end
  TK->>HT: Xác nhận nhập kho
  HT->>HT: Cộng tồn theo vị trí và lô, tạo lớp giá trị tồn
  HT->>SC: Nợ TK kho, Có hàng đã nhận chưa có hóa đơn
  opt Giao thiếu
    HT->>HT: Tạo phiếu nhận phần còn lại
  end
""")

F('mh', 'M3', 'Hóa đơn nhà cung cấp và thanh toán', 'Đối chiếu 3 bên: đơn mua, phiếu nhận, hóa đơn.', """
sequenceDiagram
  autonumber
  actor KT as Kế toán công nợ
  participant HT as Hệ thống
  participant SC as Sổ cái
  KT->>HT: Tạo hóa đơn NCC từ đơn mua hoặc từ hóa đơn điện tử nhận về
  HT->>HT: So SL và giá giữa đơn mua, phiếu nhận, hóa đơn
  alt Lệch quá dung sai
    HT-->>KT: Chặn ghi sổ, nêu dòng lệch
  else Khớp
    KT->>HT: Ghi sổ
    HT->>SC: Nợ hàng nhận chưa có hóa đơn, Nợ 1331, Có 331
  end
  HT->>HT: Tính hạn thanh toán theo điều khoản
  opt Đến hạn
    KT->>HT: Lập thanh toán
    HT->>SC: Nợ 331, Có tiền
    HT->>HT: Đối trừ công nợ với hóa đơn
  end
""")

F('ns', 'NS1', 'Lập ngân sách trên cây khoản mục', 'Sửa ô cha thì chia xuống, sửa ô con thì cộng lên; tổng khớp tới đồng.', """
sequenceDiagram
  autonumber
  actor NL as Người lập ngân sách
  participant UI as Màn ngân sách
  participant QT as Bộ quy tắc tự động
  participant DB as Cơ sở dữ liệu
  NL->>UI: Tạo ngân sách năm trên cây khoản mục
  opt Khởi tạo từ năm trước
    UI->>DB: Lấy thực tế năm trước theo khoản mục và tháng
  end
  loop Mỗi lần sửa
    NL->>UI: Sửa một ô ở bất kỳ cấp nào
    alt Ô của khoản con
      UI->>QT: Gán giá trị
    else Ô của khoản cha, ông, cụ
      QT->>QT: Chia xuống con cháu theo tỷ trọng hoặc chia đều, bỏ qua khoản khóa
      opt Tổng mới nhỏ hơn tổng khoản khóa
        QT-->>UI: Từ chối, nêu lý do
      end
    end
    QT->>QT: Cộng dồn lên cha, ông, cụ
    QT->>DB: Lưu lịch sử phân bổ
    UI-->>NL: Cả cây cập nhật
  end
  NL->>UI: Trình duyệt ngân sách
  UI->>DB: Đã duyệt thì khóa, muốn sửa phải lập phiên bản ngân sách mới
""")

F('ns', 'NS2', 'Kiểm soát ngân sách khi phát sinh chi phí', 'Chạy khi lập yêu cầu mua, chứng từ mua dịch vụ, đề nghị thanh toán.', """
sequenceDiagram
  autonumber
  participant CT as Chứng từ phát sinh chi phí
  participant NS as Kiểm soát ngân sách
  participant DB as Cơ sở dữ liệu
  actor ND as Người lập
  CT->>NS: Khoản mục, kỳ, số tiền
  NS->>DB: Kế hoạch, đã thực hiện, đã cam kết qua đơn mua
  NS->>NS: Còn lại bằng kế hoạch trừ thực hiện trừ cam kết
  alt Còn đủ
    NS-->>CT: Cho qua
  else Vượt trong dung sai
    NS-->>ND: Cảnh báo, vẫn cho lưu
  else Vượt quá dung sai
    NS-->>ND: Bắt buộc trình duyệt vượt ngân sách
  end
""")

F('bh', 'B1', 'Báo giá đến đơn bán, kiểm tra hạn mức tín dụng', 'Đơn vượt hạn mức bị chặn cho tới khi kế toán công nợ duyệt.', """
sequenceDiagram
  autonumber
  actor NVB as Nhân viên bán hàng
  participant HT as Hệ thống
  actor KTCN as Kế toán công nợ
  actor KH as Nhà phân phối
  NVB->>HT: Tạo báo giá, chọn khách, kênh, vùng
  HT->>HT: Áp bảng giá theo kênh và khuyến mãi đang chạy
  HT-->>KH: Gửi báo giá
  KH-->>NVB: Đồng ý
  NVB->>HT: Xác nhận đơn bán
  HT->>HT: Công nợ hiện tại cộng đơn đang mở cộng đơn này so với hạn mức
  alt Vượt hạn mức
    HT->>HT: Chặn đơn, Chờ duyệt tín dụng
    KTCN->>HT: Duyệt, từ chối hoặc chuyển cấp trên
  end
  HT->>HT: Giữ chỗ tồn kho, tạo phiếu xuất
  opt Thiếu hàng
    HT->>HT: Đề xuất mua hoặc báo nhà máy
  end
""")

F('bh', 'B2', 'Giao hàng FEFO theo lô', 'Lô hết hạn trước xuất trước; quét sai lô thì không cho xác nhận.', """
sequenceDiagram
  autonumber
  actor TK as Thủ kho
  participant HT as Hệ thống
  participant MQ as Máy quét mã vạch
  participant SC as Sổ cái
  HT->>HT: Chọn lô theo hạn sử dụng gần nhất
  HT->>HT: Loại lô còn hạn ít hơn mức khách yêu cầu
  HT-->>TK: Phiếu lấy hàng theo vị trí và lô
  loop Mỗi dòng
    TK->>MQ: Quét vị trí, mã hàng, số lô
    MQ->>HT: Kiểm tra đúng lô chỉ định
    opt Sai lô
      HT-->>TK: Cảnh báo, không cho xác nhận
    end
  end
  TK->>HT: Xác nhận giao
  HT->>HT: Trừ tồn theo lô, ghi lô nào giao cho khách nào
  HT->>SC: Nợ giá vốn, Có thành phẩm
""")

F('bh', 'B3', 'Hóa đơn bán và hóa đơn điện tử', 'Phát hành, cấp mã cơ quan thuế, gửi khách.', """
sequenceDiagram
  autonumber
  actor KT as Kế toán bán hàng
  participant HT as Hệ thống
  participant HD as Nhà cung cấp hóa đơn điện tử
  participant CQT as Cơ quan thuế
  participant SC as Sổ cái
  KT->>HT: Tạo hóa đơn từ số lượng đã giao
  HT->>SC: Nợ 131, Có doanh thu, Có 33311
  KT->>HT: Phát hành hóa đơn điện tử
  HT->>HD: Dữ liệu hóa đơn, ký số
  HD->>CQT: Gửi cấp mã
  alt Được cấp mã
    CQT-->>HD: Mã cơ quan thuế
    HD-->>HT: Ký hiệu, số, mã tra cứu, tệp XML
    HT-->>KT: Gửi email hóa đơn cho khách
  else Bị từ chối
    CQT-->>HD: Lý do
    HD-->>HT: Trạng thái lỗi
    HT-->>KT: Báo sửa và phát hành lại
  end
""")

F('bh', 'B4', 'Thu tiền và đối soát ngân hàng', 'Hệ thống gợi ý khớp giao dịch với hóa đơn.', """
sequenceDiagram
  autonumber
  participant NH as Ngân hàng
  participant HT as Hệ thống
  actor KT as Kế toán
  participant SC as Sổ cái
  NH->>HT: Sao kê, nhập tệp hoặc đồng bộ
  loop Mỗi giao dịch
    HT->>HT: Gợi ý khớp theo số tiền, nội dung, số hóa đơn, đối tác
    alt Khớp chắc chắn
      HT->>SC: Ghi thu, đối trừ hóa đơn
    else Cần xác nhận
      HT-->>KT: Danh sách đề xuất
      KT->>HT: Chọn hóa đơn hoặc ghi khoản khác như phí, lãi
      HT->>SC: Ghi sổ và đối trừ
    end
  end
  HT-->>KT: Số dư sổ khớp số dư sao kê
""")

F('bh', 'B5', 'Đơn sàn thương mại điện tử', 'Đơn Shopee, Lazada, Tiki, TikTok Shop tự về hệ thống.', """
sequenceDiagram
  autonumber
  participant SAN as Sàn TMĐT
  participant HT as Hệ thống
  actor TK as Thủ kho
  participant SC as Sổ cái
  SAN->>HT: Đơn mới theo lịch đồng bộ
  HT->>HT: Khớp mã hàng trên sàn với sản phẩm, tạo đơn bán kênh Online
  HT->>TK: Phiếu xuất FEFO
  TK->>HT: Đóng gói, giao đơn vị vận chuyển
  HT->>SAN: Cập nhật trạng thái và tồn khả dụng
  SAN-->>HT: Đối soát tiền về và phí sàn
  HT->>SC: Ghi doanh thu, phí sàn vào khoản mục chi phí bán hàng online
""")
