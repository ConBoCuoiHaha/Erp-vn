# Danh mục nghiệp vụ ERP LiFeOOD
# mỗi dòng: mã | tên | mô tả | căn cứ pháp lý | giai đoạn | mới (1 = bổ sung lần này)
GROUPS = []


def G(code, name, rows):
    items = []
    for line in rows.strip().splitlines():
        p = [x.strip() for x in line.split('|')]
        items.append(dict(code=p[0], name=p[1], desc=p[2], law=p[3], phase=int(p[4]), new=p[5] == '1'))
    GROUPS.append(dict(code=code, name=name, items=items))


G('HT', 'Nền tảng & quản trị hệ thống', """
HT01 | Quản lý 2 pháp nhân và kỳ kế toán | Văn phòng TP.HCM và Nhà máy Tây Ninh dùng chung hệ thống, dữ liệu tách theo công ty | | 1 | 0
HT02 | Người dùng, nhóm quyền, phân quyền theo dòng dữ liệu | Quyền đọc, tạo, sửa, xóa theo chức năng và theo công ty; quyền Sửa chứng từ đã cất cấp riêng | | 1 | 0
HT03 | Đăng nhập an toàn | Mã 2 lớp, khóa tài khoản khi nhập sai nhiều lần, hết phiên tự đăng xuất | | 1 | 0
HT04 | Luồng duyệt nhiều cấp theo hạn mức tiền | Dùng chung cho chứng từ, đơn mua, ngân sách, đề nghị thanh toán, tín dụng, nghỉ phép | | 1 | 0
HT05 | Nhật ký thay đổi và dấu vết kiểm toán | Ai sửa trường nào, giá trị cũ và mới, lúc nào | | 1 | 0
HT06 | Chuỗi đánh số chứng từ | Cấp số tự động theo loại chứng từ, theo công ty, theo năm | | 1 | 0
HT07 | Tìm kiếm nhanh toàn hệ thống | Tìm theo số chứng từ, mã số thuế, mã hàng, số lô, tên nhân viên | | 1 | 0
HT08 | Lưu trữ chứng từ điện tử | Đính kèm hóa đơn, hợp đồng; khóa không cho xóa trong thời hạn lưu trữ | Luật Kế toán 2015 | 1 | 1
HT09 | Nhập, xuất Excel và chuyển dữ liệu từ MISA | Danh mục, số dư đầu kỳ, công nợ, tồn kho, tài sản | | 1 | 0
HT10 | Sao lưu và khôi phục | Sao lưu mã hóa hằng đêm, thử khôi phục hằng tháng | | 1 | 0
HT11 | Bảo vệ dữ liệu cá nhân | Ghi nhận đồng ý xử lý dữ liệu, giới hạn người xem hồ sơ nhân sự và lương, nhật ký truy cập, yêu cầu xem, sửa, xóa dữ liệu | Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 (từ 01/01/2026) | 1 | 1
HT12 | Nhắc hạn tự động | Hạn nộp tờ khai thuế, nộp bảo hiểm, hợp đồng lao động hết hạn, lô sắp hết hạn dùng, đăng kiểm xe | | 1 | 1
HT13 | Ký số chứng từ điện tử | Ký số trên hóa đơn, chứng từ khấu trừ thuế, hồ sơ bảo hiểm | | 1 | 1
""")

G('CH', 'Cấu hình pháp lý', """
CH01 | Bảng tham số pháp lý theo ngày hiệu lực | Mỗi mức thuế suất, giảm trừ, lương tối thiểu, lương cơ sở, tỷ lệ bảo hiểm, giới hạn làm thêm, ngưỡng tài sản lưu thành dòng có ngày bắt đầu và kết thúc áp dụng; không viết cứng trong code | Theo từng văn bản gắn với tham số | 1 | 1
CH02 | Cập nhật tham số khi có văn bản mới | Nhập giá trị mới, số hiệu và tệp văn bản, ngày hiệu lực; kế toán nhập, kế toán trưởng duyệt; không sửa đè giá trị cũ | | 1 | 1
CH03 | Mô phỏng ảnh hưởng trước khi áp dụng | Tính thử bảng lương, tờ khai, khấu hao với tham số mới và so với tham số cũ | | 1 | 1
CH04 | Biểu thuế lũy tiến và bảng bậc | Sửa số bậc, ngưỡng, thuế suất mà không cần sửa code | Luật Thuế TNCN 109/2025/QH15 | 1 | 1
CH05 | Địa bàn và vùng lương tối thiểu | Gán xã, phường nơi đặt văn phòng, nhà máy, kho vào vùng I–IV; nhân viên lấy vùng theo nơi làm việc | Nghị định 293/2025/NĐ-CP | 1 | 1
CH06 | Lịch nghỉ lễ Tết và ngày làm việc theo năm | Ngày lễ, ngày nghỉ bù, số giờ làm việc chuẩn của tháng để tính lương giờ và làm thêm | Bộ luật Lao động 2019 | 1 | 1
CH07 | Nhắc rà soát tham số | Nhắc trước các mốc thay đổi đã biết (01/01, 01/7) và khi một chính sách sắp hết hạn, ví dụ giảm thuế GTGT hết 31/12/2026 | | 1 | 1
CH08 | Lịch sử tham số và gói cập nhật | Xem tham số nào áp dụng cho kỳ nào; xuất, nhập gói tham số giữa bản thử và bản thật | | 1 | 1
""")

G('DM', 'Danh mục dùng chung', """
DM01 | Đối tác | Khách hàng, nhà phân phối, nhà cung cấp, sàn TMĐT; kiểm tra trạng thái mã số thuế | | 1 | 0
DM02 | Sản phẩm, nguyên liệu, dịch vụ | Theo 5 nhãn hàng; tài khoản mặc định theo nhóm | | 1 | 0
DM03 | Đơn vị tính và quy đổi | Hũ, lốc, thùng, kg, lít | | 1 | 0
DM04 | Kho và vị trí kho | Kho nguyên liệu, thành phẩm, cách ly, đang vận chuyển | | 1 | 0
DM05 | Hệ thống tài khoản | Theo chế độ kế toán mới | Thông tư 99/2025/TT-BTC (từ 01/01/2026) | 1 | 1
DM06 | Cây khoản mục chi phí | Cụ – ông – cha – con, gắn tài khoản | | 1 | 0
DM07 | Thuế suất | GTGT 0%, 5%, 8%, 10%, không chịu thuế; bảng tham số có ngày hiệu lực | Nghị quyết 204/2025/QH15, Nghị định 174/2025/NĐ-CP | 1 | 1
DM08 | Điều khoản thanh toán | Số ngày được nợ, chiết khấu thanh toán sớm | | 1 | 0
DM09 | Tiền tệ và tỷ giá | Tỷ giá theo ngày | | 1 | 0
DM10 | Phòng ban, chức danh | Cây phòng ban, gắn khoản mục chi phí | | 1 | 0
DM11 | Tài khoản ngân hàng | Của công ty, nhà cung cấp, nhân viên nhận lương | | 1 | 1
DM12 | Vùng và kênh bán hàng | Miền Nam, Trung, Bắc; kênh GT, MT, Online | | 2 | 0
""")

G('MH', 'Mua hàng', """
MH01 | Yêu cầu mua | Phòng ban đề nghị, kiểm soát ngân sách, trình duyệt | | 1 | 0
MH02 | Đề nghị báo giá và so sánh báo giá | Gửi nhiều nhà cung cấp, chọn giá tốt | | 1 | 0
MH03 | Đơn mua hàng | Theo dõi số đã nhận, đã lập hóa đơn | | 1 | 0
MH04 | Hợp đồng mua khung | Suất ăn, vận tải, bốc xếp; theo dõi giá trị đã thực hiện | | 1 | 0
MH05 | Đối chiếu 3 bên | Đơn mua, phiếu nhận hàng, hóa đơn phải khớp trước khi ghi sổ | | 1 | 0
MH06 | Nhận và kiểm tra hóa đơn đầu vào | Tải hóa đơn điện tử, kiểm tra hóa đơn hợp lệ và mã số thuế người bán | Nghị định 70/2025/NĐ-CP | 1 | 1
MH07 | ★ Chứng từ mua dịch vụ có phiên bản | Sau khi Cất vẫn Sửa được, lưu thành phiên bản, báo cáo không đổi | | 1 | 0
MH08 | ★ Tự động tính lại số liệu chứng từ | Sửa tổng thì phân bổ các dòng; sửa dòng thì cộng dồn theo cây khoản mục | | 1 | 0
MH09 | Trả lại hàng mua, giảm giá hàng mua | Nhận hóa đơn điều chỉnh, xuất trả theo lô | Nghị định 70/2025/NĐ-CP | 1 | 1
MH10 | Phân bổ chi phí mua hàng | Vận chuyển, bốc xếp cộng vào giá nhập kho | | 1 | 1
MH11 | Thu mua nông sản không có hóa đơn | Lập bảng kê thu mua từ người trực tiếp sản xuất, ví dụ yến sào, hạt | Luật Thuế TNDN 67/2025/QH15, Nghị định 320/2025/NĐ-CP | 1 | 1
MH12 | Mua hàng nhập khẩu | Tờ khai hải quan, thuế nhập khẩu, thuế GTGT hàng nhập khẩu, chi phí nhập khẩu | | 3 | 1
MH13 | Đánh giá nhà cung cấp | Chất lượng, đúng hạn, hồ sơ an toàn thực phẩm; yêu cầu của ISO 22000 | | 2 | 1
""")

G('BH', 'Bán hàng, CRM & TMĐT', """
BH01 | Cơ hội bán hàng | Nhà phân phối, siêu thị tiềm năng; giai đoạn chăm sóc | | 2 | 0
BH02 | Báo giá | Áp bảng giá theo kênh và khuyến mãi | | 2 | 0
BH03 | Đơn bán hàng | Giữ chỗ tồn kho, theo dõi đã giao, đã lập hóa đơn | | 2 | 0
BH04 | Bảng giá theo kênh | Giá GT, MT, Online; theo số lượng | | 2 | 0
BH05 | Chương trình khuyến mãi, chiết khấu thương mại | Chiết khấu, tặng hàng, combo; thể hiện đúng trên hóa đơn | Nghị định 70/2025/NĐ-CP | 2 | 1
BH06 | Kiểm soát hạn mức công nợ khách hàng | Vượt hạn mức thì chặn đơn chờ duyệt | | 2 | 0
BH07 | Hợp đồng và chính sách nhà phân phối | Thưởng doanh số, hỗ trợ trưng bày | | 2 | 1
BH08 | Hóa đơn bán hàng điện tử có mã cơ quan thuế | Phát hành, ký số, gửi khách | Nghị định 70/2025/NĐ-CP | 2 | 0
BH09 | Hóa đơn điều chỉnh, thay thế | Xử lý hóa đơn sai sau khi đã gửi cơ quan thuế | Nghị định 70/2025/NĐ-CP | 2 | 1
BH10 | Hàng bán bị trả lại | Nhận lại theo lô, kiểm tra chất lượng, hóa đơn điều chỉnh | | 2 | 1
BH11 | Hàng khuyến mãi, biếu tặng, hàng mẫu | Xuất kho và lập hóa đơn theo quy định | Nghị định 70/2025/NĐ-CP | 2 | 1
BH12 | Chi phí trade marketing, trưng bày | Ghi theo khoản mục của nhãn hàng và kênh | | 2 | 1
BH13 | Đơn sàn thương mại điện tử | Đồng bộ đơn, tồn khả dụng, đối soát tiền về, phí sàn | | 3 | 0
BH14 | Bán hàng xuất khẩu | Thuế suất 0%, tờ khai, chứng từ thanh toán qua ngân hàng | | 3 | 1
""")

G('KHO', 'Kho, lô & mã vạch', """
KHO01 | Nhập kho mua hàng theo lô | Ghi số lô, ngày sản xuất, hạn dùng; kiểm tra chất lượng trước khi nhập | | 2 | 0
KHO02 | Xuất kho bán hàng theo hạn dùng | Lô hết hạn trước xuất trước; chặn lô còn hạn ít hơn yêu cầu của khách | | 2 | 0
KHO03 | Chuyển kho nội bộ | Có vị trí đang vận chuyển | | 2 | 0
KHO04 | Chuyển hàng giữa 2 pháp nhân | Nhà máy xuất cho Văn phòng: chứng từ vận chuyển nội bộ hoặc hóa đơn bán nội bộ | Nghị định 70/2025/NĐ-CP | 2 | 1
KHO06 | Nhập kho thành phẩm từ nhà máy | Ghi số lượng theo lô, ngày sản xuất, hạn dùng; ERP không quản lý lệnh sản xuất | | 2 | 1
KHO07 | Kiểm kê kho | Đếm bằng máy quét, duyệt và xử lý chênh lệch | | 2 | 0
KHO08 | Hàng cận hạn, hết hạn, tiêu hủy | Cảnh báo cận hạn, lập biên bản hủy, hạch toán | | 2 | 1
KHO09 | Cách ly hàng không đạt | Khóa tồn lô, chờ quyết định xử lý | | 2 | 0
KHO10 | Tồn tối thiểu và đề xuất đặt hàng | Dưới mức thì đề xuất mua hoặc báo nhà máy | | 2 | 0
KHO11 | Quét mã vạch và in tem lô | Nhập, xuất, kiểm kê bằng máy quét; in tem nhãn lô | | 2 | 0
KHO12 | Tính giá xuất kho | Bình quân hoặc nhập trước xuất trước; sổ chi tiết vật tư hàng hóa | Thông tư 99/2025/TT-BTC | 2 | 1
""")

G('RD', 'Nghiên cứu & phát triển (R&D, tách riêng)', """
RD01 | Dự án sản phẩm mới | Ý tưởng, thử mẫu, đánh giá, chuyển giao; chỉ nhóm R&D và Giám đốc truy cập, kế toán không xem được | | 3 | 1
RD02 | Công thức theo phiên bản | Nguyên liệu, tỷ lệ, quy trình; mỗi lần sửa tạo phiên bản mới, chốt thì khóa | | 3 | 1
RD03 | Mẫu thử và đánh giá | Kết quả cảm quan, chỉ tiêu kiểm nghiệm từng mẫu | | 3 | 1
RD04 | Duyệt chốt công thức | Giám đốc duyệt, nhật ký ghi người duyệt | | 3 | 1
""")

G('CL', 'Chất lượng & an toàn thực phẩm', """
CL01 | Kiểm tra nguyên liệu đầu vào | Theo điểm kiểm tra khi nhận hàng | | 2 | 0
CL02 | Giám sát điểm kiểm soát tới hạn HACCP | Đo nhiệt độ, thời gian; ngoài giới hạn thì giữ lô | | 3 | 0
CL03 | Kiểm tra thành phẩm trước khi xuất | Lô chưa đạt không cho xuất | | 2 | 0
CL04 | Cảnh báo và hành động khắc phục | Nguyên nhân, biện pháp, hạn xử lý | | 2 | 0
CL05 | Truy xuất nguồn gốc lô | Truy ngược nguyên liệu, nhà cung cấp; truy xuôi khách hàng | | 2 | 0
CL06 | Thu hồi sản phẩm | Khóa tồn, danh sách khách, nhận hàng trả về, hủy | | 2 | 0
CL07 | Hồ sơ công bố sản phẩm | Theo dõi hồ sơ tự công bố, nhãn, hạn giấy tờ an toàn thực phẩm | Luật An toàn thực phẩm 2010 và văn bản hướng dẫn | 2 | 1
CL08 | Lưu mẫu và kiểm nghiệm định kỳ | Lịch gửi mẫu, kết quả kiểm nghiệm theo lô | | 2 | 1
CL09 | Sức khỏe và tập huấn người sản xuất trực tiếp | Khám sức khỏe, xác nhận kiến thức an toàn thực phẩm | Luật An toàn thực phẩm 2010 và văn bản hướng dẫn | 2 | 1
""")

G('TS', 'Tài sản, công cụ, bảo trì & xe', """
TS01 | Ghi tăng tài sản cố định | Ngưỡng 30 triệu, nguyên giá gồm chi phí liên quan; Nợ 211, Nợ 1332 | Thông tư 45/2013/TT-BTC, sửa đổi bởi Thông tư 30/2025/TT-BTC | 1 | 0
TS02 | Tách tài sản khi số lượng lớn hơn 1 | Mỗi tài sản một thẻ, một mã | | 1 | 1
TS03 | Tính và ghi sổ khấu hao hằng tháng | Tính theo ngày ở tháng tăng, giảm; Nợ 627/641/642, Có 214 | Thông tư 45/2013/TT-BTC, sửa đổi bởi Thông tư 30/2025/TT-BTC | 1 | 0
TS04 | Điều chỉnh nguyên giá, thời gian sử dụng | Nâng cấp, sửa chữa lớn; tính lại khấu hao còn lại | Thông tư 45/2013/TT-BTC | 1 | 1
TS05 | Điều chuyển tài sản | Đổi bộ phận sử dụng hoặc chuyển giữa 2 pháp nhân | | 1 | 1
TS06 | Thanh lý, nhượng bán tài sản | Dừng khấu hao, giá trị còn lại vào 811, tiền thu vào 711, lập hóa đơn | | 1 | 1
TS07 | Kiểm kê tài sản cố định | Đối chiếu sổ và thực tế | | 1 | 1
TS08 | Thẻ tài sản và sổ tài sản cố định | In thẻ, sổ theo đơn vị sử dụng | Thông tư 99/2025/TT-BTC | 1 | 1
TS09 | Công cụ dụng cụ | Dưới 30 triệu: xuất dùng, phân bổ qua 242 | Thông tư 99/2025/TT-BTC | 1 | 1
TS10 | Xây dựng cơ bản dở dang | Tập hợp chi phí xây dựng nhà máy qua 241, quyết toán và ghi tăng | Thông tư 99/2025/TT-BTC | 1 | 1
TS11 | Bảo trì thiết bị | Bảo trì định kỳ, sửa chữa, thời gian dừng máy | | 3 | 0
TS12 | Quản lý đội xe | Nhiên liệu, bảo dưỡng, chành xe, đăng kiểm, bảo hiểm xe theo vùng | | 3 | 0
TS13 | Thuê tài sản | Thuê kho, thuê xe; tiền thuê trả trước phân bổ | | 2 | 1
""")

G('KT', 'Kế toán tổng hợp, tiền & công nợ', """
KT01 | Thu chi tiền mặt | Phiếu thu, phiếu chi, sổ quỹ | Thông tư 99/2025/TT-BTC | 1 | 1
KT02 | Thu chi qua ngân hàng | Ủy nhiệm chi, giấy báo có, báo nợ | | 1 | 1
KT03 | Đối soát ngân hàng | Khớp sao kê với chứng từ | | 1 | 0
KT04 | Công nợ phải thu | Tuổi nợ, đối chiếu công nợ, nhắc nợ | | 1 | 0
KT05 | Công nợ phải trả | Lịch thanh toán theo hạn, đối chiếu với nhà cung cấp | | 1 | 0
KT06 | Bù trừ công nợ | Đối tác vừa mua vừa bán | | 1 | 1
KT07 | Tạm ứng và hoàn ứng | Tạm ứng công tác, mua hàng; quyết toán tạm ứng | | 1 | 1
KT08 | Bút toán tổng hợp và điều chỉnh | Nhập tay có duyệt; không sửa bút toán đã khóa kỳ | | 1 | 0
KT09 | Chi phí trả trước | Phân bổ nhiều kỳ qua 242 | Thông tư 99/2025/TT-BTC | 1 | 1
KT10 | Chi phí trích trước | Trích trước chi phí qua 335 | Thông tư 99/2025/TT-BTC | 1 | 1
KT11 | Đánh giá chênh lệch tỷ giá cuối kỳ | Số dư ngoại tệ | | 1 | 1
KT12 | Dự phòng | Giảm giá hàng tồn kho, nợ phải thu khó đòi | | 1 | 1
KT13 | Kết chuyển và xác định kết quả kinh doanh | Kết chuyển doanh thu, chi phí cuối kỳ | Thông tư 99/2025/TT-BTC | 1 | 0
KT14 | Khóa sổ kỳ và chốt báo cáo | Chốt số liệu báo cáo, khóa không cho ghi vào kỳ cũ | | 1 | 0
KT15 | Kiểm tra điều kiện chứng từ | Khoản mua từ 5 triệu phải có thanh toán không dùng tiền mặt để khấu trừ GTGT và tính chi phí được trừ | Luật Thuế GTGT 48/2024/QH15, Nghị định 181/2025/NĐ-CP, Nghị định 320/2025/NĐ-CP | 1 | 1
KT16 | Vay và lãi vay | Hợp đồng vay, lịch trả, trích lãi | | 2 | 1
KT17 | Sổ kế toán | Sổ nhật ký chung, sổ cái, sổ chi tiết | Thông tư 99/2025/TT-BTC | 1 | 1
KT18 | Giao dịch nội bộ và hợp nhất 2 pháp nhân | Nối hóa đơn mua bán nội bộ, loại trừ khi hợp nhất | | 3 | 0
""")

G('NS', 'Khoản mục chi phí & ngân sách', """
NS01 | Lập ngân sách trên cây khoản mục | Sửa cha chia xuống, sửa con cộng lên, khóa khoản | | 1 | 0
NS02 | Duyệt và phiên bản ngân sách | Đã duyệt thì khóa, sửa phải tạo phiên bản mới | | 1 | 0
NS03 | Kiểm soát ngân sách khi phát sinh chi phí | Cảnh báo hoặc bắt duyệt khi vượt | | 1 | 0
NS04 | So sánh kế hoạch và thực tế | Theo khoản mục, tháng, phòng ban | | 1 | 0
NS05 | Phân bổ chi phí chung | Chia chi phí chung cho nhãn hàng, kênh, bộ phận theo tiêu thức | | 2 | 1
""")

G('THUE', 'Thuế', """
THUE01 | Tính thuế GTGT theo thuế suất | Tự áp 8% cho nhóm được giảm từ 10% tới hết 31/12/2026, loại trừ nhóm không được giảm | Nghị quyết 204/2025/QH15, Nghị định 174/2025/NĐ-CP | 1 | 1
THUE02 | Kiểm tra điều kiện khấu trừ GTGT đầu vào | Hóa đơn hợp lệ; thanh toán không dùng tiền mặt từ 5 triệu đã gồm thuế | Luật Thuế GTGT 48/2024/QH15, Nghị định 181/2025/NĐ-CP | 1 | 1
THUE03 | Tờ khai thuế GTGT tháng hoặc quý | Tổng hợp từ hóa đơn, xuất tệp XML nộp qua cổng thuế điện tử | Luật Quản lý thuế, sửa đổi bởi Luật 108/2025/QH15 (từ 01/7/2026) | 1 | 1
THUE04 | Đối chiếu hóa đơn với cơ quan thuế | So hóa đơn trong sổ với dữ liệu hóa đơn điện tử của cơ quan thuế | Nghị định 70/2025/NĐ-CP | 1 | 1
THUE05 | Tạm nộp thuế TNDN theo quý | Ước tính thu nhập chịu thuế, nhắc hạn nộp | Luật Thuế TNDN 67/2025/QH15 | 1 | 1
THUE06 | Quyết toán thuế TNDN năm | Loại chi phí không được trừ; thuế suất 20%, 17% hoặc 15% theo doanh thu; chuyển lỗ | Luật Thuế TNDN 67/2025/QH15, Nghị định 320/2025/NĐ-CP | 1 | 1
THUE07 | Khấu trừ thuế TNCN từ tiền lương | Biểu lũy tiến 5 bậc; giảm trừ 15,5 triệu bản thân, 6,2 triệu mỗi người phụ thuộc | Luật Thuế TNCN 109/2025/QH15 | 2 | 1
THUE08 | Chứng từ khấu trừ thuế TNCN điện tử | Cấp cho người lao động, truyền dữ liệu tới cơ quan thuế | Nghị định 70/2025/NĐ-CP | 2 | 1
THUE09 | Quyết toán thuế TNCN năm | Tổng hợp theo người, nhận ủy quyền quyết toán, xuất tờ khai | Luật Thuế TNCN 109/2025/QH15 | 2 | 1
THUE10 | Khấu trừ thuế thu nhập vãng lai | Cộng tác viên, hợp đồng dịch vụ cá nhân; cam kết thu nhập thấp | Luật Thuế TNCN 109/2025/QH15 và văn bản hướng dẫn | 2 | 1
THUE11 | Hồ sơ giao dịch liên kết | Mua bán giữa Văn phòng và Nhà máy: tờ khai thông tin giao dịch liên kết khi quyết toán | Quy định về giao dịch liên kết | 1 | 1
THUE12 | Lịch nghĩa vụ thuế và tiền chậm nộp | Nhắc hạn nộp tờ khai, nộp tiền; tính tiền chậm nộp khi trễ | Luật Quản lý thuế, sửa đổi bởi Luật 108/2025/QH15 | 1 | 1
THUE13 | Thuế nhà thầu nước ngoài | Khi mua dịch vụ, bản quyền từ nước ngoài | | 3 | 1
""")

G('NSU', 'Lao động & nhân sự', """
NSU01 | Tuyển dụng | Yêu cầu tuyển, hồ sơ ứng viên, phỏng vấn | | 2 | 1
NSU02 | Hồ sơ nhân viên và người phụ thuộc | Số định danh cá nhân dùng làm mã số thuế; đăng ký người phụ thuộc | Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 | 2 | 0
NSU03 | Hợp đồng lao động | Thử việc, xác định và không xác định thời hạn, phụ lục; nhắc hết hạn | Bộ luật Lao động 2019 | 2 | 0
NSU04 | Thang bảng lương và quy chế lương thưởng | Kiểm tra mức thấp nhất không dưới lương tối thiểu vùng | Bộ luật Lao động 2019, Nghị định 293/2025/NĐ-CP | 2 | 1
NSU05 | Ca làm việc | Lịch 3 ca nhà máy, ca hành chính văn phòng, làm đêm | Bộ luật Lao động 2019 | 2 | 1
NSU06 | Chấm công | Máy chấm công, điện thoại; tổng hợp công theo ca | | 2 | 0
NSU07 | Làm thêm giờ | Đăng ký, duyệt; chặn vượt 40 giờ/tháng và giới hạn năm 200 hoặc 300 giờ | Bộ luật Lao động 2019, Nghị định 145/2020/NĐ-CP | 2 | 1
NSU08 | Nghỉ phép, nghỉ lễ Tết | Phép năm 12 ngày cộng thâm niên, nghỉ việc riêng, nghỉ không lương | Bộ luật Lao động 2019 | 2 | 0
NSU09 | Ốm đau, thai sản | Hồ sơ hưởng chế độ, ngày nghỉ, tính lương những ngày nghỉ | Luật Bảo hiểm xã hội 2024 | 2 | 1
NSU10 | Tai nạn lao động, bệnh nghề nghiệp | Khai báo, điều tra, chi trả | Luật An toàn, vệ sinh lao động 2015 | 2 | 1
NSU11 | An toàn vệ sinh lao động | Huấn luyện, khám sức khỏe định kỳ, trang bị bảo hộ | Luật An toàn, vệ sinh lao động 2015 | 2 | 1
NSU12 | Khen thưởng, kỷ luật lao động | Biên bản, quyết định, lưu hồ sơ | Bộ luật Lao động 2019 | 2 | 1
NSU13 | Điều chuyển, thăng chức, điều chỉnh lương | Quyết định, phụ lục hợp đồng, báo tăng mức đóng bảo hiểm | | 2 | 1
NSU14 | Chấm dứt hợp đồng lao động | Trợ cấp thôi việc, chốt thời gian đóng bảo hiểm, quyết toán lương, phép còn lại | Bộ luật Lao động 2019 | 2 | 1
NSU15 | Báo cáo sử dụng lao động định kỳ | Báo cáo 6 tháng và năm | Bộ luật Lao động 2019, Nghị định 145/2020/NĐ-CP | 2 | 1
NSU16 | Đánh giá hiệu suất | KPI theo kỳ, làm căn cứ thưởng | | 3 | 1
NSU17 | Đào tạo | Kế hoạch, lớp học, chứng chỉ, hạn chứng chỉ | | 3 | 1
""")

G('LUONG', 'Tiền lương & bảo hiểm', """
LUONG01 | Thiết lập lương tối thiểu vùng theo địa bàn | Văn phòng TP.HCM và Nhà máy Tây Ninh; cảnh báo lương thấp hơn mức vùng | Nghị định 293/2025/NĐ-CP (từ 01/01/2026) | 2 | 1
LUONG02 | Tính lương thời gian, sản phẩm, khoán | Theo công, theo sản lượng công đoạn | Bộ luật Lao động 2019 | 2 | 0
LUONG03 | Phụ cấp và trợ cấp | Ăn ca, xăng xe, điện thoại, độc hại; đánh dấu khoản chịu thuế, khoản tính đóng bảo hiểm | Luật Thuế TNCN 109/2025/QH15, Luật Bảo hiểm xã hội 2024 | 2 | 1
LUONG04 | Tiền lương làm thêm và làm đêm | 150% ngày thường, 200% ngày nghỉ tuần, 300% lễ Tết; làm đêm thêm ít nhất 30% | Bộ luật Lao động 2019, Nghị định 145/2020/NĐ-CP | 2 | 1
LUONG05 | Tính BHXH, BHYT, BHTN | Người lao động 10,5%, doanh nghiệp 21,5%; mức trần theo lương cơ sở đổi từ 01/7/2026 | Luật Bảo hiểm xã hội 2024, Luật Việc làm 2025 | 2 | 1
LUONG06 | Kinh phí công đoàn | 2% quỹ lương làm căn cứ đóng BHXH | Luật Công đoàn 2024, Nghị định 105/2026/NĐ-CP | 2 | 1
LUONG07 | Khai báo tăng, giảm lao động đóng bảo hiểm | Lập hồ sơ điện tử khi vào làm, nghỉ việc, đổi mức lương | Luật Bảo hiểm xã hội 2024 | 2 | 1
LUONG08 | Thuế TNCN trên bảng lương | Tính cùng bảng lương, nối sang khấu trừ và quyết toán | Luật Thuế TNCN 109/2025/QH15 | 2 | 0
LUONG09 | Tạm ứng lương | Tạm ứng giữa kỳ, trừ khi tính lương | | 2 | 1
LUONG10 | Thưởng và lương tháng 13 | Tính thuế TNCN cho khoản thưởng | | 2 | 1
LUONG11 | Bảng lương, phiếu lương, chi lương qua ngân hàng | Duyệt bảng lương, gửi phiếu lương riêng từng người, tệp chi lương | | 2 | 0
LUONG12 | Hạch toán và phân bổ chi phí lương | Theo khoản mục: lương trực tiếp nhà máy, khối văn phòng; 622, 627, 641, 642 | Thông tư 99/2025/TT-BTC | 2 | 0
LUONG13 | Đề nghị thanh toán và công tác phí | Nhân viên chi hộ, xin hoàn tiền; kiểm soát ngân sách | | 2 | 0
""")

G('BC', 'Báo cáo', """
BC01 | Báo cáo tài chính | Báo cáo tình hình tài chính, kết quả kinh doanh, lưu chuyển tiền tệ, thuyết minh | Thông tư 99/2025/TT-BTC | 1 | 1
BC02 | Báo cáo phân tích chi phí nhiều kỳ theo cây | Theo mẫu MISA công ty đang dùng, truy ngược chứng từ | | 1 | 0
BC03 | Lãi gộp theo nhãn hàng, kênh, vùng, sản phẩm | Báo cáo quản trị cho ban giám đốc | | 2 | 0
BC04 | Nhập xuất tồn và hàng cận hạn | Theo kho, lô, hạn dùng | | 2 | 0
BC05 | Công nợ và tuổi nợ | Phải thu, phải trả theo đối tác, theo hạn | | 1 | 0
BC07 | Bảng kê và tổng hợp thuế | Hóa đơn đầu vào, đầu ra; đối chiếu với tờ khai | | 1 | 1
BC08 | Lao động, lương, bảo hiểm | Quỹ lương, số đóng bảo hiểm, thuế TNCN theo tháng | | 2 | 1
BC09 | Báo cáo hợp nhất 2 pháp nhân | Sau loại trừ giao dịch nội bộ | | 3 | 0
BC10 | Bảng điều hành ban giám đốc | Doanh thu, chi phí, tiền, tồn kho, công nợ trên một màn hình | | 2 | 1
BC11 | Truy ngược từ báo cáo tới chứng từ | Bấm số trên báo cáo ra chứng từ gốc | | 1 | 0
""")
