# SovWare Support Manager

A Python web application for managing Help Scout support tickets with AI-powered evaluation using OpenAI.

## Features

- **AI-Powered Evaluation**: Automatically evaluate agent replies using OpenAI GPT models
- **Help Scout Integration**: Seamlessly fetch conversation and thread data from Help Scout API
- **PostgreSQL Database**: Store evaluation results with full conversation context
- **FastAPI Framework**: Modern, async-first API with automatic OpenAPI documentation
- **Comprehensive Error Handling**: Robust error handling for API failures and edge cases

## Tech Stack

- **Framework**: FastAPI 0.104.1
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async)
- **AI Integration**: OpenAI API
- **HTTP Client**: httpx (async)
- **Environment Management**: python-dotenv

## Prerequisites

- Python 3.8+
- PostgreSQL database
- Help Scout API key
- OpenAI API key

## Installation

1. **Clone the repository** (if applicable) or navigate to the project directory:
   ```bash
   cd sovware-support-manager
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and fill in your credentials:
   ```env
   HELPSCOUT_APP_ID=your_helpscout_app_id
   HELPSCOUT_APP_SECRET=your_helpscout_app_secret
   OPENAI_API_KEY=your_actual_openai_api_key
   DATABASE_URL=postgresql://user:password@localhost:5432/sovware_support
   ```
   
   **Note:** The Help Scout service uses OAuth2 client credentials flow. The access token is automatically obtained and cached.

5. **Create the database**:
   ```bash
   createdb sovware_support  # Using PostgreSQL command
   ```

6. **Run database migrations** (if using Alembic):
   ```bash
   alembic upgrade head
   ```
   
   Or the tables will be created automatically on first run.

## Running the Application

Start the development server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use Python directly:

```bash
python -m app.main
```

The API will be available at:
- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## API Endpoints

### POST /reply/agent

Evaluate an agent's reply in a Help Scout conversation.

**Request Body:**
```json
{
  "conversation_id": "123",
  "thread_id": "456"
}
```

**Response:**
```json
{
  "conversation_id": "123",
  "thread_id": "456",
  "evaluation_message": "The agent provided a clear and helpful response...",
  "score": 8.5,
  "evaluated_at": "2024-01-01T12:00:00Z",
  "evaluation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/reply/agent" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "123",
    "thread_id": "456"
  }'
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "sovware-support-manager"
}
```

## Database Schema

### Evaluations Table

- `id` (UUID, Primary Key)
- `conversation_id` (String, Indexed)
- `thread_id` (String, Indexed)
- `conversation_data` (JSON) - Raw Help Scout data
- `evaluation_message` (Text) - AI-generated evaluation
- `score` (Float) - Score from 0.0 to 10.0
- `created_at` (DateTime)
- `updated_at` (DateTime)

## Project Structure

```
sovware-support-manager/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── database.py          # Database setup
│   ├── models/
│   │   ├── __init__.py
│   │   └── evaluation.py    # Evaluation model
│   ├── routes/
│   │   ├── __init__.py
│   │   └── reply.py         # API routes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── helpscout.py     # Help Scout API service
│   │   └── openai_service.py # OpenAI service
│   └── schemas/
│       ├── __init__.py
│       └── evaluation.py    # Pydantic schemas
├── .env.example
├── requirements.txt
└── README.md
```

## Security Considerations

1. **API Keys**: Never commit `.env` file to version control. Use `.env.example` as a template.
2. **CORS**: In production, update CORS settings in `app/main.py` to restrict allowed origins.
3. **Database**: Use strong passwords and secure database connections (SSL/TLS in production).
4. **Rate Limiting**: Consider implementing rate limiting for production use.
5. **Authentication**: Add authentication/authorization middleware for production deployment.

## Development

### Running Tests

(Add test instructions when tests are implemented)

### Code Style

The project follows PEP 8 style guidelines. Consider using:
- `black` for code formatting
- `flake8` or `pylint` for linting
- `mypy` for type checking

## Future Enhancements

- Webhook receiver endpoint for real-time Help Scout events
- Bulk evaluation endpoint
- Historical evaluation retrieval
- Analytics dashboard endpoints
- User authentication and authorization
- Rate limiting
- Caching layer for API responses

## Troubleshooting

### Database Connection Issues

- Ensure PostgreSQL is running
- Verify `DATABASE_URL` in `.env` is correct
- Check database permissions

### Help Scout API Issues

- Verify `HELPSCOUT_API_KEY` is valid
- Check API rate limits
- Ensure conversation_id and thread_id exist

### OpenAI API Issues

- Verify `OPENAI_API_KEY` is valid
- Check API quota and billing
- Ensure model name is correct

## License

(Add license information)

## Support

(Add support contact information)

