from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

# ---------- CONFIG ----------
DB_PATH = "carbon_final.db"
GRAPH_PATH = os.path.join("static", "weekly_graph.png")
# Custom absorption rate (kg CO2 per tree per year). Change this value as needed.
ABSORB_RATE = 15

app = Flask(__name__)

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            transport REAL,
            electricity REAL,
            food REAL,
            waste REAL,
            total REAL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------- Calculation Functions ----------
def calc_transport(distance_km, mode):
    factors = {
        "car": 0.21,
        "bike": 0.0,
        "bus": 0.08,
        "train": 0.05
    }
    return distance_km * factors.get(mode, 0)

def calc_electricity(units):
    return units * 0.92

def calc_food(food_type):
    factors = {
        "vegan": 2.0,
        "vegetarian": 3.0,
        "non_veg": 7.0
    }
    return factors.get(food_type, 0)

def calc_waste(kg):
    return kg * 1.2

# ---------- Helper Functions ----------
def insert_record(date_str, transport_em, electricity_em, food_em, waste_em, total):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO records (date, transport, electricity, food, waste, total) VALUES (?, ?, ?, ?, ?, ?)",
              (date_str, transport_em, electricity_em, food_em, waste_em, total))
    conn.commit()
    conn.close()

def fetch_all_records():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM records ORDER BY date ASC")
    data = c.fetchall()
    conn.close()
    return data

def fetch_week_records(days=7):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days-1)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT date, total FROM records WHERE date >= ? ORDER BY date ASC", (str(start),))
    data = c.fetchall()
    conn.close()
    return data

# ---------- Routes ----------

@app.route('/delete/<int:rid>')
def delete(rid):
    conn=sqlite3.connect("carbon_final.db")
    c=conn.cursor()
    c.execute("DELETE FROM records WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_records'))
@app.route("/")
def index():
    return render_template("index.html", absorb_rate=ABSORB_RATE)

@app.route("/add", methods=["GET", "POST"])
def add_record():
    if request.method == "POST":
        distance = float(request.form["distance"])
        mode = request.form["mode"]
        units = float(request.form["units"])
        food = request.form["food"]
        waste = float(request.form["waste"])

        transport_em = calc_transport(distance, mode)
        electricity_em = calc_electricity(units)
        food_em = calc_food(food)
        waste_em = calc_waste(waste)

        total = transport_em + electricity_em + food_em + waste_em
        date = str(datetime.date.today())

        insert_record(date, transport_em, electricity_em, food_em, waste_em, total)
        return redirect(url_for("view_records"))

    return render_template("add.html")

@app.route("/records")
def view_records():
    data = fetch_all_records()
    return render_template("records.html", data=data)

@app.route("/weekly_report")
def weekly_report():
    # Use last 7 days (including today)
    records = fetch_week_records(7)
    # Make sure we have one entry per day in the window; if missing days, fill with 0
    today = datetime.date.today()
    dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(6,-1,-1)]
    totals_by_date = {d:0.0 for d in dates}
    for row in records:
        totals_by_date[row[0]] = totals_by_date.get(row[0], 0.0) + row[1]

    ordered_dates = list(totals_by_date.keys())
    ordered_totals = [totals_by_date[d] for d in ordered_dates]

    # Plot weekly graph
    plt.figure(figsize=(9,4))
    plt.plot(ordered_dates, ordered_totals, marker='o', linewidth=2)
    plt.xticks(rotation=45)
    plt.title("Weekly Carbon Footprint (kg CO2)")
    plt.xlabel("Date")
    plt.ylabel("kg CO2")
    plt.tight_layout()
    os.makedirs(os.path.dirname(GRAPH_PATH), exist_ok=True)
    plt.savefig(GRAPH_PATH)
    plt.close()

    weekly_total = sum(ordered_totals)
    weekly_avg_per_day = weekly_total / 7.0
    # Lifetime calculations (assume 70-year lifetime)
    lifetime_years = 70
    lifetime_co2 = weekly_total * 52 * lifetime_years / 1.0  # weekly_total * 52 weeks/year * years
    # Trees required:
    # To offset the week's emissions over a year, trees_needed_week = (weekly_total * 52) / ABSORB_RATE
    trees_needed_week = (weekly_total * 52.0) / ABSORB_RATE if ABSORB_RATE > 0 else 0.0
    trees_needed_lifetime = lifetime_co2 / ABSORB_RATE if ABSORB_RATE > 0 else 0.0
    avg_weekly = weekly_total
    avg_daily = weekly_avg_per_day

    return render_template("weekly_report.html",
                           dates=ordered_dates,
                           totals=ordered_totals,
                           graph_path=GRAPH_PATH,
                           weekly_total=weekly_total,
                           avg_weekly=avg_weekly,
                           avg_daily=avg_daily,
                           trees_week=trees_needed_week,
                           trees_lifetime=trees_needed_lifetime,
                           lifetime_co2=lifetime_co2,
                           absorb_rate=ABSORB_RATE,
                           lifetime_years=lifetime_years)

if __name__ == "__main__":
    app.run(debug=True)
