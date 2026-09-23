import { registry } from "@web/core/registry";

// Menu người dùng (góc phải trên) của Odoo có "Support" và "My Odoo.com account" trỏ ra odoo.com.
// App chạy nội bộ nên bỏ hẳn; giữ lại Phím tắt, Hồ sơ của tôi, Đăng xuất.
const items = registry.category("user_menuitems");
for (const key of ["support", "documentation", "odoo_account", "install_pwa"]) {
    if (items.contains(key)) {
        items.remove(key);
    }
}
