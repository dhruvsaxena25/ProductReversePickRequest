# 📦 Barcode Scanner & Warehouse Pick System

A production-grade FastAPI application for warehouse picking operations with real-time barcode scanning.

## ✨ Features

- **🔍 Real-time Barcode Scanning** - WebSocket-based camera scanning with instant detection
- **🎯 Wildcard UPC Matching** - Match long barcodes with shorter product UPCs
- **📋 Pick Request Management** - Full lifecycle management for picking tasks
- **🔐 Role-Based Access Control** - Admin, Requester, and Picker roles
- **⚡ Auto-Increment Picking** - Scan-to-count for small quantities
- **🟢 Visual Feedback** - Green/Red indicators for valid/invalid scans
- **📝 Completion Logs** - Detailed log files for audit trails
- **🧹 Background Cleanup** - Automatic cleanup of old requests

## 🏗️ Architecture

```
app/
├── api/v1/           # REST API endpoints
├── catalog/          # Product catalog management
├── config/           # Application configuration
├── core/             # Auth, exceptions, dependencies
├── db/               # Database models & connection
├── scanner/          # Barcode scanning engine
├── schemas/          # Pydantic request/response models
├── services/         # Business logic layer
├── utils/            # Utility classes
├── websockets/       # Real-time WebSocket handlers
└── main.py           # Application entry point
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd barcode-scanner

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run the server
uvicorn app.main:app --reload
```

### First Login

```
Username: admin
Password: admin123
```

⚠️ **Security**: Change the default admin password immediately!

## 📖 API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

## 🔐 User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full system access, user management, cleanup operations |
| **Requester** | Create and manage pick requests |
| **Picker** | Execute picks, scan products, update quantities |

## 📋 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login and get tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user |
| PUT | `/api/v1/auth/change-password` | Change password |

### Users (Admin Only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/users` | Create user |
| GET | `/api/v1/users` | List users |
| GET | `/api/v1/users/{id}` | Get user |
| PUT | `/api/v1/users/{id}` | Update user |
| DELETE | `/api/v1/users/{id}` | Deactivate user |

### Pick Requests
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/pick-requests` | Create request |
| GET | `/api/v1/pick-requests` | List requests |
| GET | `/api/v1/pick-requests/{name}` | Get request |
| POST | `/api/v1/pick-requests/{name}/start` | Start picking |
| PUT | `/api/v1/pick-requests/{name}/items/{upc}` | Update quantity |
| POST | `/api/v1/pick-requests/{name}/submit` | Complete request |

### WebSockets
| Protocol | Endpoint | Description |
|----------|----------|-------------|
| WS | `/ws/create-request?token=...` | **Requester**: Scan products, build cart, submit pick request |
| WS | `/ws/pick/{name}?token=...` | **Picker**: Scan items with GREEN/RED feedback |
| WS | `/ws/scan?token=...` | General barcode scanner |

## 🔄 Complete Pick Request Flow

### Step 1: Requester Creates Pick Request (via scanning)

```
📱 Requester connects to /ws/create-request
        ↓
📷 Scans product barcode
        ↓
┌─────────────────┐
│ Bounding box    │ → Product looked up from catalog
│ appears         │ → Product name & info displayed
└─────────────────┘
        ↓
✏️ Enters quantity needed (e.g., "5")
        ↓
➕ Adds to cart → Repeats for more items
        ↓
📝 Enters request name (e.g., "monday-restock")
        ↓
✅ Submits → Pick request created in database
```

### Step 2: Picker Fulfills Request (in warehouse)

```
📱 Picker connects to /ws/pick/{request-name}
        ↓
📷 Scans product barcode
        ↓
┌─────────────────────────────────────┐
│ Is barcode in this pick request?   │
└─────────────────┬───────────────────┘
                  │
        ┌─────────┴─────────┐
        ↓                   ↓
   🟩 GREEN               🟥 RED
   "In Request"           "NOT in Request"
        ↓                   ↓
   ┌────┴────┐          ⚠️ Warning
   │ Qty≤10? │             shown
   └────┬────┘
   YES  │  NO
    ↓   │   ↓
  Auto  │ Manual
  +1    │ entry
        ↓
✅ When all picked → Submit → Generates log file
```

## 🎨 Visual Feedback Colors

| Color | Meaning | When Used |
|-------|---------|-----------|
| 🟩 **GREEN** | Valid - Item IS in pick request | Picker scanning |
| 🟥 **RED** | Invalid - Item NOT in request | Picker scanning |
| 🔵 **BLUE** | Product detected from catalog | Requester scanning |
| ⬜ **GRAY** | Unknown product (not in catalog) | Requester scanning |
| 🟧 **ORANGE** | Partial match (substring) | General scanning |
| 🟨 **YELLOW** | UPC-only mode detection | General scanning |

## 🎯 Picking Modes

| Condition | Mode | Behavior |
|-----------|------|----------|
| Quantity ≤ 10 | Scan-to-Count | Each scan = +1 |
| Quantity > 10 | Bulk Entry | Manual quantity input |

## 🐳 Docker

### Build and Run

```bash
cd docker
docker-compose up -d
```

### Development Mode

```bash
docker-compose --profile dev up app-dev
```

## 🧪 Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## ⚙️ Configuration

Key environment variables (see `.env.example` for all options):

```env
# Application
APP_NAME=Barcode Scanner API
APP_ENV=development
DEBUG=true

# JWT
JWT_SECRET_KEY=change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Pick System
PICK_TIMEOUT_MINUTES=30
AUTO_MODE_THRESHOLD=10

# Database
DATABASE_URL=sqlite:///./storage/db/warehouse.db
```

## 📁 Project Structure

```
barcode-scanner/
├── app/                    # Application code
│   ├── api/                # REST endpoints
│   ├── catalog/            # Product catalog
│   ├── config/             # Configuration
│   ├── core/               # Core utilities
│   ├── db/                 # Database
│   ├── scanner/            # Barcode scanner
│   ├── schemas/            # Pydantic models
│   ├── services/           # Business logic
│   ├── utils/              # Utilities
│   ├── websockets/         # WebSocket handlers
│   └── main.py             # Entry point
├── data/
│   └── products.json       # Product catalog
├── storage/
│   ├── db/                 # SQLite database
│   └── logs/               # Pick completion logs
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── tests/
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## 🔧 Request Name Rules

- Length: 3-50 characters
- Allowed: letters, numbers, underscore, hyphen
- Must start with a letter
- No spaces
- Case-insensitive (stored as lowercase)

**Valid examples:**
- `monday-restock`
- `urgent_order_15`
- `biscuits-jan-2025`

## 📄 License

MIT License

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request
