from flask import Flask, jsonify
import json

app = Flask(__name__)

with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data['items']

def get_category(item):
    """Phân loại category dựa trên title."""
    title = item.get('title', '').lower()
    if 'định vị' in title or 'location' in title:
        return 'location'
    if 'aim' in title or 'bám' in title or 'headshot' in title:
        return 'aim'
    return 'skin'

def convert_items(group):
    """Chuyển đổi danh sách items sang định dạng API chuẩn."""
    result = []
    for idx, item in enumerate(group):
        result.append({
            "id": f"item_{idx}",
            "title": item.get('title', ''),
            "enabled": False,
            "download_url": item.get('file_url', '')
        })
    return result

def build_tabs(items_list, game_type):
    """Tạo danh sách tabs với đầy đủ location, skin, aim (nếu cần)."""
    location_items = []
    skin_items = []
    aim_items = []

    for item in items_list:
        cat = get_category(item)
        if cat == 'location':
            location_items.append(item)
        elif cat == 'aim':
            aim_items.append(item)
        else:
            skin_items.append(item)

    tabs = []

    # Tab "Định Vị"
    if location_items:
        tabs.append({
            "id": "location",
            "title": "Định Vị",
            "items": convert_items(location_items)
        })
    else:
        # Nếu không có mục location nào, dùng mục mẫu
        if game_type == 'com.dts.freefireth':
            loc_default = [{
                "id": "all_location",
                "title": "Định Vị Trang Phục",
                "enabled": False,
                "download_url": "data/contentcache1.zip"
            }]
        else:
            loc_default = [{
                "id": "hologram_v1",
                "title": "Định Vị V1",
                "enabled": False,
                "download_url": "data/contentcache.zip"
            }]
        tabs.append({
            "id": "location",
            "title": "Định Vị",
            "items": loc_default
        })

    # Tab "Mod Skin"
    tabs.append({
        "id": "skin",
        "title": "Mod Skin",
        "items": convert_items(skin_items)
    })

    # Tab "Tăng Headshot" chỉ có ở Free Fire Max
    if game_type == 'com.dts.freefiremax':
        if aim_items:
            tabs.append({
                "id": "aim",
                "title": "Tăng Headshot( Bật 1 trong 2 )",
                "items": convert_items(aim_items)
            })
        else:
            tabs.append({
                "id": "aim",
                "title": "Tăng Headshot( Bật 1 trong 2 )",
                "items": [
                    {"id": "aim_v1", "title": "Tăng Bám Đầu", "enabled": False, "download_url": "data/hsv1.zip"},
                    {"id": "hs_v2", "title": "Bám Đầu V2", "enabled": False, "download_url": "data/hsv2ffm.zip"}
                ]
            })

    return tabs

@app.route('/apk/api.php')
def api():
    ffmax_items = [i for i in items if i.get('game_type') == 'com.dts.freefiremax']
    ffth_items  = [i for i in items if i.get('game_type') == 'com.dts.freefireth']

    response = {
        "success": True,
        "version": 1,
        "updated_at": "2026-08-26T13:45:03+00:00",
        "games": {
            "free_fire": {
                "title": "Free Fire",
                "tabs": build_tabs(ffth_items, 'com.dts.freefireth')
            },
            "free_fire_max": {
                "title": "Free Fire Max",
                "tabs": build_tabs(ffmax_items, 'com.dts.freefiremax')
            }
        }
    }
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)