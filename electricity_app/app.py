from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message
import csv
import os
import random
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'YOUR EMAIL'  #The email you will use for sending bill to the recipient
app.config['MAIL_PASSWORD'] = 'YOUR APP PASSWORD' #App password will be in this format - abcd efgh ijkl
mail = Mail(app)

CSV_FILE = 'users.csv'

def create_user_file():
    """Creates the CSV file with headers if it doesn't exist."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['username', 'email', 'password'])

def update_user_password(username, new_password):
    """Updates the password for a given user in the CSV file."""
    temp_file = 'temp.csv'
    with open(CSV_FILE, 'r', newline='') as infile, open(temp_file, 'w', newline='') as outfile:
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        headers = next(reader)
        writer.writerow(headers)
        
        for row in reader:
            if row and row[0] == username:
                row[2] = new_password
            writer.writerow(row)
            
    os.remove(CSV_FILE)
    os.rename(temp_file, CSV_FILE)

def generate_bill_pdf(bill_details, output_buffer):
    """Generates a PDF of the bill and saves it to a buffer."""
    doc = SimpleDocTemplate(output_buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph("<b>West Bengal State Electricity Distribution Company Ltd.</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.25 * inch))
    
    # Bill Details Section
    details_data = [
        ['Customer Name:', bill_details['username']],
        ['Customer Email:', bill_details['email']],
        ['Units Consumed:', bill_details['units_consumed']],
        ['Total Bill Amount:', f'Rs. {bill_details["final_bill"]:.2f}']
    ]
    
    details_table = Table(details_data, colWidths=[2*inch, 4*inch])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
    ]))
    
    elements.append(Paragraph("<b>Bill Summary</b>", styles['h2']))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(details_table)
    elements.append(Spacer(1, 0.25 * inch))
    
    # Breakup of Charges
    breakup_data = [
        ['Category', 'Amount (Rs.)'],
        ['Energy Charge', f'{bill_details["energy_charge"]:.2f}'],
        ['Fixed/Demand Charge', f'{bill_details["fixed_charge"]:.2f}'],
        ['GST (5%)', f'{bill_details["gst_amount"]:.2f}'],
        ['Total', f'{bill_details["final_bill"]:.2f}'],
    ]
    
    breakup_table = Table(breakup_data, colWidths=[3*inch, 3*inch])
    breakup_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
    ]))
    
    elements.append(Paragraph("<b>Breakup of Charges</b>", styles['h2']))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(breakup_table)
    
    doc.build(elements)
    
    return output_buffer

# ----------------- Routes -----------------

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    create_user_file()
    
    with open(CSV_FILE, 'r', newline='') as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            if row and row[0] == username and row[2] == password:
                session['logged_in'] = True
                session['username'] = username
                session['email'] = row[1]
                return redirect(url_for('calculator_page'))
    
    flash('Invalid username or password.')
    return redirect(url_for('login_page'))

@app.route('/register_page')
def register_page():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not username or not email or not password:
        flash('All fields must be filled.')
        return redirect(url_for('register_page'))
    
    create_user_file()
    with open(CSV_FILE, 'r', newline='') as file:
        reader = csv.reader(file)
        for row in reader:
            if row and (row[0] == username or row[1] == email):
                flash('Username or email already exists.')
                return redirect(url_for('register_page'))
    
    with open(CSV_FILE, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([username, email, password])
        flash('Registration successful! You can now log in.')
    
    return redirect(url_for('login_page'))

@app.route('/calculator')
def calculator_page():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    return render_template('calculator.html')

@app.route('/display_bill', methods=['POST'])
def display_bill():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))

    try:
        last_reading = float(request.form.get('last_reading'))
        current_reading = float(request.form.get('current_reading'))

        if current_reading < last_reading:
            flash('Current reading cannot be less than the last reading.')
            return redirect(url_for('calculator_page'))
        
        units = current_reading - last_reading
        
        energy_cost = 0.0
        if units <= 5:
            energy_cost = units * 2.50
        elif units <= 15:
            energy_cost = (5 * 2.50) + ((units - 5) * 5.50)
        elif units <= 30:
            energy_cost = (5 * 2.50) + (10 * 5.50) + ((units - 15) * 10.50)
        elif units <= 50:
            energy_cost = (5 * 2.50) + (10 * 5.50) + (15 * 10.50) + ((units - 30) * 12.50)
        else:
            energy_cost = (5 * 2.50) + (10 * 5.50) + (15 * 10.50) + (20 * 12.50) + ((units - 50) * 12.50)
        
        fixed_charge = 106.20 
        gst_amount = (energy_cost + fixed_charge) * 0.05
        final_bill = energy_cost + fixed_charge + gst_amount

        bill_details = {
            'username': session.get('username'),
            'email': session.get('email'),
            'units_consumed': units,
            'energy_charge': energy_cost,
            'fixed_charge': fixed_charge,
            'gst_amount': gst_amount,
            'final_bill': final_bill,
        }

        try:
            output_buffer = BytesIO()
            generate_bill_pdf(bill_details, output_buffer)
            output_buffer.seek(0)
            
            msg = Message(
                'Your Electricity Bill from WBSEDCL',
                sender=app.config['MAIL_USERNAME'],
                recipients=[session.get('email')]
            )
            msg.body = f"Dear {session.get('username')},\n\nYour electricity bill has been generated. The details are attached in the PDF.\n\nThank you,\nWBSEDCL"
            msg.attach(f'Bill_{session.get("username")}.pdf', 'application/pdf', output_buffer.getvalue())
            mail.send(msg)
            flash('Your bill has been sent to your email.')
        except Exception as e:
            flash(f'Failed to send email. Error: {e}')
        
        return render_template('bill_display.html', bill=bill_details)
        
    except (ValueError, TypeError):
        flash('Please enter valid numbers for readings.')
    
    return redirect(url_for('calculator_page'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('email', None)
    flash('You have been logged out.')
    return redirect(url_for('login_page'))

# ----------------- New Routes for Password Reset -----------------

@app.route('/forgot_password_request')
def forgot_password_request():
    return render_template('forgot_password_request.html')

@app.route('/send_otp', methods=['POST'])
def send_otp():
    email = request.form.get('email')
    
    user_found_email = None
    with open(CSV_FILE, 'r', newline='') as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            if row and row[1] == email:
                user_found_email = row[1]
                break
    
    if not user_found_email:
        flash('No account found with that email address.')
        return redirect(url_for('forgot_password_request'))
    
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['reset_email'] = email
    
    msg = Message('Password Reset OTP', sender=app.config['MAIL_USERNAME'], recipients=[email])
    msg.body = f'Your one-time password for password reset is: {otp}'
    
    try:
        mail.send(msg)
        flash('An OTP has been sent to your email.')
        return redirect(url_for('verify_otp_page'))
    except Exception as e:
        flash(f'Failed to send OTP. Please check your email configuration. Error: {e}')
        return redirect(url_for('forgot_password_request'))

@app.route('/verify_otp_page')
def verify_otp_page():
    if 'otp' not in session:
        return redirect(url_for('forgot_password_request'))
    return render_template('verify_otp.html')

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    user_otp = request.form.get('otp')
    if 'otp' in session and user_otp == session['otp']:
        session['otp_verified'] = True
        return redirect(url_for('reset_password_page'))
    else:
        flash('Invalid OTP. Please try again.')
        return redirect(url_for('verify_otp_page'))

@app.route('/reset_password_page')
def reset_password_page():
    if not session.get('otp_verified'):
        return redirect(url_for('forgot_password_request'))
    return render_template('reset_password.html')

@app.route('/reset_password', methods=['POST'])
def reset_password():
    if not session.get('otp_verified'):
        return redirect(url_for('forgot_password_request'))
    
    new_password = request.form.get('new_password')
    retype_password = request.form.get('retype_password')
    
    if new_password != retype_password:
        flash('Passwords do not match.')
        return redirect(url_for('reset_password_page'))
    
    email = session.get('reset_email')
    
    user_to_update = None
    with open(CSV_FILE, 'r', newline='') as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            if row and row[1] == email:
                user_to_update = row[0]
                break
    
    if user_to_update:
        update_user_password(user_to_update, new_password)
    
    session.pop('otp', None)
    session.pop('reset_email', None)
    session.pop('otp_verified', None)
    
    flash('Your password has been reset successfully. Please log in.')
    return redirect(url_for('login_page'))

if __name__ == '__main__':

    app.run(debug=True)
