import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .text_mining import classify_user_segment, extract_keywords, predict_mbti, extract_topics


def _utcnow() -> str:
    return datetime.utcnow().isoformat(sep=" ", timespec="seconds")


class MusicAppSystem:
    def __init__(self, db_path: str = "data/music.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- User functions ---
    def register_user(
            self,
            email: Optional[str],
            phone: Optional[str],
            nickname: str,
            gender: Optional[str] = None,
            birth_year: Optional[int] = None,
            region: Optional[str] = None,
            register_source: Optional[str] = None,
            invited_by_user_id: Optional[int] = None,
            user_id: Optional[int] = None,
            register_time: Optional[str] = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (
                    user_id, email, phone, nickname, gender, birth_year, region,
                    register_source, register_time, invited_by_user_id, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    user_id, email, phone, nickname, gender, birth_year, region,
                    register_source, register_time or _utcnow(), invited_by_user_id,
                    _utcnow(), _utcnow(),
                ),
            )
            return cur.lastrowid if user_id is None else user_id

    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    # --- personal info ---
    def get_user_recent_logs(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT play_time, duration_sec, genre, device_type 
                FROM listening_logs 
                WHERE user_id = ? 
                ORDER BY play_time DESC 
                LIMIT ?
                """,
                (user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_user_feedbacks(self, user_id: int) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT feedback_time, rating, comment_text, feedback_type 
                FROM feedbacks 
                WHERE user_id = ? 
                ORDER BY feedback_time DESC
                """,
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Event logging & Feedback ---
    def log_listening_session(
            self, user_id: int, play_time: str, duration_sec: int, genre: str = None,
            is_skipped: bool = False, device_type: str = "mobile", from_recommend: bool = False
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO listening_logs (
                    user_id, play_time, duration_sec, genre, is_skipped,
                    device_type, from_recommend, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, play_time, duration_sec, genre, int(is_skipped), device_type, int(from_recommend), _utcnow()),
            )
            return cur.lastrowid

    def log_feedback(
            self, user_id: int, feedback_time: str, rating: int, comment_text: str,
            channel: str = "in_app", feedback_type: str = "overall"
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO feedbacks (
                    user_id, feedback_time, rating, channel, feedback_type,
                    comment_text, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, feedback_time, rating, channel, feedback_type, comment_text, _utcnow()),
            )
            feedback_id = cur.lastrowid

            topics = extract_topics(comment_text)
            for topic in topics:
                sentiment = 1.0 if rating >= 4 else (-1.0 if rating <= 2 else 0.0)
                conn.execute(
                    """
                    INSERT INTO feedback_topics (feedback_id, topic_label, sentiment_score, keywords)
                    VALUES (?, ?, ?, ?)
                    """,
                    (feedback_id, topic, sentiment, topic)
                )
            return feedback_id

    # --- Analytics Support ---
    def update_user_profile_from_text(self, user_id: int) -> None:
        with self._conn() as conn:
            rows = conn.execute("SELECT comment_text FROM feedbacks WHERE user_id = ?", (user_id,)).fetchall()

        texts = [r["comment_text"] for r in rows if r["comment_text"]]
        combined = " ".join(texts)
        if not combined: return

        keywords = extract_keywords(combined, top_k=8)
        mbti = predict_mbti(combined)

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (user_id, mbti_guess, keywords_summary, last_profile_update)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    mbti_guess = excluded.mbti_guess,
                    keywords_summary = excluded.keywords_summary,
                    last_profile_update = excluded.last_profile_update
                """,
                (user_id, mbti, ",".join(keywords), _utcnow()),
            )

    def update_user_profile_from_behavior(self, user_id: int) -> None:
        with self._conn() as conn:
            top_genre = conn.execute(
                "SELECT genre, COUNT(*) as c FROM listening_logs WHERE user_id=? GROUP BY genre ORDER BY c DESC LIMIT 1",
                (user_id,)
            ).fetchone()
            last_play = conn.execute(
                "SELECT MAX(play_time) as last_t FROM listening_logs WHERE user_id=?", (user_id,)
            ).fetchone()

        main_interest = top_genre["genre"] if top_genre else None

        churn_risk = "high"
        if last_play and last_play["last_t"]:
            try:
                last_dt = datetime.fromisoformat(last_play["last_t"])
                days_diff = (datetime.utcnow() - last_dt).days
                if days_diff < 14:
                    churn_risk = "low"
                elif days_diff < 30:
                    churn_risk = "medium"
            except:
                pass 

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (user_id, main_interest, churn_risk_level, last_profile_update)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    main_interest = excluded.main_interest,
                    churn_risk_level = excluded.churn_risk_level,
                    last_profile_update = excluded.last_profile_update
                """,
                (user_id, main_interest, churn_risk, _utcnow())
            )

    def classify_user_segment(self, user_id: int) -> int:
        with self._conn() as conn:
            stats = conn.execute(
                "SELECT COUNT(*) as cnt, SUM(duration_sec) as dur FROM listening_logs WHERE user_id=?",
                (user_id,)
            ).fetchone()
            fb = conn.execute("SELECT AVG(rating) as r FROM feedbacks WHERE user_id=?", (user_id,)).fetchone()

            features = {
                "play_count": stats["cnt"] or 0,
                "total_duration": stats["dur"] or 0,
                "avg_rating": fb["r"] or 0
            }

        seg_name = classify_user_segment(features)
        return self._ensure_segment(seg_name, user_id)

    def _ensure_segment(self, name: str, user_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT segment_id FROM user_segments WHERE segment_name=?", (name,)).fetchone()
            if row:
                seg_id = row["segment_id"]
            else:
                cur = conn.execute("INSERT INTO user_segments (segment_name) VALUES (?)", (name,))
                seg_id = cur.lastrowid

            conn.execute(
                "INSERT INTO user_segment_membership (user_id, segment_id, assigned_at) VALUES (?, ?, ?) ON CONFLICT(user_id, segment_id) DO NOTHING",
                (user_id, seg_id, _utcnow())
            )
            return seg_id
