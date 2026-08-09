import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from database.db import get_db

USER_ID = 2
COUNT = 5
MONTHS = 3

# (category, weight, min_amount, max_amount, descriptions)
CATEGORIES = [
    ("Food", 35, 50, 800, [
        "Lunch at Student Biryani", "Karachi Broast order", "Grocery run at Imtiaz",
        "Chai and samosay", "Dinner at Bundu Khan", "Fruit chaat from thela",
        "Nashta at local dhaba", "KFC delivery",
    ]),
    ("Transport", 20, 20, 500, [
        "Careem ride to office", "Petrol top-up", "Rickshaw fare",
        "Bykea ride", "Bus fare to Saddar", "Parking fee",
    ]),
    ("Bills", 15, 200, 3000, [
        "K-Electric bill", "PTCL internet bill", "Mobile load - Jazz",
        "Gas bill (SSGC)", "Water bill",
    ]),
    ("Health", 8, 100, 2000, [
        "Pharmacy - D-Watson", "Doctor consultation fee", "Panadol and syrup",
        "Dental checkup",
    ]),
    ("Entertainment", 7, 100, 1500, [
        "Cinepax movie tickets", "Netflix subscription", "PlayStation game rental",
        "Snooker club",
    ]),
    ("Shopping", 10, 200, 5000, [
        "Khaadi kurta", "Shoes from Servis", "Daraz online order",
        "Mobile cover and charger",
    ]),
    ("Other", 5, 50, 1000, [
        "Eidi given to cousin", "Mosque donation", "Miscellaneous expense",
        "Stationery items",
    ]),
]

WEIGHTS = [c[1] for c in CATEGORIES]


def random_date(months):
    end = datetime.now()
    start = end - timedelta(days=months * 30)
    delta_days = (end - start).days
    offset = random.randint(0, max(delta_days, 0))
    return (start + timedelta(days=offset)).date()


def generate_expense(months):
    category, _, lo, hi, descriptions = random.choices(CATEGORIES, weights=WEIGHTS, k=1)[0]
    amount = round(random.uniform(lo, hi), 2)
    description = random.choice(descriptions)
    expense_date = random_date(months).isoformat()
    return amount, category, expense_date, description


def main():
    conn = get_db()
    rows = [generate_expense(MONTHS) for _ in range(COUNT)]

    try:
        for amount, category, expense_date, description in rows:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (USER_ID, amount, category, expense_date, description),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    dates = sorted(r[2] for r in rows)
    inserted = conn.execute(
        "SELECT id, amount, category, date, description FROM expenses "
        "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (USER_ID, COUNT),
    ).fetchall()
    conn.close()

    print(f"Inserted {COUNT} expenses for user_id={USER_ID}")
    print(f"Date range: {dates[0]} to {dates[-1]}")
    print("\nSample records:")
    for row in list(inserted)[:5]:
        print(f"  id={row['id']} | {row['date']} | {row['category']:<13} | "
              f"PKR {row['amount']:>8.2f} | {row['description']}")


if __name__ == "__main__":
    main()
