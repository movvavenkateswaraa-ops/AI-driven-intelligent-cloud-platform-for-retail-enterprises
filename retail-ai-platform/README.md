# AI-Driven Intelligent Cloud Platform for Retail Enterprises

A compact, runnable base project that shows how AI services can sit on top of retail data and be
deployed to the cloud as a container. It ships with a synthetic 12-month dataset, so it works immediately.

## What it does

| Capability | Technique | Endpoint |
|---|---|---|
| Sales forecasting | Ridge regression (trend + weekday + season) with hold-out accuracy | `GET /api/forecast?days=14` |
| Inventory optimisation | Exponentially weighted demand, days-of-cover vs supplier lead time | `GET /api/inventory?status=critical` |
| Customer segmentation | RFM features + K-Means | `GET /api/segments` |
| Product recommendations | Item-based collaborative filtering (cosine similarity) | `GET /api/recommendations/product/<id>`, `/customer/<id>` |
| Review sentiment | Lexicon-based NLP with negation handling | `GET /api/sentiment`, `POST /api/sentiment/analyze` |
| Dashboard | Flask + Chart.js | `GET /` |

## Project structure

```
retail-ai-platform/
├── app.py              Flask app: REST API + dashboard
├── config.py           Environment-based settings
├── database.py         SQLite schema and query helper
├── seed_data.py        Synthetic data generator
├── ai/                 forecasting, inventory, segmentation, recommender, sentiment
├── templates/ static/  Dashboard UI
├── tests/              API and model tests (pytest)
├── Dockerfile, docker-compose.yml
└── requirements.txt
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                                        # http://localhost:5000
pytest -q                                            # run tests
```

The database is created and seeded on first start. Delete `data/retail.db` to regenerate.

## Run with Docker

```bash
docker compose up --build        # http://localhost:8080
```

## Deploy to the cloud

The container listens on `$PORT` and exposes `/health`, so it runs on most managed container services:

- **Google Cloud Run:** `gcloud run deploy retail-ai --source . --region asia-south1 --allow-unauthenticated`
- **AWS App Runner / ECS Fargate:** push the image to ECR and point the service at port 8080 with `/health` as the health check.
- **Azure Container Apps:** `az containerapp up --name retail-ai --source .`

Cloud containers have ephemeral disks, so for a real deployment move data to a managed database
(Cloud SQL, RDS or Azure Database for PostgreSQL) by replacing the connection in `database.py`.

## Plug in real data

Load your own rows into the five tables in `database.py` (`products`, `customers`, `orders`,
`order_items`, `reviews`). Every AI module reads only from those tables, so no other code changes are needed.

## Ideas to extend

- Swap the sentiment lexicon for a Hugging Face model or a cloud NLP API.
- Replace Ridge with Prophet, LightGBM or a managed forecasting service.
- Add authentication (Flask-Login or your cloud provider's IAM) and multi-store support.
- Schedule nightly model refreshes with Cloud Scheduler, EventBridge or Airflow.
