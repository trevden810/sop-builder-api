# SOP Builder MVP - Backend API

Professional SOP generation API server with AI integration and regulatory compliance.

## 🚀 Features

- ✅ **REST API** for SOP template management
- ✅ **AI-powered generation** using OpenRouter + DeepSeek V3
- ✅ **Regulatory compliance** (FDA, HIPAA, OSHA standards)
- ✅ **PDF generation** with professional formatting
- ✅ **Brand customization** support
- ✅ **Real-time progress** tracking

## 🌐 API Endpoints

### Health Check
```
GET /api/health
```

### Templates
```
GET /api/v1/templates
GET /api/v1/templates/{template_id}
```

### Generation
```
POST /api/v1/generate
GET /api/v1/generate/{generation_id}/status
```

### Documents
```
POST /api/v1/documents/preview
```

## 🔧 Environment Variables

Required environment variables:

```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here
PORT=8000
```

## 🚀 Deployment

### Railway Deployment
1. Connect this repository to Railway
2. Set environment variables in Railway dashboard
3. Railway will automatically detect Python and deploy

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENROUTER_API_KEY=your_key_here

# Run server
python api/simple_server.py
```

## 📋 API Documentation

Once deployed, visit `/docs` for interactive API documentation.

## 🔒 Security

- CORS configured for production domains
- Environment variables for sensitive data
- Input validation on all endpoints

## 📞 Support

For issues or questions, contact support through the main application.

---

**Part of the SOP Builder MVP - Professional SOP Generation Platform**
