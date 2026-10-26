import os
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))

# Prefer a persistent volume path on Railway (mount a volume at /data).
# Falls back to local directory for development.
DATA_DIR = os.environ.get('DATA_DIR', BASE)
os.makedirs(DATA_DIR, exist_ok=True)

DB = os.path.join(DATA_DIR, 'placerhive.db')
# Legacy PythonAnywhere support
LEGACY_DB = os.path.expanduser('~/placerhive-site-backup/placerhive.db')
if not os.path.exists(DB) and os.path.exists(LEGACY_DB):
    import shutil
    shutil.copy2(LEGACY_DB, DB)

UPLOADS = os.path.join(DATA_DIR, 'uploads')
STATIC_IMAGES = os.path.join(BASE, 'static', 'images')
os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(STATIC_IMAGES, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32).hex())
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Chibuike12to13#')
PAYMENT_AMOUNT = os.environ.get('PAYMENT_AMOUNT', '299.00')
PAYMENT_DETAILS = {
    'Account Name': 'PETER GODSTIME EFERIDONO',
    'Bank': 'Lead Bank',
    'Account Number': '214175521736',
    'Routing Number': '101019644',
    'Account Type': 'Personal Checking',
    'Account Address': '9450 Southwest Gemini Drive, Beaverton, OR, 97008, USA'
}

ALLOWED_EXTENSIONS = {
    'proof': {'.pdf', '.png', '.jpg', '.jpeg', '.webp'},
    'cv': {'.pdf', '.doc', '.docx'},
    'image': {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'},
}


def allowed_file(filename, category='image'):
    ext = os.path.splitext(filename or '')[1].lower()
    return ext in ALLOWED_EXTENSIONS.get(category, set())


DEFAULT_JOBS = [
    ('Senior Software Developer', 'USA', 'Software Development', 'Permanent', 12),
    ('Cyber Security Analyst', 'Canada', 'Cyber Security', 'Contract', 8),
    ('Financial Controller', 'Nigeria', 'Accounting & Finance', 'Permanent', 6),
    ('Civil Engineer', 'California', 'Engineering', 'Permanent', 10),
    ('HR Business Partner', 'Italy', 'Human Resources (HR)', 'Permanent', 5),
    ('IT Project Manager', 'Remote', 'IT Project & Change Management', 'Contract', 7),
    ('Marketing Manager', 'Brazil', 'Marketing & Digital', 'Permanent', 9),
    ('Facilities Manager', 'China', 'Property & Facilities Management', 'Permanent', 4),
    ('Sales Executive', 'Japan', 'Sales', 'Permanent', 15),
    ('Sustainability Consultant', 'USA', 'Sustainability', 'Contract', 5),
    ('Network Engineer', 'Cameroon', 'IT Infrastructure', 'Permanent', 7),
    ('Clinical Research Associate', 'Indonesia', 'Life Sciences', 'Contract', 4),
    ('Construction Project Manager', 'Nigeria', 'Construction', 'Permanent', 6),
    ('Data Scientist', 'Remote', 'Technology', 'Permanent', 8),
    ('Banking Relationship Manager', 'USA', 'Banking & Financial Services', 'Permanent', 5),
    ('Pharmaceutical Sales Rep', 'Canada', 'Pharmaceuticals', 'Permanent', 6),
    ('Renewable Energy Engineer', 'California', 'Alternative Energy & Renewables', 'Contract', 5),
    ('Media Account Executive', 'Italy', 'Media & Communications', 'Permanent', 7),
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def ensure_column(conn, table, column, definition):
    cols = {row['name'] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in cols:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS employer_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        contact_name TEXT NOT NULL,
        job_title TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        website TEXT,
        country TEXT,
        company_size TEXT,
        hiring_needs TEXT NOT NULL,
        budget TEXT,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'awaiting_payment',
        payment_expires_at TEXT
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL,
        transaction_ref TEXT NOT NULL,
        payer_name TEXT NOT NULL,
        proof_filename TEXT,
        submitted_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        admin_note TEXT,
        verified_at TEXT,
        expires_at TEXT,
        FOREIGN KEY(submission_id) REFERENCES employer_submissions(id)
    );
    CREATE TABLE IF NOT EXISTS job_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        full_name TEXT,
        email TEXT,
        phone TEXT,
        location TEXT,
        job_title TEXT,
        specialism TEXT,
        experience TEXT,
        job_type TEXT,
        summary TEXT,
        cv_filename TEXT,
        photo_filename TEXT,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'new'
    );
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        location TEXT NOT NULL,
        category TEXT NOT NULL,
        job_type TEXT NOT NULL,
        available_roles INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS site_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS contact_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        subject TEXT,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'new'
    );
    CREATE TABLE IF NOT EXISTS newsletter_subscribers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        last_login TEXT
    );
    CREATE TABLE IF NOT EXISTS testimonials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT,
        rating INTEGER NOT NULL DEFAULT 5,
        quote TEXT NOT NULL,
        image_filename TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    ''')

    # Migrate older databases created by the first PythonAnywhere package.
    ensure_column(conn, 'job_applications', 'user_id', 'INTEGER')
    ensure_column(conn, 'job_applications', 'location', 'TEXT')
    ensure_column(conn, 'job_applications', 'job_title', 'TEXT')
    ensure_column(conn, 'job_applications', 'specialism', 'TEXT')
    ensure_column(conn, 'job_applications', 'experience', 'TEXT')
    ensure_column(conn, 'job_applications', 'job_type', 'TEXT')
    ensure_column(conn, 'job_applications', 'summary', 'TEXT')
    ensure_column(conn, 'job_applications', 'cv_filename', 'TEXT')
    ensure_column(conn, 'job_applications', 'photo_filename', 'TEXT')
    ensure_column(conn, 'payments', 'expires_at', 'TEXT')
    ensure_column(conn, 'employer_submissions', 'payment_expires_at', 'TEXT')
    ensure_column(conn, 'jobs', 'description', 'TEXT')

    # New tables for founder, service chat, and job appeals
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS service_chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT NOT NULL,
        user_email TEXT NOT NULL,
        user_phone TEXT,
        subject TEXT DEFAULT 'Service Inquiry',
        status TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS service_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        sender TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(chat_id) REFERENCES service_chats(id)
    );
    CREATE TABLE IF NOT EXISTS job_appeals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        job_title TEXT,
        applicant_name TEXT NOT NULL,
        applicant_email TEXT NOT NULL,
        applicant_phone TEXT,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        admin_note TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    ''')

    if conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 0:
        for title, location, category, job_type, count in DEFAULT_JOBS:
            conn.execute('''INSERT INTO jobs(title,location,category,job_type,available_roles,is_active,created_at,updated_at)
                            VALUES(?,?,?,?,?,?,?,?)''',
                         (title, location, category, job_type, count, 1, now_iso(), now_iso()))

    default_settings = {
        'payment_amount': PAYMENT_AMOUNT,
        'site_logo': '/static/images/placerhive-logo.svg',
        'registration_enabled': '1',
        'applications_enabled': '1',
        'payments_enabled': '1',
        'maintenance_mode': '0',
        'founder_name': 'MR PETTER',
        'founder_title': 'Founder & Chief Executive',
        'founder_bio': 'MR PETTER is the visionary founder of PLACERHIVE. With deep experience in international recruitment and talent placement, he has built a platform that connects skilled professionals with meaningful opportunities across the globe. Under his leadership, PLACERHIVE stands for integrity, excellence, and genuine care for both candidates and employers. His commitment is to create lasting careers and successful partnerships through transparent processes and personal attention.',
        'founder_photo': '',
        'company_phone': '',
        'company_email': 'support@placerhive.com.ng',
        'company_address': '',
        'company_whatsapp': '',
        'homepage_headline': 'Find Your Next Global Opportunity',
        'homepage_subtext': 'PLACERHIVE connects talented professionals with trusted employers worldwide.',
    }
    for key, value in default_settings.items():
        if conn.execute('SELECT 1 FROM site_settings WHERE key=?', (key,)).fetchone() is None:
            conn.execute('INSERT INTO site_settings(key,value) VALUES(?,?)', (key, value))
    # Refresh sample testimonials if still the old placeholder ones
    old_samples = conn.execute("SELECT COUNT(*) FROM testimonials WHERE name LIKE 'Sample %'").fetchone()[0]
    if old_samples > 0 or conn.execute('SELECT COUNT(*) FROM testimonials').fetchone()[0] == 0:
        conn.execute("DELETE FROM testimonials WHERE name LIKE 'Sample %'")
        if conn.execute('SELECT COUNT(*) FROM testimonials').fetchone()[0] == 0:
            samples = [
                ('Adaeze Okonkwo', 'Software Engineer · Canada', 5,
                 'PLACERHIVE helped me land a remote role with a global tech company within weeks. The process was clear, professional, and genuinely supportive from day one.',
                 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&h=200&fit=crop&crop=faces'),
                ('James Carter', 'Hiring Manager · USA', 5,
                 'We filled three specialist positions through PLACERHIVE. Candidate quality was excellent and communication stayed professional throughout the engagement.',
                 'https://images.unsplash.com/photo-1560250097-0b93528c311a?w=200&h=200&fit=crop&crop=faces'),
                ('Chioma Eze', 'Financial Analyst · UK', 5,
                 'From profile submission to final placement, everything felt organised. I recommend PLACERHIVE to anyone serious about international career moves.',
                 'https://images.unsplash.com/photo-1580489944761-15a19d654956?w=200&h=200&fit=crop&crop=faces'),
                ('Marcus Adeyemi', 'Project Manager · Remote', 5,
                 'Transparent process, responsive team, and real opportunities. PLACERHIVE stands out from other recruitment platforms I have used.',
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&h=200&fit=crop&crop=faces'),
            ]
            for name, role, rating, quote, img in samples:
                conn.execute('INSERT INTO testimonials(name,role,rating,quote,image_filename,created_at) VALUES(?,?,?,?,?,?)',
                             (name, role, rating, quote, img, now_iso()))
    conn.commit()
    conn.close()


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'ok': False, 'error': 'Admin login required'}), 401
        return fn(*args, **kwargs)
    return wrapper


@app.before_request
def maintenance_guard():
    if request.path.startswith('/static') or request.path.startswith('/api/admin') or request.path == '/admin': return None
    if site_setting('maintenance_mode','0') == '1' and not session.get('admin_logged_in'):
        return render_template('message.html', title='Site maintenance', message='PLACERHIVE is temporarily unavailable while the administrator makes updates.'), 503
    return None

@app.context_processor
def globals_for_templates():
    return {'payment_amount': current_payment_amount(), 'payment_details': PAYMENT_DETAILS, 'site_logo': site_setting('site_logo'), 'current_user': current_user()}


def site_setting(key, default=''):
    try:
        conn = db(); row = conn.execute('SELECT value FROM site_settings WHERE key=?', (key,)).fetchone(); conn.close()
        return row['value'] if row else default
    except Exception:
        return default

def current_user():
    uid = session.get('user_id')
    if not uid: return None
    try:
        conn=db(); row=conn.execute('SELECT id,full_name,email,phone,is_active FROM users WHERE id=?',(uid,)).fetchone(); conn.close()
        if row and row['is_active']: return dict(row)
    except Exception:
        pass
    return None

def user_required(fn):
    """For HTML pages — redirects to login."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for('login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def api_user_required(fn):
    """For JSON API endpoints — returns 401 instead of redirect."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({'ok': False, 'error': 'Login required'}), 401
        return fn(*args, **kwargs)
    return wrapper


def current_payment_amount():
    try:
        conn = db()
        row = conn.execute("SELECT value FROM site_settings WHERE key='payment_amount'").fetchone()
        conn.close()
        return row['value'] if row else PAYMENT_AMOUNT
    except Exception:
        return PAYMENT_AMOUNT


@app.route('/')
def home():
    conn = db()
    featured_jobs = conn.execute("SELECT id,title,location,category,job_type,available_roles FROM jobs WHERE is_active=1 AND available_roles>0 ORDER BY id DESC LIMIT 6").fetchall()
    total_roles = conn.execute("SELECT COALESCE(SUM(available_roles),0) FROM jobs WHERE is_active=1").fetchone()[0]
    testimonials = conn.execute("SELECT * FROM testimonials WHERE is_active=1 ORDER BY id DESC LIMIT 6").fetchall()
    conn.close()
    return render_template('index.html', featured_jobs=[dict(r) for r in featured_jobs], total_roles=total_roles, testimonials=[dict(r) for r in testimonials])


@app.route('/jobs')
def jobs():
    return render_template('jobs.html')

@app.route('/job/<int:job_id>')
def job_detail(job_id):
    conn=db(); row=conn.execute('SELECT * FROM jobs WHERE id=? AND is_active=1',(job_id,)).fetchone(); conn.close()
    if not row or row['available_roles']<=0: return render_template('not-found.html'),404
    return render_template('job-detail.html', job=dict(row))

@app.route('/about')
def about():
    return redirect(url_for('home')+'#about')

@app.route('/contact')
def contact():
    return redirect(url_for('home')+'#contact')


@app.route('/seek-a-job')
def seek_job():
    return render_template('seek-a-job.html')


@app.route('/employer')
@app.route('/employer-bass')
def employer():
    return render_template('employer.html')


@app.route('/payment')
def payment():
    sid = request.args.get('submission_id', '')
    return render_template('payment.html', submission_id=sid)


@app.route('/payment-pending')
def payment_pending():
    return render_template('payment-pending.html')

@app.route('/track-application')
def track_application():
    return render_template('track-application.html')


@app.route('/signup')
def signup():
    if site_setting('registration_enabled','1') != '1': return render_template('message.html', title='Registration unavailable', message='New account registration is currently disabled by the administrator.'), 403
    return render_template('auth.html', mode='signup')

@app.route('/login')
def login():
    return render_template('auth.html', mode='login')

@app.post('/api/auth/signup')
def api_signup():
    if site_setting('registration_enabled','1') != '1': return jsonify({'ok':False,'error':'Registration is disabled.'}),403
    data=request.form; name=data.get('full_name','').strip(); email=data.get('email','').strip().lower(); password=data.get('password',''); phone=data.get('phone','').strip()
    if not name or not email or '@' not in email or len(password)<8: return jsonify({'ok':False,'error':'Enter a name, valid email and password of at least 8 characters.'}),400
    conn=db()
    try:
        cur=conn.execute('INSERT INTO users(full_name,email,password_hash,phone,created_at) VALUES(?,?,?,?,?)',(name,email,generate_password_hash(password),phone,now_iso())); conn.commit(); uid=cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close(); return jsonify({'ok':False,'error':'An account with that email already exists.'}),409
    conn.close(); session['user_id']=uid; return jsonify({'ok':True})

@app.post('/api/auth/login')
def api_login():
    data=request.form; email=data.get('email','').strip().lower(); password=data.get('password','')
    conn=db(); row=conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if not row or not row['is_active'] or not check_password_hash(row['password_hash'],password): conn.close(); return jsonify({'ok':False,'error':'Invalid email/password or account disabled.'}),401
    conn.execute('UPDATE users SET last_login=? WHERE id=?',(now_iso(),row['id'])); conn.commit(); conn.close(); session['user_id']=row['id']; return jsonify({'ok':True})

@app.post('/api/auth/logout')
def api_logout():
    session.pop('user_id',None); return jsonify({'ok':True})

@app.route('/account')
@user_required
def account(): return render_template('account.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.post('/api/employer')
def create_employer():
    if site_setting('payments_enabled','1') != '1': return jsonify({'ok':False,'error':'Employer payments are currently disabled by the administrator.'}),403
    data = request.form
    required = ['companyName', 'contactName', 'jobTitle', 'email', 'phone', 'country', 'companySize', 'hiringNeeds']
    if any(not data.get(k, '').strip() for k in required):
        return jsonify({'ok': False, 'error': 'Please complete all required fields.'}), 400
    conn = db()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).replace(microsecond=0).isoformat()

    cur = conn.execute('''INSERT INTO employer_submissions
      (company_name,contact_name,job_title,email,phone,website,country,company_size,hiring_needs,budget,created_at,payment_expires_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', (
        data['companyName'].strip(), data['contactName'].strip(), data['jobTitle'].strip(),
        data['email'].strip(), data['phone'].strip(), data.get('website', '').strip(), data.get('country', '').strip(),
        data.get('companySize', '').strip(), data['hiringNeeds'].strip(), data.get('budget', '').strip(), now_iso(), expires
    ))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return jsonify({'ok': True, 'id': sid})


@app.post('/api/payment')
def submit_payment():
    if site_setting('payments_enabled','1') != '1': return jsonify({'ok':False,'error':'Payments are currently disabled by the administrator.'}),403
    sid = request.form.get('submission_id', '').strip()
    ref = request.form.get('transactionRef', '').strip()
    payer = request.form.get('payerName', '').strip()
    if not sid or not ref or not payer:
        return jsonify({'ok': False, 'error': 'Submission ID, transaction reference and payer name are required.'}), 400
    conn = db()
    sub = conn.execute('SELECT * FROM employer_submissions WHERE id=?', (sid,)).fetchone()
    if not sub:
        conn.close()
        return jsonify({'ok': False, 'error': 'Employer submission not found.'}), 404
    if sub['payment_expires_at']:
        try:
            if datetime.fromisoformat(sub['payment_expires_at']) < datetime.now(timezone.utc):
                conn.close(); return jsonify({'ok':False,'error':'The 30-minute payment window has expired. Please submit a new employer request.'}), 410
        except ValueError:
            pass
    proof = request.files.get('proof')
    filename = ''
    if proof and proof.filename:
        if not allowed_file(proof.filename, 'proof'):
            conn.close()
            return jsonify({'ok': False, 'error': 'Proof must be PDF or image (png/jpg/webp).'}), 400
        filename = f"{uuid.uuid4().hex}_{secure_filename(proof.filename)}"
        proof.save(os.path.join(UPLOADS, filename))

    cur = conn.execute('''INSERT INTO payments(submission_id,transaction_ref,payer_name,proof_filename,submitted_at,expires_at)
                         VALUES(?,?,?,?,?,?)''', (sid, ref, payer, filename, now_iso(), sub['payment_expires_at']))
    conn.execute("UPDATE employer_submissions SET status='payment_pending' WHERE id=?", (sid,))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return jsonify({'ok': True, 'id': pid, 'reference': ref})


@app.post('/api/job-application')
def create_job_application():
    if site_setting('applications_enabled','1') != '1': return jsonify({'ok':False,'error':'Applications are currently disabled by the administrator.'}),403
    data = request.form
    required = ['firstName', 'lastName', 'email', 'phone', 'location', 'jobTitle', 'specialism', 'experience', 'jobType']
    if any(not data.get(k, '').strip() for k in required):
        return jsonify({'ok': False, 'error': 'Please complete all required fields.'}), 400
    cv = request.files.get('cv')
    photo = request.files.get('photo')
    cv_name = photo_name = ''
    if cv and cv.filename:
        if not allowed_file(cv.filename, 'cv'):
            return jsonify({'ok': False, 'error': 'CV must be PDF or Word document.'}), 400
        cv_name = f"cv_{uuid.uuid4().hex}_{secure_filename(cv.filename)}"
        cv.save(os.path.join(UPLOADS, cv_name))
    if photo and photo.filename:
        if not allowed_file(photo.filename, 'image'):
            return jsonify({'ok': False, 'error': 'Photo must be an image (png/jpg/webp).'}), 400
        photo_name = f"photo_{uuid.uuid4().hex}_{secure_filename(photo.filename)}"
        photo.save(os.path.join(UPLOADS, photo_name))

    conn = db()
    cur = conn.execute('''INSERT INTO job_applications
        (user_id,full_name,email,phone,location,job_title,specialism,experience,job_type,summary,cv_filename,photo_filename,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            session.get('user_id'), f"{data['firstName'].strip()} {data['lastName'].strip()}", data['email'].strip(), data['phone'].strip(),
            data['location'].strip(), data['jobTitle'].strip(), data['specialism'].strip(), data['experience'].strip(),
            data['jobType'].strip(), data.get('summary', '').strip(), cv_name, photo_name, now_iso()
        ))
    application_id = cur.lastrowid
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'application_id': application_id})


@app.get('/api/payment-config')
def payment_config():
    return jsonify({'amount': current_payment_amount(), 'details': PAYMENT_DETAILS})


@app.get('/api/jobs')
def api_jobs():
    q = request.args.get('q', '').strip().lower()
    location = request.args.get('location', '').strip().lower()
    category = request.args.get('category', '').strip().lower()
    conn = db()
    rows = conn.execute('''SELECT id,title,location,category,job_type,available_roles
                           FROM jobs WHERE is_active=1 ORDER BY id DESC''').fetchall()
    conn.close()
    jobs_data = [dict(r) for r in rows if r['available_roles'] > 0]
    if q:
        jobs_data = [j for j in jobs_data if q in j['title'].lower() or q in j['category'].lower()]
    if location:
        jobs_data = [j for j in jobs_data if location in j['location'].lower()]
    if category:
        jobs_data = [j for j in jobs_data if category in j['category'].lower()]
    return jsonify(jobs_data)



@app.post('/api/contact')
def contact_message():
    data=request.form
    name=data.get('name','').strip(); email=data.get('email','').strip(); message=data.get('message','').strip()
    if not name or not email or not message:
        return jsonify({'ok':False,'error':'Name, email and message are required.'}),400
    conn=db(); conn.execute('INSERT INTO contact_messages(name,email,phone,subject,message,created_at) VALUES(?,?,?,?,?,?)',
        (name,email,data.get('phone','').strip(),data.get('subject','').strip(),message,now_iso())); conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.post('/api/newsletter')
def newsletter():
    email=request.form.get('email','').strip().lower()
    if not email or '@' not in email: return jsonify({'ok':False,'error':'Enter a valid email address.'}),400
    conn=db()
    try:
        conn.execute('INSERT INTO newsletter_subscribers(email,created_at) VALUES(?,?)',(email,now_iso())); conn.commit()
    except sqlite3.IntegrityError:
        conn.close(); return jsonify({'ok':False,'error':'This email is already subscribed.'}),409
    conn.close(); return jsonify({'ok':True})

@app.get('/api/application/mine')
@api_user_required
def application_mine():
    conn = db()
    rows = conn.execute(
        'SELECT id,job_title,location,created_at,status FROM job_applications WHERE user_id=? ORDER BY id DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify({'applications': [dict(r) for r in rows]})


@app.get('/api/application/<int:application_id>')
def application_status(application_id):
    """Public tracking — returns limited fields only (no full email exposure beyond what is needed)."""
    conn = db()
    row = conn.execute(
        'SELECT id,full_name,job_title,location,created_at,status FROM job_applications WHERE id=?',
        (application_id,)
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({'ok': False, 'error': 'Application not found.'}), 404
    # Mask email-style privacy: only show first name + last initial if possible
    data = dict(row)
    name = (data.get('full_name') or '').strip()
    parts = name.split()
    if len(parts) >= 2:
        data['full_name'] = f'{parts[0]} {parts[-1][0]}.'
    return jsonify({'ok': True, 'application': data})


@app.patch('/api/admin/users/<int:user_id>')
@admin_required
def admin_user_update(user_id):
    data=request.get_json(silent=True) or {}; active=1 if data.get('is_active') else 0
    conn=db(); conn.execute('UPDATE users SET is_active=? WHERE id=?',(active,user_id)); conn.commit(); conn.close(); return jsonify({'ok':True})

@app.patch('/api/admin/settings')
@admin_required
def admin_settings_update():
    data = request.get_json(silent=True) or {}
    toggles = ['registration_enabled', 'applications_enabled', 'payments_enabled', 'maintenance_mode']
    text_keys = [
        'payment_amount', 'founder_name', 'founder_title', 'founder_bio',
        'company_phone', 'company_email', 'company_address', 'company_whatsapp',
        'homepage_headline', 'homepage_subtext'
    ]
    conn = db()
    for key in toggles:
        if key in data:
            value = '1' if data[key] else '0'
            conn.execute(
                'INSERT INTO site_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                (key, value)
            )
    for key in text_keys:
        if key in data:
            value = str(data[key]).strip()
            if key == 'payment_amount':
                value = value.replace(',', '')
                try:
                    if float(value) < 0:
                        raise ValueError
                    value = f'{float(value):.2f}'
                except (TypeError, ValueError):
                    conn.close()
                    return jsonify({'ok': False, 'error': 'Payment amount must be a valid non-negative number.'}), 400
            conn.execute(
                'INSERT INTO site_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                (key, value)
            )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.post('/api/admin/logo')
@admin_required
def admin_logo_upload():
    f = request.files.get('logo')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'Choose a logo image.'}), 400
    if not allowed_file(f.filename, 'image'):
        return jsonify({'ok': False, 'error': 'Logo must be an image (png/jpg/webp/svg).'}), 400
    ext = os.path.splitext(secure_filename(f.filename))[1].lower() or '.png'
    filename = f'uploaded-logo-{uuid.uuid4().hex}{ext}'
    f.save(os.path.join(STATIC_IMAGES, filename))
    path = url_for('static', filename='images/' + filename)
    conn = db()
    conn.execute(
        'INSERT INTO site_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
        ('site_logo', path)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'path': path})


@app.post('/api/admin/testimonials')
@admin_required
def admin_testimonial_create():
    data=request.form; name=data.get('name','').strip(); quote=data.get('quote','').strip(); role=data.get('role','').strip(); rating=max(1,min(5,int(data.get('rating','5') or 5)))
    if not name or not quote:
        return jsonify({'ok': False, 'error': 'Name and review are required.'}), 400
    f = request.files.get('image')
    filename = ''
    if f and f.filename:
        if not allowed_file(f.filename, 'image'):
            return jsonify({'ok': False, 'error': 'Image must be png/jpg/webp/gif.'}), 400
        filename = f'testimonial-{uuid.uuid4().hex}_{secure_filename(f.filename)}'
        f.save(os.path.join(STATIC_IMAGES, filename))
    conn = db()
    cur = conn.execute(
        'INSERT INTO testimonials(name,role,rating,quote,image_filename,created_at) VALUES(?,?,?,?,?,?)',
        (name, role, rating, quote, filename, now_iso())
    )
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return jsonify({'ok': True, 'id': tid})


@app.delete('/api/admin/testimonials/<int:testimonial_id>')
@admin_required
def admin_testimonial_delete(testimonial_id):
    conn=db(); conn.execute('DELETE FROM testimonials WHERE id=?',(testimonial_id,)); conn.commit(); conn.close(); return jsonify({'ok':True})

@app.post('/api/admin/login')
def admin_login():
    payload = request.get_json(silent=True) or {}
    if payload.get('password', '') == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Incorrect password.'}), 401


@app.post('/api/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return jsonify({'ok': True})


@app.get('/api/admin/status')
def admin_status():
    return jsonify({'logged_in': bool(session.get('admin_logged_in'))})


@app.get('/api/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = db()
    payments = conn.execute('''SELECT p.*, s.company_name,s.contact_name,s.email,s.phone,s.hiring_needs,s.status AS submission_status
        FROM payments p JOIN employer_submissions s ON s.id=p.submission_id ORDER BY p.id DESC''').fetchall()
    jobs_rows = conn.execute('SELECT * FROM jobs ORDER BY id DESC').fetchall()
    apps = conn.execute('SELECT * FROM job_applications ORDER BY id DESC LIMIT 50').fetchall()
    messages = conn.execute('SELECT * FROM contact_messages ORDER BY id DESC LIMIT 50').fetchall()
    subscribers = conn.execute('SELECT * FROM newsletter_subscribers ORDER BY id DESC LIMIT 50').fetchall()
    users = conn.execute('SELECT id,full_name,email,phone,is_active,created_at,last_login FROM users ORDER BY id DESC LIMIT 100').fetchall()
    testimonials = conn.execute('SELECT * FROM testimonials ORDER BY id DESC').fetchall()
    stats = {
        'jobs': conn.execute('SELECT COUNT(*) FROM jobs WHERE is_active=1').fetchone()[0],
        'available_roles': conn.execute('SELECT COALESCE(SUM(available_roles),0) FROM jobs WHERE is_active=1').fetchone()[0],
        'pending_payments': conn.execute("SELECT COUNT(*) FROM payments WHERE status='pending'").fetchone()[0],
        'job_applications': conn.execute('SELECT COUNT(*) FROM job_applications').fetchone()[0],
        'contact_messages': conn.execute("SELECT COUNT(*) FROM contact_messages WHERE status='new'").fetchone()[0],
        'subscribers': conn.execute('SELECT COUNT(*) FROM newsletter_subscribers').fetchone()[0],
        'users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
    }
    settings = {k: site_setting(k) for k in [
        'registration_enabled','applications_enabled','payments_enabled','maintenance_mode',
        'payment_amount','site_logo','founder_name','founder_title','founder_bio','founder_photo',
        'company_phone','company_email','company_address','company_whatsapp',
        'homepage_headline','homepage_subtext'
    ]}
    try:
        appeals = conn.execute('SELECT * FROM job_appeals ORDER BY created_at DESC LIMIT 100').fetchall()
        chats = conn.execute('SELECT * FROM service_chats ORDER BY updated_at DESC LIMIT 50').fetchall()
    except Exception:
        appeals, chats = [], []
    conn.close()
    return jsonify({
        'stats': stats,
        'settings': settings,
        'users': [dict(r) for r in users],
        'testimonials': [dict(r) for r in testimonials],
        'payments': [dict(r) for r in payments],
        'jobs': [dict(r) for r in jobs_rows],
        'applications': [dict(r) for r in apps],
        'messages': [dict(r) for r in messages],
        'subscribers': [dict(r) for r in subscribers],
        'appeals': [dict(r) for r in appeals],
        'service_chats': [dict(r) for r in chats],
    })


@app.post('/api/admin/jobs')
@admin_required
def create_job_admin():
    data = request.get_json(silent=True) or {}
    title = str(data.get('title', '')).strip()
    location = str(data.get('location', '')).strip()
    category = str(data.get('category', '')).strip()
    job_type = str(data.get('job_type', '')).strip()
    try:
        available = max(0, int(data.get('available_roles', 0)))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Available roles must be a whole number.'}), 400
    if not all([title, location, category, job_type]):
        return jsonify({'ok': False, 'error': 'Title, location, category and job type are required.'}), 400
    conn = db()
    cur = conn.execute('''INSERT INTO jobs(title,location,category,job_type,available_roles,is_active,created_at,updated_at)
                          VALUES(?,?,?,?,?,?,?,?)''', (title, location, category, job_type, available, 1, now_iso(), now_iso()))
    conn.commit(); jid = cur.lastrowid; conn.close()
    return jsonify({'ok': True, 'id': jid})


@app.patch('/api/admin/jobs/<int:job_id>')
@admin_required
def update_job_admin(job_id):
    data = request.get_json(silent=True) or {}
    allowed = ['title', 'location', 'category', 'job_type']
    fields, values = [], []
    for key in allowed:
        if key in data:
            value = str(data[key]).strip()
            if not value:
                return jsonify({'ok': False, 'error': f'{key} cannot be empty.'}), 400
            fields.append(f'{key}=?'); values.append(value)
    if 'available_roles' in data:
        try:
            available = max(0, int(data['available_roles']))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'Available roles must be a whole number.'}), 400
        fields.append('available_roles=?'); values.append(available)
    if 'is_active' in data:
        fields.append('is_active=?'); values.append(1 if data['is_active'] else 0)
    if not fields:
        return jsonify({'ok': False, 'error': 'No changes supplied.'}), 400
    fields.append('updated_at=?'); values.append(now_iso()); values.append(job_id)
    conn = db()
    cur = conn.execute(f"UPDATE jobs SET {','.join(fields)} WHERE id=?", values)
    conn.commit(); conn.close()
    if cur.rowcount == 0:
        return jsonify({'ok': False, 'error': 'Job not found.'}), 404
    return jsonify({'ok': True})


@app.delete('/api/admin/jobs/<int:job_id>')
@admin_required
def delete_job_admin(job_id):
    conn = db()
    conn.execute('UPDATE jobs SET is_active=0, available_roles=0, updated_at=? WHERE id=?', (now_iso(), job_id))
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.post('/api/admin/payments/<int:pid>/verify')
@admin_required
def verify_payment(pid):
    conn = db(); row = conn.execute('SELECT * FROM payments WHERE id=?', (pid,)).fetchone()
    if not row:
        conn.close(); return jsonify({'ok': False, 'error': 'Payment not found'}), 404
    conn.execute("UPDATE payments SET status='verified',verified_at=?,admin_note=NULL WHERE id=?", (now_iso(), pid))
    conn.execute("UPDATE employer_submissions SET status='verified' WHERE id=?", (row['submission_id'],))
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.post('/api/admin/payments/<int:pid>/reject')
@admin_required
def reject_payment(pid):
    note = str((request.get_json(silent=True) or {}).get('note', 'Payment could not be verified.')).strip()
    conn = db(); row = conn.execute('SELECT * FROM payments WHERE id=?', (pid,)).fetchone()
    if not row:
        conn.close(); return jsonify({'ok': False, 'error': 'Payment not found'}), 404
    conn.execute("UPDATE payments SET status='rejected',admin_note=? WHERE id=?", (note, pid))
    conn.execute("UPDATE employer_submissions SET status='payment_rejected' WHERE id=?", (row['submission_id'],))
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.patch('/api/admin/applications/<int:aid>')
@admin_required
def update_application(aid):
    data=request.get_json(silent=True) or {}
    status=data.get('status','new')
    if status not in {'new','reviewing','shortlisted','interview','placed','rejected'}:
        return jsonify({'ok':False,'error':'Invalid application status.'}),400
    conn=db(); cur=conn.execute('UPDATE job_applications SET status=? WHERE id=?',(status,aid)); conn.commit(); conn.close()
    if cur.rowcount==0: return jsonify({'ok':False,'error':'Application not found.'}),404
    return jsonify({'ok':True})

@app.get('/uploads/<path:name>')
def uploads(name):
    # Founder photos and other public assets are served here.
    # Sensitive files (CVs, payment proofs) should only be linked from admin.
    return send_from_directory(UPLOADS, name)



# ==================== FOUNDER PAGE ====================
@app.route('/founder')
def founder_page():
    return render_template('founder.html',
        founder_name=site_setting('founder_name', 'MR PETTER'),
        founder_title=site_setting('founder_title', 'Founder & Chief Executive'),
        founder_bio=site_setting('founder_bio', ''),
        founder_photo=site_setting('founder_photo', '')
    )


# ==================== SERVICES / CHAT ====================
@app.route('/services')
def services_page():
    return render_template('services.html')


@app.post('/api/services/start')
def start_service_chat():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    subject = (data.get('subject') or 'Service Inquiry').strip()
    message = (data.get('message') or '').strip()
    if not name or not email or not message:
        return jsonify({'ok': False, 'error': 'Name, email and message are required.'}), 400
    conn = db()
    cur = conn.execute(
        'INSERT INTO service_chats(user_name,user_email,user_phone,subject,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
        (name, email, phone, subject, 'open', now_iso(), now_iso())
    )
    chat_id = cur.lastrowid
    conn.execute(
        'INSERT INTO service_messages(chat_id,sender,message,created_at) VALUES(?,?,?,?)',
        (chat_id, 'user', message, now_iso())
    )
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'chat_id': chat_id})


@app.get('/api/services/chat/<int:chat_id>')
def get_service_chat(chat_id):
    conn = db()
    chat = conn.execute('SELECT * FROM service_chats WHERE id=?', (chat_id,)).fetchone()
    if not chat:
        conn.close()
        return jsonify({'ok': False, 'error': 'Chat not found'}), 404
    messages = conn.execute(
        'SELECT sender,message,created_at FROM service_messages WHERE chat_id=? ORDER BY id ASC',
        (chat_id,)
    ).fetchall()
    conn.close()
    return jsonify({
        'ok': True,
        'chat': dict(chat),
        'messages': [dict(m) for m in messages]
    })


@app.post('/api/services/chat/<int:chat_id>/reply')
def user_reply_service_chat(chat_id):
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'ok': False, 'error': 'Message required'}), 400
    conn = db()
    chat = conn.execute('SELECT id FROM service_chats WHERE id=?', (chat_id,)).fetchone()
    if not chat:
        conn.close()
        return jsonify({'ok': False, 'error': 'Chat not found'}), 404
    conn.execute(
        'INSERT INTO service_messages(chat_id,sender,message,created_at) VALUES(?,?,?,?)',
        (chat_id, 'user', message, now_iso())
    )
    conn.execute('UPDATE service_chats SET updated_at=? WHERE id=?', (now_iso(), chat_id))
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.get('/api/admin/service-chats')
@admin_required
def admin_list_service_chats():
    conn = db()
    rows = conn.execute(
        'SELECT * FROM service_chats ORDER BY updated_at DESC LIMIT 100'
    ).fetchall()
    conn.close()
    return jsonify({'ok': True, 'chats': [dict(r) for r in rows]})


@app.get('/api/admin/service-chats/<int:chat_id>')
@admin_required
def admin_get_service_chat(chat_id):
    conn = db()
    chat = conn.execute('SELECT * FROM service_chats WHERE id=?', (chat_id,)).fetchone()
    if not chat:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not found'}), 404
    messages = conn.execute(
        'SELECT * FROM service_messages WHERE chat_id=? ORDER BY id ASC', (chat_id,)
    ).fetchall()
    conn.close()
    return jsonify({'ok': True, 'chat': dict(chat), 'messages': [dict(m) for m in messages]})


@app.post('/api/admin/service-chats/<int:chat_id>/reply')
@admin_required
def admin_reply_service_chat(chat_id):
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'ok': False, 'error': 'Message required'}), 400
    conn = db()
    chat = conn.execute('SELECT id FROM service_chats WHERE id=?', (chat_id,)).fetchone()
    if not chat:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not found'}), 404
    conn.execute(
        'INSERT INTO service_messages(chat_id,sender,message,created_at) VALUES(?,?,?,?)',
        (chat_id, 'admin', message, now_iso())
    )
    conn.execute('UPDATE service_chats SET updated_at=?, status=? WHERE id=?', (now_iso(), 'replied', chat_id))
    conn.commit(); conn.close()
    return jsonify({'ok': True})


# ==================== JOB APPEALS ====================
@app.post('/api/job-appeals')
def submit_job_appeal():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    reason = (data.get('reason') or '').strip()
    job_id = data.get('job_id')
    job_title = (data.get('job_title') or '').strip()
    if not name or not email or not reason:
        return jsonify({'ok': False, 'error': 'Name, email and reason are required.'}), 400
    conn = db()
    conn.execute(
        "INSERT INTO job_appeals(job_id,job_title,applicant_name,applicant_email,applicant_phone,reason,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (job_id, job_title, name, email, phone, reason, 'pending', now_iso(), now_iso())
    )
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.get('/api/admin/job-appeals')
@admin_required
def admin_list_job_appeals():
    conn = db()
    rows = conn.execute('SELECT * FROM job_appeals ORDER BY created_at DESC LIMIT 200').fetchall()
    conn.close()
    return jsonify({'ok': True, 'appeals': [dict(r) for r in rows]})


@app.patch('/api/admin/job-appeals/<int:aid>')
@admin_required
def admin_update_job_appeal(aid):
    data = request.get_json(silent=True) or {}
    status = data.get('status')
    note = data.get('admin_note', '')
    conn = db()
    if status:
        conn.execute('UPDATE job_appeals SET status=?, admin_note=?, updated_at=? WHERE id=?',
                     (status, note, now_iso(), aid))
    else:
        conn.execute('UPDATE job_appeals SET admin_note=?, updated_at=? WHERE id=?',
                     (note, now_iso(), aid))
    conn.commit(); conn.close()
    return jsonify({'ok': True})


# ==================== JOB DESCRIPTION UPDATE ====================
@app.patch('/api/admin/jobs/<int:jid>')
@admin_required
def admin_update_job(jid):
    data = request.get_json(silent=True) or {}
    fields = []
    values = []
    for key in ('title', 'location', 'category', 'job_type', 'description'):
        if key in data:
            fields.append(f'{key}=?')
            values.append(data[key])
    if 'available_roles' in data:
        fields.append('available_roles=?')
        values.append(int(data['available_roles']))
    if 'is_active' in data:
        fields.append('is_active=?')
        values.append(1 if data['is_active'] else 0)
    if not fields:
        return jsonify({'ok': False, 'error': 'No fields to update'}), 400
    fields.append('updated_at=?')
    values.append(now_iso())
    values.append(jid)
    conn = db()
    conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id=?", values)
    conn.commit(); conn.close()
    return jsonify({'ok': True})


# ==================== FOUNDER PHOTO UPLOAD ====================
@app.post('/api/admin/founder-photo')
@admin_required
def admin_founder_photo():
    f = request.files.get('photo')
    if not f or not allowed_file(f.filename, 'image'):
        return jsonify({'ok': False, 'error': 'Valid image required'}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    name = f'founder_{uuid.uuid4().hex[:10]}{ext}'
    path = os.path.join(UPLOADS, name)
    f.save(path)
    url = f'/uploads/{name}'
    conn = db()
    conn.execute(
        'INSERT INTO site_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
        ('founder_photo', url)
    )
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'url': url})


init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)

