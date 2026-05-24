# 📦 Inventory Management App

Full-stack inventory management with receipt OCR and vendor SKU lookup.

## Architecture

```
inventory-app/
├── backend/
│   ├── models/          # SQLAlchemy ORM models
│   ├── services/        # Business logic
│   ├── api/             # FastAPI route handlers
│   ├── vendors/         # Vendor adapters (Home Depot, etc.)
│   └── utils/           # OCR, helpers
├── frontend/
│   └── src/
│       ├── components/  # Reusable React components
│       ├── pages/       # Route pages
│       └── services/    # API client
└── tests/
```

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env   # Add your API keys
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Features
- ✅ Full CRUD inventory management
- 📷 Receipt image upload + OCR parsing
- 🏪 Home Depot SKU lookup via API
- 📊 Low stock alerts and reports
- 🔌 Extensible vendor adapter pattern
