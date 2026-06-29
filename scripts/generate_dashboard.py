from pathlib import Path
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "music.db"
OUTPUT_DIR = ROOT / "outputs"

plt.style.use('dark_background')
plt.rcParams.update({
    'figure.facecolor': 'none',  
    'axes.facecolor': 'none',  
    'grid.color': '#334155',  
    'grid.alpha': 0.3,
    'text.color': '#e2e8f0',  
    'axes.labelcolor': '#94a3b8',
    'xtick.color': '#94a3b8',
    'ytick.color': '#94a3b8',
    'font.family': 'sans-serif'
})

COLORS = ["#c77dff", "#6366f1", "#2dd4bf", "#f472b6", "#fbbf24"]


def read_table(name: str) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(f"SELECT * FROM {name}", conn)


def ensure_out():
    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

def save_plot(filename):
    plt.savefig(OUTPUT_DIR / filename, dpi=120, bbox_inches='tight', transparent=True)
    plt.close()


def plot_register_trend(users: pd.DataFrame):
    if users.empty: return
    users["day"] = pd.to_datetime(users["register_time"], format='mixed').dt.date
    daily = users.groupby("day").size().reset_index(name="count")

    plt.figure(figsize=(10, 5))
    sns.lineplot(data=daily, x="day", y="count", color="#c77dff", linewidth=2.5)
    plt.fill_between(daily["day"], daily["count"], color="#c77dff", alpha=0.1)

    plt.title("User Growth Trend", fontsize=14, pad=20)
    plt.grid(True, linestyle='--')
    sns.despine(left=True, bottom=True)
    save_plot("register_trend.png")


def plot_dau(listening: pd.DataFrame):
    if listening.empty: return
    listening["day"] = pd.to_datetime(listening["play_time"], format='mixed').dt.date
    dau = listening.groupby("day")["user_id"].nunique().reset_index(name="dau")

    plt.figure(figsize=(10, 5))
    sns.lineplot(data=dau, x="day", y="dau", color="#2dd4bf", linewidth=2.5)
    plt.fill_between(dau["day"], dau["dau"], color="#2dd4bf", alpha=0.1)

    plt.title("Daily Active Users", fontsize=14, pad=20)
    plt.grid(True, linestyle='--')
    sns.despine(left=True, bottom=True)
    save_plot("dau.png")


def plot_segments(seg_mem: pd.DataFrame, segments: pd.DataFrame):
    if seg_mem.empty: return
    merged = seg_mem.merge(segments, on="segment_id")
    counts = merged["segment_name"].value_counts().reset_index()
    counts.columns = ["segment", "count"]

    plt.figure(figsize=(6, 6))
    plt.pie(counts["count"], labels=counts["segment"], autopct='%1.1f%%',
            colors=COLORS, pctdistance=0.85,
            textprops={'color': "white", 'weight': 'bold'})

    centre_circle = plt.Circle((0, 0), 0.70, fc='none') 
    plt.gca().add_artist(centre_circle)

    plt.title("User Segments", fontsize=14)
    save_plot("segments.png")


def plot_retention_cohort(users: pd.DataFrame, listening: pd.DataFrame):
    if users.empty or listening.empty: return
    try:
        users["reg_month"] = pd.to_datetime(users["register_time"], format='mixed').dt.to_period("M")
        user_cohort = users[["user_id", "reg_month"]].drop_duplicates()
        listening["act_month"] = pd.to_datetime(listening["play_time"], format='mixed').dt.to_period("M")
        user_activity = listening[["user_id", "act_month"]].drop_duplicates()

        df = pd.merge(user_activity, user_cohort, on="user_id", how="left")
        df.dropna(inplace=True)
        df["cohort_idx"] = df.apply(lambda x: (x["act_month"] - x["reg_month"]).n, axis=1)
        df = df[df["cohort_idx"] >= 0]

        cohort_data = df.groupby(["reg_month", "cohort_idx"])["user_id"].nunique().reset_index()
        cohort_pivot = cohort_data.pivot_table(index="reg_month", columns="cohort_idx", values="user_id")
        retention = cohort_pivot.divide(cohort_pivot.iloc[:, 0], axis=0)

        plt.figure(figsize=(10, 6))
        sns.heatmap(retention, annot=True, fmt=".0%", cmap="Purples", vmin=0.0, vmax=0.5,
                    cbar=False, annot_kws={"size": 9})
        plt.title("Retention Rate (Monthly)", fontsize=14, pad=20)
        save_plot("retention.png")
    except Exception as e:
        print(f"Skipping retention plot due to data error: {e}")

def plot_active_heatmap(listening: pd.DataFrame):
    if listening.empty: return
    dt = pd.to_datetime(listening["play_time"], format='mixed')
    listening["weekday"] = dt.dt.day_name()
    listening["hour"] = dt.dt.hour

    data = listening.groupby(["weekday", "hour"]).size().reset_index(name="cnt")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    data["weekday"] = pd.Categorical(data["weekday"], categories=days, ordered=True)

    pivot = data.pivot_table(index="weekday", columns="hour", values="cnt", fill_value=0)

    plt.figure(figsize=(12, 5))
    sns.heatmap(pivot, cmap="flare", cbar_kws={'label': 'Activity'})
    plt.title("Activity Heatmap", fontsize=14, pad=20)
    plt.xlabel("Hour of Day")
    plt.ylabel("")
    save_plot("activity_heatmap.png")


def main():
    ensure_out()
    users = read_table("users")
    listening = read_table("listening_logs")
    seg_mem = read_table("user_segment_membership")
    segments = read_table("user_segments")

    print("Generating dark mode charts...")
    if not users.empty: plot_register_trend(users)
    if not seg_mem.empty: plot_segments(seg_mem, segments)
    if not listening.empty:
        plot_dau(listening)
        plot_active_heatmap(listening)
        if not users.empty: plot_retention_cohort(users, listening)

    print(f"Dashboard generated in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
