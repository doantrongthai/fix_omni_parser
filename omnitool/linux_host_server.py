import os
import sys
import shlex
import subprocess
import threading
import pyautogui
from PIL import Image
from io import BytesIO
from flask import Flask, request, jsonify, send_file
import mss

app = Flask(__name__)
computer_control_lock = threading.Lock()

cursor_path = os.path.join(os.path.dirname(__file__), "omnibox/vm/win11setup/setupscripts/server/cursor.png")

@app.route('/probe', methods=['GET'])
def probe_endpoint():
    return jsonify({"status": "Probe successful", "message": "Linux Host Service is operational"}), 200

@app.route('/vnc.html', methods=['GET'])
def vnc_endpoint():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f8fafc; color: #1e293b; text-align: center; }
            .card { background: white; padding: 32px; border-radius: 16px; border: 1px solid #e2e8f0; box-shadow: 0 4px 16px rgba(0,0,0,0.06); max-width: 480px; }
            h2 { color: #0f172a; margin-top: 8px; font-size: 20px; }
            p { color: #64748b; font-size: 14px; line-height: 1.6; }
            .status { display: inline-flex; align-items: center; gap: 6px; background: #dcfce7; color: #15803d; font-weight: 600; padding: 4px 12px; border-radius: 9999px; font-size: 13px; }
            .status::before { content: ""; width: 8px; height: 8px; background: #22c55e; border-radius: 50%; }
        </style>
    </head>
    <body>
        <div class="card">
            <span class="status">Linux Host Đã Kết Nối</span>
            <h2>🖥️ Điều Khiển Trực Tiếp Máy Linux</h2>
            <p>Agent đang kết nối và điều khiển trực tiếp chuột và màn hình của bạn.</p>
            <p style="font-size: 12px; color: #94a3b8;">Ảnh chụp từng bước và vị trí con trỏ chuột (chấm đỏ) sẽ xuất hiện trong khung Chatbot History bên trái.</p>
        </div>
    </body>
    </html>
    """, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/execute', methods=['POST'])
def execute_command():
    with computer_control_lock:
        data = request.json or {}
        command = data.get('command', [])
        shell = data.get('shell', False)
        if isinstance(command, str) and not shell:
            command = shlex.split(command)
        
        # Ensure python commands execute with current environment python
        if command and command[0] == "python":
            command[0] = sys.executable

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=shell,
                text=True,
                timeout=120
            )
            return jsonify({
                'status': 'success',
                'output': result.stdout,
                'error': result.stderr,
                'returncode': result.returncode
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

@app.route('/screenshot', methods=['GET'])
def capture_screen():
    try:
        screenshot = None
        tmp_path = f"/tmp/omniparser_screen_{os.getpid()}.png"
        clean_env = {
            "DISPLAY": os.environ.get("DISPLAY", ":0"),
            "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-0"),
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
            "PATH": "/usr/bin:/bin"
        }
        try:
            res = subprocess.run(["gnome-screenshot", "-f", tmp_path], env=clean_env, capture_output=True, timeout=5)
            if res.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 10000:
                screenshot = Image.open(tmp_path)
                screenshot.load()
        except Exception:
            pass
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        if screenshot is None:
            # Fallback to MSS if not on Wayland or if gnome-screenshot not available
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # primary display
                sct_img = sct.grab(monitor)
                screenshot = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')

        # Paste cursor icon if available
        if os.path.exists(cursor_path):
            try:
                cursor_x, cursor_y = pyautogui.position()
                cursor = Image.open(cursor_path)
                cursor = cursor.resize((int(cursor.width / 1.5), int(cursor.height / 1.5)))
                screenshot.paste(cursor, (cursor_x, cursor_y), cursor)
            except Exception:
                pass

        img_io = BytesIO()
        screenshot.save(img_io, 'PNG')
        img_io.seek(0)
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    print("Starting Linux Host Control Server on http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000)

