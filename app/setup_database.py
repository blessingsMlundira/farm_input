# setup_database.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

# =====================================================
# APP CONFIGURATION
# =====================================================

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///efarm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =====================================================
# USER MODEL
# =====================================================

class User(db.Model):

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    account_type = db.Column(db.String(50), nullable=False)


# =====================================================
# FARMER MODEL
# =====================================================

class Farmer(db.Model):

    __tablename__ = 'farmers'

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(200), nullable=False)

    date_of_birth = db.Column(db.String(100), nullable=False)

    age = db.Column(db.Integer, nullable=False)

    nationality = db.Column(db.String(100), nullable=False)

    phone = db.Column(db.String(50), nullable=False)

    email = db.Column(db.String(150))

    village_headman = db.Column(db.String(150), nullable=False)

    traditional_authority = db.Column(db.String(150), nullable=False)

    district = db.Column(db.String(150), nullable=False)

    gender = db.Column(db.String(20), nullable=False)

    farmer_type = db.Column(db.String(50), nullable=False)


# =====================================================
# DISBURSEMENT MODEL
# =====================================================

class Disbursement(db.Model):

    __tablename__ = 'disbursements'

    id = db.Column(db.Integer, primary_key=True)

    farmer_id = db.Column(
        db.Integer,
        db.ForeignKey('farmers.id'),
        nullable=False
    )

    disbursement_date = db.Column(db.String(100), nullable=False)

    # Fertilizer
    fertilizer_bags = db.Column(db.Integer)
    fertilizer_type = db.Column(db.String(100))
    fertilizer_unit_price = db.Column(db.Float)
    fertilizer_total = db.Column(db.Float)

    # Seeds
    seeds_kg = db.Column(db.Integer)
    seed_type = db.Column(db.String(100))
    seed_unit_price = db.Column(db.Float)
    seed_total = db.Column(db.Float)

    # Chemicals
    chemicals_litres = db.Column(db.Integer)
    chemical_type = db.Column(db.String(100))
    chemical_unit_price = db.Column(db.Float)
    chemical_total = db.Column(db.Float)

    # Loan Total
    total_loan_amount = db.Column(db.Float, default=0)

    remarks = db.Column(db.Text)

    farmer = db.relationship('Farmer', backref='disbursements')
    
# =====================================================
# REPAYMENT MODEL
# =====================================================

class Repayment(db.Model):

    __tablename__ = 'repayments'

    id = db.Column(db.Integer, primary_key=True)

    farmer_id = db.Column(
        db.Integer,
        db.ForeignKey('farmers.id'),
        nullable=False
    )

    payment_date = db.Column(db.String(100), nullable=False)

    amount_paid = db.Column(db.Float, nullable=False)

    payment_method = db.Column(db.String(100), nullable=False)

    payment_month = db.Column(db.String(50), nullable=False)

    payment_year = db.Column(db.Integer, nullable=False)

    remarks = db.Column(db.Text)

    # Relationship
    farmer = db.relationship('Farmer', backref='repayments')

# =====================================================
# CREATE DATABASE + DEFAULT USER
# =====================================================

with app.app_context():

    # Create all tables
    db.create_all()

    # Check if admin already exists
    existing_user = User.query.filter_by(username='admin').first()

    if not existing_user:

        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            account_type='administrator'
        )

        db.session.add(admin)
        db.session.commit()

        print("Database created successfully")
        print("Default admin user created")
        print("Username: admin")
        print("Password: admin123")

    else:
        print("Admin user already exists")