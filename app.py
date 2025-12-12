#!/usr/bin/env python3
"""
EDU Toolbox - Multi-Module Flask Desktop Application
→ Works with ONLY .exe (no external config/ folder needed)
→ SECURE: After logout, BACK NAVIGATION → always login page.
"""
import os
import sys
import json
import sqlite3
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, send_from_directory
import webview
import traceback 
import ctypes

# === UTF-8 Safety for Windows/.exe ===
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def resource_path(relative_path):
    """Get absolute path to resource for PyInstaller compatibility"""
    try:
        base_path = sys._MEIPASS  # ← Critical: Use _MEIPASS for bundled resources
    except Exception:
        base_path = Path(__file__).parent
    if os.name == 'nt':
        relative_path = relative_path.replace('/', '\\')
    return Path(base_path) / relative_path

# Get base directory - FIXED FOR EXECUTABLE
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)  # ← Now points to internal temp folder
else:
    BASE_DIR = Path(__file__).parent

# Flask app setup
app = Flask(__name__, 
           template_folder=resource_path('ui'),
           static_folder=resource_path('static'))

app.secret_key = 'edu_toolbox_secure_key_2024_FIXED'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_PERMANENT'] = False

class EDUToolboxApp:
    def __init__(self):
        self.data_path = resource_path("data")
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_path / "user_data.db"
        
        self.ui_path = resource_path('ui')
        self.modules_path = resource_path('modules')
        self.assets_path = resource_path('assets')
        # ✅ FIXED: config_path now uses resource_path → works in .exe
        self.config_path = resource_path("config")
        self.config_path.mkdir(exist_ok=True)
        
        # ✅ Auto-create clean licenses.json if missing (UTF-8, no BOM)
        licenses_file = self.config_path / "licenses.json"
        if not licenses_file.exists():
            sample_licenses = [
                {
                    "license_key": "A1B2C3D4E5F6G7H8",
                    "user_name": "Demo Student",
                    "user_email": "student@demo.edu",
                    "role": "student",
                    "college_name": "Demo College",
                    "expiry_date": "2030-12-31T23:59:59"
                },
                {
                    "license_key": "TEACHER123456789",
                    "user_name": "Demo Teacher",
                    "user_email": "teacher@demo.edu",
                    "role": "teacher",
                    "college_name": "Demo College",
                    "expiry_date": "2030-12-31T23:59:59"
                },
                # 👇 YOUR REAL LICENSE — UNCOMMENT & UPDATE
                {
                    "license_key": "C7B4LMP8PZDE6VMD",
                    "user_name": "Aarav Sharma",
                    "user_email": "aarav.sharma@gmail.com",
                    "role": "student",
                    "college_name": "Your Institution",
                    "expiry_date": "2026-12-31T23:59:59"
                }
            ]
            try:
                with open(licenses_file, 'w', encoding='utf-8') as f:
                    json.dump(sample_licenses, f, indent=2, ensure_ascii=False)
                print(f"[INFO] Created licenses.json at: {licenses_file}")
            except Exception as e:
                print(f"[WARN] Could not create licenses.json: {e}")

        self._ensure_directories()
        self.init_database()
        self.load_modules()
    
    def _ensure_directories(self):
        directories = [
            self.data_path,
            self.modules_path,
            self.assets_path,
            self.config_path,
            self.assets_path / "models",
            self.assets_path / "excel",
            self.assets_path / "guides",
            self.assets_path / "witness",
            self.assets_path / "icons"
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def init_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT UNIQUE NOT NULL,
                    user_type TEXT NOT NULL,
                    name TEXT,
                    email TEXT,
                    password TEXT,
                    institution TEXT,
                    expiry TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    module_id TEXT,
                    title TEXT NOT NULL,
                    content TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    module_id TEXT,
                    due_date TEXT,
                    created_by INTEGER,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    module_id TEXT,
                    progress_percentage INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    time_spent INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS module_access (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    module_id TEXT,
                    access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exercise_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_id INTEGER,
                    user_id INTEGER,
                    submission_text TEXT,
                    file_path TEXT,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    grade INTEGER,
                    feedback TEXT,
                    FOREIGN KEY (exercise_id) REFERENCES exercises (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN password TEXT")
            except sqlite3.OperationalError:
                pass
            conn.commit()
        except Exception as e:
            print(f"ERROR initializing database: {e}")
        finally:
            if conn:
                conn.close()
    
    def load_modules(self):
        modules_file = self.modules_path / "modules.json"
        if not modules_file.exists():
            default_modules = {"modules": []}
            with open(modules_file, 'w') as f:
                json.dump(default_modules, f, indent=2)
        try:
            with open(modules_file, 'r') as f:
                self.modules_config = json.load(f)
        except Exception as e:
            print(f"ERROR loading modules.json: {e}")
            self.modules_config = {"modules": []}
    
    def get_user_modules(self, user_type):
        return [m for m in self.modules_config["modules"] if user_type in m["access_level"]]
    
    def launch_file(self, file_path, user_role=None):
        full_path = resource_path(f"assets/models/{file_path}")
        if full_path.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(full_path))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(full_path)])
                else:
                    subprocess.Popen(["xdg-open", str(full_path)])
                return True
            except Exception as e:
                return False
        return False
    
    def start_flask_server(self):
        app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)
    
    def create_window(self):
        self.window = webview.create_window(
            title='Faculty Tool Box By Nivid Informatics Pvt Ltd',
            url='http://127.0.0.1:8080',
            width=1400,
            height=900,
            min_size=(1200, 800),
            resizable=True
        )
        try:
            icon_path = str(resource_path('ui/NividLogo.ico'))
            if Path(icon_path).exists():
                hwnd = webview.windows[0].hwnd
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, ctypes.wintypes.LPCWSTR(icon_path))
        except Exception as e:
            print(f"Icon set failed: {e}")
        return self.window
    
    def run(self):
        flask_thread = threading.Thread(target=self.start_flask_server, daemon=True)
        flask_thread.start()
        window = self.create_window()
        webview.start(debug=False)

edu_app = EDUToolboxApp()

def get_user_id_from_session():
    if not session.get('logged_in'):
        return None, "User not logged in"
    raw_user_id = session.get('user_id')
    if raw_user_id is None:
        return None, "Session missing 'user_id'"
    try:
        user_id = int(raw_user_id)
        if user_id <= 0:
            raise ValueError("user_id must be positive")
    except (ValueError, TypeError):
        return None, f"Invalid user_id in session: {raw_user_id!r}"
    try:
        conn = sqlite3.connect(edu_app.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result is None:
            return None, f"User ID {user_id} not found in database"
    except Exception as e:
        return None, f"Database error during user validation: {e}"
    return user_id, None

@app.before_request
def track_session():
    pass

@app.after_request
def track_redirects(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

@app.route('/')
def index():
    return render_template('Login.html')

@app.route('/login', methods=['POST'])
def login():
    user_type = request.form.get('user_type', '').strip().lower()
    email = request.form.get('email', '').strip().lower()
    activation_key = request.form.get('activation_key', '').strip()

    if not all([user_type, email, activation_key]):
        return '''
        <script>
            alert("❌ ALL FIELDS ARE REQUIRED:\\n• Role\\n• Email\\n• Activation Key");
            history.back();
        </script>
        ''', 400

    # ✅ FIXED: Load licenses.json from bundled resources
    licenses_json = resource_path("config/licenses.json")
    print(f"[DEBUG] Loading licenses from: {licenses_json}")

    if not licenses_json.exists():
        print(f"[ERROR] licenses.json NOT FOUND at: {licenses_json}")
        return '''
        <script>
            alert("❌ License system error. Contact admin.");
            history.back();
        </script>
        ''', 500

    # 🔒 BOM-safe JSON loading
    try:
        with open(licenses_json, 'rb') as f:
            raw = f.read()
        
        # Remove UTF-8 BOM if present
        if raw.startswith(b'\xef\xbb\xbf'):
            raw = raw[3:]
        
        text = raw.decode('utf-8').strip()
        if not text:
            raise ValueError("licenses.json is empty")
        
        licenses = json.loads(text)
        if not isinstance(licenses, list):
            raise ValueError("licenses.json must be a JSON array")

    except Exception as e:
        error_msg = f"JSON error: {e}"
        print(f"[ERROR] {error_msg}")
        log_file = Path(sys.executable).parent / "license_error.log"
        with open(log_file, 'w', encoding='utf-8') as lf:
            lf.write(f"{datetime.now()}: {error_msg}\n")
            lf.write(f"File used: {licenses_json}\n")
        
        return '''
        <script>
            alert("❌ Invalid license file.\\nSee license_error.log for details.");
            history.back();
        </script>
        ''', 500

    user_info = None
    for lic in licenses:
        if (
            lic.get('license_key') == activation_key and
            lic.get('user_email', '').strip().lower() == email and
            lic.get('role', '').strip().lower() == user_type
        ):
            user_info = lic
            break

    if not user_info:
        return '''
        <script>
            alert("❌ LOGIN FAILED!\\n\\n• Email and activation key must match.\\n• Check case & spacing.");
            history.back();
        </script>
        ''', 401

    name = user_info.get('user_name', email.split('@')[0])

    conn = sqlite3.connect(edu_app.db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE user_key = ?", (activation_key,))
        row = cursor.fetchone()
        if row:
            user_id = row[0]
        else:
            cursor.execute('''
                INSERT INTO users (user_key, user_type, name, email, institution, expiry)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                activation_key, user_type, name, email,
                user_info.get('college_name', 'N/A'),
                user_info.get('expiry_date', '')
            ))
            user_id = cursor.lastrowid
            conn.commit()
    except Exception as e:
        conn.close()
        print(f"[DB ERROR] {e}")
        return '''
        <script>
            alert("❌ Database error.");
            history.back();
        </script>
        ''', 500
    conn.close()

    session.update({
        'logged_in': True,
        'role': user_type,
        'name': name,
        'email': email,
        'user_id': user_id,
        'activation_key': activation_key
    })

    return redirect(f'/{user_type}/dashboard')

# ✅ SECURE ROUTES
def require_login(role=None):
    if not session.get('logged_in'):
        return redirect('/')
    if role and session.get('role') != role:
        return redirect('/')
    return None

@app.route('/student/dashboard')
def student_dashboard():
    if require_login('student'):
        return require_login('student')
    return render_template('Student Panel/Student_Dashboard.html')

@app.route('/teacher/dashboard')
def teacher_dashboard():
    if require_login('teacher'):
        return require_login('teacher')
    return render_template('Teacher Panel/Teacher_Dashboard.html')

@app.route('/student/library')
def student_library():
    if require_login('student'):
        return require_login('student')
    return render_template('Student Panel/Model_Library.html')

@app.route('/student/notes')
def student_notes():
    if require_login('student'):
        return require_login('student')
    return render_template('Student Panel/My_Notes_Student.html')

@app.route('/student/exercises')
def student_exercises():
    if require_login('student'):
        return require_login('student')
    return render_template('Student Panel/Assignments_Student.html')

@app.route('/teacher/library')
def teacher_library():
    if require_login('teacher'):
        return require_login('teacher')
    return render_template('Teacher Panel/Model_Library.html')

@app.route('/teacher/students')
def teacher_students():
    if require_login('teacher'):
        return require_login('teacher')
    return render_template('Teacher Panel/Students_Data.html')

@app.route('/teacher/exercises')
def teacher_exercises():
    if require_login('teacher'):
        return require_login('teacher')
    return render_template('Teacher Panel/Assignments.html')

@app.route('/teacher/analytics')
def teacher_analytics():
    if require_login('teacher'):
        return require_login('teacher')
    return '<h1>Analytics</h1><p><a href="/teacher/dashboard">Back to Dashboard</a></p>'

# Navigation fixes
@app.route('/Student_Dashboard.html')
def student_dashboard_html():
    return redirect('/student/dashboard')

@app.route('/Model_Library.html')
def student_model_library_html():
    return redirect('/student/library')

@app.route('/My_Notes_Student.html')
def student_notes_html():
    return redirect('/student/notes')

@app.route('/Assignments_Student.html')
def student_assignments_html():
    return redirect('/student/exercises')

@app.route('/Teacher_Dashboard.html')
def teacher_dashboard_html():
    return redirect('/teacher/dashboard')

@app.route('/teacher/Model_Library.html')
def teacher_model_library_html():
    return redirect('/teacher/library')

@app.route('/assignment.html')
def teacher_assignment_html():
    return redirect('/teacher/exercises')

# APIs
@app.route('/api/modules')
def get_modules():
    user_type = session.get('role', 'student')
    modules = edu_app.get_user_modules(user_type)
    return jsonify({'modules': modules})

@app.route('/api/launch_file', methods=['POST'])
def launch_file():
    data = request.get_json()
    file_path = data.get('file_path')
    if not file_path:
        return jsonify({"success": False, "error": "No file path"}), 400
    normalized = os.path.normpath(file_path)
    if '..' in normalized or normalized.startswith(os.sep) or ':' in normalized:
        return jsonify({"success": False, "error": "Invalid path"}), 400
    full_path = resource_path(f"assets/models/{normalized}")
    if not full_path.exists():
        return jsonify({"success": False, "error": "File not found"}), 404
    try:
        if sys.platform == "win32":
            os.startfile(str(full_path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(full_path)])
        else:
            subprocess.Popen(["xdg-open", str(full_path)])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to open file"}), 500

@app.route('/api/notes', methods=['GET', 'POST'])
@app.route('/api/notes/<int:note_id>', methods=['PUT', 'DELETE'])
def handle_notes(note_id=None):
    user_id, error = get_user_id_from_session()
    if error:
        return jsonify({"success": False, "error": error}), 401
    conn = sqlite3.connect(edu_app.db_path)
    cursor = conn.cursor()
    try:
        if request.method == 'GET':
            cursor.execute('SELECT id, title, content, tags, created_at FROM notes WHERE user_id = ? ORDER BY title', (user_id,))
            notes = [{"id": r[0], "title": r[1], "content": r[2], "tags": r[3] or "", "created_at": r[4]} for r in cursor.fetchall()]
            return jsonify({"notes": notes})
        elif request.method == 'POST':
            data = request.get_json()
            title = (data.get('title') or '').strip()
            content = (data.get('content') or '').strip()
            if not title or not content:
                return jsonify({"success": False, "error": "Title and content required"}), 400
            cursor.execute('INSERT INTO notes (user_id, module_id, title, content, tags) VALUES (?, ?, ?, ?, ?)', (user_id, 'general', title, content, data.get('tags', '')))
            note_id_new = cursor.lastrowid
            conn.commit()
            return jsonify({"success": True, "id": note_id_new})
        elif request.method == 'PUT' and note_id:
            data = request.get_json()
            title = (data.get('title') or '').strip()
            content = (data.get('content') or '').strip()
            if not title or not content:
                return jsonify({"success": False, "error": "Title and content required"}), 400
            cursor.execute('UPDATE notes SET title = ?, content = ?, tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?', (title, content, data.get('tags', ''), note_id, user_id))
            conn.commit()
            return jsonify({"success": cursor.rowcount > 0})
        elif request.method == 'DELETE' and note_id:
            cursor.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
            conn.commit()
            return jsonify({"success": cursor.rowcount > 0})
        return jsonify({"error": "Invalid method"}), 405
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@app.route('/files/<path:filename>')
@app.route('/api/download_file/<path:filename>')
def serve_files(filename):
    normalized = os.path.normpath(filename)
    if '..' in normalized or normalized.startswith(os.sep) or ':' in normalized:
        return "Invalid path", 400
    file_path = resource_path(f"assets/models/{normalized}")
    if not file_path.exists():
        return "File not found", 404
    return send_file(str(file_path), as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Logout</title>
        <script>
            history.replaceState(null, "", "/");
            window.location.replace("/");
        </script>
    </head>
    <body>
        <p>Logging out...</p>
        <noscript>
            <meta http-equiv="refresh" content="0;url=/">
            <p><a href="/">Go to Login</a></p>
        </noscript>
    </body>
    </html>
    '''

@app.route('/<path:filename>')
def catch_all(filename):
    static_extensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico']
    if any(filename.endswith(ext) for ext in static_extensions):
        try:
            return send_from_directory(resource_path('static'), filename)
        except:
            return '', 404
    if filename.endswith('.html'):
        if 'Model_Library' in filename:
            return redirect('/student/library') if 'student' in filename.lower() else redirect('/teacher/library')
        elif 'My_Notes' in filename or 'Notes' in filename:
            return redirect('/student/notes')
        elif 'Assignments' in filename:
            return redirect('/student/exercises') if 'student' in filename.lower() else redirect('/teacher/exercises')
        elif 'Students_Data' in filename:
            return redirect('/teacher/students')
        elif 'Student_Dashboard' in filename:
            return redirect('/student/dashboard')
        elif 'Teacher_Dashboard' in filename:
            return redirect('/teacher/dashboard')
        elif 'Login' in filename:
            return redirect('/')
    return '', 404

if __name__ == '__main__':
    try:
        edu_app.run()
    except Exception as e:
        error_msg = f"CRITICAL ERROR: {e}\n{traceback.format_exc()}"
        log_path = Path(sys.executable).parent / "startup_error.log"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(error_msg)
        input("Press Enter to exit...")
        sys.exit(1)