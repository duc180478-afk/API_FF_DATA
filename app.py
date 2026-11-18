#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API_FF_DATA Server (app.py) — Tích hợp Trang Quản Trị Web (/admin) & Mã Hoá Động Chimera-VM (.chmr)
Cho phép:
  1. Truy cập /admin để Thêm / Sửa / Xoá trực tiếp các bản Mod, URL MediaFire, ảnh, danh mục trong data.json.
  2. Khi App Android gọi /api_mods.php (hoặc /api/chimera_data), Server đọc data.json mới nhất,
     biên dịch động sang định dạng nhị phân đa hình Chimera-VM:
       [8-byte Dynamic Opcode Map] + [16-byte Server Key Share] + [Payload .chmr]
     và ký HMAC-SHA256 gửi về cho C++ NDK (libchimera_core.so) giải mã trên RAM!
"""

import base64
import hashlib
import hmac
import json
import os
import time
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for

from Chimera_Builder import ChimeraCompiler, DATA_TYPE_STRING_URL

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "chimera-admin-session-secret-2026")

DATA_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
APP_SECRET = os.environ.get("APP_SECRET", "FAKEPING_BY_MDUCDZ")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Khóa Client cố định nằm trong vùng nhớ XOM (PROT_EXEC) của libchimera_core.so
CLIENT_KEY_SHARE_XOM = 0x8F4A2C91E73B6D05

# Bộ đệm biên dịch .chmr trên RAM Server (tự động biên dịch lại mỗi khi Admin sửa data.json)
_cached_mtime = 0.0
_cached_envelope_b64 = ""


def load_data_items():
    if not os.path.exists(DATA_JSON_PATH):
        return []
    with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict) and "items" in raw:
        return raw["items"]
    return raw if isinstance(raw, list) else []


def save_data_items(items):
    global _cached_mtime
    with open(DATA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    _cached_mtime = 0.0  # Buộc biên dịch lại gói .chmr mới với Opcode Map mới


def get_compiled_chimera_envelope_b64() -> str:
    """
    Biên dịch data.json trên Server thành gói Envelope nhị phân Chimera-VM:
      [8B Dynamic Opcode Map] + [16B Server Key Share] + [Payload .chmr]
    """
    global _cached_mtime, _cached_envelope_b64
    mtime = os.path.getmtime(DATA_JSON_PATH) if os.path.exists(DATA_JSON_PATH) else 0.0
    if _cached_envelope_b64 and mtime == _cached_mtime:
        return _cached_envelope_b64

    items = load_data_items()
    compact_json = json.dumps(items, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    # Sinh ngẫu nhiên bảng 8 V-Opcode đa hình và 16-byte Server Key Share mới mỗi lần đóng gói
    compiler = ChimeraCompiler(client_key_share=CLIENT_KEY_SHARE_XOM)
    chmr_payload = compiler.compile_blob_asset(compact_json, DATA_TYPE_STRING_URL)

    opcode_map_8b = bytes(compiler.opcode_map)
    server_key_16b = compiler.server_key_share
    envelope = opcode_map_8b + server_key_16b + chmr_payload

    _cached_envelope_b64 = base64.b64encode(envelope).decode("ascii")
    _cached_mtime = mtime
    return _cached_envelope_b64


# ============================================================================
# 1. API TRẢ DỮ LIỆU ĐÃ MÃ HOÁ CHIMERA-VM (.chmr) CHO APP ANDROID C++
# ============================================================================
@app.route("/api_mods.php", methods=["GET", "POST"])
@app.route("/api/chimera_data", methods=["GET", "POST"])
def api_chimera_mods():
    params = {}
    if request.is_json:
        params.update(request.get_json(silent=True) or {})
    params.update(request.form.to_dict())
    params.update(request.args.to_dict())

    key = str(params.get("key", "")).strip()
    hwid = str(params.get("hwid", "")).strip()
    ts = int(params.get("ts", 0) or 0)
    nonce = str(params.get("nonce", "")).strip()
    sig = str(params.get("sig", "")).strip().lower()

    # Nếu App gửi đầy đủ chữ ký HMAC thì kiểm tra xác thực nghiêm ngặt
    if key and hwid and ts and nonce and sig:
        if abs(int(time.time()) - ts) > 180:
            return jsonify({"error": "timestamp_expired"}), 403
        canon = f"mods|{key}|{hwid}|{ts}|{nonce}"
        expected = hmac.new(
            APP_SECRET.encode("utf-8"), canon.encode("utf-8"), hashlib.sha256
        ).hexdigest().lower()
        if not hmac.compare_digest(expected, sig):
            return jsonify({"error": "invalid_signature"}), 403

    chmr_b64 = get_compiled_chimera_envelope_b64()
    now_ts = int(time.time())
    resp_sig = hmac.new(
        APP_SECRET.encode("utf-8"),
        f"{chmr_b64}|chimera_v1|{now_ts}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().lower()

    return jsonify({
        "mode": "chimera_v1",
        "chmr": chmr_b64,
        "t": now_ts,
        "s": resp_sig,
    })


# ============================================================================
# 2. TRANG QUẢN TRỊ WEB (/admin) THÊM / SỬA / XOÁ FILE, URL TRONG data.json
# ============================================================================
ADMIN_HTML = """
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quản Trị data.json (Chimera-VM Server)</title>
<style>
  body{font-family:system-ui,-apple-system,sans-serif;background:#f2f2f7;color:#1c1c1e;margin:0;padding:24px}
  .wrap{max-width:1060px;margin:0 auto}
  .card{background:#fff;border-radius:18px;padding:20px;margin-bottom:20px;box-shadow:0 4px 16px rgba(0,0,0,.06)}
  h1,h2{margin-top:0}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  label{display:block;font-size:12px;font-weight:600;color:#5b5b60;margin-bottom:4px}
  input,select{width:100%;padding:10px 12px;border:1px solid #d1d1d6;border-radius:10px;font-size:14px;box-sizing:border-box;margin-bottom:12px}
  .btn{background:#005ccd;color:#fff;border:0;padding:10px 18px;border-radius:999px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block;font-size:13px}
  .btn.danger{background:#e53935}
  .btn.ghost{background:#e5e5ea;color:#1c1c1e}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{padding:10px 8px;border-bottom:1px solid #e5e5ea;text-align:left}
  .thumb{width:44px;height:44px;border-radius:8px;object-fit:cover}
  .badge{background:#e8f0fe;color:#0050b3;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600}
</style>
</head>
<body>
<div class="wrap">
  {% if not logged_in %}
  <div class="card" style="max-width:420px;margin:60px auto">
    <h2>Đăng nhập Quản Trị data.json</h2>
    {% if msg %}<p style="color:#e53935">{{ msg }}</p>{% endif %}
    <form method="post">
      <input type="hidden" name="action" value="login">
      <label>Mật khẩu Admin (Mặc định: admin123 hoặc biến môi trường ADMIN_PASSWORD)</label>
      <input type="password" name="password" required>
      <button class="btn" type="submit">Đăng nhập</button>
    </form>
  </div>
  {% else %}
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
    <h1>Quản Trị data.json · Chimera-VM Server</h1>
    <span class="badge">Tổng: {{ items|length }} bản Mod · Tự động mã hoá .chmr</span>
  </div>
  {% if msg %}<div class="card" style="background:#e8faee;color:#0b5a22;font-weight:600">{{ msg }}</div>{% endif %}

  <div class="card">
    <h2>{{ 'Sửa Mod #' + edit_item.id if edit_item else 'Thêm Mod / URL mới vào data.json' }}</h2>
    <form method="post">
      <input type="hidden" name="action" value="{{ 'save_edit' if edit_item else 'add' }}">
      {% if edit_item %}<input type="hidden" name="id" value="{{ edit_item.id }}">{% endif %}
      <div class="row">
        <div>
          <label>Tên hiển thị (title)</label>
          <input name="title" required value="{{ edit_item.title if edit_item else '' }}" placeholder="Skin Bá Sàn FF">
        </div>
        <div>
          <label>Mô tả (description)</label>
          <input name="description" required value="{{ edit_item.description if edit_item else '' }}" placeholder="Nhân Vật Ignis / Alok">
        </div>
      </div>
      <label>Link tải MediaFire .zip (file_url)</label>
      <input name="file_url" required value="{{ edit_item.file_url if edit_item else '' }}" placeholder="https://www.mediafire.com/file/xxxx/mod.zip/file">
      <label>Link ảnh xem trước (image_url)</label>
      <input name="image_url" value="{{ edit_item.image_url if edit_item else '' }}" placeholder="https://iili.io/xxxx.jpg">
      <div class="row">
        <div>
          <label>Phiên bản Game (game_type)</label>
          <select name="game_type">
            <option value="com.dts.freefireth" {{ 'selected' if edit_item and edit_item.game_type == 'com.dts.freefireth' else '' }}>com.dts.freefireth (FF Thường)</option>
            <option value="com.dts.freefiremax" {{ 'selected' if edit_item and edit_item.game_type == 'com.dts.freefiremax' else '' }}>com.dts.freefiremax (FF Max)</option>
            <option value="com.garena.ffvn" {{ 'selected' if edit_item and edit_item.game_type == 'com.garena.ffvn' else '' }}>com.garena.ffvn (FF VN)</option>
          </select>
        </div>
        <div>
          <label>Danh mục (skin_type)</label>
          <select name="skin_type">
            <option value="character" {{ 'selected' if edit_item and edit_item.skin_type == 'character' else '' }}>character (Nhân vật / Trang phục)</option>
            <option value="gun" {{ 'selected' if edit_item and edit_item.skin_type == 'gun' else '' }}>gun (Skin súng)</option>
            <option value="toy" {{ 'selected' if edit_item and edit_item.skin_type == 'toy' else '' }}>toy (Định vị / Vật phẩm)</option>
            <option value="fixlag" {{ 'selected' if edit_item and edit_item.skin_type == 'fixlag' else '' }}>fixlag (Fix lag)</option>
          </select>
        </div>
      </div>
      <button class="btn" type="submit">{{ 'Lưu cập nhật & Mã hoá lại .chmr' if edit_item else '+ Thêm Mod & Mã hoá .chmr' }}</button>
      {% if edit_item %}<a href="/admin" class="btn ghost">Huỷ</a>{% endif %}
    </form>
  </div>

  <div class="card" style="overflow-x:auto">
    <h2>Danh sách Mod trong data.json ({{ items|length }})</h2>
    <table>
      <thead>
        <tr><th>ID</th><th>Ảnh</th><th>Tên & Mô tả</th><th>Game</th><th>Loại</th><th>URL MediaFire</th><th>Thao tác</th></tr>
      </thead>
      <tbody>
      {% for it in items %}
        <tr>
          <td><b>{{ it.id }}</b></td>
          <td>{% if it.image_url %}<img class="thumb" src="{{ it.image_url }}">{% endif %}</td>
          <td><b>{{ it.title }}</b><br><small>{{ it.description }}</small></td>
          <td><code>{{ it.game_type }}</code></td>
          <td><code>{{ it.skin_type }}</code></td>
          <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><a href="{{ it.file_url }}" target="_blank">{{ it.file_url }}</a></td>
          <td>
            <a class="btn ghost" href="/admin?edit={{ it.id }}">Sửa</a>
            <form method="post" style="display:inline" onsubmit="return confirm('Xoá mục #{{ it.id }}?')">
              <input type="hidden" name="action" value="delete">
              <input type="hidden" name="id" value="{{ it.id }}">
              <button class="btn danger" type="submit">Xoá</button>
            </form>
          </td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</div>
</body>
</html>
"""


@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    msg = ""
    if request.method == "POST":
        act = request.form.get("action", "")
        if act == "login":
            if request.form.get("password") == ADMIN_PASSWORD:
                session["admin_ok"] = True
                return redirect(url_for("admin_panel"))
            msg = "Sai mật khẩu Admin!"
        elif session.get("admin_ok"):
            items = load_data_items()
            if act == "add":
                max_id = max([int(x.get("id", 0)) for x in items if str(x.get("id", "")).isdigit()] + [100])
                new_id = str(max_id + 1)
                items.insert(0, {
                    "id": new_id,
                    "title": request.form.get("title", "").strip(),
                    "description": request.form.get("description", "").strip(),
                    "game_type": request.form.get("game_type", "com.dts.freefiremax"),
                    "skin_type": request.form.get("skin_type", "character"),
                    "file_url": request.form.get("file_url", "").strip(),
                    "image_url": request.form.get("image_url", "").strip(),
                })
                save_data_items(items)
                msg = f"Đã thêm mục #{new_id} và biên dịch lại gói Chimera-VM (.chmr)!"
            elif act == "save_edit":
                target_id = request.form.get("id", "").strip()
                for x in items:
                    if str(x.get("id", "")) == target_id:
                        x["title"] = request.form.get("title", "").strip()
                        x["description"] = request.form.get("description", "").strip()
                        x["game_type"] = request.form.get("game_type", "com.dts.freefiremax")
                        x["skin_type"] = request.form.get("skin_type", "character")
                        x["file_url"] = request.form.get("file_url", "").strip()
                        x["image_url"] = request.form.get("image_url", "").strip()
                        break
                save_data_items(items)
                msg = f"Đã cập nhật mục #{target_id} và biên dịch lại gói Chimera-VM (.chmr)!"
            elif act == "delete":
                target_id = request.form.get("id", "").strip()
                items = [x for x in items if str(x.get("id", "")) != target_id]
                save_data_items(items)
                msg = f"Đã xoá mục #{target_id} khỏi data.json!"

    logged_in = bool(session.get("admin_ok"))
    items = load_data_items() if logged_in else []
    edit_id = request.args.get("edit", "").strip()
    edit_item = next((x for x in items if str(x.get("id", "")) == edit_id), None) if edit_id else None
    return render_template_string(
        ADMIN_HTML,
        logged_in=logged_in,
        items=items,
        edit_item=edit_item,
        msg=msg,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))