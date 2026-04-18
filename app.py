import os
import io
import re
from datetime import datetime, timedelta, date
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit, join_room, leave_room

from models import db, User, Photo, Journal, Letter, TimelineEvent, CareerLog, Discussion, DatePlan, Punishment, Manifestation, SongShare, Notification, MiniGame, GameSession, SurpriseEntry

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_for_us'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///us_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def before_request():
    if current_user.is_authenticated:
        if not current_user.last_active or (datetime.utcnow() - current_user.last_active) > timedelta(minutes=5):
            current_user.last_active = datetime.utcnow()
            db.session.commit()

@app.context_processor
def inject_now():
    if current_user.is_authenticated:
        unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(10).all()
        return {'current_datetime': datetime.utcnow(), 'unread_notifications_count': unread_notifications, 'notifications': notifications}
    return {'current_datetime': datetime.utcnow(), 'unread_notifications_count': 0, 'notifications': []}

def is_inactive(user):
    if not user.last_active: return False
    return datetime.utcnow() - user.last_active > timedelta(hours=24)

def notify_partner(message, link=None):
    partner = User.query.filter(User.id != current_user.id).first()
    if partner:
        notif = Notification(user_id=partner.id, message=message, link=link)
        db.session.add(notif)
        db.session.commit()

def calculate_score():
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    photos = Photo.query.filter(Photo.uploaded_at >= seven_days_ago).count()
    journals = Journal.query.filter(Journal.created_at >= seven_days_ago).count()
    letters = Letter.query.filter(Letter.created_at >= seven_days_ago).count()
    score = min(100, (photos * 10) + (journals * 10) + (letters * 20))
    if score > 0: score += 20
    return min(100, score)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    score = calculate_score()
    today = datetime.utcnow().date()
    
    today_photo = Photo.query.filter(db.func.date(Photo.uploaded_at) == today).order_by(Photo.uploaded_at.desc()).first()
    latest_letter = Letter.query.order_by(Letter.created_at.desc()).first()
    next_date = DatePlan.query.filter(DatePlan.date_time >= datetime.utcnow(), DatePlan.status == 'upcoming').order_by(DatePlan.date_time.asc()).first()
    
    partner = User.query.filter(User.id != current_user.id).first()
    partner_inactive = is_inactive(partner) if partner else False
    self_inactive = is_inactive(current_user)
    
    my_song = SongShare.query.filter_by(user_id=current_user.id).order_by(SongShare.created_at.desc()).first()
    partner_song = SongShare.query.filter_by(user_id=partner.id).order_by(SongShare.created_at.desc()).first() if partner else None
    
    return render_template('dashboard.html', score=score, today_photo=today_photo, 
                           latest_letter=latest_letter, next_date=next_date,
                           self_inactive=self_inactive, partner_inactive=partner_inactive, partner=partner,
                           my_song=my_song, partner_song=partner_song)

def extract_spotify_id(link):
    match = re.search(r'track/([a-zA-Z0-9]+)', link)
    if match: return match.group(1)
    return None

@app.route('/share_song', methods=['POST'])
@login_required
def share_song():
    link = request.form.get('spotify_link')
    mood = request.form.get('mood')
    
    track_id = extract_spotify_id(link)
    if not track_id:
        flash('Invalid Spotify link!')
        return redirect(url_for('dashboard'))
        
    embed_link = f"https://open.spotify.com/embed/track/{track_id}?utm_source=generator"
    
    song = SongShare(user_id=current_user.id, spotify_link=embed_link, mood=mood)
    db.session.add(song)
    
    event = TimelineEvent(title=f"{current_user.username} is listening to a song ({mood})", event_date=datetime.utcnow(), event_type='custom')
    db.session.add(event)
    db.session.commit()
    
    notify_partner(f"{current_user.username} is listening to a new song! 🎵", url_for('dashboard'))
    
    return redirect(url_for('dashboard'))

@app.route('/notifications/read', methods=['POST'])
@login_required
def read_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/photos', methods=['GET', 'POST'])
@login_required
def photos():
    if request.method == 'POST':
        if 'photo' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['photo']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            from PIL import Image
            img = Image.open(file)
            img.thumbnail((800, 800))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(filepath, optimize=True, quality=85)
            
            photo = Photo(user_id=current_user.id, filename=filename)
            db.session.add(photo)
            
            event = TimelineEvent(title=f"{current_user.username} uploaded a photo", event_date=datetime.utcnow(), event_type='photo')
            db.session.add(event)
            db.session.commit()
            
            notify_partner(f"{current_user.username} uploaded a new photo! 📸", url_for('photos'))
            
            return redirect(url_for('photos'))
            
    all_photos = Photo.query.order_by(Photo.uploaded_at.desc()).all()
    return render_template('photos.html', photos=all_photos)

@app.route('/journal', methods=['GET', 'POST'])
@login_required
def journal():
    if request.method == 'POST':
        content = request.form.get('content')
        mood = request.form.get('mood')
        is_shared = request.form.get('is_shared') == 'on'
        
        entry = Journal(user_id=current_user.id, content=content, mood=mood, is_shared=is_shared)
        db.session.add(entry)
        
        event = TimelineEvent(title=f"{current_user.username} wrote in journal", event_date=datetime.utcnow(), event_type='journal')
        db.session.add(event)
        db.session.commit()
        
        if is_shared:
            notify_partner(f"{current_user.username} wrote a shared journal entry! 📖", url_for('journal'))
            
        return redirect(url_for('journal'))
        
    entries = Journal.query.filter((Journal.user_id == current_user.id) | (Journal.is_shared == True)).order_by(Journal.created_at.desc()).all()
    return render_template('journal.html', entries=entries)

@app.route('/letters', methods=['GET', 'POST'])
@login_required
def letters():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        unlock_date_str = request.form.get('unlock_date')
        
        unlock_date = datetime.strptime(unlock_date_str, '%Y-%m-%d') if unlock_date_str else None
        
        letter = Letter(author_id=current_user.id, title=title, content=content, category=category, unlock_date=unlock_date)
        db.session.add(letter)
        
        event = TimelineEvent(title=f"{current_user.username} wrote a letter: {title}", event_date=datetime.utcnow(), event_type='letter')
        db.session.add(event)
        db.session.commit()
        
        notify_partner(f"{current_user.username} wrote you a letter: {title} 💌", url_for('view_letter', id=letter.id))
        
        return redirect(url_for('letters'))
        
    all_letters = Letter.query.order_by(Letter.created_at.desc()).all()
    return render_template('letters.html', letters=all_letters)

@app.route('/letter/<int:id>')
@login_required
def view_letter(id):
    letter = Letter.query.get_or_404(id)
    if letter.unlock_date and letter.unlock_date > datetime.utcnow() and letter.author_id != current_user.id:
        flash('This letter is locked until a future date!')
        return redirect(url_for('letters'))
        
    if letter.author_id != current_user.id and not letter.opened_at:
        letter.opened_at = datetime.utcnow()
        db.session.commit()
        
    return render_template('letter_read.html', letter=letter)

@app.route('/letter/<int:id>/pdf')
@login_required
def letter_pdf(id):
    letter = Letter.query.get_or_404(id)
    if letter.unlock_date and letter.unlock_date > datetime.utcnow() and letter.author_id != current_user.id:
        abort(403)
        
    content = f"Title: {letter.title}\n\n{letter.content}"
    return send_file(io.BytesIO(content.encode('utf-8')), download_name=f"{letter.title}.txt", as_attachment=True)

@app.route('/timeline')
@login_required
def timeline():
    events = TimelineEvent.query.order_by(TimelineEvent.event_date.desc()).all()
    return render_template('timeline.html', events=events)

@app.route('/career', methods=['GET', 'POST'])
@login_required
def career():
    if request.method == 'POST':
        week_start_str = request.form.get('week_start')
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date() if week_start_str else datetime.utcnow().date()
        
        log = CareerLog(
            user_id=current_user.id,
            week_start=week_start,
            goals_achieved=request.form.get('goals_achieved'),
            goals_not_achieved=request.form.get('goals_not_achieved'),
            problems_faced=request.form.get('problems_faced'),
            improvements=request.form.get('improvements')
        )
        db.session.add(log)
        db.session.commit()
        return redirect(url_for('career'))
        
    logs = CareerLog.query.order_by(CareerLog.week_start.desc()).all()
    return render_template('career.html', logs=logs)

@app.route('/discussions', methods=['GET', 'POST'])
@login_required
def discussions():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            discussion = Discussion(
                created_by_id=current_user.id,
                title=request.form.get('title'),
                description=request.form.get('description')
            )
            db.session.add(discussion)
            db.session.commit()
            notify_partner(f"{current_user.username} started a new discussion: {discussion.title} 💬", url_for('discussions'))
        elif action == 'update_status':
            disc_id = request.form.get('id')
            discussion = Discussion.query.get(disc_id)
            if discussion:
                discussion.status = request.form.get('status')
                db.session.commit()
        return redirect(url_for('discussions'))
        
    discs = Discussion.query.order_by(Discussion.created_at.desc()).all()
    return render_template('discuss.html', discussions=discs)

@app.route('/dates', methods=['GET', 'POST'])
@login_required
def dates():
    if request.method == 'POST':
        date_time_str = request.form.get('date_time')
        date_time = datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M') if date_time_str else datetime.utcnow()
        
        plan = DatePlan(
            created_by_id=current_user.id,
            title=request.form.get('title'),
            description=request.form.get('description'),
            date_time=date_time,
            date_type=request.form.get('date_type')
        )
        db.session.add(plan)
        db.session.commit()
        notify_partner(f"{current_user.username} planned a new date: {plan.title} 📅", url_for('dates'))
        return redirect(url_for('dates'))
        
    plans = DatePlan.query.order_by(DatePlan.date_time.asc()).all()
    return render_template('dates.html', plans=plans)

@app.route('/punishments', methods=['GET', 'POST'])
@login_required
def punishments():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            description = request.form.get('description')
            partner = User.query.filter(User.id != current_user.id).first()
            if partner:
                punishment = Punishment(
                    assigned_to_id=partner.id,
                    assigned_by_id=current_user.id,
                    description=description
                )
                db.session.add(punishment)
                event = TimelineEvent(title=f"{current_user.username} assigned a punishment to {partner.username}", event_date=datetime.utcnow(), event_type='custom')
                db.session.add(event)
                db.session.commit()
                notify_partner(f"You received a new punishment: {description} ⚖️", url_for('punishments'))
        elif action == 'complete':
            p_id = request.form.get('punishment_id')
            punishment = Punishment.query.get(p_id)
            if punishment and punishment.assigned_to_id == current_user.id:
                punishment.status = 'completed'
                punishment.completed_at = datetime.utcnow()
                event = TimelineEvent(title=f"{current_user.username} completed a punishment!", event_date=datetime.utcnow(), event_type='custom')
                db.session.add(event)
                db.session.commit()
                notify_partner(f"{current_user.username} completed a punishment! ✅", url_for('punishments'))
        return redirect(url_for('punishments'))
        
    partner = User.query.filter(User.id != current_user.id).first()
    my_punishments = Punishment.query.filter_by(assigned_to_id=current_user.id).order_by(Punishment.created_at.desc()).all()
    partner_punishments = Punishment.query.filter_by(assigned_to_id=partner.id).order_by(Punishment.created_at.desc()).all() if partner else []
    
    # Superpower Level: based on how long partner has been inactive
    superpower_level = 0
    inactivity_hours = 0
    if partner and partner.last_active:
        hours_inactive = (datetime.utcnow() - partner.last_active).total_seconds() / 3600
        inactivity_hours = round(hours_inactive, 1)
        if hours_inactive >= 72:
            superpower_level = 3
        elif hours_inactive >= 48:
            superpower_level = 2
        elif hours_inactive >= 24:
            superpower_level = 1
    
    # If I am the inactive one, flip perspective
    self_inactive_hours = 0
    self_superpower_level = 0
    if current_user.last_active:
        self_hours = (datetime.utcnow() - current_user.last_active).total_seconds() / 3600
        self_inactive_hours = round(self_hours, 1)
        if self_hours >= 72:
            self_superpower_level = 3
        elif self_hours >= 48:
            self_superpower_level = 2
        elif self_hours >= 24:
            self_superpower_level = 1
    
    return render_template('punishments.html',
        my_punishments=my_punishments,
        partner_punishments=partner_punishments,
        superpower_level=superpower_level,
        inactivity_hours=inactivity_hours,
        self_superpower_level=self_superpower_level,
        partner=partner
    )

@app.route('/universe')
@login_required
def universe():
    """The shared Universe — each memory is a cosmic body."""
    # Collect all memories as cosmic bodies
    journals = Journal.query.order_by(Journal.created_at.asc()).all()
    photos = Photo.query.order_by(Photo.uploaded_at.asc()).all()
    letters = Letter.query.order_by(Letter.created_at.asc()).all()
    events = TimelineEvent.query.order_by(TimelineEvent.event_date.asc()).all()
    manifestations = Manifestation.query.filter_by(status='manifested').order_by(Manifestation.manifested_at.asc()).all()

    # Build unified memory list for the canvas
    cosmic_bodies = []
    for j in journals:
        cosmic_bodies.append({'type': 'journal', 'title': j.content[:40] + '...' if len(j.content) > 40 else j.content, 'date': j.created_at.strftime('%b %d, %Y'), 'user': j.user.username, 'color': '#7ed6df', 'size': 'star'})
    for p in photos:
        cosmic_bodies.append({'type': 'photo', 'title': f'Photo by {p.user.username}', 'date': p.uploaded_at.strftime('%b %d, %Y'), 'user': p.user.username, 'img': p.filename, 'color': '#f9ca24', 'size': 'planet'})
    for l in letters:
        cosmic_bodies.append({'type': 'letter', 'title': l.title, 'date': l.created_at.strftime('%b %d, %Y'), 'user': l.author.username, 'color': '#ff9ff3', 'size': 'star'})
    for e in events:
        cosmic_bodies.append({'type': 'event', 'title': e.title, 'date': e.event_date.strftime('%b %d, %Y'), 'user': 'Us', 'color': '#ffeaa7', 'size': 'comet'})
    for m in manifestations:
        cosmic_bodies.append({'type': 'manifestation', 'title': m.title, 'date': m.manifested_at.strftime('%b %d, %Y') if m.manifested_at else '', 'user': m.user.username, 'color': '#a29bfe', 'size': 'nebula'})

    total = len(cosmic_bodies)
    # Universe Level (1–10 scale)
    if total >= 100: universe_level = 10
    elif total >= 70: universe_level = 9
    elif total >= 50: universe_level = 8
    elif total >= 35: universe_level = 7
    elif total >= 25: universe_level = 6
    elif total >= 15: universe_level = 5
    elif total >= 10: universe_level = 4
    elif total >= 5:  universe_level = 3
    elif total >= 2:  universe_level = 2
    else:             universe_level = 1

    universe_names = {1: 'Stardust', 2: 'Nebula', 3: 'Young Star', 4: 'Solar System', 5: 'Star Cluster',
                      6: 'Galaxy Arm', 7: 'Spiral Galaxy', 8: 'Galaxy Cluster', 9: 'Supercluster', 10: 'Observable Universe'}
    
    import json
    return render_template('universe.html',
        cosmic_bodies=cosmic_bodies,
        cosmic_bodies_json=json.dumps(cosmic_bodies),
        universe_level=universe_level,
        universe_name=universe_names[universe_level],
        total_memories=total
    )

@app.route('/manifestations', methods=['GET', 'POST'])
@login_required
def manifestations():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            manifestation = Manifestation(
                user_id=current_user.id,
                title=request.form.get('title'),
                description=request.form.get('description')
            )
            db.session.add(manifestation)
            event = TimelineEvent(title=f"{current_user.username} added a new manifestation: {manifestation.title}", event_date=datetime.utcnow(), event_type='custom')
            db.session.add(event)
            db.session.commit()
            notify_partner(f"{current_user.username} added a new wish: {manifestation.title} 🌟", url_for('manifestations'))
        elif action == 'manifested':
            m_id = request.form.get('manifestation_id')
            manifestation = Manifestation.query.get(m_id)
            if manifestation:
                manifestation.status = 'manifested'
                manifestation.manifested_at = datetime.utcnow()
                event = TimelineEvent(title=f"A manifestation came true: {manifestation.title} ✨", event_date=datetime.utcnow(), event_type='custom')
                db.session.add(event)
                db.session.commit()
                notify_partner(f"A wish came true: {manifestation.title}! ✨", url_for('manifestations'))
        return redirect(url_for('manifestations'))
        
    wishing = Manifestation.query.filter_by(status='wishing').order_by(Manifestation.created_at.desc()).all()
    manifested = Manifestation.query.filter_by(status='manifested').order_by(Manifestation.manifested_at.desc()).all()
    
    return render_template('manifestations.html', wishing=wishing, manifested=manifested)
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        current_user.is_online = True
        db.session.commit()
        emit('presence_update', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        current_user.is_online = False
        db.session.commit()
        emit('presence_update', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

@socketio.on('heartbeat_sync')
def handle_heartbeat_sync():
    if current_user.is_authenticated:
        # Broadcast heartbeat to everyone
        emit('partner_heartbeat', {'user_id': current_user.id}, broadcast=True, include_self=False)

@socketio.on('interaction')
def handle_interaction(data):
    if current_user.is_authenticated:
        current_user.interaction_score = (current_user.interaction_score or 0) + 1
        db.session.commit()
        # Broadcast interaction to update the shared universe evolution
        emit('universe_evolution', {'user_id': current_user.id, 'score': current_user.interaction_score, 'type': data.get('type', 'tap')}, broadcast=True)

@socketio.on('update_mood')
def handle_update_mood(data):
    if current_user.is_authenticated:
        current_user.current_mood = data.get('mood')
        db.session.commit()
        
        # Determine partner's mood
        partner = User.query.filter(User.id != current_user.id).first()
        partner_mood = partner.current_mood if partner else None
        
        emit('mood_sync', {
            'user_id': current_user.id,
            'my_mood': current_user.current_mood,
            'partner_mood': partner_mood
        }, broadcast=True)

# ─── Games: Start a game session ────────────────────────────────
@app.route('/games', methods=['GET'])
@login_required
def games():
    partner = User.query.filter(User.id != current_user.id).first()
    sessions = GameSession.query.filter(
        db.or_(GameSession.user1_id == current_user.id, GameSession.user2_id == current_user.id)
    ).order_by(GameSession.created_at.desc()).all()
    # Pending: sessions where I still need to answer
    pending = [s for s in sessions if s.user2_id == current_user.id and not s.user2_answer]
    return render_template('games.html', sessions=sessions, pending=pending, partner=partner)

@app.route('/games/play', methods=['POST'])
@login_required
def play_game():
    """Create a new game session with a question."""
    partner = User.query.filter(User.id != current_user.id).first()
    game_type = request.form.get('game_type', 'this_or_that')
    question = request.form.get('question')
    option_a = request.form.get('option_a', '')
    option_b = request.form.get('option_b', '')
    my_answer = request.form.get('my_answer', '')

    session = GameSession(
        game_type=game_type,
        question=question,
        option_a=option_a,
        option_b=option_b,
        user1_id=current_user.id,
        user1_answer=my_answer,
        user1_answered_at=datetime.utcnow(),
        user2_id=partner.id if partner else None,
        status='waiting'
    )
    db.session.add(session)
    db.session.commit()
    if partner:
        notify_partner(f"🎮 {current_user.username} asked you: \"{question}\"", url_for('games'))
    return redirect(url_for('games'))

@app.route('/games/answer/<int:session_id>', methods=['POST'])
@login_required
def answer_game(session_id):
    """Partner submits their answer."""
    session = GameSession.query.get_or_404(session_id)
    if session.user2_id != current_user.id:
        abort(403)
    session.user2_answer = request.form.get('answer', '')
    session.user2_answered_at = datetime.utcnow()
    session.status = 'completed'
    db.session.commit()
    notify_partner(f"🎮 {current_user.username} answered your game question!", url_for('games'))
    return redirect(url_for('games'))

# ─── Surprises: Save and complete ───────────────────────────────
@app.route('/surprises', methods=['GET'])
@login_required
def surprises():
    my_surprises = SurpriseEntry.query.filter_by(user_id=current_user.id).order_by(SurpriseEntry.created_at.desc()).all()
    return render_template('surprises.html', surprises=my_surprises)

@app.route('/surprises/save', methods=['POST'])
@login_required
def save_surprise():
    task_text = request.form.get('task_text', '')
    if task_text:
        entry = SurpriseEntry(user_id=current_user.id, task_text=task_text)
        db.session.add(entry)
        db.session.commit()
    return jsonify({'status': 'ok', 'id': entry.id if task_text else None})

@app.route('/surprises/complete/<int:entry_id>', methods=['POST'])
@login_required
def complete_surprise(entry_id):
    entry = SurpriseEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        abort(403)
    entry.completed = True
    entry.completed_at = datetime.utcnow()
    entry.response = request.form.get('response', '')
    db.session.commit()
    notify_partner(f"✨ {current_user.username} completed a surprise task: {entry.task_text[:50]}", url_for('surprises'))
    return redirect(url_for('surprises'))

# ─── Full Data Export ────────────────────────────────────────────
@app.route('/export')
@login_required
def export_universe():
    """Show the dramatic export page."""
    partner = User.query.filter(User.id != current_user.id).first()
    stats = {
        'journals': Journal.query.count(),
        'letters': Letter.query.count(),
        'photos': Photo.query.count(),
        'timeline': TimelineEvent.query.count(),
        'games': GameSession.query.count(),
        'surprises': SurpriseEntry.query.count(),
        'manifestations': Manifestation.query.count(),
    }
    return render_template('export.html', stats=stats, partner=partner)

@app.route('/export/download')
@login_required
def download_export():
    """Generate and download a full ZIP of all relationship data."""
    import json, zipfile, io, os
    
    partner = User.query.filter(User.id != current_user.id).first()
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Journals
        journals = Journal.query.order_by(Journal.created_at.asc()).all()
        journals_data = [{'id': j.id, 'author': j.user.username, 'content': j.content, 'mood': j.mood, 'date': j.created_at.isoformat()} for j in journals]
        zf.writestr('journals.json', json.dumps(journals_data, indent=2, ensure_ascii=False))

        # Letters
        letters = Letter.query.order_by(Letter.created_at.asc()).all()
        letters_data = [{'id': l.id, 'title': l.title, 'content': l.content, 'author': l.author.username, 'category': l.category, 'date': l.created_at.isoformat(), 'unlock_date': l.unlock_date.isoformat() if l.unlock_date else None} for l in letters]
        zf.writestr('letters.json', json.dumps(letters_data, indent=2, ensure_ascii=False))

        # Timeline
        events = TimelineEvent.query.order_by(TimelineEvent.event_date.asc()).all()
        events_data = [{'id': e.id, 'title': e.title, 'description': e.description, 'type': e.event_type, 'date': e.event_date.isoformat()} for e in events]
        zf.writestr('timeline.json', json.dumps(events_data, indent=2, ensure_ascii=False))

        # Game History
        games = GameSession.query.order_by(GameSession.created_at.asc()).all()
        games_data = []
        for g in games:
            games_data.append({
                'id': g.id, 'type': g.game_type, 'question': g.question,
                'option_a': g.option_a, 'option_b': g.option_b,
                'player1': g.user1.username if g.user1 else '', 'player1_answer': g.user1_answer, 'player1_answered_at': g.user1_answered_at.isoformat() if g.user1_answered_at else None,
                'player2': g.user2.username if g.user2 else '', 'player2_answer': g.user2_answer, 'player2_answered_at': g.user2_answered_at.isoformat() if g.user2_answered_at else None,
                'status': g.status, 'date': g.created_at.isoformat()
            })
        zf.writestr('game_history.json', json.dumps(games_data, indent=2, ensure_ascii=False))

        # Surprises
        all_surprises = SurpriseEntry.query.order_by(SurpriseEntry.created_at.asc()).all()
        surprises_data = [{'id': s.id, 'user': s.user.username, 'task': s.task_text, 'response': s.response, 'completed': s.completed, 'completed_at': s.completed_at.isoformat() if s.completed_at else None, 'date': s.created_at.isoformat()} for s in all_surprises]
        zf.writestr('surprises.json', json.dumps(surprises_data, indent=2, ensure_ascii=False))

        # Manifestations
        manifs = Manifestation.query.order_by(Manifestation.created_at.asc()).all()
        manifs_data = [{'id': m.id, 'title': m.title, 'description': m.description, 'status': m.status, 'date': m.created_at.isoformat(), 'manifested_at': m.manifested_at.isoformat() if m.manifested_at else None} for m in manifs]
        zf.writestr('manifestations.json', json.dumps(manifs_data, indent=2, ensure_ascii=False))

        # Photos (copy actual files)
        photos = Photo.query.all()
        photos_meta = []
        upload_dir = app.config['UPLOAD_FOLDER']
        for p in photos:
            fpath = os.path.join(upload_dir, p.filename)
            if os.path.exists(fpath):
                zf.write(fpath, f'photos/{p.filename}')
            photos_meta.append({'id': p.id, 'filename': p.filename, 'uploader': p.user.username, 'caption': p.caption, 'date': p.uploaded_at.isoformat()})
        zf.writestr('photos.json', json.dumps(photos_meta, indent=2, ensure_ascii=False))

        # Generate beautiful HTML story
        u1 = current_user.username
        u2 = partner.username if partner else 'Partner'
        html_story = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Our Story — {u1} & {u2}</title>
<style>
    body {{ background: #0B0C10; color: white; font-family: 'Georgia', serif; max-width: 900px; margin: 0 auto; padding: 3rem 2rem; }}
    h1 {{ background: linear-gradient(135deg, #FF9A9E, #F2C94C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 3rem; text-align: center; margin-bottom: 0.5rem; }}
    .subtitle {{ text-align: center; color: rgba(255,255,255,0.5); margin-bottom: 4rem; }}
    h2 {{ color: #FF9A9E; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.5rem; margin: 3rem 0 1.5rem; }}
    .item {{ background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }}
    .meta {{ color: rgba(255,255,255,0.4); font-size: 0.85rem; margin-top: 0.5rem; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 3rem; justify-content: center; }}
    .stat {{ background: rgba(255,154,158,0.1); border: 1px solid rgba(255,154,158,0.3); border-radius: 12px; padding: 1rem 2rem; text-align: center; }}
    .stat-num {{ font-size: 2rem; font-weight: bold; color: #F2C94C; }}
    .stat-label {{ color: rgba(255,255,255,0.5); font-size: 0.85rem; }}
</style>
</head>
<body>
    <h1>Our Private Universe</h1>
    <p class="subtitle">{u1} & {u2} · Exported {datetime.utcnow().strftime('%B %d, %Y')}</p>
    <div class="stats">
        <div class="stat"><div class="stat-num">{len(journals_data)}</div><div class="stat-label">Journals</div></div>
        <div class="stat"><div class="stat-num">{len(letters_data)}</div><div class="stat-label">Letters</div></div>
        <div class="stat"><div class="stat-num">{len(photos_meta)}</div><div class="stat-label">Photos</div></div>
        <div class="stat"><div class="stat-num">{len(games_data)}</div><div class="stat-label">Games</div></div>
        <div class="stat"><div class="stat-num">{len(surprises_data)}</div><div class="stat-label">Surprises</div></div>
    </div>
    <h2>📓 Journals</h2>
    {''.join(f'<div class="item"><p>{j["content"]}</p><p class="meta">{j["author"]} · {j["date"][:10]}</p></div>' for j in journals_data)}
    <h2>💌 Letters</h2>
    {''.join(f'<div class="item"><h3>{l["title"]}</h3><p>{l["content"]}</p><p class="meta">{l["author"]} · {l["date"][:10]}</p></div>' for l in letters_data)}
    <h2>🎮 Game History</h2>
    {''.join(f'<div class="item"><p><strong>{g["question"]}</strong></p><p>{g["player1"]}: {g.get("player1_answer","—")} · {g["player2"]}: {g.get("player2_answer","—")}</p><p class="meta">{g["date"][:10]}</p></div>' for g in games_data)}
    <h2>⭐ Timeline</h2>
    {''.join(f'<div class="item"><p><strong>{e["title"]}</strong></p><p class="meta">{e["date"][:10]}</p></div>' for e in events_data)}
</body>
</html>"""
        zf.writestr('our_story.html', html_story)

    zip_buffer.seek(0)
    filename = f'private_universe_{datetime.utcnow().strftime("%Y%m%d")}.zip'
    return send_file(zip_buffer, download_name=filename, as_attachment=True, mimetype='application/zip')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
