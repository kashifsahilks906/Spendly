import random
import sys
from datetime import datetime

sys.path.insert(0, ".")

from werkzeug.security import generate_password_hash
from database.db import get_db, init_db

FIRST_NAMES = [
    "Ahmed", "Bilal", "Usman", "Hamza", "Saeed", "Faisal", "Imran", "Tariq",
    "Asad", "Zeeshan", "Junaid", "Kashif", "Waqas", "Adeel", "Shahid",
    "Ayesha", "Sana", "Mahnoor", "Hira", "Rabia", "Sadia", "Farah",
    "Nadia", "Amina", "Zainab", "Mehak", "Iqra", "Komal",
]

LAST_NAMES = [
    "Khan", "Malik", "Butt", "Chaudhry", "Sheikh", "Qureshi", "Raza",
    "Hussain", "Abbasi", "Baig", "Awan", "Gill", "Rana", "Soomro",
    "Bhutto", "Jatoi", "Marwat", "Durrani", "Niazi", "Yousafzai",
]


def generate_user():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    number = random.randint(0, 999)
    digits = random.choice([2, 3])
    number_str = str(number).zfill(digits)[-digits:]
    email = f"{first.lower()}.{last.lower()}{number_str}@gmail.com"
    return name, email


def main():
    init_db()
    conn = get_db()

    while True:
        name, email = generate_user()
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing is None:
            break

    password_hash = generate_password_hash("password123")
    created_at = datetime.now().isoformat(sep=" ", timespec="seconds")

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (name, email, password_hash, created_at),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    print("Seeded user:")
    print(f"  id:    {user_id}")
    print(f"  name:  {name}")
    print(f"  email: {email}")


if __name__ == "__main__":
    main()
