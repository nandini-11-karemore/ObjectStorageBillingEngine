from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from flask import send_file
import io
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

    upload_time = db.Column(
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


# FILE UPLOAD
@app.route('/upload', methods=['GET', 'POST'])
def upload():

    user_id = session.get('user_id')

    if not user_id:
        return redirect('/login')

    if request.method == 'POST':

        file = request.files['file']

        if file:

            filepath = os.path.join(
                app.config['UPLOAD_FOLDER'],
                file.filename
            )

            # SAVE FILE
            file.save(filepath)

            # FILE SIZE
            size = os.path.getsize(filepath) / (1024 * 1024)

            # SAVE TO DATABASE
            new_file = StorageObject(
                user_id=user_id,
                file_name=file.filename,
                file_size=size
            )

            db.session.add(new_file)
            db.session.commit()

            return redirect('/dashboard')

    return render_template('upload.html')


# DELETE FILE
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

        filepath = os.path.join(
            app.config['UPLOAD_FOLDER'],
            file.file_name
        )

        # DELETE FILE
        if os.path.exists(filepath):
            os.remove(filepath)

        # DELETE DATABASE RECORD
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
with app.app_context():
    db.create_all()
# MAIN FUNCTION
if __name__ == '__main__':

    with app.app_context():
        db.create_all()

    app.run(debug=False)