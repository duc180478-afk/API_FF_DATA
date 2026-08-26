from flask import Flask, jsonify
import json

app = Flask(__name__)

with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data['items']

def build_items(group):
    result = []
    for index, item in enumerate(group):
        result.append({
            "id": f"item_{index}",
            "title": item.get('title', ''),
            "enabled": False,
            "download_url": item.get('file_url', '')
        })
    return result

@app.route('/apk/api.php')
def api():
    ffmax = [i for i in items if i.get('game_type') == 'com.dts.freefiremax']
    ffth  = [i for i in items if i.get('game_type') == 'com.dts.freefireth']

    response = {
        "success": True,
        "version": 1,
        "updated_at": "2026-08-26T13:45:03+00:00",
        "games": {
            "free_fire": {
                "title": "Free Fire",
                "tabs": [
                    {
                        "id": "location",
                        "title": "Định Vị",
                        "items": [
                            {
                                "id": "all_location",
                                "title": "Định Vị Trang Phục",
                                "enabled": False,
                                "download_url": "data/contentcache1.zip"
                            }
                        ]
                    },
                    {
                        "id": "skin",
                        "title": "Mod Skin",
                        "items": build_items(ffth)
                    }
                ]
            },
            "free_fire_max": {
                "title": "Free Fire Max",
                "tabs": [
                    {
                        "id": "location",
                        "title": "Định Vị",
                        "items": [
                            {
                                "id": "hologram_v1",
                                "title": "Định Vị V1",
                                "enabled": False,
                                "download_url": "data/contentcache.zip"
                            }
                        ]
                    },
                    {
                        "id": "skin",
                        "title": "Mod Skin",
                        "items": build_items(ffmax)
                    },
                    {
                        "id": "aim",
                        "title": "Tăng Headshot( Bật 1 trong 2 )",
                        "items": [
                            {
                                "id": "aim_v1",
                                "title": "Tăng Bám Đầu",
                                "enabled": False,
                                "download_url": "data/hsv1.zip"
                            },
                            {
                                "id": "hs_v2",
                                "title": "Bám Đầu V2",
                                "enabled": False,
                                "download_url": "data/hsv2ffm.zip"
                            }
                        ]
                    }
                ]
            }
        }
    }
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)