"""Reset database by dropping and recreating all tables"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.database import Base, engine, Project, ProjectPhase, SessionLocal

def reset_db():
    """Drop and recreate all tables"""
    print("🗑️ Dropping all existing tables...")
    Base.metadata.drop_all(bind=engine)
    print("✅ All tables dropped.")
    
    print("🔨 Creating new tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully with fresh schema.")
    
    # Initialize Discovery Project (Permanent Context)
    db = SessionLocal()
    try:
        discovery_project = Project(
            id="00000000-0000-0000-0000-000000000000",
            title="Discovery",
            description="Global research context for papers and chat history.",
            mode="RESEARCH",
            current_phase=ProjectPhase.DISCOVERY
        )
        db.add(discovery_project)
        db.commit()
        print("✅ Discovery project initialized")
    except Exception as e:
        print(f"⚠️ Discovery project already exists or error: {e}")
    finally:
        db.close()
    
    # Verify the schema by inspecting columns
    from sqlalchemy import inspect
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('projects')]
    
    if 'current_phase' in columns and 'phase_history' in columns:
        print("✅ VERIFIED: projects table has 'current_phase' and 'phase_history' columns.")
    else:
        print("❌ ERROR: projects table is still missing columns!")
        print(f"Current columns: {columns}")

if __name__ == "__main__":
    reset_db()
