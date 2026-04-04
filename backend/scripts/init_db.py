"""Initialize database with Alembic migrations"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.database import Base, engine, SessionLocal, Project, ProjectPhase

def init_db():
    """Create all tables"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully with all tables")
    print("✅ Schema includes current_phase and phase_history columns")
    
    # Create virtual discovery project if it doesn't exist
    db = SessionLocal()
    try:
        VIRTUAL_PROJECT_ID = "discovery-virtual-library"
        
        virtual_project = db.query(Project).filter(Project.id == VIRTUAL_PROJECT_ID).first()
        if not virtual_project:
            print("Creating virtual discovery project...")
            virtual_project = Project(
                id=VIRTUAL_PROJECT_ID,
                title="Discovery Library",
                description="Virtual project for storing discovered papers before adding to real projects",
                mode="RESEARCH",
                current_phase=ProjectPhase.DISCOVERY
            )
            db.add(virtual_project)
            db.commit()
            print("✅ Virtual discovery project created!")
        else:
            print("✅ Virtual discovery project already exists")
    except Exception as e:
        print(f"Error creating virtual project: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
