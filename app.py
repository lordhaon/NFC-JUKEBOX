#!/usr/bin/env python3
"""
NFC Jukebox - Flask Web Interface
Manages NFC tag → Jellyfin movie mappings and controls Roku TVs
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import json, os, requests, threading, time, re, logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nfc-jukebox-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
TAGS_FILE   = os.path.join(os.path.dirname(__file__), 'tags.json')
LOG_FILE    = os.path.join(os.path.dirname(__file__), 'scan_log.json')

DEFAULT_CONFIG = {
    "ha_url":             "http://homeassistant.local:8123",
    "ha_token":           "",
    "jellyfin_url":       "http://localhost:8096",
    "jellyfin_token":     "",
    "jellyfin_user_id":   "",
    "default_roku_ip":    "192.168.1.15",
    "default_channel_id": "592369"
}

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass
    return default.copy() if isinstance(default, dict) else default

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

config   = load_json(CONFIG_FILE, DEFAULT_CONFIG)
tags     = load_json(TAGS_FILE, {})
scan_log = load_json(LOG_FILE, [])

def save_config(): save_json(CONFIG_FILE, config)
def save_tags():   save_json(TAGS_FILE, tags)
def save_log():    save_json(LOG_FILE, scan_log[-200:])

def jellyfin_get(path, params=None):
    try:
        headers = {"X-Emby-Token": config.get("jellyfin_token", "")}
        r = requests.get(f"{config['jellyfin_url']}/{path}", headers=headers, params=params, timeout=5)
        return r.json() if r.ok else None
    except Exception as e:
        log.error(f"Jellyfin GET error: {e}")
        return None

def roku_launch_content(roku_ip, channel_id, jellyfin_id, media_type="movie", resume=True, audio_lang=None):
    try:
        params = {"contentId": jellyfin_id, "mediaType": media_type}

        # Resume: fetch playback position from Jellyfin
        if resume and jellyfin_id and media_type != "series":
            user_id = config.get('jellyfin_user_id', '')
            user_data = jellyfin_get(f"Users/{user_id}/Items/{jellyfin_id}/UserData")
            if user_data:
                ticks  = user_data.get('PlaybackPositionTicks', 0)
                played = user_data.get('Played', False)
                if ticks and ticks > 0 and not played:
                    params['startPositionTicks'] = str(ticks)
                    log.info(f"Resuming from {ticks//600000000:.0f}m ({ticks} ticks)")

        # Audio language: update user config in Jellyfin
        if audio_lang and jellyfin_id:
            user_id = config.get('jellyfin_user_id', '')
            try:
                user_cfg = requests.get(
                    f"{config['jellyfin_url']}/Users/{user_id}",
                    headers={"X-Emby-Token": config.get("jellyfin_token", "")}, timeout=3
                ).json()
                if user_cfg:
                    cfg = user_cfg.get('Configuration', {})
                    cfg['AudioLanguagePreference'] = audio_lang
                    requests.post(
                        f"{config['jellyfin_url']}/Users/{user_id}/Configuration",
                        headers={"X-Emby-Token": config.get("jellyfin_token", ""),
                                 "Content-Type": "application/json"},
                        json=cfg, timeout=3
                    )
                    log.info(f"Set audio language to {audio_lang}")
            except Exception as e:
                log.error(f"Audio lang error: {e}")

        r = requests.post(f"http://{roku_ip}:8060/launch/{channel_id}", params=params, timeout=5)
        log.info(f"Roku launch {r.status_code}: {params}")
        return r.ok
    except Exception as e:
        log.error(f"Roku launch error: {e}")
        return False

def roku_keypress(roku_ip, key):
    try:
        r = requests.post(f"http://{roku_ip}:8060/keypress/{key}", timeout=3)
        return r.ok
    except Exception as e:
        log.error(f"Roku keypress error: {e}")
        return False

def roku_get(roku_ip, path):
    try:
        r = requests.get(f"http://{roku_ip}:8060/{path}", timeout=3)
        return r.text if r.ok else None
    except:
        return None

def ha_get(path):
    try:
        r = requests.get(f"{config['ha_url']}/api/{path}",
            headers={"Authorization": f"Bearer {config['ha_token']}"}, timeout=5)
        return r.json() if r.ok else None
    except Exception as e:
        log.error(f"HA GET error: {e}")
        return None

def ha_post(path, data):
    try:
        r = requests.post(f"{config['ha_url']}/api/{path}",
            headers={"Authorization": f"Bearer {config['ha_token']}",
                     "Content-Type": "application/json"},
            json=data, timeout=5)
        return r.json() if r.ok else None
    except Exception as e:
        log.error(f"HA POST error: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    safe = {k: v for k, v in config.items() if 'token' not in k}
    safe['ha_token_set']       = bool(config.get('ha_token'))
    safe['jellyfin_token_set'] = bool(config.get('jellyfin_token'))
    return jsonify(safe)

@app.route('/api/config', methods=['POST'])
def set_config():
    global config
    config.update(request.json)
    save_config()
    return jsonify({"ok": True})

@app.route('/api/tags', methods=['GET'])
def get_tags():
    return jsonify(tags)

@app.route('/api/tags/<tag_id>', methods=['POST'])
def set_tag(tag_id):
    tags[tag_id] = request.json
    save_tags()
    return jsonify({"ok": True})

@app.route('/api/tags/<tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    if tag_id in tags:
        del tags[tag_id]
        save_tags()
    return jsonify({"ok": True})

@app.route('/api/log', methods=['GET'])
def get_log():
    return jsonify(list(reversed(scan_log[-100:])))

@app.route('/api/log', methods=['DELETE'])
def clear_log():
    scan_log.clear()
    save_log()
    return jsonify({"ok": True})

@app.route('/api/ha/roku_players')
def get_roku_players():
    states = ha_get("states")
    if not states:
        return jsonify([])
    players = []
    for s in states:
        if not s["entity_id"].startswith("media_player."):
            continue
        if not any(a in str(s["attributes"].get("source_list", []))
                   for a in ["Jellyfin", "Netflix", "Roku"]):
            continue
        players.append({
            "entity_id": s["entity_id"],
            "name":      s["attributes"].get("friendly_name", s["entity_id"]),
            "state":     s["state"],
            "roku_ip":   s["attributes"].get("host", config.get("default_roku_ip", "192.168.1.15"))
        })
    return jsonify(players)

@app.route('/api/ha/all_players')
def get_all_players():
    states = ha_get("states")
    if not states:
        return jsonify([])
    return jsonify([
        {"entity_id": s["entity_id"],
         "name": s["attributes"].get("friendly_name", s["entity_id"]),
         "state": s["state"]}
        for s in states if s["entity_id"].startswith("media_player.")
    ])

@app.route('/api/jellyfin/search')
def jellyfin_search():
    query   = request.args.get('q', '')
    types   = request.args.get('types', 'Movie,Series')
    user_id = config.get('jellyfin_user_id', '')
    if not query:
        return jsonify([])
    results = jellyfin_get(f"Users/{user_id}/Items", params={
        "searchTerm": query, "IncludeItemTypes": types,
        "Recursive": "true", "Fields": "PrimaryImageAspectRatio", "Limit": 20
    })
    if not results:
        return jsonify([])
    items = []
    for item in results.get("Items", []):
        thumb = None
        if item.get("ImageTags", {}).get("Primary"):
            thumb = f"{config['jellyfin_url']}/Items/{item['Id']}/Images/Primary?maxHeight=150&token={config.get('jellyfin_token','')}"
        items.append({"id": item["Id"], "name": item["Name"],
                      "type": item["Type"], "year": item.get("ProductionYear"), "thumb": thumb})
    return jsonify(items)

@app.route('/api/jellyfin/users')
def jellyfin_users():
    users = jellyfin_get("Users")
    if not users:
        return jsonify([])
    return jsonify([{"id": u["Id"], "name": u["Name"]} for u in users])

@app.route('/api/play', methods=['POST'])
def play_media():
    data       = request.json
    source     = data.get('source', 'jellyfin')
    roku_ip    = data.get('roku_ip', config.get('default_roku_ip', '192.168.1.15'))
    channel_id = data.get('channel_id', '592369')

    if source == 'external':
        content_id = data.get('ext_content_id', '')
        media_type = data.get('ext_media_type', 'movie')
        try:
            params = {'contentId': content_id, 'mediaType': media_type} if content_id else {}
            r = requests.post(f"http://{roku_ip}:8060/launch/{channel_id}", params=params, timeout=5)
            log.info(f"External launch {channel_id} content={content_id} status={r.status_code}")
            return jsonify({"ok": r.ok})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})
    else:
        ok = roku_launch_content(
            roku_ip     = roku_ip,
            channel_id  = channel_id,
            jellyfin_id = data.get('jellyfin_id'),
            media_type  = data.get('media_type', 'movie'),
            resume      = data.get('resume', True),
            audio_lang  = data.get('audio_lang', '')
        )
        return jsonify({"ok": ok})

@app.route('/api/roku/<roku_ip>/apps')
def get_roku_apps(roku_ip):
    xml = roku_get(roku_ip, "query/apps")
    if not xml:
        return jsonify([])
    apps = re.findall(r'<app id="([^"]+)"[^>]*>([^<]+)</app>', xml)
    return jsonify([{"id": a[0], "name": a[1]} for a in apps])

@app.route('/api/roku/<roku_ip>/keypress/<key>', methods=['POST'])
def roku_key(roku_ip, key):
    return jsonify({"ok": roku_keypress(roku_ip, key)})

@app.route('/api/ha/remote_command', methods=['POST'])
def ha_remote_command():
    data = request.json
    result = ha_post("services/remote/send_command",
        {"entity_id": data.get("entity_id"), "command": data.get("command")})
    return jsonify({"ok": result is not None})

@app.route('/api/ha/roku_keypress', methods=['POST'])
def ha_roku_keypress():
    data = request.json or {}
    entity_id = data.get("entity_id")
    command   = data.get("command")
    if not entity_id or not command:
        return jsonify({"ok": False})
    result = ha_post("services/remote/send_command", {
        "entity_id": entity_id.replace("media_player.", "remote."),
        "command": command
    })
    return jsonify({"ok": result is not None})

# ── NFC scanning thread ───────────────────────────────────────────────────────
scanning_active = False
pending_tag     = None
pending_lock    = threading.Lock()

def nfc_scan_loop():
    global pending_tag
    log.info("NFC scan loop started")
    from smartcard.System import readers
    from smartcard.Exceptions import CardConnectionException
    GET_UID  = [0xFF, 0xCA, 0x00, 0x00, 0x00]
    last_uid  = None
    last_time = 0

    while scanning_active:
        try:
            r = readers()
            if not r:
                time.sleep(2)
                continue
            conn = r[0].createConnection()
            conn.connect()
            data, sw1, sw2 = conn.transmit(GET_UID)
            conn.disconnect()
            uid = '-'.join(f'{b:02X}' for b in data)
            now = time.time()

            if uid and (uid != last_uid or now - last_time > 5):
                last_uid  = uid
                last_time = now
                log.info(f"Tag scanned: {uid}")

                entry = {
                    "tag_id":    uid,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "label":     tags.get(uid, {}).get("label", "Unknown"),
                    "played":    uid in tags
                }
                scan_log.append(entry)
                save_log()

                socketio.emit('tag_scanned', {
                    "tag_id":   uid,
                    "known":    uid in tags,
                    "tag_data": tags.get(uid, {})
                })

                if uid in tags:
                    tag    = tags[uid]
                    source = tag.get("source", "jellyfin")
                    roku_ip    = tag.get("roku_ip", config.get("default_roku_ip", "192.168.1.15"))
                    channel_id = tag.get("channel_id", "592369")

                    if source == "external":
                        content_id = tag.get("ext_content_id", "")
                        media_type = tag.get("ext_media_type", "movie")
                        try:
                            params = {'contentId': content_id, 'mediaType': media_type} if content_id else {}
                            r = requests.post(f"http://{roku_ip}:8060/launch/{channel_id}", params=params, timeout=5)
                            ok = r.ok
                        except Exception as e:
                            log.error(f"External launch error: {e}")
                            ok = False
                    else:
                        ok = roku_launch_content(
                            roku_ip     = roku_ip,
                            channel_id  = channel_id,
                            jellyfin_id = tag.get("jellyfin_id"),
                            media_type  = tag.get("media_type", "movie"),
                            resume      = tag.get("resume", True),
                            audio_lang  = tag.get("audio_lang", "")
                        )
                    log.info(f"Launched '{tag.get('label')}' [{source}] — ok={ok}")
                else:
                    with pending_lock:
                        pending_tag = uid

        except CardConnectionException:
            last_uid = None
        except Exception as e:
            if 'No smart card' not in str(e) and 'No card' not in str(e):
                log.error(f"NFC loop error: {e}")
            last_uid = None

        time.sleep(0.5)

@app.route('/api/scan/once')
def scan_once():
    try:
        from smartcard.System import readers
        GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        r = readers()
        if not r:
            return jsonify({"ok": False, "error": "No reader found"})
        conn = r[0].createConnection()
        conn.connect()
        data, sw1, sw2 = conn.transmit(GET_UID)
        conn.disconnect()
        uid = '-'.join(f'{b:02X}' for b in data)
        return jsonify({"ok": True, "uid": uid})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route('/api/scan/start', methods=['POST'])
def start_scan():
    global scanning_active
    if not scanning_active:
        scanning_active = True
        threading.Thread(target=nfc_scan_loop, daemon=True).start()
    return jsonify({"ok": True, "scanning": True})

@app.route('/api/scan/stop', methods=['POST'])
def stop_scan():
    global scanning_active
    scanning_active = False
    return jsonify({"ok": True, "scanning": False})

@app.route('/api/scan/status')
def scan_status():
    return jsonify({"scanning": scanning_active, "pending_tag": pending_tag})

@app.route('/api/scan/pending/clear', methods=['POST'])
def clear_pending():
    global pending_tag
    with pending_lock:
        pending_tag = None
    return jsonify({"ok": True})

@socketio.on('connect')
def on_connect():
    emit('status', {"scanning": scanning_active})

if __name__ == '__main__':
    if os.path.exists('/dev/bus/usb'):
        scanning_active = True
        threading.Thread(target=nfc_scan_loop, daemon=True).start()
        log.info("Auto-started NFC scanning")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
