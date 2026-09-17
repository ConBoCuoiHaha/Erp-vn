# Sơ đồ tuần tự phần 1: trọng tâm chứng từ mua dịch vụ có phiên bản
KEY = []  # (code, title, why, mermaid)


def S(lst, code, title, why, src):
    lst.append((code, title, why, src.strip('\n')))


STATE = """
stateDiagram-v2
  state "Nháp" as Nhap
  state "Chờ duyệt" as ChoDuyet
  state "Đã cất" as DaCat
  state "Đang sửa" as DangSua
  state "Đã hủy" as Huy
  [*] --> Nhap
  Nhap --> DaCat : Cất, trong hạn mức
  Nhap --> ChoDuyet : Cất, vượt hạn mức
  ChoDuyet --> DaCat : Duyệt
  ChoDuyet --> Nhap : Trả lại
  DaCat --> DangSua : Sửa
  DangSua --> DaCat : Lưu sửa đổi, thêm phiên bản
  DangSua --> DaCat : Hủy sửa, bỏ bản nháp
  DaCat --> Huy : Hủy chứng từ, bút toán đảo
  Huy --> [*]
"""

FOCUS = ['CHUNG_TU_MUA_DV', 'PHIEN_BAN_CHUNG_TU', 'DONG_PHIEN_BAN', 'CHENH_LECH_PHIEN_BAN',
         'QUY_TAC_TU_DONG', 'KHOAN_MUC_CHI_PHI', 'BUT_TOAN', 'DONG_BUT_TOAN',
         'BAO_CAO_CHOT', 'GIA_TRI_BAO_CAO_CHOT', 'NHAT_KY_THAY_DOI']
FOCUS_EXTRA = [
    ('PHIEN_BAN_CHUNG_TU', '||--o{', 'NHAT_KY_THAY_DOI', 'ghi nhật ký'),
    ('DONG_BUT_TOAN', '}o--o{', 'GIA_TRI_BAO_CAO_CHOT', 'tổng hợp vào khi chốt'),
]

S(KEY, 'K1', 'Lập và Cất chứng từ mua dịch vụ',
  'Cất lần đầu khóa lại số gốc lúc mua vào thành Phiên bản 1. Bút toán sinh từ phiên bản này.', """
sequenceDiagram
  autonumber
  actor KT as Kế toán
  participant UI as Màn chứng từ
  participant QT as Bộ quy tắc tự động
  participant DY as Luồng duyệt
  participant DB as Cơ sở dữ liệu
  participant SC as Sổ cái
  KT->>UI: Thêm chứng từ, hoặc Lập từ hợp đồng, từ đơn mua
  UI->>DB: Lấy số MDV kế tiếp từ chuỗi số
  KT->>UI: Chọn nhà cung cấp
  DB-->>UI: Tên, MST, địa chỉ, điều khoản thanh toán, TK công nợ
  loop Mỗi dòng dịch vụ
    KT->>UI: Mã dịch vụ, SL, Đơn giá, Khoản mục CP
    UI->>QT: Tính thành tiền, thuế, TK chi phí
    QT-->>UI: Thành tiền, tiền thuế, tổng theo cây cụ ông cha con
  end
  UI->>DB: Kiểm tra ngân sách khoản mục trong kỳ
  opt Vượt ngân sách
    DB-->>UI: Cảnh báo phần vượt
  end
  KT->>UI: Cất
  UI->>DY: Tổng thanh toán so với hạn mức
  alt Vượt hạn mức
    DY->>DB: Tạo yêu cầu duyệt, trạng thái Chờ duyệt
    DY-->>KT: Chờ người duyệt
  else Trong hạn mức hoặc đã duyệt
    UI->>DB: Tạo Phiên bản 1 gốc lúc mua vào và khóa lại
    UI->>DB: Phiên bản hiện hành bằng phiên bản báo cáo bằng 1
    UI->>SC: Nợ TK chi phí, Nợ 1331, Có 3311 theo Phiên bản 1
    SC-->>UI: Số bút toán
    UI-->>KT: Trạng thái Đã cất, hiện nút Sửa
  end
""")

S(KEY, 'K2', 'Bấm Sửa sau khi Cất',
  'Sửa tạo phiên bản mới, không ghi đè số cũ. Báo cáo vẫn đọc phiên bản báo cáo nên không đổi.', """
sequenceDiagram
  autonumber
  actor KT as Kế toán
  participant UI as Màn chứng từ
  participant QT as Bộ quy tắc tự động
  participant DB as Cơ sở dữ liệu
  participant BC as Báo cáo
  KT->>UI: Bấm Sửa trên chứng từ Đã cất
  UI->>DB: Kiểm tra quyền Sửa chứng từ đã cất
  alt Không có quyền
    UI-->>KT: Báo không đủ quyền, giữ chế độ xem
  else Có quyền
    UI->>DB: Tạo Phiên bản mới dạng nháp, sao chép phiên bản hiện hành
    DB-->>UI: Các dòng mới, mỗi dòng trỏ về dòng gốc lúc mua vào
    UI-->>KT: Chế độ Đang sửa, cột Gốc lúc mua vào nằm cạnh cột đang sửa
    loop Mỗi lần sửa một ô
      KT->>UI: Sửa Tổng, SL, Đơn giá, Thành tiền, Khoản mục hoặc khóa dòng
      UI->>QT: Áp quy tắc tự động, xem K3
      QT-->>UI: Mọi số liên quan tính lại, ô khác gốc được tô màu
    end
    alt Lưu sửa đổi
      KT->>UI: Lưu sửa đổi, nhập lý do
      UI->>DB: Khóa phiên bản mới, đặt làm phiên bản hiện hành
      UI->>DB: Ghi chênh lệch từng trường và nhật ký thay đổi
      Note over DB: Phiên bản báo cáo giữ nguyên, bút toán giữ nguyên
      UI-->>KT: Đã lưu phiên bản mới
    else Hủy sửa
      KT->>UI: Hủy sửa
      UI->>DB: Xóa phiên bản nháp
      UI-->>KT: Trở lại phiên bản hiện hành
    end
  end
  KT->>BC: Mở báo cáo phân tích chi phí
  BC->>DB: Đọc phiên bản báo cáo của từng chứng từ
  BC-->>KT: Số liệu giống hệt trước khi sửa
""")

S(KEY, 'K3', 'Bộ quy tắc tự động tính lại số liệu',
  'Đây là phần MISA không làm được: sửa một con số thì mọi con số phụ thuộc tự đổi theo, tổng luôn khớp tới đồng.', """
sequenceDiagram
  autonumber
  participant UI as Màn chứng từ
  participant QT as Bộ quy tắc tự động
  participant CAY as Cây khoản mục
  UI->>QT: Ô vừa sửa và giá trị mới
  QT->>QT: Đọc quy tắc đang bật cho chứng từ mua dịch vụ
  alt Sửa Tổng tiền dịch vụ
    QT->>QT: Tách dòng đang khóa và dòng tự do
    alt Tổng mới nhỏ hơn tổng dòng khóa
      QT-->>UI: Từ chối, nêu số tiền đang khóa
    else Hợp lệ
      QT->>QT: Chia phần còn lại theo tỷ trọng, phần dư cho dòng có số lẻ lớn nhất
      QT->>QT: Đơn giá bằng Thành tiền chia SL cho từng dòng
    end
  else Sửa tổng của một khoản mục cha trên bảng tổng hợp
    QT->>CAY: Lấy các dòng thuộc nhánh con cháu
    QT->>QT: Chia xuống theo tỷ trọng, bỏ qua dòng khóa
  else Sửa SL hoặc Đơn giá
    QT->>QT: Thành tiền bằng SL nhân Đơn giá
  else Sửa Thành tiền
    QT->>QT: Đơn giá bằng Thành tiền chia SL
  else Đổi Khoản mục CP của dòng
    QT->>CAY: Chuyển số tiền của dòng sang nhánh mới
  end
  QT->>QT: Tiền thuế bằng Thành tiền nhân thuế suất, làm tròn tới đồng
  QT->>CAY: Cộng dồn lên con, cha, ông, cụ
  CAY-->>QT: Tổng từng cấp
  QT-->>UI: Dòng, tổng tiền, thuế, tổng thanh toán, bảng cây, chênh lệch so với gốc
""")

S(KEY, 'K4', 'Lịch sử phiên bản, so sánh, khôi phục số gốc',
  'Mọi lần sửa đều xem lại được; khôi phục số lúc mua vào cũng là một lần sửa có nhật ký.', """
sequenceDiagram
  autonumber
  actor ND as Người dùng
  participant UI as Màn chứng từ
  participant DB as Cơ sở dữ liệu
  ND->>UI: Mở tab Lịch sử phiên bản
  UI->>DB: Đọc mọi phiên bản, người sửa, lý do, thời điểm
  UI-->>ND: Dòng thời gian, đánh dấu bản gốc, bản hiện hành, bản báo cáo
  ND->>UI: Chọn 2 phiên bản để so sánh
  UI->>DB: Đọc chênh lệch từng dòng, từng trường
  UI-->>ND: Bảng cũ và mới, tô màu phần khác, ghi rõ ô do người sửa hay do tự tính
  opt Khôi phục số gốc lúc mua vào
    ND->>UI: Khôi phục gốc cho một dòng hoặc cả chứng từ
    UI->>DB: Tạo phiên bản mới mang số của Phiên bản 1
    Note over DB: Không xóa phiên bản nào
  end
  opt In hoặc xuất
    ND->>UI: In, xuất Excel phiên bản đang xem
  end
""")

S(KEY, 'K5', 'Báo cáo không đổi và truy ngược chứng từ',
  'Báo cáo tổng hợp từ bút toán, mà bút toán chỉ sinh từ phiên bản báo cáo. Số sau sửa chỉ hiện ở cột tham khảo nếu người xem bật lên.', """
sequenceDiagram
  autonumber
  actor ND as Người xem
  participant BC as Báo cáo
  participant DB as Cơ sở dữ liệu
  participant SC as Sổ cái
  ND->>BC: Mở báo cáo phân tích chi phí nhiều kỳ
  alt Kỳ đã chốt
    BC->>DB: Đọc giá trị báo cáo đã chốt
  else Kỳ đang mở
    BC->>SC: Tổng hợp dòng bút toán theo khoản mục và tháng
    Note over SC: Bút toán chỉ sinh từ phiên bản báo cáo nên sửa đổi không lọt vào
  end
  BC-->>ND: Cây cụ ông cha con nhiều kỳ
  ND->>BC: Bấm một ô số
  BC->>SC: Lấy dòng bút toán tạo nên ô đó
  SC-->>BC: Chứng từ gốc
  BC-->>ND: Danh sách, có dấu cho chứng từ đã có phiên bản sửa sau
  opt Xem số sau sửa để tham khảo
    ND->>BC: Bật cột Theo phiên bản hiện hành
    BC->>DB: Đọc phiên bản hiện hành
    BC-->>ND: Cột tham khảo và cột chênh lệch, không ghi vào báo cáo
  end
""")

S(KEY, 'K6', 'Tùy chọn: đưa sửa đổi vào báo cáo',
  'Chỉ dùng khi số gốc sai thật. Không sửa bút toán cũ mà ghi bút toán điều chỉnh vào kỳ đang mở, có Kế toán trưởng duyệt.', """
sequenceDiagram
  autonumber
  actor KT as Kế toán
  actor KTT as Kế toán trưởng
  participant UI as Màn chứng từ
  participant DB as Cơ sở dữ liệu
  participant SC as Sổ cái
  KT->>UI: Đề nghị đưa phiên bản hiện hành vào báo cáo
  UI->>DB: Tạo yêu cầu duyệt kèm bảng chênh lệch
  KTT->>UI: Xem chênh lệch
  alt Từ chối
    KTT->>UI: Từ chối, ghi lý do
    UI->>DB: Giữ nguyên phiên bản báo cáo
  else Duyệt
    KTT->>UI: Duyệt
    UI->>SC: Ghi bút toán điều chỉnh bằng phần chênh lệch vào kỳ đang mở
    Note over SC: Kỳ đã khóa và báo cáo đã chốt không bị đụng tới
    UI->>DB: Đặt phiên bản báo cáo bằng phiên bản hiện hành
  end
""")
