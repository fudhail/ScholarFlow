"""Seed database with mock project for demo"""

from app.models.database import SessionLocal, Project, LibraryItem, LabAsset, ProjectPhase
from datetime import datetime
import uuid

def seed_demo_project():
    """Create a demo project with sample data"""
    db = SessionLocal()
    
    try:
        # Check if demo project already exists
        existing = db.query(Project).filter(Project.title.like("%Demo%")).first()
        if existing:
            print("✅ Demo project already exists")
            return
        
        # Create demo project
        project_id = str(uuid.uuid4())
        demo_project = Project(
            id=project_id,
            title="AI Research Literature Review (Demo)",
            description="A demonstration project showcasing ScholarFlow's capabilities for conducting AI research literature reviews.",
            mode="RESEARCH",
            current_phase=ProjectPhase.ANALYSIS,
            methodology="Systematic review of recent transformer-based models for NLP tasks",
            findings="Initial analysis shows promising results in few-shot learning scenarios",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(demo_project)
        
        # Add mock library items (papers)
        papers = [
            LibraryItem(
                id=str(uuid.uuid4()),
                project_id=project_id,
                title="Attention Is All You Need",
                authors=["Vaswani et al."],
                year=2017,
                abstract="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
                is_selected_for_context=True,
                relevance_score=0.95,
                arxiv_id="1706.03762",
                chunk_count=24
            ),
            LibraryItem(
                id=str(uuid.uuid4()),
                project_id=project_id,
                title="BERT: Pre-training of Deep Bidirectional Transformers",
                authors=["Devlin et al."],
                year=2019,
                abstract="We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers...",
                is_selected_for_context=True,
                relevance_score=0.92,
                arxiv_id="1810.04805",
                chunk_count=31
            ),
            LibraryItem(
                id=str(uuid.uuid4()),
                project_id=project_id,
                title="Language Models are Few-Shot Learners (GPT-3)",
                authors=["Brown et al."],
                year=2020,
                abstract="Recent work has demonstrated substantial gains on many NLP tasks and benchmarks by pre-training on a large corpus of text...",
                is_selected_for_context=False,
                relevance_score=0.88,
                arxiv_id="2005.14165",
                chunk_count=42
            )
        ]
        
        for paper in papers:
            db.add(paper)
        
        # Add mock lab asset
        lab_asset = LabAsset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            name="Transformer Architecture Diagram",
            asset_type="image",
            file_path="demo/transformer_architecture.png",
            ai_description="A detailed architectural diagram showing the encoder-decoder structure of the Transformer model with multi-head attention mechanisms, positional encoding, and feed-forward layers. The diagram illustrates the data flow from input embeddings through multiple encoder layers to the decoder, highlighting the self-attention and cross-attention components.",
            mime_type="image/png",
            file_size=245678
        )
        
        db.add(lab_asset)
        
        # Commit all changes
        db.commit()
        print(f"✅ Successfully created demo project: {project_id}")
        print(f"   - Added {len(papers)} papers to library")
        print(f"   - Added 1 lab asset")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_project()
