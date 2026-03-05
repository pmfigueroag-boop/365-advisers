"""
alembic.ini placeholder — Alembic migration system setup.
─────────────────────────────────────────────────────────────────────────────
Fixes audit finding #13 — database schema evolution.

To initialize Alembic, run:
    pip install alembic
    alembic init alembic

To create a migration after model changes:
    alembic revision --autogenerate -m "description"

To apply migrations:
    alembic upgrade head

Current tables managed by SQLAlchemy ORM (database.py):
  - fundamental_analyses
  - technical_analyses  
  - score_history
  - opportunity_score_history
  - portfolios
  - portfolio_positions

NOTE: For now, init_db() uses create_all() which only creates
      missing tables. It does NOT modify existing columns.
      Once Alembic is initialized, replace create_all() with 
      alembic upgrade head in the lifespan function.
"""
