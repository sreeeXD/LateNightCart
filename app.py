# app.py

from flask import Flask, render_template, url_for, redirect, request
from flask_sqlalchemy import SQLAlchemy

# --- CONFIGURATION ---
app = Flask(__name__)

# Configure the SQLite database file
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_strong_secret_key_here' # Important for security

db = SQLAlchemy(app)

# --- DATABASE MODEL ---
# Define the structure (schema) for your Snack items
class Snack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(200), nullable=True, default=url_for('static', filename='images/default.jpg'))
    is_available = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"Snack('{self.name}', '{self.price}', '{self.quantity}')"

# --- ROUTES (URL Handlers) ---

@app.route("/")
def home():
    """Renders the static home page."""
    return render_template('index.html')

@app.route("/snacks")
def snacks():
    """Renders the snack page with dynamic data from the database."""
    # Query the database to get all snacks
    snacks_list = Snack.query.order_by(Snack.name).all()
    return render_template('snacks.html', snacks=snacks_list)


# --- INITIAL SETUP ---
# To create the database file (site.db) and the 'Snack' table
if __name__ == '__main__':
    with app.app_context():
        # 1. Create the database and tables if they don't exist
        db.create_all()
        
        # 2. Add some sample data if the table is empty (run only once)
        if not Snack.query.first():
            sample_snacks = [
                Snack(name='Spicy Chips Pack', price=20.00, quantity=15, image_url='https://via.placeholder.com/400x300/64561a/fcfcfc?text=Spicy+Chips'),
                Snack(name='Chocolate Cookie', price=50.00, quantity=8, image_url='https://via.placeholder.com/400x300/917c22/fcfcfc?text=Cookie'),
                Snack(name='Energy Drink', price=35.00, quantity=0, is_available=False, image_url='https://via.placeholder.com/400x300/373012/fcfcfc?text=Energy+Drink')
            ]
            db.session.add_all(sample_snacks)
            db.session.commit()
            print("Sample snacks added to the database.")

    # Run the Flask development server
    app.run(debug=True)