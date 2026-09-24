/** Ô Thời gian sử dụng: hiện ngay số tháng tương ứng theo từng ký tự đang gõ, không đợi rời ô hay lưu.
 *  Số tháng tính ngay trên trình duyệt nên không gọi máy chủ lần nào. */
import { registry } from "@web/core/registry";
import { FloatField, floatField } from "@web/views/fields/float/float_field";
import { parseFloat } from "@web/views/fields/parsers";
import { useState } from "@odoo/owl";

export class LfoodLifeField extends FloatField {
    static template = "lfood_asset.LifeField";

    setup() {
        super.setup();
        // raw = nội dung đang gõ dở; null nghĩa là lấy số đã ghi vào bản ghi
        this.typing = useState({ raw: null });
    }

    onInput(ev) {
        this.typing.raw = ev.target.value;
    }

    onFocusOut() {
        super.onFocusOut();
        this.typing.raw = null;
    }

    get months() {
        let value = this.value;
        if (this.typing.raw !== null) {
            try {
                value = parseFloat(this.typing.raw);
            } catch {
                return 0;
            }
        }
        const unit = this.props.record.data.life_unit;
        return Math.round((value || 0) * (unit === "year" ? 12 : 1));
    }

    get showMonths() {
        return !this.props.readonly && this.props.record.data.life_unit === "year" && this.months > 0;
    }
}

export const lfoodLifeField = { ...floatField, component: LfoodLifeField };

registry.category("fields").add("lfood_life", lfoodLifeField);
