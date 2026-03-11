from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from datetime import datetime
import joblib

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key-change-this')
DB = 'games.db'

try:
    stacking_model = joblib.load('model/model.pkl')
except FileNotFoundError:
    stacking_model = None

def init_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                score INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT
            )
        ''')
        conn.commit()

def get_user_id(username):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username=?', (username,))
        user = c.fetchone()
    return user[0] if user else None

def calculate_level(total_score):
    if total_score >= 40:
        return "Advanced", "Level 3 (requiring very substantial support)", "At this advanced level, continue challenging your memory with complex tasks. Consult a healthcare professional for personalized cognitive therapy. Regular practice can help maintain and improve cognitive functions."
    elif total_score >= 20:
        return "Intermediate", "Level 2 (requiring substantial support)", "You're progressing well! Focus on intermediate tasks to build memory strength. Consider incorporating daily brain exercises and discuss with a doctor for ongoing support strategies."
    else:
        return "Beginner", "Level 1 (requiring support)", "Start with basic memory tasks to establish a foundation. Seek guidance from a medical professional for tailored advice on cognitive health and potential underlying conditions."

def get_level_number(total_score):
    if total_score >= 40:
        return 3
    elif total_score >= 20:
        return 2
    else:
        return 1

def predict_asd_score(game_scores):
    game_to_a_mapping = {
        'Arcade Catch 3D': 'A1',
        'Balloon Pop Mania': 'A2',
        'Color Match Reflex': 'A3',
        'Easy Puzzle': 'A4',
        'Memory Lights': 'A5',
        'Memory Match Pro': 'A6',
        'Reflex Challenge': 'A7',
        'Stack Tower': 'A8',
        'Target Hunt': 'A9'
    }
    a1_to_a9 = [0]*9
    for game_name, entries in game_scores.items():
        if game_name in game_to_a_mapping:
            idx = int(game_to_a_mapping[game_name][1:]) - 1
            max_score = max([entry['score'] for entry in entries]) if entries else 0
            a1_to_a9[idx] = 1 if max_score > 0 else 0
    input_data = pd.DataFrame([a1_to_a9], columns=[f'A{i}' for i in range(1,10)])
    if stacking_model:
        predicted_score = stacking_model.predict(input_data)[0]
        return round(predicted_score, 1)
    return None

def generate_medical_report(predicted_score, game_scores):
    current_date = datetime.now().strftime('%Y-%m-%d')
    if predicted_score is None:
        return "Model not available. Please check model loading."
    if predicted_score <= 3:
        interpretation = "Low likelihood of ASD traits."
    elif 4 <= predicted_score <= 6:
        interpretation = "Moderate likelihood; further evaluation recommended."
    else:
        interpretation = "High likelihood of ASD traits; consult a specialist for comprehensive assessment."
    input_summary = ""
    game_to_a_mapping = {
        'Arcade Catch 3D': 'A1',
        'Balloon Pop Mania': 'A2',
        'Color Match Reflex': 'A3',
        'Easy Puzzle': 'A4',
        'Memory Lights': 'A5',
        'Memory Match Pro': 'A6',
        'Reflex Challenge': 'A7',
        'Stack Tower': 'A8',
        'Target Hunt': 'A9'
    }
    for game_name, a_label in game_to_a_mapping.items():
        max_score = max([entry['score'] for entry in game_scores.get(game_name, [])]) if game_scores.get(game_name) else 0
        binary_value = 1 if max_score > 0 else 0
        input_summary += f"- {a_label} ({game_name}): {binary_value}\n"
    report = f"""
**Medical Prediction Report: ASD Traits Assessment**

**Patient ID:** [Auto-Generated: ASD-Report-{session.get('user', 'Unknown')}]
**Date of Assessment:** {current_date}
**Assessment Tool:** QCHAT-10 Score Prediction Model
**Model Used:** Stacking Hybrid Ensemble (R² = 0.944)
**Data Source:** Trained on ASD Dataset (Features: A1-A9 from Game Scores)

**Input Game Scores (Mapped to A1-A9):**
{input_summary}
**Predicted QCHAT-10 Score:** {predicted_score} (Out of 10)
**Interpretation:** {interpretation}
**Confidence Level:** High (Based on model R² of 0.944).

**Recommendations:**
- Schedule a follow-up with a pediatrician or developmental specialist.
- Consider early intervention if ASD traits are confirmed.
"""
    return report

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        flash("Please fill all fields", "error")
        return redirect(url_for('index'))
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT password FROM users WHERE username=?', (username,))
        user = c.fetchone()
    if user and check_password_hash(user[0], password):
        session['user'] = username
        flash(f"Welcome, {username}!", "success")
        return redirect(url_for('home'))
    else:
        flash("Invalid credentials", "error")
        return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash("Please fill all fields", "error")
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password)
        try:
            with sqlite3.connect(DB) as conn:
                c = conn.cursor()
                c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_pw))
                conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash("Username already exists!", "error")
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/home')
def home():
    if 'user' not in session:
        flash("Please login first", "error")
        return redirect(url_for('index'))
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out successfully", "success")
    return redirect(url_for('index'))

@app.route('/game/<game_id>')
def game(game_id):
    if 'user' not in session:
        flash("Please login first", "error")
        return redirect(url_for('index'))
    valid_games = ['1','2','3','4','5','6','7','8','9']
    if game_id not in valid_games:
        flash("Game not found", "error")
        return redirect(url_for('home'))
    return render_template(f'{game_id}.html')

@app.route('/task')
def task():
    if 'user' not in session:
        flash("Please login first", "error")
        return redirect(url_for('index'))
    user_id = get_user_id(session['user'])
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT SUM(score) FROM scores WHERE user_id=?', (user_id,))
        total = c.fetchone()[0] or 0
    level_num = get_level_number(total)
    return render_template(f't{level_num}.html')

@app.route('/submit_score', methods=['POST'])
def submit_score():
    if 'user' not in session:
        flash("Please login first", "error")
        return redirect(url_for('home'))
    game = request.form.get('game')
    score_str = request.form.get('score')
    if not game or not score_str:
        flash("Invalid score submission!", "error")
        return redirect(url_for('home'))
    try:
        score = int(score_str)
        if score < 0:
            raise ValueError
    except ValueError:
        flash("Score must be a positive number!", "error")
        return redirect(url_for('home'))
    user_id = get_user_id(session['user'])
    if not user_id:
        flash("User error", "error")
        return redirect(url_for('home'))
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('INSERT INTO scores (user_id, game, score) VALUES (?, ?, ?)', (user_id, game, score))
        conn.commit()
    flash(f"Score submitted for {game}: {score}", "success")
    return redirect(url_for('home'))

@app.route('/scores')
def scores():
    if 'user' not in session:
        flash("Please login first", "error")
        return redirect(url_for('index'))
    user_id = get_user_id(session['user'])
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT game, score, timestamp FROM scores WHERE user_id=? ORDER BY timestamp DESC', (user_id,))
        personal_scores = c.fetchall()
        c.execute('''
            SELECT users.username, scores.game, scores.score, scores.timestamp
            FROM scores
            JOIN users ON scores.user_id = users.id
            ORDER BY scores.score DESC
            LIMIT 10
        ''')
        global_scores = c.fetchall()
    return render_template('scores.html', personal_scores=personal_scores, global_scores=global_scores)

@app.route('/report')
def report():
    if 'user' not in session:
        flash("Please login first", "error")
        return render_template('login.html')
    return render_template('report.html')

@app.route('/report_data')
def report_data():
    if 'user' not in session:
        return jsonify({"error": "Please login first"})
    user_id = get_user_id(session['user'])
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT game, score, timestamp FROM scores WHERE user_id=? ORDER BY game', (user_id,))
        scores = c.fetchall()
    game_scores = {}
    for game, score, ts in scores:
        if game not in game_scores:
            game_scores[game] = []
        game_scores[game].append({'score': score, 'timestamp': ts})
    total_score = sum([entry['score'] for entries in game_scores.values() for entry in entries])
    num_entries = sum([len(entries) for entries in game_scores.values()])
    average_score = total_score / num_entries if num_entries else 0
    level, medical_note, _ = calculate_level(total_score)
    asd_predicted_score = predict_asd_score(game_scores)
    medical_report = generate_medical_report(asd_predicted_score, game_scores)
    return jsonify({
        "game_scores": game_scores,
        "total_score": total_score,
        "average_score": average_score,
        "level": level,
        "medical_note": medical_note,
        "asd_predicted_score": asd_predicted_score,
        "medical_report": medical_report
    })

@app.route('/levels')
def levels():
    if 'user' not in session:
        flash("Please login first", "error")
        return redirect(url_for('index'))
    user_id = get_user_id(session['user'])
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT SUM(score) FROM scores WHERE user_id=?', (user_id,))
        total = c.fetchone()[0] or 0
    level, medical_note, medical_advice = calculate_level(total)
    return render_template('levels.html', total_score=total, level=level, medical_note=medical_note, medical_advice=medical_advice)

# Teacher Routes
@app.route('/teacher/register', methods=['GET', 'POST'])
def teacher_register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email', '')
        if not username or not password:
            flash("Please fill all required fields", "error")
            return redirect(url_for('teacher_register'))
        hashed_pw = generate_password_hash(password)
        try:
            with sqlite3.connect(DB) as conn:
                c = conn.cursor()
                c.execute('INSERT INTO teachers (username, password, email) VALUES (?, ?, ?)', (username, hashed_pw, email))
                conn.commit()
            flash("Teacher registration successful! Please login.", "success")
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash("Username already exists!", "error")
            return redirect(url_for('teacher_register'))
    return render_template('teacher_register.html')

@app.route('/teacher/login', methods=['POST'])
def teacher_login():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        flash("Please fill all fields", "error")
        return redirect(url_for('index'))
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT password FROM teachers WHERE username=?', (username,))
        teacher = c.fetchone()
    if teacher and check_password_hash(teacher[0], password):
        session['teacher'] = username
        flash(f"Welcome, Teacher {username}!", "success")
        return redirect(url_for('teacher_dashboard'))
    else:
        flash("Invalid teacher credentials", "error")
        return redirect(url_for('index'))

@app.route('/teacher/dashboard')
def teacher_dashboard():
    if 'teacher' not in session:
        flash("Please login as a teacher first", "error")
        return redirect(url_for('index'))
    
    # Get all students and their data
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        # Get all students with their total scores
        c.execute('''
            SELECT 
                users.id,
                users.username,
                COALESCE(SUM(scores.score), 0) as total_score,
                COUNT(DISTINCT scores.game) as games_played,
                MAX(scores.timestamp) as last_activity
            FROM users
            LEFT JOIN scores ON users.id = scores.user_id
            GROUP BY users.id, users.username
            ORDER BY total_score DESC
        ''')
        students_data = []
        for row in c.fetchall():
            student_id, username, total_score, games_played, last_activity = row
            level, medical_note, _ = calculate_level(total_score)
            level_num = get_level_number(total_score)
            students_data.append({
                'id': student_id,
                'username': username,
                'total_score': total_score,
                'games_played': games_played,
                'level': level,
                'level_num': level_num,
                'medical_note': medical_note,
                'last_activity': last_activity
            })
    
    return render_template('teacher_dashboard.html', students=students_data, teacher=session['teacher'])

@app.route('/teacher/student/<int:student_id>')
def teacher_view_student(student_id):
    if 'teacher' not in session:
        flash("Please login as a teacher first", "error")
        return redirect(url_for('index'))
    
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        # Get student info
        c.execute('SELECT username FROM users WHERE id=?', (student_id,))
        student = c.fetchone()
        if not student:
            flash("Student not found", "error")
            return redirect(url_for('teacher_dashboard'))
        
        # Get student scores
        c.execute('SELECT game, score, timestamp FROM scores WHERE user_id=? ORDER BY timestamp DESC', (student_id,))
        scores = c.fetchall()
        
        # Get total score
        c.execute('SELECT SUM(score) FROM scores WHERE user_id=?', (student_id,))
        total = c.fetchone()[0] or 0
    
    level, medical_note, medical_advice = calculate_level(total)
    
    # Organize scores by game
    game_scores = {}
    for game, score, ts in scores:
        if game not in game_scores:
            game_scores[game] = []
        game_scores[game].append({'score': score, 'timestamp': ts})
    
    return render_template('teacher_student_detail.html', 
                         student_name=student[0],
                         student_id=student_id,
                         game_scores=game_scores,
                         total_score=total,
                         level=level,
                         medical_note=medical_note,
                         medical_advice=medical_advice,
                         teacher=session['teacher'])

@app.route('/teacher/logout')
def teacher_logout():
    session.pop('teacher', None)
    flash("Teacher logged out successfully", "success")
    return redirect(url_for('index'))

# Chatbot API endpoint
@app.route('/chatbot', methods=['POST'])
def chatbot():
    if 'user' not in session and 'teacher' not in session:
        return jsonify({"error": "Please login first"}), 401
    
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Message is required"}), 400
    
    # Simple rule-based chatbot responses
    response = get_chatbot_response(user_message, 'teacher' in session)
    
    return jsonify({"response": response})

# Specialized Chatbot API endpoint
@app.route('/chatbot_specialized', methods=['POST'])
def chatbot_specialized():
    if 'user' not in session and 'teacher' not in session:
        return jsonify({"error": "Please login first"}), 401
    
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Message is required"}), 400
    
    if 'teacher' in session:
        # Teacher mode: Get student details by username or ID
        response = get_student_details_response(user_message)
    else:
        # Student mode: Analyze level and recommend games
        response = get_game_recommendation_response()
    
    return jsonify({"response": response})

def get_student_details_response(query):
    query = query.strip()
    
    # Try to find student by username or ID
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        
        # Try as username first
        c.execute('SELECT id, username FROM users WHERE username LIKE ?', (f'%{query}%',))
        students = c.fetchall()
        
        # If no results and query is numeric, try as ID
        if not students and query.isdigit():
            c.execute('SELECT id, username FROM users WHERE id=?', (int(query),))
            students = c.fetchall()
        
        if not students:
            return f"No student found matching '{query}'. Please provide a valid student username or ID."
        
        if len(students) > 1:
            result = "Multiple students found:\n\n"
            for student_id, username in students:
                c.execute('SELECT SUM(score) FROM scores WHERE user_id=?', (student_id,))
                total = c.fetchone()[0] or 0
                level_num = get_level_number(total)
                result += f"• ID: {student_id}, Username: {username}, Total Score: {total}, Level: {level_num}\n"
            result += "\nPlease specify the exact username or ID."
            return result
        
        # Single student found
        student_id, username = students[0]
        
        # Get detailed information
        c.execute('SELECT game, score, timestamp FROM scores WHERE user_id=? ORDER BY timestamp DESC', (student_id,))
        scores = c.fetchall()
        
        c.execute('SELECT SUM(score) FROM scores WHERE user_id=?', (student_id,))
        total_score = c.fetchone()[0] or 0
        
        level, medical_note, _ = calculate_level(total_score)
        level_num = get_level_number(total_score)
        
        # Count games played
        c.execute('SELECT COUNT(DISTINCT game) FROM scores WHERE user_id=?', (student_id,))
        games_played = c.fetchone()[0] or 0
        
        # Get last activity
        c.execute('SELECT MAX(timestamp) FROM scores WHERE user_id=?', (student_id,))
        last_activity = c.fetchone()[0] or "No activity"
        
        # Organize scores by game
        game_scores = {}
        for game, score, ts in scores:
            if game not in game_scores:
                game_scores[game] = []
            game_scores[game].append(score)
        
        # Calculate average
        avg_score = total_score / len(scores) if scores else 0
        
        response = f"**Student Details:**\n\n"
        response += f"• Username: {username}\n"
        response += f"• Student ID: {student_id}\n"
        response += f"• Total Score: {total_score}\n"
        response += f"• Average Score: {avg_score:.1f}\n"
        response += f"• Level: {level_num} - {level}\n"
        response += f"• Games Played: {games_played}\n"
        response += f"• Medical Note: {medical_note}\n"
        response += f"• Last Activity: {last_activity[:10] if last_activity != 'No activity' else 'No activity'}\n\n"
        
        if game_scores:
            response += "**Game Performance:**\n"
            for game, scores_list in game_scores.items():
                max_score = max(scores_list)
                avg_game_score = sum(scores_list) / len(scores_list)
                response += f"• {game}: Best {max_score}, Avg {avg_game_score:.1f} ({len(scores_list)} plays)\n"
        
        return response

def get_game_recommendation_response():
    if 'user' not in session:
        return "Please login first."
    
    user_id = get_user_id(session['user'])
    
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        
        # Get user's total score
        c.execute('SELECT SUM(score) FROM scores WHERE user_id=?', (user_id,))
        total_score = c.fetchone()[0] or 0
        
        # Get games played
        c.execute('SELECT DISTINCT game FROM scores WHERE user_id=?', (user_id,))
        played_games = [row[0] for row in c.fetchall()]
        
        # Get game performance
        c.execute('SELECT game, MAX(score) as max_score FROM scores WHERE user_id=? GROUP BY game', (user_id,))
        game_performance = {row[0]: row[1] for row in c.fetchall()}
    
    level_num = get_level_number(total_score)
    level, medical_note, advice = calculate_level(total_score)
    
    # All available games
    all_games = [
        'Memory Lights',
        'Arcade Catch 3D',
        'Color Tap Frenzy',
        'Stack Tower',
        'Puzzle Slider Extreme',
        'Balloon Pop Mania',
        'Memory Match Pro',
        'Reflex Challenge',
        'Target Hunt'
    ]
    
    # Find unplayed games
    unplayed_games = [g for g in all_games if g not in played_games]
    
    # Find games with low scores (for improvement)
    low_performance_games = [(g, s) for g, s in game_performance.items() if s < 5]
    
    response = f"**Your Performance Analysis:**\n\n"
    response += f"• Current Level: Level {level_num} - {level}\n"
    response += f"• Total Score: {total_score}\n"
    response += f"• Games Played: {len(played_games)}/{len(all_games)}\n\n"
    
    response += f"**Recommendations:**\n\n"
    
    if level_num == 1:
        response += "You're at Beginner level. Focus on building foundational skills:\n"
        if 'Memory Lights' not in played_games:
            response += "• Try 'Memory Lights' - Great for memory training\n"
        if 'Balloon Pop Mania' not in played_games:
            response += "• Try 'Balloon Pop Mania' - Improves hand-eye coordination\n"
        if low_performance_games:
            response += f"• Practice '{low_performance_games[0][0]}' more to improve your score\n"
    elif level_num == 2:
        response += "You're at Intermediate level. Challenge yourself with:\n"
        if 'Stack Tower' not in played_games:
            response += "• Try 'Stack Tower' - Tests precision and planning\n"
        if 'Reflex Challenge' not in played_games:
            response += "• Try 'Reflex Challenge' - Enhances reaction time\n"
        if unplayed_games:
            response += f"• Explore new games like '{unplayed_games[0]}' to gain more points\n"
    else:
        response += "Excellent! You're at Advanced level. Maintain your skills:\n"
        if 'Target Hunt' not in played_games:
            response += "• Try 'Target Hunt' - Advanced focus and precision\n"
        if 'Memory Match Pro' not in played_games:
            response += "• Try 'Memory Match Pro' - Complex memory patterns\n"
        response += "• Keep practicing to maintain cognitive sharpness\n"
    
    if unplayed_games:
        response += f"\n**Unplayed Games ({len(unplayed_games)}):** "
        response += ", ".join(unplayed_games[:3])
        if len(unplayed_games) > 3:
            response += f" and {len(unplayed_games) - 3} more"
    
    response += f"\n\n{advice}"
    
    return response

def get_chatbot_response(message, is_teacher=False):
    message_lower = message.lower()
    
    # Context-aware responses
    if is_teacher:
        # Teacher-specific responses
        if any(word in message_lower for word in ['student', 'students', 'learner']):
            return "You can view all your students' progress on the dashboard. Click on 'View Details' to see individual student performance, game scores, and ASD assessment reports."
        elif any(word in message_lower for word in ['score', 'scores', 'performance']):
            return "Student scores are tracked for each game. The total score determines their level (Beginner, Intermediate, or Advanced). You can view detailed score breakdowns in each student's detail page."
        elif any(word in message_lower for word in ['level', 'levels', 'progress']):
            return "Students progress through 3 levels: Level 1 (Beginner, 0-19 points), Level 2 (Intermediate, 20-39 points), and Level 3 (Advanced, 40+ points). Each level provides different cognitive tasks."
        elif any(word in message_lower for word in ['asd', 'autism', 'assessment', 'report']):
            return "Our system uses a machine learning model to predict ASD traits based on game performance. The QCHAT-10 score prediction has an R² of 0.944. You can view detailed medical reports for each student."
        elif any(word in message_lower for word in ['game', 'games', 'activity']):
            return "Students can play 9 different cognitive games: Memory Lights, Arcade Catch 3D, Color Tap Frenzy, Stack Tower, Puzzle Slider Extreme, Balloon Pop Mania, and more. Each game assesses different cognitive skills."
    else:
        # Student-specific responses
        if any(word in message_lower for word in ['game', 'games', 'play']):
            return "You can play various cognitive games from the home page. Each game is designed to assess and improve different cognitive skills. Try different games to increase your score!"
        elif any(word in message_lower for word in ['score', 'scores', 'points']):
            return "Your score is calculated based on your performance in all games. Higher scores unlock advanced levels. You can check your detailed scores and progress in the Report section."
        elif any(word in message_lower for word in ['level', 'levels']):
            return "There are 3 levels: Beginner (0-19 points), Intermediate (20-39 points), and Advanced (40+ points). Play more games to increase your score and unlock higher levels with more challenging tasks!"
        elif any(word in message_lower for word in ['report', 'progress', 'assessment']):
            return "You can view your detailed progress report which includes game scores, total performance, level assessment, and a medical prediction report. Click on 'Report' in the navigation menu."
        elif any(word in message_lower for word in ['help', 'how']):
            return "I can help you understand how to play games, check your scores, and track your progress. Just ask me about games, scores, levels, or reports!"
    
    # General responses
    if any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
        return "Hello! I'm your AI assistant. How can I help you today?"
    elif any(word in message_lower for word in ['thank', 'thanks']):
        return "You're welcome! Feel free to ask if you need any more help."
    elif any(word in message_lower for word in ['bye', 'goodbye']):
        return "Goodbye! Have a great day!"
    else:
        if is_teacher:
            return "I can help you with student management, score tracking, level assessments, and ASD reports. What would you like to know?"
        else:
            return "I can help you with games, scores, levels, and progress reports. What would you like to know?"

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
