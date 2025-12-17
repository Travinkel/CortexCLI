
from sqlalchemy import create_engine, inspect

from config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

inspector = inspect(engine)
tables = inspector.get_table_names()

for table in tables:
    print(table)
