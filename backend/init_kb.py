import sys
sys.path.insert(0, '.')
from app.services.knowledge_base import knowledge_base_service

articles = knowledge_base_service.initialize_default_knowledge()
print(f'Initialized {len(articles)} default articles')
for a in articles:
    print(f'  - {a["title"]} ({a["category"]})')  