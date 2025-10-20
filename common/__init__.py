# Общие утилиты
# ├─ common/                   # общие утилиты/базовые абстракции
# │  ├─ __init__.py
# │  ├─ db.py                  # atomic helpers, on_commit, select_for_update
# │  ├─ caching.py             # Redis-кеш, TTL-профили
# │  ├─ security.py            # шифрование секретов, PII-редакция
# │  ├─ errors.py
# │  ├─ enums.py
# │  ├─ typing.py
# │  └─ outbox.py