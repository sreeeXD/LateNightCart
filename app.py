from flask import Flask, render_template, url_for, redirect, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps # FIX: Necessary for Flask decorators
import hmac
import os

# --- CONFIGURATION ---
app = Flask(__name__)

# Configure the SQLite database file
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# CRITICAL: This MUST be a strong, random value for session security
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'a_very_secret_and_long_key_for_cvr_hostel' 

db = SQLAlchemy(app)

# --- DATABASE MODELS ---

# 1. User Model (Admin/Student Accounts)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student') # 'admin' or 'student'

    def __repr__(self):
        return f"User('{self.username}', '{self.role}')"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 2. Snack Model (Inventory)
class Snack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(200), nullable=True, default='/static/images/default.jpg')
    is_available = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"Snack('{self.name}', '{self.price}', '{self.quantity}')"

# 3. Order Model (Customer Orders)
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    snack_id = db.Column(db.Integer, db.ForeignKey('snack.id'), nullable=False)
    buyer_name = db.Column(db.String(100), nullable=False)
    room_number = db.Column(db.String(10), nullable=False)
    quantity_ordered = db.Column(db.Integer, nullable=False)
    order_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='Pending') # Pending, Completed

    snack = db.relationship('Snack', backref=db.backref('orders', lazy=True))


# --- AUTHENTICATION & SESSION MANAGEMENT ---

def login_required(f):
    """Decorator to restrict access to authenticated users."""
    @wraps(f) # FIX APPLIED HERE
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to restrict access to admin users."""
    @wraps(f) # FIX APPLIED HERE
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Access Denied: Admin privileges required.', 'danger')
            return redirect(url_for('snacks'))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def home():
    """Renders the static home page."""
    return render_template('index.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        room_number = request.form.get('room_number') # Room number used as part of 'username' for clarity
        
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
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['logged_in'] = True
            session['username'] = user.username
            session['role'] = user.role
            
            flash(f"Welcome, {user.username}!", 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('snacks'))
        else:
            flash('Login failed. Check your username and password.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('role', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# --- USER ROUTES (SNACK SHOP) ---

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
        room_number = request.form.get('room_number') # Still needed for order tracking
        
        try:
            quantity_ordered = int(request.form.get('quantity'))
        except ValueError:
            flash('Invalid quantity.', 'danger')
            return redirect(url_for('order', snack_id=snack_id))

        if quantity_ordered <= 0 or quantity_ordered > snack.quantity:
            flash('Invalid quantity selected or quantity exceeds stock.', 'danger')
            return redirect(url_for('order', snack_id=snack_id))

        new_order = Order(
            snack_id=snack.id,
            buyer_name=buyer_name,
            room_number=room_number,
            quantity_ordered=quantity_ordered
        )

        snack.quantity -= quantity_ordered
        if snack.quantity == 0:
            snack.is_available = False

        try:
            db.session.add(new_order)
            db.session.commit()
            flash(f'Success! Order placed for {quantity_ordered}x {snack.name}. Room {room_number} notified.', 'success')
            return redirect(url_for('snacks'))
        except Exception:
            db.session.rollback()
            flash('There was an issue processing your order.', 'danger')
            return redirect(url_for('snacks'))
            
    return render_template('order_form.html', snack=snack)

# --- ADMIN ROUTES ---

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    inventory = Snack.query.all()
    pending_orders = Order.query.filter_by(status='Pending').order_by(Order.order_time.desc()).all()
    return render_template('admin_dashboard.html', inventory=inventory, pending_orders=pending_orders)

@app.route("/admin/complete_order/<int:order_id>")
@admin_required
def complete_order(order_id):
    order_to_complete = Order.query.get_or_404(order_id)
    order_to_complete.status = 'Completed'
    db.session.commit()
    flash(f"Order #{order_id} for {order_to_complete.buyer_name} completed!", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/manage_snack", defaults={'snack_id': None}, methods=['GET', 'POST'])
@app.route("/admin/manage_snack/<int:snack_id>", methods=['GET', 'POST'])
@admin_required
def manage_snack(snack_id):
    if snack_id is None:
        snack = None
        title = "Add New Snack"
    else:
        snack = Snack.query.get_or_404(snack_id)
        title = f"Edit {snack.name}"

    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price'))
        quantity = int(request.form.get('quantity'))
        image_url = request.form.get('image_url')
        
        if snack is None:
            snack = Snack(name=name, price=price, quantity=quantity, image_url=image_url)
            db.session.add(snack)
            flash(f"New snack '{name}' added successfully.", 'success')
        else:
            snack.name = name
            snack.price = price
            snack.quantity = quantity
            snack.image_url = image_url
            flash(f"Snack '{name}' updated successfully.", 'success')
            
        snack.is_available = True if snack.quantity > 0 else False
        
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    
    return render_template('manage_snack.html', title=title, snack=snack)

@app.route("/admin/delete_snack/<int:snack_id>", methods=['POST'])
@admin_required
def delete_snack(snack_id):
    snack = Snack.query.get_or_404(snack_id)
    
    if Order.query.filter_by(snack_id=snack_id, status='Pending').first():
        flash(f"Cannot delete {snack.name}: There are still pending orders!", 'danger')
        return redirect(url_for('admin_dashboard'))

    db.session.delete(snack)
    db.session.commit()
    flash(f"Snack '{snack.name}' successfully deleted.", 'success')
    return redirect(url_for('admin_dashboard'))

# --- INITIAL SETUP & RUN SERVER ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Add a default admin user if one does not exist
        if not User.query.filter_by(role='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('cvr_admin123') # CHANGE THIS PASSWORD IMMEDIATELY!
            db.session.add(admin)
            print("Default admin user created.")

        # Add sample snacks if the table is empty (run only once)
        if not Snack.query.first():
            sample_snacks = [
                Snack(name='Spicy Chips Pack', price=20.00, quantity=15, image_url='https://via.placeholder.com/400x300/64561a/fcfcfc?text=Spicy+Chips'),
                Snack(name='Chocolate Cookie', price=50.00, quantity=8, image_url='https://via.placeholder.com/400x300/917c22/fcfcfc?text=Cookie'),
                Snack(name='Energy Drink', price=35.00, quantity=0, is_available=False, image_url='https://via.placeholder.com/400x300/373012/fcfcfc?text=Energy+Drink')
            ]
            db.session.add_all(sample_snacks)
            print("Sample snacks added to the database.")

        db.session.commit()
        print("Database setup complete.")

    app.run(debug=True)