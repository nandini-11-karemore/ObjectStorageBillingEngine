from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from flask import send_file
from supabase_client import supabase
import io
import uuid
# CREATE FLASK APP
app = Flask(__name__)

# SECRET KEY
app.secret_key = 'secret123'

# UPLOAD FOLDER
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# DATABASE CONFIGURATION
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///storage.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# INITIALIZE DATABASE
db = SQLAlchemy(app)

# USER MODEL
class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(100), nullable=False)

    password = db.Column(db.String(100), nullable=False)


# STORAGE OBJECT MODEL
class StorageObject(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    file_name = db.Column(
        db.String(200),
        nullable=False
    )

    file_size = db.Column(
        db.Float,
        nullable=False
    )
    
    file_url = db.Column(db.String(500))

    upload_time = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class LoginHistory(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        nullable=False
    )

    user_name = db.Column(
        db.String(100),
        nullable=False
    )

    login_time = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
# HOME PAGE
@app.route('/')
def home():
    return render_template('index.html')


# REGISTER PAGE
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        new_user = User(
            name=name,
            email=email,
            password=password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect('/login')

    return render_template('register.html')


# LOGIN PAGE
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.password == password:

            session['user_id'] = user.id
            session['user_name'] = user.name
            new_login = LoginHistory(
                user_id=user.id,
                user_name=user.name
            )

            db.session.add(new_login)
            db.session.commit()

            return redirect('/dashboard')

        return "Invalid Email or Password"

    return render_template('login.html')


# LOGOUT
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')


# DASHBOARD PAGE
@app.route('/dashboard')
def dashboard():

    user_id = session.get('user_id')

    if not user_id:
        return redirect('/login')

    # USER FILES
    files = StorageObject.query.filter_by(
        user_id=user_id
    ).order_by(
        StorageObject.upload_time.desc()
    ).all()

    # TOTAL FILES
    total_files = len(files)

    # TOTAL STORAGE
    total_storage = 0

    for file in files:
        total_storage += file.file_size

    # BILLING
    free_limit = 1000

    rate = 0.02

    if total_storage > free_limit:
        bill = (total_storage - free_limit) * rate
    else:
        bill = 0

    return render_template(
        'dashboard.html',
        total_files=total_files,
        total_storage=round(total_storage, 2),
        bill=round(bill, 2),
        files=files
    )
@app.route('/admin')
def admin():

    total_users = User.query.count()

    total_files = StorageObject.query.count()

    files = StorageObject.query.all()

    total_storage = 0

    for file in files:
        total_storage += file.file_size

    # DEMO REVENUE CALCULATION
    total_revenue = round(total_storage * 0.02, 2)

    recent_users = User.query.order_by(
        User.id.desc()
    ).limit(5).all()

    recent_files = StorageObject.query.order_by(
        StorageObject.id.desc()
    ).limit(5).all()
    recent_files = StorageObject.query.order_by(
    StorageObject.upload_time.desc()
).limit(10).all()

    return render_template(
        'admin.html',
        total_users=total_users,
        total_files=total_files,
        total_storage=round(total_storage, 2),
        total_revenue=total_revenue,
        recent_users=recent_users,
        recent_files=recent_files
    )
#from supabase_client import supabase

# FILE UPLOAD
@app.route('/upload', methods=['GET', 'POST'])
def upload():

    user_id = session.get('user_id')

    if not user_id:
        return redirect('/login')

    if request.method == 'POST':

        file = request.files.get('file')

        if not file or file.filename == "":
            return "No file selected"

        try:
            # Read file into memory
            file_bytes = file.read()

            # Calculate file size (MB)
            size = len(file_bytes) / (1024 * 1024)

            # Generate unique filename
            unique_filename = f"{uuid.uuid4()}_{file.filename}"

            # Upload to Supabase Storage
            supabase.storage.from_("uploads").upload(
                path=unique_filename,
                file=file_bytes,
                file_options={
                    "content-type": file.content_type,
                    "upsert": "false"
                }
            )

            # Get public URL
            file_url = supabase.storage.from_("uploads").get_public_url(unique_filename)

            # Save metadata in database
            new_file = StorageObject(
                user_id=user_id,
                file_name=unique_filename,
                file_size=size,
                file_url=file_url
            )

            db.session.add(new_file)
            db.session.commit()

            return redirect('/dashboard')

        except Exception as e:
            return f"Upload Error: {str(e)}"

    return render_template('upload.html')

    

#DELETE FILE
@app.route('/delete/<int:file_id>')
def delete_file(file_id):

    user_id = session.get('user_id')

    if not user_id:
        return redirect('/login')

    file = StorageObject.query.filter_by(
        id=file_id,
        user_id=user_id
    ).first()

    if file:

        # Delete from Supabase Storage
        try:
            supabase.storage.from_("uploads").remove([file.file_name])
        except Exception as e:
            print("Supabase Delete Error:", e)

        # Delete from database
        db.session.delete(file)
        db.session.commit()

    return redirect('/dashboard')

# INVOICE PAGE
@app.route('/invoice')
def invoice():

    user_id = session.get('user_id')

    if not user_id:
        return redirect('/login')

    files = StorageObject.query.filter_by(
        user_id=user_id
    ).all()

    total_files = len(files)

    total_storage = 0

    for file in files:
        total_storage += file.file_size

    free_limit = 1000

    rate = 0.02

    if total_storage > free_limit:
        bill = (total_storage - free_limit) * rate
    else:
        bill = 0

    return render_template(
    'invoice.html',
    user_name=session.get('user_name'),
    total_files=total_files,
    total_storage=round(total_storage, 2),
    bill=round(bill, 2),
    generated_on=datetime.now().strftime("%d-%m-%Y %H:%M")
)
# DOWNLOAD PDF INVOICE
@app.route('/download_invoice')
def download_invoice():

    user_id = session.get('user_id')

    if not user_id:
        return redirect('/login')

    files = StorageObject.query.filter_by(
        user_id=user_id
    ).all()

    total_files = len(files)

    total_storage = sum(
        file.file_size for file in files
    )

    free_limit = 1000

    rate = 0.02

    if total_storage > free_limit:
        bill = (total_storage - free_limit) * rate
    else:
        bill = 0

    buffer = io.BytesIO()

    p = canvas.Canvas(buffer)

    p.setTitle("Storage Billing Invoice")

    p.drawString(
        100, 800,
        "Storage Billing Invoice"
    )

    p.drawString(
        100, 760,
        f"User: {session.get('user_name')}"
    )

    p.drawString(
        100, 730,
        f"Total Files: {total_files}"
    )

    p.drawString(
        100, 700,
        f"Storage Used: {round(total_storage,2)} MB"
    )

    p.drawString(
        100, 670,
        f"Bill Amount: ₹ {round(bill,2)}"
    )

    p.drawString(
        100, 640,
        f"Generated On: {datetime.now().strftime('%d-%m-%Y %H:%M')}"
    ) 

    p.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True, 
        download_name="invoice.pdf",
        mimetype='application/pdf'
    )
@app.route('/users')
def users():

    all_users = User.query.all()

    return render_template(
        'users.html',
        users=all_users
    )
@app.route('/login-history')
def login_history():

    records = LoginHistory.query.order_by(
        LoginHistory.login_time.desc()
    ).all()

    return render_template(
        'login_history.html',
        records=records
    )
with app.app_context():
    db.create_all()
# MAIN FUNCTION
if __name__ == '__main__':

    with app.app_context():
        db.create_all()

    app.run(debug=False)

