from app import app
from models import db, User

def init_db():
    with app.app_context():
        db.create_all()

        # Check if users already exist
        if User.query.count() == 0:
            user1 = User(username='user1')
            user1.set_password('pass1')
            user2 = User(username='user2')
            user2.set_password('pass2')

            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()
            print("Database initialized and users 'user1', 'user2' created.")
        else:
            print("Database already initialized.")

if __name__ == '__main__':
    init_db()
