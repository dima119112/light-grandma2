# Коли буде світло? — група 4.1

Статичний сайт. GitHub Actions раз на 15 хвилин читає графік підчерги 4.1 на сайті Житомиробленерго і записує `schedule.json`. GitHub Pages лише віддає сторінку.

## Як увімкнути
1. Репозиторій має бути публічним.
2. Settings → Actions → General → Workflow permissions → **Read and write permissions**.
3. Settings → Pages → Build and deployment → Deploy from a branch → `main` → `/ (root)` → Save.
4. Actions → Update schedule → Run workflow. Перший графік з’явиться після цього запуску, далі сам кожні 15 хвилин.

Сайт не засинає: Pages працює постійно. Свіжість даних — це розклад Actions, а не окремий сервер.

## Локальна перевірка
```bash
pip install -r requirements.txt
python scripts/update_schedule.py
python -m http.server 8080