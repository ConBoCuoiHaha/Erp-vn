# Danh mục cấu hình ERP LiFeOOD
# dòng: nhóm cấu hình | mục | nội dung cấu hình | loại (L luật, Q quy chế công ty, H hệ thống) | nghiệp vụ dùng
SECTIONS = []


def S(code, name, rows):
    items = []
    for line in rows.strip().splitlines():
        p = [x.strip() for x in line.split('|')]
        items.append(dict(group=p[0], name=p[1], desc=p[2], kind=p[3], used=p[4]))
    SECTIONS.append(dict(code=code, name=name, items=items))


S('HT', 'Hệ thống & doanh nghiệp', """
Doanh nghiệp | Thông tin pháp nhân | Tên, mã số thuế, địa chỉ, người đại diện, kế toán trưởng, cơ quan thuế quản lý, mã đơn vị BHXH; riêng cho Văn phòng và Nhà máy | Q | HT01
Doanh nghiệp | Năm tài chính và kỳ kế toán | Tháng bắt đầu năm tài chính, kỳ tháng hoặc quý, ngày khóa sổ | Q | HT01, KT14
Doanh nghiệp | Chế độ và phương pháp kế toán | Chế độ kế toán, đồng tiền hạch toán, phương pháp tính thuế GTGT, phương pháp hạch toán hàng tồn kho | L | DM05, KT17
Định dạng | Số và làm tròn | Dấu phân cách, số chữ số lẻ của tiền, số lượng, đơn giá, tỷ giá, tỷ lệ; cách làm tròn | H | toàn hệ thống
Định dạng | Ngày giờ và ngôn ngữ | Định dạng ngày, múi giờ, tiếng Việt | H | toàn hệ thống
Chứng từ | Chuỗi đánh số | Tiền tố, độ dài, đặt lại theo năm hoặc tháng, riêng từng loại chứng từ và công ty | Q | HT06
Chứng từ | Mẫu in chứng từ và sổ | Mẫu phiếu thu, phiếu chi, phiếu nhập xuất, sổ kế toán theo chế độ kế toán; logo, chữ ký, người lập | L | HT08, KT17
Chứng từ | Ký số | Chứng thư số, nhà cung cấp, loại chứng từ phải ký | H | HT13
Người dùng | Vai trò và quyền | Quyền theo chức năng, theo công ty, theo phòng ban; quyền xem lương, quyền sửa chứng từ đã cất, quyền sửa cấu hình | Q | HT02
Người dùng | Luồng duyệt | Loại chứng từ, khoảng tiền, các bước, người hoặc nhóm duyệt, duyệt thay khi vắng | Q | HT04
Bảo mật | Đăng nhập | Độ dài mật khẩu, đổi mật khẩu định kỳ, mã 2 lớp bắt buộc cho nhóm nào, thời gian hết phiên, số lần sai bị khóa | H | HT03
Bảo mật | Dữ liệu cá nhân | Mục đích xử lý, thời hạn lưu, ai được xem hồ sơ và lương, che số CCCD, nhật ký truy cập | L | HT11
Vận hành | Sao lưu | Giờ sao lưu, nơi lưu, số bản giữ lại, nhắc thử khôi phục | H | HT10
Vận hành | Nhắc hạn và thông báo | Loại nhắc, trước bao nhiêu ngày, gửi cho ai, qua email hay trong app | Q | HT12
Kết nối | Dịch vụ bên ngoài | Hóa đơn điện tử, ngân hàng, cổng BHXH, sàn TMĐT, máy chấm công; tài khoản kết nối | H | BH08, KT03, LUONG07, BH13, NSU06
""")

S('PL', 'Pháp lý dùng chung', """
Văn bản | Danh mục văn bản pháp lý | Số hiệu, loại, ngày ban hành, ngày hiệu lực, hết hiệu lực, văn bản thay thế, tệp đính kèm | L | CH01, CH02
Tham số | Bảng tham số theo ngày hiệu lực | Mọi mức tiền, tỷ lệ, ngưỡng theo luật; mỗi giá trị có ngày bắt đầu, kết thúc, văn bản căn cứ | L | CH01
Tham số | Duyệt thay đổi tham số | Ai được nhập, ai duyệt, bắt buộc đính kèm văn bản | Q | CH02
Tham số | Mô phỏng | Phạm vi được tính thử: bảng lương, tờ khai, khấu hao; kỳ mẫu | H | CH03
Địa bàn | Địa bàn và vùng lương tối thiểu | Tỉnh, xã phường sau sắp xếp địa giới, vùng I–IV, ngày áp dụng | L | CH05, LUONG01
Lịch | Lịch nghỉ lễ Tết từng năm | Ngày lễ, nghỉ bù, làm bù, hệ số làm thêm ngày lễ | L | CH06, NSU08
Lịch | Mốc rà soát | Các mốc nhắc rà soát 01/01, 01/7 và ngày hết hạn của chính sách tạm thời | Q | CH07
""")

S('KT', 'Kế toán tổng hợp', """
Tài khoản | Hệ thống tài khoản | Tài khoản cấp 1, 2 theo chế độ kế toán; tài khoản chi tiết của công ty; bắt buộc theo dõi đối tượng, khoản mục | L | DM05
Tài khoản | Định khoản tự động | Bảng tài khoản Nợ, Có mặc định cho từng loại nghiệp vụ: mua, bán, nhập xuất kho, lương, bảo hiểm, thuế, khấu hao, chênh lệch tỷ giá, làm tròn | Q | KT08
Tài khoản | Tài khoản theo nhóm hàng và đối tác | Tài khoản kho, giá vốn, doanh thu theo nhóm sản phẩm; phải thu, phải trả theo nhóm đối tác | Q | DM01, DM02
Tiền | Quỹ và tài khoản ngân hàng | Quỹ tiền mặt, tài khoản ngân hàng, định mức tồn quỹ | Q | KT01, KT02
Tiền | Đối soát ngân hàng | Mẫu sao kê từng ngân hàng, quy tắc tự khớp theo số tiền, nội dung, số hóa đơn | H | KT03
Tiền | Ngưỡng thanh toán không dùng tiền mặt | Mức tiền bắt buộc chuyển khoản để khấu trừ thuế GTGT và tính chi phí được trừ; cảnh báo hoặc chặn | L | KT15, THUE02
Công nợ | Khoảng tuổi nợ và hạn mức mặc định | Các khoảng quá hạn, hạn mức công nợ mặc định theo nhóm khách | Q | KT04, BH06
Công nợ | Trích lập dự phòng | Mức trích dự phòng nợ phải thu khó đòi và giảm giá hàng tồn kho theo văn bản hiện hành | L | KT12
Tỷ giá | Nguồn và loại tỷ giá | Ngân hàng lấy tỷ giá, tỷ giá mua, bán, chuyển khoản; tỷ giá đánh giá cuối kỳ | L | KT11
Phân bổ | Chi phí trả trước và trích trước | Thời gian phân bổ mặc định theo loại, tài khoản | Q | KT09, KT10
Cuối kỳ | Kết chuyển | Thứ tự bút toán kết chuyển, tài khoản xác định kết quả | L | KT13
Cuối kỳ | Khóa sổ | Việc phải xong trước khi khóa: đối soát, khấu hao, phân bổ, chứng từ chờ duyệt | Q | KT14
Hợp nhất | Giao dịch nội bộ | Cặp công ty, tài khoản nội bộ, quy tắc tự tạo hóa đơn đối ứng, bút toán loại trừ | Q | KT18
""")

S('THUE', 'Thuế, phí và lệ phí', """
Thuế GTGT | Danh mục thuế suất | Mã thuế, thuế suất, không chịu thuế, không kê khai; tài khoản thuế đầu vào, đầu ra | L | DM07, THUE01
Thuế GTGT | Chính sách giảm thuế | Nhóm hàng được giảm, nhóm loại trừ, mức giảm, thời gian áp dụng | L | THUE01
Thuế GTGT | Kỳ kê khai và mẫu tờ khai | Tháng hoặc quý, phiên bản mẫu tờ khai, bảng kê kèm theo | L | THUE03
Thuế TNDN | Thuế suất và ưu đãi | Thuế suất theo doanh thu năm, ưu đãi theo địa bàn hoặc ngành nếu có | L | THUE06
Thuế TNDN | Chi phí không được trừ | Danh mục khoản chi bị loại, điều kiện chứng từ, ngưỡng thanh toán | L | THUE06, KT15
Thuế TNDN | Tạm nộp và chuyển lỗ | Cách tạm nộp theo quý, tỷ lệ tối thiểu, thời gian chuyển lỗ theo văn bản hiện hành | L | THUE05, THUE06
Thuế TNCN | Biểu thuế lũy tiến | Số bậc, ngưỡng, thuế suất | L | THUE07
Thuế TNCN | Giảm trừ gia cảnh | Mức cho bản thân, người phụ thuộc; điều kiện người phụ thuộc | L | THUE07
Thuế TNCN | Thu nhập miễn thuế và không tính thuế | Khoản phụ cấp, trợ cấp không tính vào thu nhập chịu thuế và mức giới hạn | L | LUONG03, THUE07
Thuế TNCN | Khấu trừ thu nhập vãng lai | Thuế suất khấu trừ, ngưỡng mỗi lần chi trả, cam kết thu nhập thấp | L | THUE10
Thuế TNCN | Quyết toán năm | Điều kiện nhận ủy quyền quyết toán, mẫu tờ khai | L | THUE09
Thuế khác | Thuế nhà thầu | Tỷ lệ GTGT và TNDN theo loại dịch vụ | L | THUE13
Thuế khác | Thuế nhập khẩu, xuất khẩu | Biểu thuế theo mã hàng, tỷ giá tính thuế | L | MH12, BH14
Phí, lệ phí | Lệ phí trước bạ | Tỷ lệ theo loại tài sản khi mua xe, tài sản phải đăng ký | L | TS01
Phí, lệ phí | Phí môi trường và phí khác | Phí bảo vệ môi trường đối với nước thải nhà máy, phí sử dụng đường bộ, phí kiểm nghiệm, lệ phí hồ sơ an toàn thực phẩm | L | TS12, CL07, CL08
Phí, lệ phí | Lệ phí môn bài | Đã bãi bỏ từ 01/01/2026; giữ mục để tra cứu các năm trước | L | —
Hóa đơn | Hóa đơn điện tử | Nhà cung cấp, ký hiệu, mẫu số, loại hóa đơn, cách gửi cơ quan thuế, email gửi khách | L | BH08, BH09
Nghĩa vụ | Lịch hạn nộp | Hạn nộp từng loại tờ khai và tiền thuế; cách tính tiền chậm nộp | L | THUE12
Giao dịch liên kết | Bên liên kết | Danh sách bên liên kết, trường hợp được miễn lập hồ sơ | L | THUE11
""")

S('LUONG', 'Tiền lương', """
Kỳ lương | Kỳ và ngày chốt | Kỳ lương tháng, ngày chốt công, ngày trả lương, tạm ứng giữa kỳ | Q | LUONG11, LUONG09
Kỳ lương | Công chuẩn | Công theo lịch thực tế hoặc số ngày cố định; giờ làm một ngày; ngày nghỉ tuần | Q | LUONG02
Ca | Ca làm việc | Giờ vào, giờ ra, nghỉ giữa ca, ca đêm, ca gãy; phụ cấp theo ca | Q | NSU05
Hình thức | Hình thức trả lương | Theo thời gian, theo sản phẩm (đơn giá từng công đoạn), khoán | Q | LUONG02
Hình thức | Thang bảng lương | Chức danh, bậc, mức lương, hệ số; kiểm tra không thấp hơn lương tối thiểu vùng | L | NSU04, LUONG01
Thành phần lương | Danh mục thành phần lương | Mã, tên, công thức, thứ tự tính; có chịu thuế TNCN không, có tính đóng bảo hiểm không; tài khoản và khoản mục hạch toán | Q | LUONG02, LUONG12
Thành phần lương | Công thức lương | Soạn công thức bằng mã tham số và thành phần, xem trước kết quả cho một nhân viên | H | LUONG02
Phụ cấp | Phụ cấp và trợ cấp | Ăn ca, xăng xe, điện thoại, nhà ở, trách nhiệm, độc hại, chuyên cần: mức, điều kiện, cách tính theo công | Q | LUONG03
Làm thêm | Hệ số làm thêm và làm đêm | Ngày thường, nghỉ tuần, lễ Tết, làm đêm, làm thêm vào ban đêm | L | LUONG04
Làm thêm | Giới hạn làm thêm | Giờ tối đa theo ngày, tháng, năm; ngành được làm thêm tới mức cao | L | NSU07
Thử việc | Lương thử việc | Tỷ lệ tối thiểu so với lương chính thức, thời gian thử việc tối đa theo loại công việc | L | NSU03
Thưởng | Thưởng và lương tháng 13 | Loại thưởng, công thức theo KPI, doanh số, thâm niên; cách tính thuế cho khoản thưởng | Q | LUONG10
Khấu trừ | Khoản khấu trừ | Tạm ứng, bồi thường thiệt hại; mức khấu trừ tối đa mỗi tháng theo luật lao động | L | LUONG09
Thôi việc | Trợ cấp thôi việc, mất việc | Công thức theo thời gian làm việc không đóng BHTN; lương làm căn cứ | L | NSU14
Chi trả | Làm tròn và chi lương | Làm tròn thực lĩnh, mẫu tệp chi lương theo ngân hàng | Q | LUONG11
Chi trả | Phiếu lương | Mẫu phiếu lương, gửi riêng từng người, mật khẩu mở phiếu | Q | LUONG11
Hạch toán | Hạch toán lương | Tài khoản 334, 622, 627, 641, 642 theo phòng ban; khoản mục chi phí lương | Q | LUONG12
""")

S('BHXH', 'Bảo hiểm & công đoàn', """
Tỷ lệ | Tỷ lệ đóng bảo hiểm | BHXH hưu trí tử tuất, ốm đau thai sản, tai nạn lao động bệnh nghề nghiệp, BHYT, BHTN; phần người lao động và doanh nghiệp | L | LUONG05
Căn cứ | Tiền lương làm căn cứ đóng | Thành phần lương được tính đóng: mức lương, phụ cấp lương, khoản bổ sung xác định | L | LUONG05
Căn cứ | Mức sàn và mức trần | Sàn theo lương tối thiểu vùng; trần BHXH, BHYT theo lương cơ sở; trần BHTN theo lương tối thiểu vùng | L | LUONG05
Đối tượng | Đối tượng tham gia | Loại hợp đồng, thời hạn hợp đồng, người nước ngoài, người làm không trọn thời gian | L | LUONG05, LUONG07
Tăng giảm | Quy tắc tăng, giảm trong tháng | Vào làm, nghỉ việc giữa tháng; nghỉ không lương, ốm đau đủ số ngày thì không đóng | L | LUONG07
Chế độ | Ốm đau, thai sản | Mức hưởng, số ngày tối đa, căn cứ tính | L | NSU09
Chế độ | Tai nạn lao động, bệnh nghề nghiệp | Trách nhiệm chi trả của doanh nghiệp, mức bồi thường | L | NSU10
Đơn vị | Thông tin đơn vị tham gia | Mã đơn vị, cơ quan BHXH, phương thức đóng, kết nối nộp hồ sơ điện tử | H | LUONG07
Công đoàn | Kinh phí và đoàn phí công đoàn | Tỷ lệ kinh phí trên quỹ lương đóng BHXH, tỷ lệ và mức tối đa đoàn phí | L | LUONG06
Tự nguyện | Bảo hiểm công ty tự mua | Bảo hiểm sức khỏe, tai nạn: đối tượng, mức phí, có tính vào thu nhập chịu thuế không | Q | LUONG03
""")

S('NSU', 'Lao động & nhân sự', """
Hợp đồng | Loại hợp đồng lao động | Loại, thời hạn, số lần ký xác định thời hạn, mẫu hợp đồng và phụ lục | L | NSU03
Hợp đồng | Nhắc hết hạn | Trước bao nhiêu ngày nhắc hết thử việc, hết hợp đồng | Q | NSU03, HT12
Tổ chức | Phòng ban, chức danh, cấp bậc | Cây tổ chức, chức danh, quản lý trực tiếp | Q | DM10
Chấm công | Quy tắc chấm công | Thiết bị, làm tròn phút, đi muộn về sớm, quên chấm, chấm công qua điện thoại theo vị trí | Q | NSU06
Nghỉ | Phép năm | Số ngày theo điều kiện làm việc, cộng thâm niên, phép tồn chuyển năm sau, thanh toán phép chưa nghỉ | L | NSU08
Nghỉ | Loại nghỉ | Nghỉ việc riêng có lương, nghỉ không lương, nghỉ ốm, thai sản; số ngày và giấy tờ | L | NSU08, NSU09
Kỷ luật | Khen thưởng, kỷ luật | Hình thức, thời hiệu xử lý, mẫu biên bản, quyết định | L | NSU12
An toàn | An toàn vệ sinh lao động | Chu kỳ khám sức khỏe, nhóm huấn luyện, trang bị bảo hộ theo vị trí | L | NSU11
Báo cáo | Báo cáo lao động định kỳ | Kỳ báo cáo, mẫu, hạn nộp | L | NSU15
Tuyển dụng | Quy trình tuyển dụng | Các vòng, người phỏng vấn, mẫu đánh giá | Q | NSU01
Đánh giá | Đánh giá hiệu suất | Kỳ đánh giá, thang điểm, tiêu chí theo chức danh, liên kết thưởng | Q | NSU16
Đào tạo | Đào tạo và chứng chỉ | Loại khóa học, chứng chỉ bắt buộc theo vị trí, hạn chứng chỉ | Q | NSU17
""")

S('DM', 'Danh mục', """
Đối tác | Nhóm đối tác | Nhóm khách hàng, nhà cung cấp; điều khoản, hạn mức, tài khoản mặc định theo nhóm | Q | DM01
Sản phẩm | Nhóm sản phẩm và nhãn hàng | Nhóm, nhãn; tài khoản, thuế mặc định, cách tính giá | Q | DM02
Sản phẩm | Đơn vị tính | Nhóm đơn vị, tỷ lệ quy đổi, làm tròn | Q | DM03
Khoản mục | Cây khoản mục chi phí | Cấp, mã số, tài khoản được phép, khoản mục mặc định theo phòng ban | Q | DM06
Bán hàng | Vùng, kênh | Vùng bán hàng, tỉnh thành thuộc vùng, kênh phân phối | Q | DM12
""")

S('MH', 'Mua hàng & chứng từ mua dịch vụ', """
Mua hàng | Hạn mức và số báo giá | Mức tiền phải duyệt, số báo giá tối thiểu theo khoảng tiền | Q | MH01, MH02
Mua hàng | Dung sai đối chiếu 3 bên | Chênh lệch số lượng, đơn giá cho phép giữa đơn mua, phiếu nhận, hóa đơn | Q | MH05
Mua hàng | Phân bổ chi phí mua | Tiêu thức phân bổ vận chuyển, bốc xếp: giá trị, số lượng, trọng lượng | Q | MH10
Mua hàng | Thu mua không có hóa đơn | Mẫu bảng kê, đối tượng được lập bảng kê, người ký | L | MH11
Mua hàng | Đánh giá nhà cung cấp | Tiêu chí, trọng số, chu kỳ đánh giá, ngưỡng loại | Q | MH13
Chứng từ mua dịch vụ | Quyền sửa sau khi Cất | Nhóm được Sửa, thời hạn được sửa tính từ ngày Cất, bắt buộc nhập lý do | Q | MH07
Chứng từ mua dịch vụ | Quy tắc tự động tính | Cách phân bổ khi sửa tổng: theo tỷ trọng, chia đều, theo định mức; làm tròn; dòng nhận phần lẻ; tôn trọng dòng khóa | Q | MH08
Chứng từ mua dịch vụ | Đưa sửa đổi vào báo cáo | Cho phép hay không, người duyệt, chỉ ghi vào kỳ đang mở | Q | MH07
Chứng từ mua dịch vụ | Cột hiển thị trên lưới | Ẩn, hiện, thứ tự cột như MISA; bật tắt cột tài khoản | H | MH07
""")

S('BH', 'Bán hàng', """
Giá | Bảng giá và chiết khấu | Bảng giá theo kênh, chiết khấu theo số lượng, chiết khấu thanh toán | Q | BH04
Giá | Khuyến mãi | Loại chương trình, điều kiện, ngân sách khoản mục, cách thể hiện trên hóa đơn | L | BH05
Công nợ | Kiểm soát tín dụng | Hạn mức mặc định theo nhóm, hành động khi vượt: cảnh báo hay chặn, người duyệt | Q | BH06
Giao hàng | Hạn dùng tối thiểu khi giao | Số ngày còn hạn tối thiểu theo khách hoặc kênh | Q | KHO02
Chính sách | Nhà phân phối | Thưởng doanh số theo bậc, hỗ trợ trưng bày, hoa hồng | Q | BH07, BH12
Trả hàng | Hàng bán bị trả lại | Thời hạn nhận trả, lý do, kho nhận, cách lập hóa đơn điều chỉnh | Q | BH10
Hàng tặng | Hàng khuyến mãi, biếu tặng, hàng mẫu | Tài khoản chi phí, cách lập hóa đơn, khoản mục | L | BH11
TMĐT | Kết nối sàn | Shop, lịch đồng bộ, ghép mã hàng, tài khoản phí sàn | H | BH13
""")

S('KHO', 'Kho & lô', """
Giá kho | Phương pháp tính giá xuất kho | Bình quân tức thời, bình quân cuối kỳ, nhập trước xuất trước; theo nhóm hàng | L | KHO12
Xuất kho | Chiến lược lấy hàng | Hạn dùng gần nhất trước, nhập trước xuất trước; không cho tồn âm | Q | KHO02
Lô | Quản lý lô và hạn dùng | Nhóm hàng bắt buộc theo lô, cách đặt số lô, số ngày cảnh báo cận hạn | Q | KHO01, KHO08
Mã vạch | Chuẩn mã vạch và tem | Chuẩn mã, mẫu tem lô có hạn dùng, máy in tem | H | KHO11
Tồn kho | Tồn tối thiểu, tối đa | Theo sản phẩm và kho; hành động khi thiếu | Q | KHO10
Kiểm kê | Kiểm kê định kỳ | Chu kỳ, phạm vi, dung sai chênh lệch được tự duyệt | Q | KHO07
Hao hụt | Hao hụt cho phép | Tỷ lệ hao hụt tự nhiên theo nhóm hàng, xử lý phần vượt | Q | KHO07, KHO08
Tiêu hủy | Hàng hết hạn, tiêu hủy | Thành phần hội đồng, mẫu biên bản, tài khoản hạch toán | L | KHO08
""")

S('RD', 'R&D (tách riêng)', """
Phân quyền | Ai được xem dự án và công thức R&D | Mặc định chỉ nhóm R&D và Giám đốc; kế toán và nhân viên khác không truy cập | Q | RD01, RD02
Công thức | Quy tắc phiên bản và chốt công thức | Sửa là tạo phiên bản mới; người được duyệt chốt | Q | RD02, RD04
Mẫu thử | Chỉ tiêu đánh giá mẫu | Danh sách chỉ tiêu cảm quan, kiểm nghiệm, thang điểm | Q | RD03
""")

S('CL', 'Chất lượng & an toàn thực phẩm', """
Kiểm tra | Điểm kiểm tra | Nơi kiểm, sản phẩm áp dụng, kiểu kiểm tra, tần suất lấy mẫu | Q | CL01, CL03
HACCP | Giới hạn điểm kiểm soát tới hạn | Chỉ tiêu, giới hạn trên dưới, hành động khi vượt giới hạn | Q | CL02
Kiểm nghiệm | Chỉ tiêu và chu kỳ kiểm nghiệm | Chỉ tiêu theo sản phẩm, chu kỳ gửi mẫu, thời gian lưu mẫu | L | CL08
Hồ sơ | Hồ sơ công bố sản phẩm | Loại hồ sơ, thời hạn hiệu lực, nhắc gia hạn | L | CL07
Nhân sự | Người sản xuất trực tiếp | Chu kỳ khám sức khỏe, xác nhận kiến thức an toàn thực phẩm | L | CL09
Thu hồi | Quy trình thu hồi | Mức độ, người phê duyệt, mẫu thông báo khách hàng | Q | CL06
""")

S('TS', 'Tài sản & công cụ', """
Ghi nhận | Tiêu chuẩn tài sản cố định | Ngưỡng nguyên giá, thời gian sử dụng tối thiểu | L | TS01, TS09
Khấu hao | Khung thời gian khấu hao | Thời gian tối thiểu, tối đa theo loại tài sản | L | TS01, TS03
Khấu hao | Phương pháp và cách tính | Đường thẳng, số dư giảm dần, sản lượng; tính theo ngày ở tháng tăng giảm | L | TS03
Tài khoản | Tài khoản theo loại tài sản | Nguyên giá, hao mòn, chi phí theo bộ phận sử dụng, khoản mục | Q | TS03
Công cụ | Phân bổ công cụ dụng cụ | Thời gian phân bổ tối đa, phân bổ một lần hay nhiều lần | L | TS09
Vận hành | Bảo trì và đội xe | Chu kỳ bảo trì, nhắc đăng kiểm, bảo hiểm xe, định mức nhiên liệu | Q | TS11, TS12
""")

S('NS', 'Ngân sách', """
Ngân sách | Kỳ và phiên bản | Kỳ ngân sách, cho phép lập lại phiên bản sau khi duyệt | Q | NS01, NS02
Ngân sách | Quy tắc phân bổ trên cây | Theo tỷ trọng, chia đều, cố định; làm tròn; khóa khoản | Q | NS01
Kiểm soát | Mức vượt ngân sách | Vượt bao nhiêu phần trăm thì cảnh báo, bao nhiêu thì bắt duyệt | Q | NS03
Phân bổ | Tiêu thức phân bổ chi phí chung | Theo doanh thu, sản lượng, số người cho nhãn hàng, kênh, bộ phận | Q | NS05
""")

S('BC', 'Báo cáo', """
Báo cáo tài chính | Mẫu và chỉ tiêu | Mẫu báo cáo theo chế độ kế toán, mã chỉ tiêu, công thức lấy số | L | BC01
Quản trị | Báo cáo tự thiết kế | Chỉ tiêu, công thức, cây chỉ tiêu như báo cáo chi phí MISA, cột kỳ so sánh | Q | BC02, BC03
Phân phối | Gửi báo cáo định kỳ | Người nhận, lịch gửi, định dạng | Q | BC10
Bảng điều hành | Chỉ số trên bảng điều hành | Chỉ số, người được xem | Q | BC10
""")
