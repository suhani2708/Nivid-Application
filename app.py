#!/usr/bin/env python3
"""
EDU Toolbox - Multi-Module Flask Desktop Application
Connects existing HTML designs to backend functionality
"""
import os
import sys
import json
import sqlite3
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, make_response, send_from_directory
import webview

def resource_path(relative_path):
    """Get absolute path to resource for PyInstaller compatibility"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent
    
    # Handle Windows path separators
    if os.name == 'nt':
        relative_path = relative_path.replace('/', '\\')
    
    return Path(base_path) / relative_path

# Simple logging to console only
def log_diagnostic(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    print(full_message)  # Console output only

# Get base directory - FIXED FOR EXECUTABLE
if getattr(sys, 'frozen', False):
    # Running as PyInstaller .exe
    BASE_DIR = Path(sys.executable).parent
else:
    # Running as script (python app.py)
    BASE_DIR = Path(__file__).parent
print(f"Application base directory (persistent): {BASE_DIR}")

# Flask app setup
app = Flask(__name__, 
           template_folder=resource_path('ui'),
           static_folder=resource_path('static'))

# CRITICAL: Session configuration for login to work - PROVEN WORKING
app.secret_key = 'edu_toolbox_secure_key_2024_FIXED'
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_PERMANENT'] = False

print(f"Flask app configured with secret key: {app.secret_key[:10]}...")
print(f"Session config: {dict(app.config)}")

class EDUToolboxApp:
    def __init__(self):
        self.base_path = BASE_DIR
        self.ui_path = resource_path('ui')
        self.data_path = BASE_DIR/"data"
        self.modules_path = resource_path('modules')
        self.assets_path = resource_path('assets')
        self.config_path = resource_path('config')
        self.db_path = self.data_path / "user_data.db"
        
        # Create directories if missing
        self._ensure_directories()
        
        # Initialize database
        self.init_database()
        
        # Load modules configuration
        self.load_modules()
    
    def _ensure_directories(self):
        """Create essential directories with safety checks"""
        directories = [
            self.data_path,
            self.modules_path,
            self.assets_path,
            self.config_path,
            self.assets_path / "models",  # CRITICAL FOR YOUR FILES
            self.assets_path / "excel",
            self.assets_path / "guides",
            self.assets_path / "witness",
            self.assets_path / "icons"
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                print(f"Ensured directory exists: {directory}")
            except Exception as e:
                print(f"ERROR creating directory {directory}: {e}")
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT UNIQUE NOT NULL,
                    user_type TEXT NOT NULL,
                    email TEXT,
                    institution TEXT,
                    expiry TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Notes table
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
            
            # Exercises table
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
            
            # Student progress table
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
            
            # Module access table
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
            
            # Exercise submissions table
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
            
            conn.commit()
            print(f"Database initialized at: {self.db_path}")
        except Exception as e:
            print(f"ERROR initializing database: {e}")
        finally:
            if conn:
                conn.close()
    
    def load_modules(self):
        """Load modules configuration with safety checks"""
        modules_file = self.modules_path / "modules.json"
        
        # Create default modules if file doesn't exist
        if not modules_file.exists():
            default_modules = {
                "modules": [
                    {
                        "id": "line_balancing",
                        "name": "Line Balancing",
                        "description": "Production line optimization and workstation balancing",
                        "files": {
                            "excel": "Line balancing adv.xlsm",
                            "witness": "Line Balancing 3d clothing Mfg(after1).mod",
                            "guide": "User_Guide.pptx",
                            "problem": "Problem Statement_Line Balancing .docx",
                            "example": "Example Problem Statement & Step-by-step.docx",
                            "witness_export": "LB.wexp"
                        },
                        "access_level": ["student", "teacher"]
                    },
                    {
                        "id": "supply_chain",
                        "name": "Supply Chain Management",
                        "description": "Supply chain optimization and network design",
                        "files": {
                            "excel": "supply_chain_model.xlsm",
                            "guide": "Supply_Chain_Guide.pptx"
                        },
                        "access_level": ["student", "teacher"]
                    },
                    {
                        "id": "mrp",
                        "name": "Material Requirements Planning",
                        "description": "MRP calculations and inventory management",
                        "files": {
                            "excel": "mrp_calculator.xlsm",
                            "guide": "MRP_Guide.pptx"
                        },
                        "access_level": ["student", "teacher"]
                    }
                ]
            }
            
            try:
                with open(modules_file, 'w') as f:
                    json.dump(default_modules, f, indent=2)
                print(f"Created default modules configuration at: {modules_file}")
            except Exception as e:
                print(f"ERROR creating modules.json: {e}")
        
        # Load configuration
        try:
            with open(modules_file, 'r') as f:
                self.modules_config = json.load(f)
            print(f"Loaded modules configuration from: {modules_file}")
        except Exception as e:
            print(f"ERROR loading modules configuration: {e}")
            self.modules_config = {"modules": []}
    
    def validate_license(self, user_key, user_type):
        """Validate license and get/create user"""
        # Demo licenses for testing
        demo_licenses = {
            "A1B2C3D4E5F6G7H8": {"type": "student", "email": "student@demo.edu"},
            "TEACHER123456789": {"type": "teacher", "email": "teacher@demo.edu"}
        }
        
        if user_key in demo_licenses and demo_licenses[user_key]["type"] == user_type:
            # Get or create user in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM users WHERE user_key = ?", (user_key,))
            user = cursor.fetchone()
            
            if not user:
                cursor.execute('''
                    INSERT INTO users (user_key, user_type, email, institution, expiry)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_key, user_type, demo_licenses[user_key]["email"], 
                     "Demo Institution", "2025-12-31"))
                user_id = cursor.lastrowid
                conn.commit()
            else:
                user_id = user[0]
            
            conn.close()
            return True, {"id": user_id, "user_key": user_key, "user_type": user_type}
        
        return False, "Invalid license"
    
    def get_user_modules(self, user_type):
        """Get modules accessible to user type"""
        accessible_modules = []
        for module in self.modules_config["modules"]:
            if user_type in module["access_level"]:
                accessible_modules.append(module)
        return accessible_modules
    
    def launch_file(self, file_path, user_role=None):
        """Launch actual educational files from assets/models directory"""
        print(f"DEBUG: File launch requested: {file_path}")
        
        # Resolve full path using resource_path
        full_path = resource_path(f"assets/models/{file_path}")
        print(f"DEBUG: Resolved file path: {full_path}")
        print(f"DEBUG: File exists? {full_path.exists()}")
        
        if full_path.exists():
            try:
                print(f"DEBUG: Opening file: {full_path}")
                # Use platform-specific opening method
                if sys.platform == "win32":
                    os.startfile(str(full_path))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(full_path)])
                else:  # linux
                    subprocess.Popen(["xdg-open", str(full_path)])
                return True
            except Exception as e:
                print(f"DEBUG: File open error: {e}")
                return False
        else:
            print(f"DEBUG: File NOT FOUND at: {full_path}")
            # List available files for debugging
            try:
                if full_path.parent.exists():
                    files = [f.name for f in full_path.parent.iterdir() if f.is_file()]
                    print(f"DEBUG: Available files in directory: {files}")
                else:
                    print(f"DEBUG: Directory doesn't exist: {full_path.parent}")
            except Exception as e:
                print(f"DEBUG: Directory listing error: {e}")
            return False
    
    def start_flask_server(self):
        """Start Flask server in a separate thread"""
        app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)
    
    def create_window(self):
        """Create and configure the webview window"""
        self.window = webview.create_window(
            title='EDU Toolbox - Multi-Module Learning Platform',
            url='http://127.0.0.1:8080',
            width=1400,
            height=900,
            min_size=(1200, 800),
            resizable=True
        )
        return self.window
    
    def run(self):
        """Run the desktop application"""
        flask_thread = threading.Thread(target=self.start_flask_server, daemon=True)
        flask_thread.start()
        
        window = self.create_window()
        webview.start(debug=False)

# Global app instance
edu_app = EDUToolboxApp()

# COMPREHENSIVE TRACKING SYSTEM
@app.before_request
def track_session():
    """Track every request and session state"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    session_id = request.cookies.get('session', 'NO_SESSION')
    print(f"\n[{timestamp}] REQUEST: {request.method} {request.path}")
    print(f"[{timestamp}] Session ID: {session_id[:20]}..." if len(session_id) > 20 else f"[{timestamp}] Session ID: {session_id}")
    print(f"[{timestamp}] Session Data: {dict(session)}")
    if request.form:
        print(f"[{timestamp}] Form Data: {dict(request.form)}")
    print(f"[{timestamp}] Cookies: {len(request.cookies)} cookies")

@app.after_request
def track_redirects(response):
    """Track all redirects and responses with security headers"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    # SECURITY: Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    if response.status_code in [301, 302, 303, 307, 308]:
        location = response.headers.get('Location', 'unknown')
        print(f"[{timestamp}] REDIRECT: {request.path} -> {location} (Status: {response.status_code})")
        print(f"[{timestamp}] Session after redirect: {dict(session)}")
    else:
        print(f"[{timestamp}] RESPONSE: {response.status_code} for {request.path}")
    return response

# Flask Routes
@app.route('/')
def index():
    return render_template('Login.html')

@app.route('/login', methods=['POST'])
def login():
    user_type = request.form.get('user_type', 'student')
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    activation_key = request.form.get('activation_key', '').strip()

    # ✅ Require all fields
    if not user_type or not name or not email or not password or not activation_key:
        return '''
        <script>
            alert("All fields are required: Name, Email, Password, and FTB Activation Key.");
            window.history.back();
        </script>
        ''', 400

    # ✅ Store real user info in session
    session.update({
        'logged_in': True,
        'role': user_type,
        'name': name,              # ← Real name from form
        'email': email,
        'activation_key': activation_key,
        'user_id': f"{user_type}{activation_key.replace(' ', '')}"
    })

    return redirect(f'/{user_type}/dashboard')

@app.route('/student/dashboard')
def student_dashboard():
    return render_template('Student Panel/Student_Dashboard.html')

@app.route('/teacher/dashboard')
def teacher_dashboard():
    return render_template('Teacher Panel/Teacher_Dashboard.html')

# Student Pages - No Validation
@app.route('/student/library')
def student_library():
    try:
        return render_template('Student Panel/Model_Library.html')
    except:
        return '<h1>Student Model Library</h1><p><a href="/student/dashboard">Back to Dashboard</a></p>'

@app.route('/student/notes')
def student_notes():
    try:
        return render_template('Student Panel/My_Notes_Student.html')
    except:
        return '<h1>Student Notes</h1><p><a href="/student/dashboard">Back to Dashboard</a></p>'

@app.route('/student/exercises')
def student_exercises():
    try:
        return render_template('Student Panel/Assignments_Student.html')
    except:
        return '<h1>Student Exercises</h1><p><a href="/student/dashboard">Back to Dashboard</a></p>'

# Teacher Pages - No Validation
@app.route('/teacher/library')
def teacher_library():
    try:
        return render_template('Teacher Panel/Model_Library.html')
    except:
        return '<h1>Teacher Model Library</h1><p><a href="/teacher/dashboard">Back to Dashboard</a></p>'


@app.route('/teacher/students')
def teacher_students():
    try:
        return render_template('Teacher Panel/Students_Data.html')
    except:
        return '<h1>Students Data</h1><p><a href="/teacher/dashboard">Back to Dashboard</a></p>'

@app.route('/teacher/exercises')
def teacher_exercises():
    try:
        return render_template('Teacher Panel/Assignments.html')
    except:

        return '<h1>Teacher Exercises</h1><p><a href="/teacher/dashboard">Back to Dashboard</a></p>'

@app.route('/teacher/analytics')
def teacher_analytics():
    return '<h1>Analytics</h1><p><a href="/teacher/dashboard">Back to Dashboard</a></p>'

# Settings and other pages
@app.route('/settings')
def settings():
    return '<h1>Settings</h1><p><a href="/">Back to Home</a></p>'

# Fix navigation - Student Panel
@app.route('/Student_Dashboard.html')
@app.route('/Student Panel/Student_Dashboard.html')
def student_dashboard_html():
    return redirect('/student/dashboard')

@app.route('/Model_Library.html')
@app.route('/Student Panel/Model_Library.html')
def student_model_library_html():
    return redirect('/student/library')

@app.route('/My_Notes_Student.html')
@app.route('/Student Panel/My_Notes_Student.html')
def student_notes_html():
    return redirect('/student/notes')

@app.route('/Assignments_Student.html')
@app.route('/Student Panel/Assignments_Student.html')
def student_assignments_html():
    return redirect('/student/exercises')

# Fix navigation - Teacher Panel
@app.route('/Teacher_Dashboard.html')
@app.route('/Teacher Panel/Teacher_Dashboard.html')
def teacher_dashboard_html():
    return redirect('/teacher/dashboard')

@app.route('/teacher/Model_Library.html')
@app.route('/Teacher Panel/Model_Library.html')
def teacher_model_library_html():
    return redirect('/teacher/library')

@app.route('/assignment.html')
@app.route('/Teacher Panel/assignment.html')
def teacher_assignment_html():
   
    return redirect('/teacher/exercises')

# API Routes for backend functionality
@app.route('/api/modules')
def get_modules():
    """Get modules accessible to current user"""
    print("DEMO MODE: Modules access without authentication")
    user_type = session.get('role', 'student')  # Default to student
    print(f"Modules access - Role: {user_type}")
    modules = edu_app.get_user_modules(user_type)
    return jsonify({'modules': modules})


    

@app.route('/api/launch_file', methods=['POST'])
def launch_file():
    """Securely launch educational files"""
    data = request.get_json()
    file_path = data.get('file_path')
    if not file_path:
        return jsonify({"success": False, "error": "No file path"}), 400

    # SECURITY: Path traversal protection
    normalized = os.path.normpath(file_path)
    if '..' in normalized or normalized.startswith(os.sep) or ':' in normalized:
        print(f"[SECURITY] Blocked path traversal attempt: {file_path}")
        return jsonify({"success": False, "error": "Invalid path"}), 400

    # Resolve path using resource_path
    full_path = resource_path(f"assets/models/{normalized}")
    print(f"[LAUNCH] Resolved path: {full_path}")

    if not full_path.exists():
        print(f"[ERROR] File not found: {full_path}")
        return jsonify({"success": False, "error": "File not found"}), 404

    try:
        print(f"[LAUNCH] Opening file: {full_path}")
        # Use platform-specific opening method
        if sys.platform == "win32":
            os.startfile(str(full_path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(full_path)])
        else:  # linux
            subprocess.Popen(["xdg-open", str(full_path)])
        return jsonify({"success": True})
    except Exception as e:
        print(f"[LAUNCH ERROR] {e}")
        return jsonify({"success": False, "error": "Failed to open file"}), 500

# ===== 🔥 FIXED: NOTES API — FULL CRUD, UTF-8 SAFE =====
@app.route('/api/notes', methods=['GET', 'POST'])
@app.route('/api/notes/<int:note_id>', methods=['PUT', 'DELETE'])
def handle_notes(note_id=None):
    # 🔑 Map session role to integer user_id (1 = student, 2 = teacher)
    user_role = session.get('role', 'student')
    user_id = 1 if user_role == 'student' else 2

    conn = None
    try:
        conn = sqlite3.connect(edu_app.db_path)
        cursor = conn.cursor()

        # ✅ Ensure demo users exist (idempotent)
        cursor.execute(
            "INSERT OR IGNORE INTO users (id, user_key, user_type, email, institution, expiry) VALUES (?, ?, ?, ?, ?, ?)",
            (1, 'DEMO_STUDENT', 'student', 'student@demo.edu', 'Demo Institute', '2030-12-31')
        )
        cursor.execute(
            "INSERT OR IGNORE INTO users (id, user_key, user_type, email, institution, expiry) VALUES (?, ?, ?, ?, ?, ?)",
            (2, 'DEMO_TEACHER', 'teacher', 'teacher@demo.edu', 'Demo Institute', '2030-12-31')
        )
        conn.commit()

        # ===== GET NOTES =====
        if request.method == 'GET':
            cursor.execute(
                'SELECT id, title, content, tags, created_at FROM notes WHERE user_id = ? ORDER BY title',
                (user_id,)
            )
            notes = [
                {
                    "id": r[0],
                    "title": r[1],
                    "content": r[2],
                    "tags": r[3],
                    "created_at": r[4]
                } for r in cursor.fetchall()
            ]
            return jsonify({"notes": notes})

        # ===== CREATE NOTE =====
        elif request.method == 'POST':
            data = request.get_json()
            if not isinstance(data, dict):
                return jsonify({"success": False, "error": "Invalid JSON"}), 400

            title = (data.get('title') or '').strip()
            content = (data.get('content') or '').strip()

            if not title or not content:
                return jsonify({"success": False, "error": "Title and content required"}), 400

            cursor.execute(
                'INSERT INTO notes (user_id, module_id, title, content, tags) VALUES (?, ?, ?, ?, ?)',
                (user_id, 'general', title, content, data.get('tags', ''))
            )
            note_id_new = cursor.lastrowid
            conn.commit()

            print(f"[NOTE] Created note {note_id_new} for {user_role}")

            return jsonify({"success": True, "id": note_id_new})

        # ===== UPDATE NOTE =====
        elif request.method == 'PUT' and note_id:
            data = request.get_json()

            title = (data.get('title') or '').strip()
            content = (data.get('content') or '').strip()

            if not title or not content:
                return jsonify({"success": False, "error": "Title and content required"}), 400

            cursor.execute(
                'UPDATE notes SET title = ?, content = ?, tags = ? WHERE id = ? AND user_id = ?',
                (title, content, data.get('tags', ''), note_id, user_id)
            )
            conn.commit()

            return jsonify({"success": cursor.rowcount > 0})

        # ===== DELETE NOTE =====
        elif request.method == 'DELETE' and note_id:
            cursor.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
            conn.commit()

            return jsonify({"success": cursor.rowcount > 0})

        return jsonify({"error": "Invalid method"}), 405

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        if conn:
            conn.close()


# ===== 🔥 FIXED: FILE SERVING — UTF-8 SAFE =====
@app.route('/files/<path:filename>')
def serve_files(filename):
    """Securely serve files from assets/models directory"""
    try:
        # SECURITY: Clean the path
        normalized = os.path.normpath(filename)

        if '..' in normalized or normalized.startswith(os.sep) or ':' in normalized:
            print(f"[SECURITY] Blocked path traversal attempt: {filename}")
            return "Invalid path", 400

        # Resolve file path
        file_path = resource_path(f"assets/models/{normalized}")

        if not file_path.exists():
            print(f"[ERROR] File not found: {file_path}")
            return "File not found", 404

        print(f"[SERVE] Sending file: {file_path}")

        # Serve safely
        return send_file(str(file_path), as_attachment=True)

    except Exception as e:
        print(f"ERROR serving file '{filename}': {e}")
        return "File not found or access denied", 404

@app.route('/api/download_file/<path:filename>')
def download_file(filename):
    """Download educational files securely"""
    print(f"File download request for: {filename}")
    
    # SECURITY: Path traversal protection
    filename = os.path.normpath(filename)
    if '..' in filename or filename.startswith('/') or ':' in filename:
        print(f"SECURITY: Path traversal attempt blocked: {filename}")
        return jsonify({'error': 'Invalid file path'}), 400
    
    # Resolve file path
    file_path = resource_path(f"assets/models/{filename}")
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return jsonify({'error': 'File not found'}), 404
    
    try:
        print(f"Serving file download: {file_path}")
        return send_file(str(file_path), as_attachment=True)
    except Exception as e:
        print(f"Error serving file: {e}")
        return jsonify({'error': 'Error serving file'}), 500

@app.route('/logout')
def logout():
    """Handle logout with tracking"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"\n[{timestamp}] LOGOUT REQUEST")
    print(f"[{timestamp}] Session before clear: {dict(session)}")
    session.clear()
    print(f"[{timestamp}] Session cleared, redirecting to /")
    return redirect('/')

# Catch-all for static assets
@app.route('/<path:filename>')
def catch_all(filename):
    """Handle static assets and redirects"""
    # Handle common static files
    static_extensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico']
    if any(filename.endswith(ext) for ext in static_extensions):
        try:
            return send_from_directory(resource_path('static'), filename)
        except:
            return '', 404
    
    # Handle HTML file redirects
    if filename.endswith('.html'):
        print(f"Redirecting HTML file: {filename}")
        if 'Model_Library' in filename:
            if 'student' in filename.lower() or 'Student' in filename:
                return redirect('/student/library')
            else:
                return redirect('/teacher/library')
        elif 'My_Notes' in filename or 'Notes' in filename:
            return redirect('/student/notes')
        elif 'Assignments' in filename:
            if 'student' in filename.lower() or 'Student' in filename:
                return redirect('/student/exercises')
            else:
                return redirect('/teacher/exercises')
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
        # Start the application
        edu_app.run()
    except Exception as e:
        print(f"CRITICAL ERROR starting application: {e}")
        sys.exit(1)