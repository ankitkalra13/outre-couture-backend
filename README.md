# Outre Couture Backend API

A Flask-based REST API for Outre Couture's admin panel and website, featuring product management, category management, and RFQ (Request for Quote) handling with email notifications.

## Features

- **Product Management**: CRUD operations for products with category-based organization
- **Category Management**: Create and manage product categories
- **RFQ System**: Handle customer quote requests with automatic email notifications
- **Email Integration**: Automated email notifications for RFQ submissions
- **MongoDB Integration**: NoSQL database for flexible data storage
- **RESTful APIs**: Clean and consistent API endpoints

## Prerequisites

- Python 3.8+
- MongoDB (local or cloud instance)
- Gmail account for email notifications (or other SMTP provider)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp env.example .env
   ```
   
   Edit `.env` file with your configuration:
   - MongoDB connection string
   - Email credentials
   - Admin email address

5. **Start MongoDB** (if using local instance)
   ```bash
   mongod
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

The API will be available at `http://localhost:5000`

## API Endpoints

### Health Check
- `GET /api/health` - Check API and database status

### Categories
- `GET /api/categories` - Get all categories
- `POST /api/categories` - Create a new category

### Products
- `GET /api/products` - Get all products (with filters)
- `GET /api/products/<product_id>` - Get specific product
- `POST /api/products` - Create a new product (Admin)
- `PUT /api/products/<product_id>` - Update a product (Admin)
- `DELETE /api/products/<product_id>` - Delete a product (Admin)

### RFQ (Request for Quote)
- `POST /api/rfq` - Submit RFQ form
- `GET /api/rfq` - Get all RFQ requests (Admin)
- `PUT /api/rfq/<rfq_id>` - Update RFQ status (Admin)

## API Usage Examples

### Create a Category
```bash
curl -X POST http://localhost:5000/api/categories \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Fashion Accessories",
    "description": "Stylish fashion accessories and jewelry"
  }'
```

### Create a Product
```bash
curl -X POST http://localhost:5000/api/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Designer Handbag",
    "category_id": "category-uuid-here",
    "price": 299.99,
    "description": "Luxury designer handbag made from premium leather",
    "images": ["image1.jpg", "image2.jpg"],
    "specifications": {
      "material": "Genuine Leather",
      "color": "Brown",
      "size": "Medium"
    }
  }'
```

### Submit RFQ
```bash
curl -X POST http://localhost:5000/api/rfq \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890",
    "company": "Fashion Store Inc",
    "requirements": "Custom designed handbags for our boutique",
    "product_category": "Handbags",
    "quantity": "100 pieces",
    "budget": "$50,000",
    "timeline": "3 months"
  }'
```

### Get Products with Filters
```bash
curl "http://localhost:5000/api/products?category_id=category-uuid&limit=10&skip=0"
```

## Database Schema

### Categories Collection
```json
{
  "id": "uuid-string",
  "name": "Category Name",
  "description": "Category description",
  "created_at": "2024-01-01T00:00:00.000Z"
}
```

### Products Collection
```json
{
  "id": "uuid-string",
  "name": "Product Name",
  "category_id": "category-uuid",
  "category_name": "Category Name",
  "price": 299.99,
  "description": "Product description",
  "images": ["image1.jpg", "image2.jpg"],
  "specifications": {
    "material": "Leather",
    "color": "Brown"
  },
  "is_active": true,
  "created_at": "2024-01-01T00:00:00.000Z",
  "updated_at": "2024-01-01T00:00:00.000Z"
}
```

### RFQ Collection
```json
{
  "id": "uuid-string",
  "name": "Customer Name",
  "email": "customer@example.com",
  "phone": "+1234567890",
  "company": "Company Name",
  "requirements": "Detailed requirements",
  "additional_info": "Additional information",
  "product_category": "Category",
  "quantity": "100 pieces",
  "budget": "$50,000",
  "timeline": "3 months",
  "status": "new",
  "created_at": "2024-01-01T00:00:00.000Z"
}
```

## Email Configuration

The system sends two types of emails:

1. **Admin Notification**: When a new RFQ is submitted
2. **Customer Confirmation**: Confirmation email to the customer

### Gmail Setup
1. Enable 2-factor authentication on your Gmail account
2. Generate an App Password
3. Use the App Password in your `.env` file

### Other SMTP Providers
Update the `MAIL_SERVER` and `MAIL_PORT` in your `.env` file according to your provider's settings.

## Error Handling

All API endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error message description"
}
```

## Security Considerations

- Implement authentication/authorization for admin endpoints
- Use HTTPS in production
- Validate and sanitize all input data
- Use environment variables for sensitive configuration
- Implement rate limiting for public endpoints

## Development

### Running in Development Mode
```bash
export FLASK_ENV=development
export FLASK_DEBUG=True
python app.py
```

### Testing
```bash
# Test health endpoint
curl http://localhost:5000/api/health

# Test database connection
curl http://localhost:5000/api/categories
```

## Production Deployment

1. Set `FLASK_ENV=production`
2. Use a production WSGI server (Gunicorn, uWSGI)
3. Set up proper MongoDB authentication
4. Configure HTTPS
5. Set up monitoring and logging
6. Implement proper backup strategies

## Support

For issues and questions, please contact the development team.
