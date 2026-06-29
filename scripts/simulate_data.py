import random
import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker


ROOT = Path(__file__).resolve().parents[1]

DB_PATH = ROOT / "data" / "music.db"
faker = Faker("en_US")

random.seed(42)
Faker.seed(42)

USER_COUNT = 3000  # number of users to simulate
GENRES = ["Pop", "Rock", "Jazz", "HipHop", "Classical", "Electronic", "R&B", "K-Pop"]
SCENES = ["Study", "Workout", "Commute", "Sleep", "Party", "Relax"]


def _utcnow():
    return datetime.utcnow().isoformat(sep=" ")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = OFF")  # speed up inserts
    conn.row_factory = sqlite3.Row
    return conn


def bulk_insert(conn, table, columns, data):
    if not data: return
    placeholders = ",".join(["?"] * len(columns))
    col_str = ",".join(columns)
    sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})"
    batch_size = 1000
    for i in range(0, len(data), batch_size):
        conn.executemany(sql, data[i:i + batch_size])
    print(f"  -> Inserted {len(data)} rows into {table}")


def generate_users(n):

    print(f"Generating {n} users ...")
    users = []
    user_ids = list(range(1, n + 1))
    now = datetime.utcnow()
    sources = ["ads", "friend", "social", "search", "store"]
    genders = ["M", "F", "O", None]

    # trend_type: 0=stable, 1=recent surge, 2=early surge
    trend_type = random.choice([0, 1, 1, 2])

    for uid in user_ids:
        # Determine registration time distribution based on trend type
        if trend_type == 1:
            # Recent surge: most users registered in the last 30 days
            days_ago = int(random.triangular(0, 365, 0))
        elif trend_type == 2:
            # Early surge
            days_ago = int(random.triangular(0, 365, 365))
        else:
            # Uniform distribution (exponential distribution)
            days_ago = int(random.expovariate(1 / 150))
            days_ago = min(days_ago, 365)

        reg_time = (now - timedelta(days=days_ago, hours=random.randint(0, 23))).isoformat(sep=" ")

        users.append((
            uid,
            faker.unique.email(),
            faker.unique.phone_number(),
            faker.user_name(),
            random.choice(genders),
            random.randint(1970, 2010),
            faker.state(), 
            random.choice(sources),
            reg_time,
            None, # No invitation code generated
            'active',
            _utcnow(), _utcnow()
        ))
    return users


def generate_preferences(user_ids):
    prefs = []
    for uid in user_ids:
        fav_g = random.sample(GENRES, k=random.randint(1, 3))
        fav_s = random.sample(SCENES, k=random.randint(1, 2))
        prefs.append((
            uid, ",".join(fav_g), ",".join(fav_s),
            faker.sentence(), _utcnow(), _utcnow()
        ))
    return prefs


def generate_listening_logs(users_data):
    print("Generating logs (This may take 5-10s)...")
    logs = []
    now = datetime.utcnow()

    # 0=regular, 1=night owl (more late night), 2=commuter (more rush hours)
    active_pattern = random.choice([0, 0, 1, 2])

    for u in users_data:
        uid = u[0]
        reg_str = u[8]
        birth_year = u[5]
        reg_time = datetime.fromisoformat(reg_str)

        days_active = (now - reg_time).days
        if days_active < 1: continue

        n_logs = random.randint(1,365)

        for _ in range(n_logs):
            delta_days = random.randint(0, days_active)

            # Generate hour based on pattern
            if active_pattern == 1:  
                hour = int(random.triangular(0, 23, 23))  # Biased towards 23
            elif active_pattern == 2:  
                hour = random.choice([7, 8, 9, 17, 18, 19] + list(range(0, 24)))
            else:
                hour = random.randint(0, 23)

            play_time = now - timedelta(days=delta_days, hours=0) 
            play_time = play_time.replace(hour=hour, minute=random.randint(0, 59)) 

            if play_time < reg_time: continue

            logs.append((
                uid, play_time.isoformat(sep=" "),
                random.randint(120, 300),
                random.choice(GENRES),  
                1 if random.random() < 0.1 else 0,
                random.choice(["mobile", "web"]),
                1 if random.random() < 0.3 else 0,
                _utcnow()
            ))
    return logs


def generate_feedbacks(user_ids):
    fbs = []
    comments = [
        "Great sound quality.", "Love the new UI.", "Too expensive.",
        "Please add lyrics.", "Crash on startup.", "Best music app ever.",
        "Recommendations are spot on."
    ]
    # Select 5% to 15% of users to provide feedback
    target_users = random.sample(user_ids, int(len(user_ids) * random.uniform(0.05, 0.15)))
    now = datetime.utcnow()

    for uid in target_users:
        fbs.append((
            uid, now.isoformat(sep=" "),
            random.randint(1, 5),
            "app", "general",
            random.choice(comments),
            _utcnow()
        ))
    return fbs


def calculate_profiles_via_sql(conn):
    print("Calculating profiles & segments...")
    conn.execute("""
    INSERT OR REPLACE INTO user_profiles (user_id, main_interest, churn_risk_level, last_profile_update)
    SELECT 
        user_id,
        (SELECT genre FROM listening_logs l2 WHERE l2.user_id = l1.user_id GROUP BY genre ORDER BY COUNT(*) DESC LIMIT 1),
        CASE WHEN MAX(play_time) < date('now', '-30 days') THEN 'high' ELSE 'low' END,
        datetime('now')
    FROM listening_logs l1
    GROUP BY user_id
    """)

    conn.execute("DELETE FROM user_segment_membership")
    segments = {
        "Power User": "SELECT user_id FROM listening_logs GROUP BY user_id HAVING COUNT(*) > 30",
        "New User": "SELECT user_id FROM users WHERE register_time > date('now', '-7 days')",
        "Churn Risk": "SELECT user_id FROM user_profiles WHERE churn_risk_level = 'high'"
    }

    conn.execute("DELETE FROM user_segments") 
    for name, query in segments.items():
        conn.execute("INSERT INTO user_segments (segment_name) VALUES (?)", (name,))
        seg_id = conn.execute("SELECT segment_id FROM user_segments WHERE segment_name=?", (name,)).fetchone()[0]
        conn.execute(
            f"INSERT OR IGNORE INTO user_segment_membership (user_id, segment_id, assigned_at) SELECT user_id, {seg_id}, datetime('now') FROM ({query})")


def main():
    print(f"=== START SIMULATION: {USER_COUNT} Users ===")

    users_data = generate_users(USER_COUNT)
    user_ids = [u[0] for u in users_data]
    prefs_data = generate_preferences(user_ids)
    logs_data = generate_listening_logs(users_data)
    fb_data = generate_feedbacks(user_ids)

    with get_conn() as conn:
        print("Cleaning DB...")
        tables = ["feedback_topics", "user_segment_membership", "user_profiles", "feedbacks",
                  "listening_logs", "user_preferences", "membership_subscriptions", "users", "user_segments"]
        for t in tables:
            try:
                conn.execute(f"DELETE FROM {t}")
            except:
                pass

        print("Inserting Data...")
        bulk_insert(conn, "users",
                    ["user_id", "email", "phone", "nickname", "gender", "birth_year", "region", "register_source",
                     "register_time", "invited_by_user_id", "status", "created_at", "updated_at"], users_data)
        bulk_insert(conn, "user_preferences",
                    ["user_id", "fav_genres", "fav_scenes", "extra_info", "created_at", "updated_at"], prefs_data)
        bulk_insert(conn, "listening_logs",
                    ["user_id", "play_time", "duration_sec", "genre", "is_skipped", "device_type", "from_recommend",
                     "created_at"], logs_data)
        bulk_insert(conn, "feedbacks",
                    ["user_id", "feedback_time", "rating", "channel", "feedback_type", "comment_text", "created_at"],
                    fb_data)

        calculate_profiles_via_sql(conn)
        conn.commit()

    print("=== SUCCESS: Database Refreshed with NEW Random Data! ===")


if __name__ == "__main__":
    main()
