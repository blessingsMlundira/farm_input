from flask import Flask, render_template
from flask import request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import or_
from sqlalchemy import func
from sqlalchemy import text


app = Flask(__name__)

# =====================================================
# CONFIGURATION
# =====================================================

app.config['SECRET_KEY'] = 'efarm-secret-key'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///efarm.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)



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

    payment_method = db.Column(db.String(100))

    payment_month = db.Column(db.String(50))

    payment_year = db.Column(db.Integer)

    remarks = db.Column(db.Text)

    farmer = db.relationship('Farmer', backref='repayments')

# =====================================================
# USER MODEL
# =====================================================

class User(db.Model):

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    account_type = db.Column(db.String(50), nullable=False, default='administrator')


def normalize_account_type(account_type):
    if account_type is None:
        return 'administrator'

    normalized = str(account_type).strip().lower()

    if normalized == 'admin':
        return 'administrator'

    return normalized


def ensure_user_schema():
    inspector = db.inspect(db.engine)
    table_names = inspector.get_table_names()

    if 'users' not in table_names:
        db.create_all()
        return

    columns = {column['name'] for column in inspector.get_columns('users')}

    if 'account_type' not in columns:
        with db.engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN account_type VARCHAR(50) DEFAULT 'administrator'"
                )
            )

    with db.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE users SET account_type = 'administrator' WHERE lower(account_type) = 'admin'"
            )
        )


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
# LOGIN
# =====================================================

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):

            session['user'] = user.username
            session['account_type'] = normalize_account_type(user.account_type)

            return redirect(url_for('dashboard'))

        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

def get_farmer_balance(farmer_id):

    total_loan = db.session.query(
        func.coalesce(func.sum(Disbursement.total_loan_amount), 0)
    ).filter_by(farmer_id=farmer_id).scalar()

    total_paid = db.session.query(
        func.coalesce(func.sum(Repayment.amount_paid), 0)
    ).filter_by(farmer_id=farmer_id).scalar()

    remaining = float(total_loan) - float(total_paid)

    return {
        "total_loan": float(total_loan),
        "total_paid": float(total_paid),
        "remaining": remaining
    }

@app.route('/farmer/<int:farmer_id>')
def farmer_profile(farmer_id):

    farmer = Farmer.query.get_or_404(farmer_id)

    total_disbursed = 0
    for d in farmer.disbursements:
        total_disbursed += (
            (d.fertilizer_bags or 0) * 10000 +
            (d.seeds_kg or 0) * 2000 +
            (d.chemicals_litres or 0) * 5000
        )

    total_paid = sum([r.amount_paid for r in farmer.repayments])

    balance = total_disbursed - total_paid

    return render_template(
        "farmer_profile.html",
        farmer=farmer,
        total_disbursed=total_disbursed,
        total_paid=total_paid,
        balance=balance
    )

# =====================================================
# DASHBOARD
# =====================================================

@app.route('/dashboard')
def dashboard():

    if 'user' not in session:
        return redirect(url_for('login'))

    # =====================================================
    # TOTAL FARMERS
    # =====================================================

    total_farmers = Farmer.query.count()

    # =====================================================
    # TOTAL DISBURSEMENTS
    # =====================================================

    total_disbursements = Disbursement.query.count()

    # =====================================================
    # TOTAL REPAYMENTS
    # =====================================================

    repayments = Repayment.query.all()

    total_repayments = sum(
        repayment.amount_paid for repayment in repayments
    )

    # =====================================================
    # TOTAL OUTSTANDING BALANCE
    # =====================================================

    total_disbursed_value = 0

    disbursements = Disbursement.query.all()

    for d in disbursements:

        fertilizer_value = (d.fertilizer_bags or 0) * 10000

        seed_value = (d.seeds_kg or 0) * 2000

        chemical_value = (d.chemicals_litres or 0) * 5000

        total_disbursed_value += (
            fertilizer_value +
            seed_value +
            chemical_value
        )

    outstanding_balance = (
        total_disbursed_value -
        total_repayments
    )

    # =====================================================
    # RECENT ACTIVITY
    # =====================================================

    recent_farmers = Farmer.query.order_by(
        Farmer.id.desc()
    ).limit(3).all()

    recent_disbursements = Disbursement.query.order_by(
        Disbursement.id.desc()
    ).limit(3).all()

    recent_repayments = Repayment.query.order_by(
        Repayment.id.desc()
    ).limit(3).all()

    return render_template(

        'dashboard.html',

        total_farmers=total_farmers,

        total_disbursements=total_disbursements,

        total_repayments=total_repayments,

        outstanding_balance=outstanding_balance,

        recent_farmers=recent_farmers,

        recent_disbursements=recent_disbursements,

        recent_repayments=recent_repayments
    )



# =====================================================
# LOGOUT
# =====================================================

@app.route('/logout')
def logout():

    session.pop('user', None)
    session.pop('account_type', None)

    return redirect(url_for('login'))



@app.route('/add-user', methods=['GET', 'POST'])
def add_user():

    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']
        account_type = normalize_account_type(request.form['account_type'])

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            flash('Username already exists. Please choose another.', 'danger')
            return redirect(url_for('add_user'))

        new_user = User(
            username=username,
            password=generate_password_hash(password),
            account_type=account_type
        )

        db.session.add(new_user)
        db.session.commit()

        flash('User added successfully!', 'success')
        return redirect(url_for('add_user'))

    users = User.query.order_by(User.id.desc()).all()

    return render_template('add_user.html', users=users)


@app.route('/delete-user/<int:user_id>', methods=['POST'])
def delete_user(user_id):

    if 'user' not in session:
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)

    db.session.delete(user)
    db.session.commit()

    flash('User deleted successfully!', 'success')

    return redirect(url_for('add_user'))



@app.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):

    if 'user' not in session:
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':

        username = request.form['username'].strip()
        password = request.form['password'].strip()
        account_type = normalize_account_type(request.form['account_type'])

        # Check whether another user already has this username
        existing_user = User.query.filter(
            User.username == username,
            User.id != user.id
        ).first()

        if existing_user:
            flash(
                'Username already exists. Please choose another.',
                'danger'
            )
            return redirect(
                url_for('edit_user', user_id=user.id)
            )

        # Update username
        user.username = username

        # Update account type
        user.account_type = account_type

        # Only change password if a new password was entered
        if password:
            user.password = generate_password_hash(password)

        db.session.commit()

        flash('User updated successfully!', 'success')

        return redirect(url_for('add_user'))

    return render_template(
        'edit_user.html',
        user=user
    )

# =====================================================
# FARMER ROUTES
# =====================================================

@app.route('/add-farmer', methods=['GET', 'POST'])
def add_farmer():

    # Check if user is logged in
    if 'user' not in session:
        return redirect(url_for('login'))

    # Handle form submission
    if request.method == 'POST':

        try:

            # Create new farmer object
            farmer = Farmer(

                full_name=request.form['full_name'],

                date_of_birth=request.form['date_of_birth'],

                age=request.form['age'],

                nationality=request.form['nationality'],

                phone=request.form['phone'],

                email=request.form.get('email'),

                village_headman=request.form['village_headman'],

                traditional_authority=request.form['traditional_authority'],

                district=request.form['district'],

                gender=request.form['gender'],

                farmer_type=request.form['farmer_type']
            )

            # Save to database
            db.session.add(farmer)

            db.session.commit()

            flash('Farmer registered successfully!', 'success')

            return redirect(url_for('add_farmer'))

        except Exception as e:

            db.session.rollback()

            flash(f'Error saving farmer: {str(e)}', 'danger')

    return render_template('add_farmer.html')

@app.route('/farmers')
def farmer_list():

    if 'user' not in session:
        return redirect(url_for('login'))

    farmers = Farmer.query.all()

    farmers_data = []

    for f in farmers:

        bal = get_farmer_balance(f.id)

        farmers_data.append({
            "id": f.id,
            "full_name": f.full_name,
            "age": f.age,
            "gender": f.gender,
            "district": f.district,
            "phone": f.phone,
            "farmer_type": f.farmer_type,
            "balance": bal["remaining"]
        })

    return render_template('farmer_list.html', farmers=farmers)


@app.route('/api/farmer-balance/<int:farmer_id>')
def farmer_balance_api(farmer_id):

    total_loan = db.session.query(
        func.coalesce(func.sum(Disbursement.total_loan_amount), 0)
    ).filter_by(farmer_id=farmer_id).scalar()

    total_paid = db.session.query(
        func.coalesce(func.sum(Repayment.amount_paid), 0)
    ).filter_by(farmer_id=farmer_id).scalar()

    remaining = float(total_loan) - float(total_paid)

    return {
        "total_loan": float(total_loan),
        "total_paid": float(total_paid),
        "remaining": float(remaining)
    }


# =====================================================
# DISBURSEMENT ROUTES
# =====================================================

@app.route('/add_disbursement', methods=['GET', 'POST'])
def add_disbursement():

    # Check login
    if 'user' not in session:
        return redirect(url_for('login'))

    # Load farmers for dropdown
    farmers = Farmer.query.all()

    if request.method == 'POST':

        try:
            # ----------------------------
            # GET FORM DATA
            # ----------------------------

            fertilizer_bags = request.form.get('fertilizer_bags', 0)
            fertilizer_unit_price = request.form.get('fertilizer_unit_price', 0)
            fertilizer_total = request.form.get('fertilizer_total', 0)

            seeds_kg = request.form.get('seeds_kg', 0)
            seed_unit_price = request.form.get('seed_unit_price', 0)
            seed_total = request.form.get('seed_total', 0)

            chemicals_litres = request.form.get('chemicals_litres', 0)
            chemical_unit_price = request.form.get('chemical_unit_price', 0)
            chemical_total = request.form.get('chemical_total', 0)

            total_loan_amount = request.form.get('total_loan_amount', 0)

            # ----------------------------
            # CREATE DISBURSEMENT
            # ----------------------------

            disbursement = Disbursement(

                farmer_id=request.form['farmer_id'],
                disbursement_date=request.form['disbursement_date'],

                fertilizer_bags=int(fertilizer_bags or 0),
                fertilizer_type=request.form.get('fertilizer_type'),
                fertilizer_unit_price=float(fertilizer_unit_price or 0),
                fertilizer_total=float(fertilizer_total or 0),

                seeds_kg=int(seeds_kg or 0),
                seed_type=request.form.get('seed_type'),
                seed_unit_price=float(seed_unit_price or 0),
                seed_total=float(seed_total or 0),

                chemicals_litres=int(chemicals_litres or 0),
                chemical_type=request.form.get('chemical_type'),
                chemical_unit_price=float(chemical_unit_price or 0),
                chemical_total=float(chemical_total or 0),

                total_loan_amount=float(total_loan_amount or 0),

                remarks=request.form.get('remarks')
            )

            db.session.add(disbursement)
            db.session.commit()

            flash('Disbursement saved successfully!', 'success')
            return redirect(url_for('add_disbursement'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error saving disbursement: {str(e)}', 'danger')

    return render_template(
        'add_disbursement.html',
        farmers=farmers
    )
@app.route('/disbursements')
def disbursement_list():

    if 'user' not in session:
        return redirect(url_for('login'))

    disbursements = Disbursement.query.all()

    return render_template(
        'disbursement_list.html',
        disbursements=disbursements
    )



@app.route('/add_payment', methods=['GET', 'POST'])
def add_payment():

    if 'user' not in session:
        return redirect(url_for('login'))

    farmers = Farmer.query.all()

    if request.method == 'POST':

        try:

            repayment = Repayment(

                farmer_id=request.form['farmer_id'],

                payment_date=request.form['payment_date'],

                amount_paid=request.form['amount_paid'],

                payment_method=request.form['payment_method'],

                payment_month=request.form['payment_month'],

                payment_year=request.form['payment_year'],

                remarks=request.form.get('remarks')
            )

            db.session.add(repayment)
            db.session.commit()

            flash('Payment recorded successfully!', 'success')

            return redirect(url_for('add_payment'))

        except Exception as e:

            db.session.rollback()

            flash(f'Error saving payment: {str(e)}', 'danger')

    return render_template(
        'add_payment.html',
        farmers=farmers
    )




# @app.route('/repayments')
# def repayment_list():

#     if 'user' not in session:
#         return redirect(url_for('login'))

#     repayments = Repayment.query.all()

#     return render_template(
#         'repayment_list.html',
#         repayments=repayments
#     )

def calculate_farmer_balance(farmer):
    total_disbursed = 0

    for d in farmer.disbursements:
        total_disbursed += (
            (d.fertilizer_bags or 0) * 10000 +
            (d.seeds_kg or 0) * 2000 +
            (d.chemicals_litres or 0) * 5000
        )

    total_paid = sum(p.amount_paid or 0 for p in farmer.repayments)

    return total_disbursed - total_paid

@app.route('/repayments')
def repayments():

    if 'user' not in session:
        return redirect(url_for('login'))

    repayments = Repayment.query.order_by(Repayment.id.desc()).all()

    # attach computed balance per farmer
    for r in repayments:
        r.balance = calculate_farmer_balance(r.farmer)

    return render_template(
        'repayment_list.html',
        repayments=repayments
    )

# =====================================================
# REPORT ROUTES
# =====================================================

@app.route('/farmer_report')
def farmer_report():

    # =====================================================
    # GET FILTER VALUES FROM URL
    # =====================================================

    search_query = request.args.get('search', '').strip()
    district_filter = request.args.get('district', '').strip()
    type_filter = request.args.get('type', '').strip()

    # =====================================================
    # BASE QUERY
    # =====================================================

    query = Farmer.query

    # =====================================================
    # SEARCH (NAME / PHONE / ID)
    # =====================================================

    if search_query:
        query = query.filter(
            or_(
                Farmer.full_name.ilike(f"%{search_query}%"),
                Farmer.phone.ilike(f"%{search_query}%"),
                Farmer.id.like(f"%{search_query}%")
            )
        )

    # =====================================================
    # DISTRICT FILTER
    # =====================================================

    if district_filter and district_filter != "All Districts":
        query = query.filter(Farmer.district == district_filter)

    # =====================================================
    # TYPE FILTER (Individual / Group)
    # =====================================================

    if type_filter and type_filter != "All Types":
        query = query.filter(Farmer.farmer_type == type_filter)

    # =====================================================
    # FINAL RESULTS
    # =====================================================

    farmers = query.order_by(Farmer.id.desc()).all()

    # =====================================================
    # SUMMARY STATS (based on FULL dataset, not filtered)
    # =====================================================

    total_farmers = Farmer.query.count()
    individual_farmers = Farmer.query.filter_by(farmer_type="Individual").count()
    group_farmers = Farmer.query.filter_by(farmer_type="Group").count()

    return render_template(
        "farmer_report.html",
        farmers=farmers,
        total_farmers=total_farmers,
        individual_farmers=individual_farmers,
        group_farmers=group_farmers,
        search_query=search_query,
        district_filter=district_filter,
        type_filter=type_filter
    )


@app.route('/disbursement_report')
def disbursement_report():

    if 'user' not in session:
        return redirect(url_for('login'))

    search = request.args.get('search', '')
    input_type = request.args.get('input_type', '')
    date = request.args.get('date', '')

    query = Disbursement.query

    # SEARCH (farmer name or ID)
    if search:
        query = query.join(Farmer).filter(
            db.or_(
                Farmer.full_name.ilike(f"%{search}%"),
                Disbursement.id.like(f"%{search}%")
            )
        )

    # FILTER BY DATE
    if date:
        query = query.filter(Disbursement.disbursement_date == date)

    disbursements = query.order_by(Disbursement.id.desc()).all()

    total = len(disbursements)

    completed = total  # (you can enhance later if you add status column)
    pending = 0

    # breakdown counts (simple logic)
    for d in disbursements:
        if not (d.fertilizer_bags or d.seeds_kg or d.chemicals_litres):
            pending += 1

    return render_template(
        "disbursement_report.html",
        disbursements=disbursements,
        total=total,
        completed=completed,
        pending=pending
    )

@app.route('/repayment_report')
def repayment_report():

    if 'user' not in session:
        return redirect(url_for('login'))

    repayments = Repayment.query.order_by(Repayment.id.desc()).all()

    total_collected = 0
    partial_count = 0
    outstanding_total = 0

    for r in repayments:

        # compute balance per farmer
        total_disbursed = sum(
            (d.fertilizer_bags or 0) * 10000 +
            (d.seeds_kg or 0) * 2000 +
            (d.chemicals_litres or 0) * 5000
            for d in r.farmer.disbursements
        )

        total_paid = sum(p.amount_paid or 0 for p in r.farmer.repayments)

        balance = total_disbursed - total_paid
        r.balance = balance

        total_collected += r.amount_paid or 0

        if balance > 0 and r.amount_paid > 0:
            partial_count += 1

        if balance > 0:
            outstanding_total += balance

    return render_template(
        "repayment_report.html",
        repayments=repayments,
        total_collected=total_collected,
        partial_count=partial_count,
        outstanding_total=outstanding_total
    )


@app.route('/reports')
def reports():

    if 'user' not in session:
        return redirect(url_for('login'))

    return render_template('reports.html')


# =====================================================
# RUN APPLICATION
# =====================================================

with app.app_context():
    db.create_all()
    ensure_user_schema()

if __name__ == '__main__':
    app.run(debug=True)