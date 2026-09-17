#!/bin/sh
# Sao lưu tự động ERP LiFeOOD
#  - Sao lưu theo giờ trong BACKUP_TIMES (mặc định 12:00, 17:30)
#  - Laptop tắt qua giờ hẹn: bật lên mà bản gần nhất quá 24 giờ thì sao lưu bù ngay
#  - App yêu cầu "Sao lưu ngay": tạo tệp /backups/.request
#  - Mỗi bản: database.dump (pg_dump), filestore.tar.gz (tệp đính kèm), SHA256SUMS, manifest.json
#  - Giữ: KEEP_DAILY bản ngày, KEEP_WEEKLY bản tuần, KEEP_MONTHLY bản tháng
#  - Có OFFSITE và BACKUP_PASSPHRASE: chép thêm 1 bản mã hóa AES-256 ra thư mục ngoài (OneDrive)

B=/backups
DB="${PGDATABASE:-lfood}"
KEEP_DAILY="${KEEP_DAILY:-14}"
KEEP_WEEKLY="${KEEP_WEEKLY:-8}"
KEEP_MONTHLY="${KEEP_MONTHLY:-12}"
BACKUP_TIMES="${BACKUP_TIMES:-12:00,17:30}"

mkdir -p "$B/daily" "$B/weekly" "$B/monthly"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$B/backup.log"; }

write_status() {
  # $1 ok|error  $2 thông điệp  $3 thư mục
  printf '{"time": "%s", "result": "%s", "message": "%s", "folder": "%s", "times": "%s"}\n' \
    "$(date -Iseconds)" "$1" "$2" "${3:-}" "$BACKUP_TIMES" > "$B/status.json.tmp" && mv "$B/status.json.tmp" "$B/status.json"
}

newest_epoch() {
  newest=$(ls -1d "$B"/daily/2*/ 2>/dev/null | sort | tail -n 1)
  if [ -z "$newest" ]; then echo 0; else stat -c %Y "$newest"; fi
}

prune() {
  kind="$1"; keep="$2"
  ls -1d "$B/$kind"/2*/ 2>/dev/null | sort | head -n "-$keep" | while read -r old; do
    rm -rf "$old" && log "Xóa bản cũ $kind: $(basename "$old")"
  done
}

fail() {
  log "LỖI: $1"
  write_status error "$1" "$2"
  [ -n "$2" ] && rm -rf "$B/daily/$2.part"
  return 1
}

do_backup() {
  reason="$1"
  ts=$(date +%Y-%m-%d_%H%M%S)
  part="$B/daily/$ts.part"
  log "Bắt đầu sao lưu ($reason)"
  mkdir -p "$part" || { fail "Không tạo được thư mục sao lưu" "$ts"; return 1; }

  pg_dump -h db -U odoo -Fc -Z 6 "$DB" -f "$part/database.dump" 2>>"$B/backup.log" \
    || { fail "pg_dump thất bại" "$ts"; return 1; }

  if [ -d "/odoo-data/filestore/$DB" ]; then
    tar -czf "$part/filestore.tar.gz" -C /odoo-data/filestore "$DB" 2>>"$B/backup.log" \
      || { fail "Nén tệp đính kèm thất bại" "$ts"; return 1; }
  else
    tar -czf "$part/filestore.tar.gz" -T /dev/null
  fi

  counts=$(psql -h db -U odoo -d "$DB" -At -c "SELECT json_build_object(
      'vouchers', (SELECT count(*) FROM lfood_service_voucher),
      'voucher_lines', (SELECT count(*) FROM lfood_service_voucher_line),
      'audit_logs', (SELECT count(*) FROM lfood_audit_log),
      'users', (SELECT count(*) FROM res_users),
      'last_audit_hash', (SELECT hash FROM lfood_audit_log ORDER BY id DESC LIMIT 1))" 2>>"$B/backup.log") \
    || { fail "Không đọc được số dòng để đối chiếu" "$ts"; return 1; }

  (cd "$part" && sha256sum database.dump filestore.tar.gz > SHA256SUMS) || { fail "Tính mã băm thất bại" "$ts"; return 1; }
  size=$(du -sb "$part" | cut -f1)
  cat > "$part/manifest.json" <<EOF
{"created": "$(date -Iseconds)", "database": "$DB", "reason": "$reason", "size_bytes": $size, "odoo": "19.0", "counts": $counts}
EOF
  mv "$part" "$B/daily/$ts" || { fail "Không hoàn tất thư mục sao lưu" "$ts"; return 1; }

  # bản tuần: chưa có bản nào trong 7 ngày gần nhất
  if [ -z "$(find "$B/weekly" -mindepth 1 -maxdepth 1 -type d -mtime -7 2>/dev/null)" ]; then
    cp -a "$B/daily/$ts" "$B/weekly/$ts" && log "Lưu thêm bản tuần $ts"
  fi
  # bản tháng: chưa có bản nào của tháng này
  if [ -z "$(ls -1d "$B/monthly/$(date +%Y-%m)"* 2>/dev/null)" ]; then
    cp -a "$B/daily/$ts" "$B/monthly/$ts" && log "Lưu thêm bản tháng $ts"
  fi

  # bản mã hóa ngoài laptop
  if [ -d /offsite ] && [ -n "${BACKUP_PASSPHRASE:-}" ]; then
    tar -C "$B/daily" -cf - "$ts" | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_PASSPHRASE \
      -out "/offsite/lfood_$ts.tar.enc" && log "Đã chép bản mã hóa ra ngoài: lfood_$ts.tar.enc"
    ls -1 /offsite/lfood_*.tar.enc 2>/dev/null | sort | head -n "-$KEEP_DAILY" | xargs -r rm -f
  fi

  prune daily "$KEEP_DAILY"; prune weekly "$KEEP_WEEKLY"; prune monthly "$KEEP_MONTHLY"
  find "$B/daily" -maxdepth 1 -name '*.part' -mmin +120 -exec rm -rf {} + 2>/dev/null
  log "Sao lưu xong daily/$ts ($(du -sh "$B/daily/$ts" | cut -f1))"
  write_status ok "Sao lưu thành công ($reason)" "daily/$ts"
}

log "Dịch vụ sao lưu khởi động. Giờ sao lưu: $BACKUP_TIMES. Giữ $KEEP_DAILY ngày, $KEEP_WEEKLY tuần, $KEEP_MONTHLY tháng."
until pg_isready -h db -U odoo >/dev/null 2>&1; do sleep 3; done
until psql -h db -U odoo -d "$DB" -At -c "SELECT 1 FROM lfood_service_voucher LIMIT 1" >/dev/null 2>&1; do sleep 10; done

while true; do
  now=$(date +%s)
  hm=$(date +%H:%M)
  last=$(newest_epoch)
  if [ -f "$B/.request" ]; then
    rm -f "$B/.request"
    do_backup "Yêu cầu từ app"
  elif [ $((now - last)) -gt 86400 ]; then
    do_backup "Sao lưu bù, bản gần nhất quá 24 giờ"
  else
    for t in $(echo "$BACKUP_TIMES" | tr ',' ' '); do
      if [ "$hm" = "$t" ] && [ $((now - $(newest_epoch))) -gt 600 ]; then
        do_backup "Theo lịch $t"
      fi
    done
  fi
  sleep 20
done
