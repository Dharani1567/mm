from flask import Flask, jsonify, request, render_template, redirect, session, url_for
from db_connection import get_db_connection
from datetime import date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2.extras
from flask_cors import CORS
import csv
from flask import make_response

app = Flask(__name__)
app.secret_key = "supersecretkey"
CORS(app, supports_credentials=True)


# -------------------------
#  AUTH ROUTES
# -------------------------
@app.route("/")
def home():
    # if logged in -> route based on role
    if "user_id" in session:
        # If stock admin, show their dashboard
        if session.get("role") == "stock_admin":
            return redirect("/stock_dashboard")
        return render_template("index.html")
    return redirect("/login")
@app.route('/dashboard')
def dashboard():
    return render_template('index.html')


@app.route("/login", methods=["GET"])
def show_login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("emailIn")
    password = request.form.get("passwordIn")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT user_id, name, role, email, password
        FROM users
        WHERE email = %s
    """, (email,))

    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return "<h3>Email not found</h3>"

    if check_password_hash(user["password"], password):
        session["user_id"] = user["user_id"]
        session["name"] = user["name"]
        session["role"] = user["role"]

        # Redirect based on role
        if user["role"] == "stock_admin":
            return redirect("/stock_dashboard")
        else:
            return redirect("/")
    else:
        return "<h3>Invalid password</h3>"


@app.route("/signup", methods=["POST"])
def signup():
    fullname = request.form["fullname"]
    email = request.form["email"]
    password = generate_password_hash(request.form["password"])

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (name, role, email, password)
            VALUES (%s, %s, %s, %s)
        """, (fullname, "admin", email, password))

        conn.commit()
        message = "Account created successfully!"
    except Exception as e:
        conn.rollback()
        print("Signup Error:", e)
        message = "Email already exists!"

    cur.close()
    conn.close()

    return render_template("login.html", message=message)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# -------------------------
#  MEDICINES APIs
# -------------------------
@app.route('/medicines', methods=['GET'])
def get_medicines():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
        SELECT 
            m.*, 
            s.name AS supplier_name,
            c.category_name
        FROM medicines m
        LEFT JOIN suppliers s ON m.supplier_id = s.supplier_id
        LEFT JOIN categories c ON m.category_id = c.category_id
        ORDER BY m.medicine_id;
        """
        
        cur.execute(query)
        rows = cur.fetchall()

        medicines = []
        for row in rows:
            medicines.append({
                "medicine_id": row["medicine_id"],
                "name": row["name"],
                "batch_number": row["batch_number"],
                "expiry_date": str(row["expiry_date"]) if row["expiry_date"] else None,
                "quantity": row["quantity"],
                "supplier_id": row["supplier_id"],
                "supplier_name": row["name"],   #  FIXED
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "price": float(row["price"]) if row["price"] is not None else None
            })

        return jsonify(medicines)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass



# New API: medicines in stock for stock_admin (quantity > 0)
@app.route('/medicines-in-stock', methods=['GET'])
def get_medicines_in_stock():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT m.*, s.name AS supplier_name, c.category_name FROM medicines m LEFT JOIN suppliers s ON m.supplier_id = s.supplier_id LEFT JOIN categories c ON m.category_id = c.category_id WHERE m.quantity > 0 ORDER BY m.name;")
        rows = cur.fetchall()

        medicines = []
        for row in rows:
            medicines.append({
                "medicine_id": row["medicine_id"],
                "name": row["name"],
                "batch_number": row["batch_number"],
                "expiry_date": str(row["expiry_date"]) if row["expiry_date"] else None,
                "quantity": row["quantity"],
                "supplier_id": row["supplier_id"],
                "supplier_name": row.get("name"),
                "category_id": row["category_id"],
                "category_name": row.get("category_name"),
                "price": float(row["price"]) if row["price"] is not None else None
            })

        return jsonify(medicines)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


# Add / Update / Delete APIs (unchanged)
@app.route('/medicines', methods=['POST'])
def add_medicine():
    data = request.json or {}

    required = ['name', 'batch_number', 'expiry_date', 'quantity', 'supplier_id', 'category_id', 'price']
    missing = [f for f in required if f not in data]

    if missing:
        return jsonify({"error": "Missing fields", "missing": missing}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO medicines (name, batch_number, expiry_date, quantity, supplier_id, category_id, price)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data['name'], data['batch_number'], data['expiry_date'],
            data['quantity'], data['supplier_id'], data['category_id'], data['price']
        ))

        conn.commit()

        return jsonify({"message": "Medicine added successfully"}), 201

    except Exception as e:
        conn.rollback()
        print(" Error adding medicine:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()


@app.route('/medicines/<int:medicine_id>', methods=['PUT'])
def update_medicine(medicine_id):
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = """
        UPDATE medicines SET
            name = %s, batch_number = %s, expiry_date = %s, quantity = %s,
            supplier_id = %s, category_id = %s, price = %s
        WHERE medicine_id = %s;
        """
        cur.execute(query, (
            data.get('name'), data.get('batch_number'), data.get('expiry_date'),
            data.get('quantity'), data.get('supplier_id'), data.get('category_id'),
            data.get('price'), medicine_id
        ))
        conn.commit()
        return jsonify({"message": "Medicine updated successfully"})
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Error updating medicine"}), 500


@app.route('/medicines/<int:medicine_id>', methods=['DELETE'])
def delete_medicine(medicine_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM medicines WHERE medicine_id = %s;", (medicine_id,))
        conn.commit()
        return jsonify({"message": "Medicine deleted successfully"})
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Error deleting medicine"}), 500


# Search (unchanged; you can route stock_admin to /medicines-in-stock if you want server-side search)
@app.route('/search', methods=['GET'])
def search_medicines():
    query = request.args.get('q', '')
    results = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        sql = """
        SELECT * FROM medicines
        WHERE name ILIKE %s OR batch_number ILIKE %s;
        """
        cur.execute(sql, (f"%{query}%", f"%{query}%"))
        rows = cur.fetchall()
        for row in rows:
            results.append({
                "medicine_id": row[0],
                "name": row[1],
                "batch_number": row[2],
                "expiry_date": str(row[3]),
                "quantity": row[4],
                "supplier_id": row[5],
                "category_id": row[6],
                "price": float(row[7]) if row[7] is not None else None
            })
        return jsonify(results)
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Error searching medicines"}), 500


# Alerts (unchanged)
#@app.route('/alerts', methods=['GET'])
def alerts():
    alerts_data = {"low_stock": [], "near_expiry": []}
    today = date.today()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM medicines WHERE quantity < 10;")
        low_stock = cur.fetchall()
        for row in low_stock:
            alerts_data["low_stock"].append({"name": row[1], "quantity": row[4]})
        cur.execute("SELECT * FROM medicines WHERE expiry_date <= %s;", (today + timedelta(days=30),))
        near_expiry = cur.fetchall()
        for row in near_expiry:
            alerts_data["near_expiry"].append({"name": row[1], "expiry_date": str(row[3])})
        return jsonify(alerts_data)
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Error fetching alerts"}), 500


# -------------------------
#  SUPPLIERS / CATEGORIES (unchanged)
# -------------------------


@app.route('/add_supplier_page')
def add_supplier_page():
    # prevent stock_admin from adding
    if session.get("role") == "stock_admin":
        return redirect("/stock_dashboard")
    return render_template('add_supplier.html')




@app.route('/suppliers', methods=['GET'])
def get_suppliers():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM suppliers ORDER BY supplier_id;")
        rows = cur.fetchall()

        suppliers = []
        for row in rows:
            suppliers.append({
                "supplier_id": row["supplier_id"],
                "name": row["name"],   # use 'name'
                "supplier_name": row["name"],  # if you want both
                "contact_number": row["contact_number"],
                "email": row["email"],
                "address": row["address"],
            })

        return jsonify(suppliers)

    except Exception as e:
        print("❌ ERROR in /suppliers:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


@app.route('/suppliers', methods=['POST'])
def add_supplier():
    data = request.json

    required = ["name", "contact_number", "email", "address"]
    missing = [f for f in required if f not in data]

    if missing:
        return jsonify({"error": "Missing fields", "missing": missing}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO suppliers (name, contact_number, email, address)
        VALUES (%s, %s, %s, %s)
        """, (data['name'], data['contact_number'], data['email'], data['address']))

        conn.commit()

        return jsonify({"message": "Supplier added"}), 201

    

    except Exception as e:
        conn.rollback()
        print("Error adding supplier:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()




@app.route('/categories', methods=['GET'])
def get_categories():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM categories ORDER BY category_id;")
        rows = cur.fetchall()

        cats = [{
            "category_id": r["category_id"],
            "category_name": r["category_name"],
            "description": r["description"]
        } for r in rows]

        return jsonify(cats)

    except Exception as e:
        print("Error in /categories:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass



# -------------------------
#  DASHBOARD STATS (unchanged)
# -------------------------
@app.route('/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT expiry_date, quantity FROM medicines;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    total = len(rows)
    expiring_soon = 0
    low_stock = 0
    today = date.today()
    for row in rows:
        expiry_date, quantity = row
        if expiry_date and (expiry_date - today).days <= 30:
            expiring_soon += 1
        if quantity is not None and quantity <= 10:
            low_stock += 1
    return jsonify({
        "total": total,
        "expiring_soon": expiring_soon,
        "low_stock": low_stock
    })


# -------------------------
#  FRONTEND PAGES
# -------------------------
@app.route('/medicines_page')
def medicines_page():
    return render_template('medicines.html')


@app.route('/add_medicine_page')
def add_medicine_page():
    # prevent stock_admin from adding
    if session.get("role") == "stock_admin":
        return redirect("/stock_dashboard")
    return render_template('add_medicine.html')


@app.route('/update_medicine_page')
def update_medicine_page():
    # prevent stock_admin from editing
    if session.get("role") == "stock_admin":
        return redirect("/stock_dashboard")
    return render_template('update_medicine.html')


@app.route('/suppliers_page')
def suppliers_page():
    # prevent stock_admin from supplier pages
    if session.get("role") == "stock_admin":
        return redirect("/stock_dashboard")
    return render_template('suppliers.html')


#@app.route('/reports_page')
def reports_page():
    return render_template('reports.html')


# New: stock admin dashboard
@app.route('/stock_dashboard')
def stock_dashboard():
    # only stock_admin or admin allowed (admin redirected to normal dashboard)
    if "user_id" not in session:
        return redirect("/login")
    if session.get("role") == "admin":
        return redirect("/")
    if session.get("role") != "stock_admin":
        return "<h3>Unauthorized</h3>", 403
    return render_template("stock_dashboard.html")
@app.route('/report/stock')
def stock_report():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT m.medicine_id, m.name, m.batch_number, m.quantity,
                   s.name AS supplier, m.price
            FROM medicines m
            LEFT JOIN suppliers s ON m.supplier_id = s.supplier_id
            ORDER BY m.medicine_id;
        """)

        rows = cur.fetchall()

        # Convert to CSV
        output = "ID,Name,Batch,Quantity,Supplier,Price\n"
        for r in rows:
            output += f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]}\n"

        response = make_response(output)
        response.headers["Content-Disposition"] = "attachment; filename=stock_report.csv"
        response.headers["Content-Type"] = "text/csv"
        return response

    except Exception as e:
        print("Stock Report Error:", e)
        return jsonify({"error": str(e)}), 500


# -------------------------
#  RUN
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)
