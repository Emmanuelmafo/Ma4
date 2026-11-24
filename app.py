import os
from decimal import Decimal, InvalidOperation
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from database import fetch_all, fetch_one, init_db, insert, run

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "development-key-change-before-deploy")

@app.before_request
def ensure_schema():
    # Keep Railway's health probe independent of database availability.
    # Normal application pages initialise the SmartShop tables before use.
    if request.endpoint != "health":
        init_db()

@app.get("/")
def home():
    return redirect(url_for("dashboard", role="owner"))

@app.get("/dashboard/<role>")
def dashboard(role):
    if role not in {"owner", "manager", "employee"}:
        role = "owner"
    totals = fetch_one("""SELECT COALESCE(SUM(storage_quantity), 0) AS storage,
               COALESCE(SUM(display_quantity), 0) AS display FROM smartshop_products""")
    product_count = fetch_one("SELECT COUNT(*) AS count FROM smartshop_products")["count"]
    today_sales = fetch_one("""SELECT COALESCE(SUM(total_amount), 0) AS amount
        FROM smartshop_sales WHERE DATE(created_at) = CURRENT_DATE""")["amount"]
    smartshop_products = fetch_all("SELECT * FROM smartshop_products ORDER BY name LIMIT 12")
    return render_template("dashboard.html", role=role, totals=totals,
        product_count=product_count, today_sales=today_sales, products=smartshop_products)

@app.route("/manager/receive", methods=["GET", "POST"])
def receive_stock():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        box_barcode = request.form.get("box_barcode", "").strip() or None
        try:
            boxes = int(request.form.get("boxes", "0"))
            units_per_box = int(request.form.get("units_per_box", "0"))
            loose_units = int(request.form.get("loose_units", "0"))
            buying_price = Decimal(request.form.get("buying_price", "0"))
            selling_price = Decimal(request.form.get("selling_price", "0"))
        except (ValueError, InvalidOperation):
            flash("Enter valid numbers for quantities and prices.", "error")
            return redirect(url_for("receive_stock"))
        quantity = boxes * units_per_box + loose_units
        if not name or quantity <= 0 or min(boxes, units_per_box, loose_units) < 0 or min(buying_price, selling_price) < 0:
            flash("Enter a product name and valid quantities and prices.", "error")
            return redirect(url_for("receive_stock"))
        existing = fetch_one("SELECT id FROM smartshop_products WHERE LOWER(name)=LOWER(:name)", {"name": name})
        if existing:
            product_id = existing["id"]
            run("""UPDATE smartshop_products SET storage_quantity = storage_quantity + :quantity,
                buying_price = :buying_price, selling_price = :selling_price,
                box_barcode = COALESCE(:box_barcode, box_barcode) WHERE id = :product_id""",
                {"quantity": quantity, "buying_price": str(buying_price), "selling_price": str(selling_price),
                 "box_barcode": box_barcode, "product_id": product_id})
        else:
            product_id = insert("""INSERT INTO smartshop_products
                (name, box_barcode, storage_quantity, buying_price, selling_price)
                VALUES (:name, :box_barcode, :quantity, :buying_price, :selling_price)""",
                {"name": name, "box_barcode": box_barcode, "quantity": quantity,
                 "buying_price": str(buying_price), "selling_price": str(selling_price)})
        run("""INSERT INTO smartshop_stock_movements
            (product_id, movement_type, quantity, source_location, destination_location, note)
            VALUES (:product_id, 'RECEIVE', :quantity, 'SUPPLIER', 'STORAGE', 'Stock received')""",
            {"product_id": product_id, "quantity": quantity})
        flash(f"Received {quantity} units of {name} into storage.", "success")
        return redirect(url_for("dashboard", role="manager"))
    return render_template("form.html", mode="receive", products=[])

@app.route("/manager/register-item-barcode", methods=["GET", "POST"])
def register_item_barcode():
    if request.method == "POST":
        try:
            product_id = int(request.form.get("product_id", "0"))
        except ValueError:
            product_id = 0
        barcode = request.form.get("scanned_barcode", "").strip()
        product = fetch_one("SELECT id, name FROM smartshop_products WHERE id=:id", {"id": product_id})
        if not product or not barcode:
            flash("Search for a product and scan its individual barcode before registering.", "error")
        else:
            try:
                run("INSERT INTO smartshop_item_barcodes (product_id, barcode) VALUES (:product_id, :barcode)",
                    {"product_id": product_id, "barcode": barcode})
                flash(f"Individual barcode registered for {product['name']}.", "success")
            except Exception:
                flash("That barcode is already registered. Scan a different item's barcode.", "error")
        return redirect(url_for("register_item_barcode", product_id=product_id))
    search = request.args.get("search", "").strip()
    selected_id = request.args.get("product_id", type=int)
    matches = fetch_all("SELECT id, name, storage_quantity, display_quantity FROM smartshop_products WHERE LOWER(name) LIKE LOWER(:term) ORDER BY name LIMIT 20",
                        {"term": f"%{search}%"}) if search else []
    selected = fetch_one("SELECT id, name FROM smartshop_products WHERE id=:id", {"id": selected_id}) if selected_id else None
    barcode_count = fetch_one("SELECT COUNT(*) AS count FROM smartshop_item_barcodes WHERE product_id=:id",
                              {"id": selected_id})["count"] if selected_id else 0
    return render_template("form.html", mode="register_barcode", products=matches,
                           selected_product=selected, barcode_count=barcode_count, search=search)

@app.route("/manager/display", methods=["GET", "POST"])
def move_to_display():
    if request.method == "POST":
        try:
            product_id = int(request.form.get("product_id", "0"))
            quantity = int(request.form.get("quantity", "0"))
        except ValueError:
            flash("Choose a product and enter a valid quantity.", "error")
            return redirect(url_for("move_to_display"))
        product = fetch_one("SELECT * FROM smartshop_products WHERE id=:id", {"id": product_id})
        if not product or quantity <= 0 or quantity > product["storage_quantity"]:
            flash("Insufficient storage stock or invalid quantity.", "error")
        else:
            run("""UPDATE smartshop_products SET storage_quantity = storage_quantity - :quantity,
                display_quantity = display_quantity + :quantity WHERE id = :id""",
                {"quantity": quantity, "id": product_id})
            run("""INSERT INTO smartshop_stock_movements
                (product_id, movement_type, quantity, source_location, destination_location, note)
                VALUES (:id, 'TRANSFER', :quantity, 'STORAGE', 'DISPLAY', 'Prepared for display')""",
                {"id": product_id, "quantity": quantity})
            flash("Stock moved to display. Total stock remains unchanged.", "success")
        return redirect(url_for("move_to_display"))
    smartshop_products = fetch_all("SELECT * FROM smartshop_products ORDER BY name")
    return render_template("form.html", mode="display", products=smartshop_products)

@app.route("/employee/pos", methods=["GET", "POST"])
def point_of_sale():
    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()
        try:
            quantity = int(request.form.get("quantity", "1"))
            selected_product_id = int(request.form.get("link_product_id", "0"))
        except ValueError:
            quantity = 0
            selected_product_id = 0

        product = None
        if barcode:
            product = fetch_one("""SELECT p.* FROM smartshop_products p
                LEFT JOIN smartshop_item_barcodes b ON b.product_id=p.id
                WHERE b.barcode=:barcode OR p.box_barcode=:barcode""",
                {"barcode": barcode})

            # An unknown item barcode is linked inline at the till.
            # The employee only chooses a product the first time this barcode appears.
            if not product and selected_product_id:
                selected = fetch_one(
                    "SELECT id, name FROM smartshop_products WHERE id=:id",
                    {"id": selected_product_id})
                if selected:
                    try:
                        run("""INSERT INTO smartshop_item_barcodes (product_id, barcode)
                            VALUES (:product_id, :barcode)""",
                            {"product_id": selected_product_id, "barcode": barcode})
                    except Exception:
                        # A simultaneous scan may have registered it already.
                        pass
                    product = fetch_one("""SELECT p.* FROM smartshop_products p
                        LEFT JOIN smartshop_item_barcodes b ON b.product_id=p.id
                        WHERE b.barcode=:barcode OR p.box_barcode=:barcode""",
                        {"barcode": barcode})

            if not product:
                products = fetch_all(
                    "SELECT id, name, display_quantity, selling_price FROM smartshop_products ORDER BY name")
                return render_template("form.html", mode="pos", products=products,
                    unknown_barcode=barcode, scanned_quantity=max(quantity, 1))

        else:
            try:
                product_id = int(request.form.get("product_id", "0"))
            except ValueError:
                product_id = 0
            product = fetch_one(
                "SELECT * FROM smartshop_products WHERE id=:id", {"id": product_id})

        if not product or quantity <= 0 or quantity > product["display_quantity"]:
            flash("Product not found or insufficient display stock.", "error")
        else:
            amount = Decimal(str(product["selling_price"])) * quantity
            sale_id = insert(
                "INSERT INTO smartshop_sales (total_amount) VALUES (:amount)",
                {"amount": str(amount)})
            run("""INSERT INTO smartshop_sale_items
                (sale_id, product_id, quantity, unit_price)
                VALUES (:sale_id, :product_id, :quantity, :price)""",
                {"sale_id": sale_id, "product_id": product["id"],
                 "quantity": quantity, "price": str(product["selling_price"])})
            run("""UPDATE smartshop_products
                SET display_quantity = display_quantity - :quantity
                WHERE id = :product_id""",
                {"quantity": quantity, "product_id": product["id"]})
            run("""INSERT INTO smartshop_stock_movements
                (product_id, movement_type, quantity, source_location, destination_location, note)
                VALUES (:product_id, 'SALE', :quantity, 'DISPLAY', 'SOLD', 'POS sale')""",
                {"product_id": product["id"], "quantity": quantity})
            flash(f"Sale completed: {quantity} × {product['name']} = K{amount}.", "success")
        return redirect(url_for("point_of_sale"))

    smartshop_products = fetch_all("SELECT * FROM smartshop_products ORDER BY name")
    return render_template("form.html", mode="pos", products=smartshop_products)

@app.get("/api/product/barcode/<barcode>")
def barcode_lookup(barcode):
    product = fetch_one("""SELECT p.id, p.name, p.selling_price, p.display_quantity FROM smartshop_products p
        LEFT JOIN smartshop_item_barcodes b ON b.product_id=p.id
        WHERE b.barcode=:barcode OR p.box_barcode=:barcode""", {"barcode": barcode})
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(dict(product))

@app.get("/health")
def health():
    return jsonify({"status": "ok", "application": "SmartShop", "framework": "Flask"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
