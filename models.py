from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    is_online = db.Column(db.Boolean, default=False)
    current_mood = db.Column(db.String(50), nullable=True)
    interaction_score = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('photos', lazy=True))

class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(10), nullable=True) # Emoji
    is_shared = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('journals', lazy=True))

class Letter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False) # open_when, normal, future
    unlock_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    opened_at = db.Column(db.DateTime, nullable=True)
    reaction = db.Column(db.String(10), nullable=True)
    author = db.relationship('User', backref=db.backref('letters', lazy=True))

class TimelineEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.DateTime, nullable=False)
    event_type = db.Column(db.String(50), nullable=False) # photo, journal, letter, custom
    reference_id = db.Column(db.Integer, nullable=True)

class CareerLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)
    goals_achieved = db.Column(db.Text, nullable=True)
    goals_not_achieved = db.Column(db.Text, nullable=True)
    problems_faced = db.Column(db.Text, nullable=True)
    improvements = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('career_logs', lazy=True))

class Discussion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='pending') # pending, discussed, resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', backref=db.backref('discussions', lazy=True))

class DatePlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date_time = db.Column(db.DateTime, nullable=False)
    date_type = db.Column(db.String(50), nullable=False) # online, offline, surprise
    status = db.Column(db.String(50), default='upcoming') # upcoming, past, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', backref=db.backref('date_plans', lazy=True))

class Punishment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # None = System
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending') # pending, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref=db.backref('punishments_received', lazy=True))
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id], backref=db.backref('punishments_given', lazy=True))

class Manifestation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='wishing') # wishing, manifested
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    manifested_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref=db.backref('manifestations', lazy=True))

class SongShare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spotify_link = db.Column(db.String(500), nullable=False)
    mood = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('song_shares', lazy=True))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('notifications', lazy=True))

class MiniGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_type = db.Column(db.String(50), nullable=False) # quiz, this_or_that
    question = db.Column(db.String(255), nullable=False)
    option_a = db.Column(db.String(100), nullable=True)
    option_b = db.Column(db.String(100), nullable=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user1_answer = db.Column(db.String(100), nullable=True)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user2_answer = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default='active') # active, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class MemoryMapPin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    photo_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', backref=db.backref('memory_pins', lazy=True))

class GameSession(db.Model):
    """Stores every game question played + both partners' answers."""
    id = db.Column(db.Integer, primary_key=True)
    game_type = db.Column(db.String(50), nullable=False)   # this_or_that, quiz, truth, dare
    question = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(200), nullable=True)
    option_b = db.Column(db.String(200), nullable=True)
    # User 1 (who started the game)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user1_answer = db.Column(db.String(500), nullable=True)
    user1_answered_at = db.Column(db.DateTime, nullable=True)
    # User 2 (partner)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user2_answer = db.Column(db.String(500), nullable=True)
    user2_answered_at = db.Column(db.DateTime, nullable=True)
    # Status
    status = db.Column(db.String(50), default='waiting')   # waiting, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user1 = db.relationship('User', foreign_keys=[user1_id], backref=db.backref('games_started', lazy=True))
    user2 = db.relationship('User', foreign_keys=[user2_id], backref=db.backref('games_answered', lazy=True))

class SurpriseEntry(db.Model):
    """Stores every surprise drop task + response."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # who received it
    task_text = db.Column(db.String(500), nullable=False)
    response = db.Column(db.Text, nullable=True)            # optional written response
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('surprises', lazy=True))
