/** Gửi lỗi JavaScript của trình duyệt về máy chủ để người quản trị biết app hỏng ở đâu khi người dùng đang dùng.
 *  Mỗi lần mở trang chỉ gửi tối đa 20 lỗi và không gửi lại lỗi trùng, tránh làm nặng máy chủ. */
const SENT = new Set();
let left = 20;

function send(message, detail) {
    const key = (message || "") + "|" + (detail || "").split("\n")[0];
    if (!message || left <= 0 || SENT.has(key)) {
        return;
    }
    SENT.add(key);
    left -= 1;
    const body = new FormData();
    body.append("message", String(message).slice(0, 300));
    body.append("detail", String(detail || "").slice(0, 4000));
    body.append("url", String(window.location.href).slice(0, 500));
    // keepalive để lỗi lúc đang rời trang vẫn gửi được
    fetch("/lfood/monitor/js", { method: "POST", body, keepalive: true }).catch(() => {});
}

window.addEventListener("error", (ev) => {
    const where = ev.filename ? ` (${ev.filename}:${ev.lineno})` : "";
    send((ev.message || "Lỗi JavaScript") + where, ev.error && ev.error.stack);
});

window.addEventListener("unhandledrejection", (ev) => {
    const reason = ev.reason;
    send(reason && (reason.message || String(reason)), reason && reason.stack);
});
