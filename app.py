from flask import Flask, render_template, request, redirect, url_for, session, Response
import mysql.connector
import csv
from io import StringIO

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='lb'
    )

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/user-login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        if user and user[2] == password:
            return redirect(url_for('user_dashboard', user_id=user[0]))
        return render_template('user_login.html', error='Invalid email or password.')

    return render_template('user_login.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin WHERE email = %s", (email,))
        admin = cur.fetchone()

        if admin and admin[2] == password:
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_login.html', error='Invalid email or password.')

    return render_template('admin_login.html')

@app.route('/user-dashboard')
def user_dashboard():
    user_id = request.args.get('user_id')

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, title, author, available FROM books WHERE available > 0")
    books = cur.fetchall()

    cur.execute("""
        SELECT b.title, br.date_from, br.date_to, br.status
        FROM borrow_requests br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = %s
    """, (user_id,))
    borrow_history = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('user_dashboard.html', books=books, borrow_history=borrow_history, user_id=user_id)

@app.route('/borrow-book', methods=['POST'])
def borrow_book():
    user_id = request.form['user_id']
    book_id = request.form['book_id']
    date_from = request.form['date_from']
    date_to = request.form['date_to']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT available FROM books WHERE id = %s", (book_id,))
    book = cur.fetchone()

    if book and book[0] > 0:
        cur.execute("""
            INSERT INTO borrow_requests (user_id, book_id, date_from, date_to, status)
            VALUES (%s, %s, %s, %s, 'Pending')
        """, (user_id, book_id, date_from, date_to))
        cur.execute("UPDATE books SET available = available - 1 WHERE id = %s", (book_id,))
        conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for('user_dashboard', user_id=user_id))

@app.route('/admin-dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        request_id = request.form.get('request_id')
        if 'approve' in request.form:
            cur.execute("UPDATE borrow_requests SET status = 'Approved' WHERE id = %s", (request_id,))
        elif 'deny' in request.form:
            cur.execute("UPDATE borrow_requests SET status = 'Denied' WHERE id = %s", (request_id,))
        conn.commit()

    cur.execute("""
        SELECT br.id, u.email, b.title, br.status
        FROM borrow_requests br
        JOIN users u ON br.user_id = u.id
        JOIN books b ON br.book_id = b.id
    """)
    borrow_requests = cur.fetchall()

    cur.execute("SELECT id, email FROM users")
    users = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('admin_dashboard.html', borrow_requests=borrow_requests, users=users)

@app.route('/user_history/<int:user_id>')
def user_history(user_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT br.id, br.book_id, b.title AS book_name, br.date_from, br.date_to, br.status
        FROM borrow_requests br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = %s AND br.status IN ('Approved', 'Returned')
    """, (user_id,))
    borrowing_history = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('user_history.html', borrowing_history=borrowing_history, user_id=user_id)

@app.route('/return-book', methods=['POST'])
def return_book():
    request_id = request.form['request_id']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("UPDATE borrow_requests SET status = 'Returned' WHERE id = %s", (request_id,))
    cur.execute("""
        UPDATE books
        SET available = available + 1
        WHERE id = (SELECT book_id FROM borrow_requests WHERE id = %s)
    """, (request_id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(request.referrer or url_for('home'))

@app.route('/download-history/<int:user_id>')
def download_history(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT b.title, br.date_from, br.date_to, br.status
        FROM borrow_requests br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = %s
    """, (user_id,))
    borrow_history = cur.fetchall()

    cur.close()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Book Title', 'From', 'To', 'Status'])
    writer.writerows(borrow_history)

    output.seek(0)
    return Response(output, mimetype='text/csv',
                    headers={"Content-Disposition": f"attachment;filename=borrow_history_user_{user_id}.csv"})

@app.route('/logout')
def logout():
    return redirect(url_for('home'))

@app.route("/user_register", methods=["GET", "POST"])
def user_register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, password))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('user_login'))
        except mysql.connector.IntegrityError:
            return "User already exists!"
        except Exception as e:
            return f"Something went wrong: {e}"

    return render_template("user_register.html")

@app.route('/admin/book-management')
def book_management():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books")
    books = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('book_management.html', books=books)

@app.route('/add-book', methods=['POST'])
def add_book():
    title = request.form['title']
    author = request.form['author']
    quantity = request.form['quantity']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO books (title, author, available) VALUES (%s, %s, %s)", (title, author, quantity))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('book_management'))

@app.route('/delete-book', methods=['POST'])
def delete_book():
    book_id = request.form['book_id']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM books WHERE id = %s", (book_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('book_management'))

if __name__ == '__main__':
    app.run(debug=True)
