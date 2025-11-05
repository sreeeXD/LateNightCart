from flask import Flask, render_template, url_for, redirect, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os

# --- CONFIGURATION ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'a_very_secret_and_long_key_for_cvr_hostel'

# Upload settings
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Snack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(200), nullable=True, default='/static/images/default.jpg')
    is_available = db.Column(db.Boolean, default=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    snack_id = db.Column(db.Integer, db.ForeignKey('snack.id'), nullable=False)
    buyer_name = db.Column(db.String(100), nullable=False)
    room_number = db.Column(db.String(10), nullable=False)
    quantity_ordered = db.Column(db.Integer, nullable=False)
    order_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='Pending')

    snack = db.relationship('Snack', backref=db.backref('orders', lazy=True))


# --- HELPERS & DECORATORS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Access Denied: Admin privileges required.', 'danger')
            return redirect(url_for('snacks'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    """Check if uploaded file has an allowed image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- ROUTES ---

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        room_number = request.form.get('room_number')
        password = request.form.get('password')

        full_username = f"{username}-{room_number}"

        if User.query.filter_by(username=full_username).first():
            flash('Username already exists. Please choose another.', 'danger')
            return redirect(url_for('register'))

        user = User(username=full_username, role='student')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template("register.html")


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        room_number = request.form.get('room_number')
        password = request.form.get('password')

        full_username = f"{username}-{room_number}"
        user = User.query.filter_by(username=full_username).first()

        if user and user.check_password(password):
            session['logged_in'] = True
            session['username'] = user.username
            session['role'] = user.role
            flash(f"Welcome, {user.username}!", 'success')

            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('snacks'))
        else:
            flash('Login failed. Check your credentials.', 'danger')
            return redirect(url_for('login'))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


# --- SNACK SHOP (USER) ---
@app.route("/snacks")
@login_required
def snacks():
    snacks_list = Snack.query.order_by(Snack.name).all()
    return render_template('snacks.html', snacks=snacks_list)


@app.route("/order/<int:snack_id>", methods=['GET', 'POST'])
@login_required
def order(snack_id):
    snack = Snack.query.get_or_404(snack_id)

    if request.method == 'POST':
        buyer_name = session.get('username')
        room_number = request.form.get('room_number')
        quantity_ordered = int(request.form.get('quantity'))

        if quantity_ordered > snack.quantity:
            flash('Not enough stock available.', 'danger')
            return redirect(url_for('snacks'))

        new_order = Order(snack_id=snack.id, buyer_name=buyer_name,
                          room_number=room_number, quantity_ordered=quantity_ordered)
        snack.quantity -= quantity_ordered
        db.session.add(new_order)
        db.session.commit()

        flash('Order placed successfully!', 'success')
        return redirect(url_for('snacks'))

    return render_template('order_form.html', snack=snack)


# --- ADMIN ROUTES ---
@app.route("/admin_dashboard")
@admin_required
def admin_dashboard():
    snacks = Snack.query.all()
    orders = Order.query.order_by(Order.order_time.desc()).all()
    return render_template('admin_dashboard.html', snacks=snacks, orders=orders)


@app.route("/manage_snack", methods=['GET', 'POST'])
@admin_required
def manage_snack():
    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price'))
        quantity = int(request.form.get('quantity'))
        image_file = request.files.get('image')

        image_url = '/static/images/default.jpg'
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(save_path)
            image_url = f"/static/uploads/{filename}"

        new_snack = Snack(name=name, price=price, quantity=quantity, image_url=image_url)
        db.session.add(new_snack)
        db.session.commit()

        flash(f"Snack '{name}' added successfully!", 'success')
        return redirect(url_for('manage_snack'))

    snacks = Snack.query.order_by(Snack.name).all()
    return render_template('manage_snack.html', snacks=snacks)


@app.route("/edit_snack/<int:snack_id>", methods=['GET', 'POST'])
@admin_required
def edit_snack(snack_id):
    snack = Snack.query.get_or_404(snack_id)

    if request.method == 'POST':
        snack.name = request.form.get('name')
        snack.price = float(request.form.get('price'))
        snack.quantity = int(request.form.get('quantity'))
        image_file = request.files.get('image')

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(save_path)
            snack.image_url = f"/static/uploads/{filename}"

        db.session.commit()
        flash(f"{snack.name} updated successfully!", 'success')
        return redirect(url_for('manage_snack'))

    return render_template('edit_snack.html', snack=snack)


@app.route("/delete_snack/<int:snack_id>")
@admin_required
def delete_snack(snack_id):
    snack = Snack.query.get_or_404(snack_id)
    if snack.image_url and snack.image_url.startswith('/static/uploads/'):
        try:
            os.remove(snack.image_url.lstrip('/'))
        except Exception:
            pass

    db.session.delete(snack)
    db.session.commit()
    flash(f"Snack '{snack.name}' deleted successfully!", 'success')
    return redirect(url_for('manage_snack'))


@app.route("/complete_order/<int:order_id>")
@admin_required
def complete_order(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = 'Completed'
    db.session.commit()
    flash(f"Order #{order.id} marked as completed.", 'success')
    return redirect(url_for('admin_dashboard'))


# --- MAIN ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
