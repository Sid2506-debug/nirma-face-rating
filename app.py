import streamlit as st
import json
import os
import random
import hashlib
from PIL import Image
from datetime import datetime, timedelta

# ----------------------------
# CONFIG
# ----------------------------
BASE_ELO = 1200
K_FACTOR = 32
MAX_VOTES_PER_HOUR = 15
MIN_MATCHES_FOR_STATS = 6

USERS_FILE = "users.json"
VOTES_FILE = "votes.json"
UPLOAD_DIR = "uploads"

st.set_page_config(page_title="Nirma Face Rating", layout="centered")

# ----------------------------
# FILE SETUP
# ----------------------------
os.makedirs(UPLOAD_DIR, exist_ok=True)

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(VOTES_FILE):
    with open(VOTES_FILE, "w") as f:
        json.dump({}, f)

# ----------------------------
# HELPERS
# ----------------------------
def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def expected_score(ra, rb):
    return 1 / (1 + 10 ** ((rb - ra) / 400))

def update_elo(ra, rb, sa):
    ea = expected_score(ra, rb)
    ra_new = ra + K_FACTOR * (sa - ea)
    rb_new = rb + K_FACTOR * ((1 - sa) - (1 - ea))
    return round(ra_new), round(rb_new)

def compute_percentiles(users_list):
    sorted_users = sorted(users_list.items(), key=lambda x: x[1]["elo"])
    N = len(sorted_users)
    percentiles = {}
    for rank, (email, data) in enumerate(sorted_users):
        percentile = (rank / (N-1) * 100) if N > 1 else 100
        percentiles[email] = percentile
    return percentiles

def percentile_description(p):
    if p < 50:
        return "Room for improvement — the good thing is, things change fast."
    elif p < 60:
        return "Above average — a solid base."
    elif p < 70:
        return "Pretty good — people definitely notice."
    elif p < 80:
        return "Strong presence — you stand out."
    elif p < 90:
        return "Excellent — well above most peers."
    else:
        return "Elite tier — very few reach here."

# ----------------------------
# LOAD DATA
# ----------------------------
users = load_json(USERS_FILE)
votes = load_json(VOTES_FILE)

# ----------------------------
# TITLE / INTRO
# ----------------------------
st.title("🎓 Nirma Face Rating")

st.markdown("""
**More real than AI face raters. More honest than golden-ratio calculators.**

This ranking is done **by real Nirma students**, not by artificial intelligence or beauty formulas.
No symmetry tricks. No fake scores. Just **human perception**.

✔ Rated by people  
✔ Compared head-to-head  
✔ Anonymous *(your name & identity are hidden)*  

Only **Nirma University students** can participate.
""")

# ----------------------------
# SESSION STATE
# ----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.email = None

# ======================================================
# REGISTER / LOGIN
# ======================================================
st.header("🔑 Register / Login")
action = st.radio("Choose:", ["Login", "Register"])
email = st.text_input("Nirma Email")
password = st.text_input("Password", type="password")

gender = None
if action == "Register":
    gender = st.radio("Select Gender:", ["Male", "Female"])

if st.button("Submit"):
    if not email.endswith("@nirmauni.ac.in"):
        st.error("Only Nirma University emails allowed.")
    else:
        if action == "Register":
            if email in users:
                st.error("Email already registered.")
            elif gender is None:
                st.error("Please select your gender.")
            else:
                users[email] = {
                    "password": hash_password(password),
                    "elo": BASE_ELO,
                    "pic": None,
                    "gender": gender,
                    "vote_times": [],
                    "matches_played": 0
                }
                save_json(USERS_FILE, users)
                st.success("Registered successfully. Please login.")
        else:
            if email not in users:
                st.error("Email not registered.")
            elif users[email]["password"] != hash_password(password):
                st.error("Incorrect password.")
            else:
                st.session_state.logged_in = True
                st.session_state.email = email
                st.rerun()

# ======================================================
# MAIN APP
# ======================================================
if st.session_state.logged_in:

    user_email = st.session_state.email
    user_gender = users[user_email]["gender"]
    st.header(f"Welcome, {user_email.split('@')[0]}")

    choice = st.selectbox(
        "Choose an action:",
        ["Vote (Left / Right)", "Upload Picture", "Stats"]
    )

    # =======================
    # VOTING
    # =======================
    if choice == "Vote (Left / Right)":

        st.markdown("""
### 🔥 This is the real comparison

No ratings. No numbers. No bias.  
Just one simple question:
""")

        now = datetime.now()
        users[user_email]["vote_times"] = [
            t for t in users[user_email]["vote_times"]
            if now - datetime.fromisoformat(t) < timedelta(hours=1)
        ]

        if len(users[user_email]["vote_times"]) >= MAX_VOTES_PER_HOUR:
            st.warning("⏳ Vote limit reached.")
        else:
            eligible = [
                u for u in users
                if users[u]["pic"] and u != user_email and users[u]["gender"] == user_gender
            ]

            if len(eligible) < 2:
                st.info("Waiting for more uploads from your gender.")
            else:
                if user_email not in votes:
                    votes[user_email] = []

                tried_pairs = votes[user_email]
                possible_pairs = []

                # Determine if similar-Elo matching is active
                uploaded_photos_count = sum(1 for u in users if users[u]["pic"])
                use_elo_matching = uploaded_photos_count >= 30

                # Build possible pairs
                for i in range(len(eligible)):
                    for j in range(i + 1, len(eligible)):
                        pair = sorted([eligible[i], eligible[j]])
                        if pair in tried_pairs:
                            continue

                        if use_elo_matching:
                            # Only allow pairs with similar Elo (+/-100)
                            elo_diff = abs(users[pair[0]]["elo"] - users[pair[1]]["elo"])
                            if elo_diff <= 100:
                                possible_pairs.append(pair)
                        else:
                            possible_pairs.append(pair)

                if not possible_pairs:
                    st.info("You have rated all available pairs.")
                else:
                    a, b = random.choice(possible_pairs)
                    col1, col2 = st.columns(2)

                    with col1:
                        st.image(Image.open(users[a]["pic"]), use_column_width=True)
                        if st.button("Left looks better"):
                            ra, rb = update_elo(users[a]["elo"], users[b]["elo"], 1)
                            users[a]["elo"], users[b]["elo"] = ra, rb
                            users[a]["matches_played"] += 1
                            users[b]["matches_played"] += 1
                            votes[user_email].append(sorted([a, b]))
                            users[user_email]["vote_times"].append(now.isoformat())
                            save_json(USERS_FILE, users)
                            save_json(VOTES_FILE, votes)
                            st.rerun()

                    with col2:
                        st.image(Image.open(users[b]["pic"]), use_column_width=True)
                        if st.button("Right looks better"):
                            ra, rb = update_elo(users[a]["elo"], users[b]["elo"], 0)
                            users[a]["elo"], users[b]["elo"] = ra, rb
                            users[a]["matches_played"] += 1
                            users[b]["matches_played"] += 1
                            votes[user_email].append(sorted([a, b]))
                            users[user_email]["vote_times"].append(now.isoformat())
                            save_json(USERS_FILE, users)
                            save_json(VOTES_FILE, votes)
                            st.rerun()

    # =======================
    # UPLOAD
    # =======================
    elif choice == "Upload Picture":
        if users[user_email]["pic"] is None:
            st.markdown("""
### 📸 Upload Your Photo

Your journey starts here.

Your face enters **real, one-to-one comparisons** with other Nirma students.
No AI, no fake scores — just **honest feedback**.

**Upload rules:**
- Only **one photo**
- Clear **full face**
- Your own photo only

📊 More votes = **more accurate stats**.  
The sooner you upload, the sooner you can see **where you stand**.
""")
            file = st.file_uploader("Upload your photo", type=["jpg", "png", "jpeg"])
            if file:
                img = Image.open(file).convert("RGB")
                path = os.path.join(UPLOAD_DIR, user_email.replace("@", "_") + ".jpg")
                img.save(path)
                users[user_email]["pic"] = path
                save_json(USERS_FILE, users)
                st.success("Photo uploaded successfully. Now you can vote and see your stats grow!")
        else:
            st.info("Photo already uploaded. Let others vote and see your percentile evolve.")

    # =======================
    # STATS
    # =======================
    elif choice == "Stats":
        if users[user_email]["pic"] is None:
            st.markdown("""
### 📊 Stats are waiting for your photo

Right now, you’re **invisible to the system**.

Upload your photo to:
- Get **ranked anonymously**  
- See your **exact percentile**
- Know how you stand **among real peers**

Your photo unlocks **real, evolving stats** as votes come in.
""")
        elif users[user_email]["matches_played"] < MIN_MATCHES_FOR_STATS:
            st.info(
                f"✨ Good start! Your photo has been rated "
                f"**{users[user_email]['matches_played']} / {MIN_MATCHES_FOR_STATS}** times.\n\n"
                "Keep going! After a few more votes, your **full stats unlock** and you see your standing clearly."
            )
        else:
            percentiles = compute_percentiles(users)
            p = percentiles[user_email]

            st.metric("Your Elo", users[user_email]["elo"])
            st.metric("Your Percentile", f"{p:.1f}")

            st.markdown(
                f"You are rated **higher than {p:.0f}%** of students of your gender at Nirma."
            )
            st.markdown(f"**Insight:** {percentile_description(p)}")
            st.markdown(
                "Every new vote can change your percentile. "
                "Come back often to see your ranking evolve!"
            )
