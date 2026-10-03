# Hop & Barley — інтернет-магазин (Django / DRF)

**Автор:** ПІБ, група · **Репозиторій:** <посилання>

Веб-магазин (сесійна автентифікація), REST API (JWT), Swagger, адмін-аналітика,
GraphQL-аналітика (бонус), PostgreSQL, Docker Compose, CI.

## Запуск (Docker)
```bash
git clone <repo> && cd myshop
cp .env.example .env                      # необов'язково
docker compose up --build
```
Перший запуск у новому клоні: якщо в репозиторії немає міграцій —
`docker compose run --rm web python manage.py makemigrations products orders` (і закомітити).

Далі:
```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo      # демо-товари
```
- Магазин: http://localhost:8000/
- Адмінка: http://localhost:8000/admin/ (аналітика — у списку замовлень)
- Swagger: http://localhost:8000/api/docs/
- GraphiQL (DEBUG): http://localhost:8000/graphql/ (потрібен вхід staff через /admin/)

Листи за замовчуванням друкуються в консоль контейнера
(`docker compose logs web`); SMTP — через змінні `EMAIL_*`.

## Ролі
`setup_roles` (виконується при старті) створює групи **Catalog managers** і
**Order managers**. Призначайте їх staff-користувачам в адмінці.
Статуси замовлень змінюються лише діями адмінки (скасування повертає товар на склад).

## API та JWT
```bash
# 1. Реєстрація
curl -X POST localhost:8000/api/users/register/ -H 'Content-Type: application/json' \
  -d '{"username":"dave","email":"dave@example.com","password":"S3cure-pass!"}'
# 2. Вхід → access (15 хв) + refresh (7 днів)
curl -X POST localhost:8000/api/users/login/ -H 'Content-Type: application/json' \
  -d '{"username":"dave","password":"S3cure-pass!"}'
# 3. Запити з токеном
TOKEN=<access>
curl localhost:8000/api/products/?q=ipa\&sort=-popularity\&min_price=50
curl -X POST localhost:8000/api/cart/ -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"product_id":1,"quantity":2}'
curl -X POST localhost:8000/api/orders/ -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"Dave D","phone":"+380501234567","email":"dave@example.com","shipping_address":"Kyiv, Khreshchatyk 1","payment_method":"card"}'
# 4. Оновлення access (refresh ротується, старий анулюється)
curl -X POST localhost:8000/api/users/token/refresh/ -H 'Content-Type: application/json' \
  -d '{"refresh":"<refresh>"}'
```
| Ресурс | URL | Методи |
|---|---|---|
| Товари | `/api/products/`, `/api/products/<id>/` | GET |
| Відгуки | `/api/products/<id>/reviews/` | GET, POST (лише після покупки) |
| Замовлення | `/api/orders/`, `/api/orders/<id>/` | POST, GET, PATCH/PUT/DELETE (скасування) |
| Кошик | `/api/cart/` (`DELETE ?product_id=`) | GET, POST, PATCH, DELETE |
| Користувачі | `/api/users/register/`, `/login/`, `/token/refresh/` | POST |

Параметри каталогу: `q`, `category` (slug, з підкатегоріями), `min_price`, `max_price`,
`sort` (`price`, `newest`, `popularity`; префікс `-` — спадання), `page`.

## GraphQL (staff)
```graphql
{ salesSummary { revenue ordersCount averageOrderValue }
  topProducts(limit: 5) { name unitsSold revenue }
  lowStock(threshold: 5) { name stock }
  revenueTrend(days: 30) { day revenue ordersCount }
  userActivity(days: 30) { usersTotal activeUsers repeatCustomers } }
```

## Тести та лінтери
```bash
docker compose run --rm web pytest --cov --cov-report=term-missing
docker compose run --rm web ruff check .
docker compose run --rm web mypy .
```
(локально потрібен PostgreSQL і змінні `DB_*`.)

## Git workflow
`main` (стабільна) ← `develop` ← `feature/catalog`, `feature/cart`, `feature/api` …
Невеликі змістовні коміти (`feat: ...`, `test: ...`, `docs: ...`).

## Чек-ліст
- [x] `docker compose up` піднімає застосунок + PostgreSQL
- [x] Каталог: фільтри, пошук, сортування, пагінація
- [x] Сторінка товару: деталі, відгуки (лише після покупки), кошик
- [x] Кошик у сесії, підсумок, перевірка залишків
- [x] Checkout: транзакція, валідація, email клієнту й адміну
- [x] Кабінет: реєстрація/вхід, історія з фільтром, профіль, зміна пароля
- [x] Адмінка: фільтри, пошук, actions, аналітика, ролі
- [x] REST API: JWT access+refresh, права доступу, Swagger
- [x] Типізація, докстрінги, ruff, mypy, pytest
- [x] Бонус: GraphQL, CI (GitHub Actions), uv/pyproject