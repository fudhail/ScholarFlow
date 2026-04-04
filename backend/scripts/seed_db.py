
import sys
import os
import uuid
from datetime import datetime
import json

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.database import engine, Base, SessionLocal, Project, LibraryItem, ChatSession, ProjectPhase

def seed():
    print("🌱 Seeding database...")
    
    # 1. Reset Database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Database reset")
    
    db = SessionLocal()
    
    try:
        # 2. Create Sample Project
        project_id = str(uuid.uuid4())
        project = Project(
            id=project_id,
            title="Transformer Architecture Analysis",
            description="Deep dive into attention mechanisms and transformer variants.",
            mode="RESEARCH",
            current_phase=ProjectPhase.DISCOVERY
        )
        db.add(project)
        
        # 3. Create Sample Papers
        papers = [
            {
                "title": "Attention Is All You Need",
                "authors": ["Vaswani et al."],
                "year": 2017,
                "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
                "arxiv_id": "1706.03762",
                "url": "https://arxiv.org/abs/1706.03762"
            },
            {
                "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                "authors": ["Devlin et al."],
                "year": 2018,
                "abstract": "We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers...",
                "arxiv_id": "1810.04805",
                "url": "https://arxiv.org/abs/1810.04805"
            }
        ]
        
        for p in papers:
            item = LibraryItem(
                project_id=project_id,
                title=p["title"],
                authors=p["authors"],
                year=p["year"],
                abstract=p["abstract"],
                arxiv_id=p["arxiv_id"],
                url=p["url"],
                is_selected_for_context=True
            )
            db.add(item)
            
        # 4. Create Sample Chat Sessions
        session1 = ChatSession(
            project_id=project_id,
            title="Initial Exploration",
            messages=[
                {"role": "user", "content": "What is the core idea of the Transformer?", "timestamp": str(datetime.now())},
                {"role": "assistant", "content": "The core idea is the self-attention mechanism...", "timestamp": str(datetime.now())}
            ]
        )
        db.add(session1)
        
        session2 = ChatSession(
            project_id=project_id,
            title="BERT Analysis",
            messages=[
                {"role": "user", "content": "How does BERT differ from GPT?", "timestamp": str(datetime.now())},
                {"role": "assistant", "content": "BERT is bidirectional while GPT is unidirectional...", "timestamp": str(datetime.now())}
            ]
        )
        db.add(session2)
        
        db.commit()
        print(f"✅ Seeding complete! Created Project: {project.title} ({project_id})")
        
    except Exception as e:
        print(f"❌ Error seeding DB: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
