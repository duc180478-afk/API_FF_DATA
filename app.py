from flask import Flask, jsonify
import json

app = Flask(__name__)

with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data['items']

def make_items(group):
    result = []
    for index, item in enumerate(group):
        result.append({
            "id": item.get('id', f"item_{index}"),
            "title": item['title'],
            "enabled": False,
            "download_url": item.get('file_url', ''),
            "image_url": item.get('image_url', ''),
            "description": item.get('description', '')
        })
    return result

@app.route('/apk/api.php')
def api():
    ffmax = [i for i in items if i['game_type'] == 'com.dts.freefiremax']
    ffth = [i for i in items if i['game_type'] == 'com.dts.freefireth']

    return jsonify({
        "success": True,
        "version": 1,
        "updated_at": "2026-08-26T13:45:03+00:00",
        "games": {
            "free_fire": {
                "title": "Free Fire",
                "tabs": [{
                    "id": "skin",
                    "title": "Mod Skin",
                    "items": make_items(ffth)
                }]
            },
            "free_fire_max": {
                "title": "Free Fire Max",
                "tabs": [{
                    "id": "skin",
                    "title": "Mod Skin",
                    "items": make_items(ffmax)
                }]
            }
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)