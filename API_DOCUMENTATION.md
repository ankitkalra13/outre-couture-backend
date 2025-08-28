# Outre Couture Backend API Documentation

## Base URL
```
http://localhost:5000/api
```

## Authentication
The API uses JWT (JSON Web Tokens) for authentication. Admin endpoints require a valid JWT token with admin role.

### Authentication Flow:
1. **Register** a new user account
2. **Login** to get a JWT token
3. Include the token in the `Authorization` header for protected endpoints: `Authorization: Bearer <token>`

### Environment Variables:
Add to your `.env` file:
```
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
JWT_EXPIRATION_HOURS=24
JWT_REFRESH_EXPIRATION_DAYS=7

# Security Configuration
BCRYPT_ROUNDS=12
PASSWORD_MIN_LENGTH=8
MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
```

### Security Features:
- **Password Hashing**: Passwords are hashed using bcrypt with configurable rounds
- **Password Validation**: Minimum length, uppercase, lowercase, and digit requirements
- **Account Lockout**: Temporary lockout after multiple failed login attempts
- **Input Sanitization**: All user inputs are sanitized to prevent injection attacks
- **Token Refresh**: Refresh tokens for secure token renewal
- **Email Validation**: Basic email format validation
- **Rate Limiting**: Login attempt tracking and account lockout

## Response Format
All API responses follow this format:
```json
{
  "success": true/false,
  "data": {...} // or "error": "error message"
}
```

---

## 1. Health Check

### GET /health
Check if the API and database are running properly.

**Response:**
```json
{
  "success": true,
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-01-01T00:00:00.000Z"
}
```

---

## 2. Authentication

### POST /auth/register
Register a new user account.

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit

**Request Body:**
```json
{
  "username": "john_doe",
  "password": "SecurePass123",
  "email": "john@example.com",
  "role": "user" // optional, defaults to "user"
}
```

**Response:**
```json
{
  "success": true,
  "message": "User registered successfully",
  "user": {
    "_id": "user_id",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "user",
    "created_at": "2024-01-01T00:00:00.000Z",
    "is_active": true
  },
  "access_token": "jwt_access_token_here",
  "refresh_token": "jwt_refresh_token_here"
}
```

### POST /auth/login
Login and get JWT token.

**Security Notes:**
- Account is locked for 15 minutes after 5 failed attempts
- Passwords are verified against bcrypt hashes

**Request Body:**
```json
{
  "username": "john_doe",
  "password": "SecurePass123"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "_id": "user_id",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "user",
    "last_login": "2024-01-01T00:00:00.000Z"
  },
  "access_token": "jwt_access_token_here",
  "refresh_token": "jwt_refresh_token_here"
}
```

**Error Responses:**
```json
{
  "success": false,
  "error": "Account temporarily locked. Try again in 10 minutes"
}
```

### GET /auth/verify
Verify JWT token and get user information.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "success": true,
  "user": {
    "user_id": "user_id",
    "username": "john_doe",
    "role": "user",
    "exp": 1640995200,
    "iat": 1640908800
  }
}
```

### POST /auth/refresh
Refresh access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "jwt_refresh_token_here"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Token refreshed successfully",
  "access_token": "new_jwt_access_token_here",
  "refresh_token": "new_jwt_refresh_token_here"
}
```

### POST /auth/logout
Logout user (client should discard tokens).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

## 3. Categories

### GET /categories
Get all product categories.

**Response:**
```json
{
  "success": true,
  "categories": [
    {
      "id": "uuid-string",
      "name": "Handbags",
      "description": "Luxury designer handbags and purses",
      "created_at": "2024-01-01T00:00:00.000Z"
    }
  ]
}
```

### POST /categories
Create a new product category. **Requires admin authentication.**

**Security Features:**
- Input sanitization to prevent injection attacks
- Category name validation (minimum 2 characters)
- Tracks which admin created the category

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "name": "New Category",
  "description": "Category description"
}
```

**Response:**
```json
{
  "success": true,
  "category": {
    "id": "uuid-string",
    "name": "New Category",
    "description": "Category description",
    "created_at": "2024-01-01T00:00:00.000Z"
  }
}
```

---

## 3. Products

### GET /products
Get all products with optional filters.

**Query Parameters:**
- `category_id` (optional): Filter by category ID
- `is_active` (optional): Filter by active status (default: true)
- `limit` (optional): Number of products to return (default: 50)
- `skip` (optional): Number of products to skip (default: 0)

**Example:**
```
GET /products?category_id=uuid&limit=10&skip=0
```

**Response:**
```json
{
  "success": true,
  "products": [
    {
      "id": "uuid-string",
      "name": "Classic Leather Tote Bag",
      "category_id": "category-uuid",
      "category_name": "Handbags",
      "price": 299.99,
      "description": "Timeless leather tote bag...",
      "images": ["image1.jpg", "image2.jpg"],
      "specifications": {
        "material": "Italian Leather",
        "color": "Cognac Brown",
        "size": "Large"
      },
      "is_active": true,
      "created_at": "2024-01-01T00:00:00.000Z",
      "updated_at": "2024-01-01T00:00:00.000Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "skip": 0
}
```

### GET /products/{product_id}
Get a specific product by ID.

**Response:**
```json
{
  "success": true,
  "product": {
    "id": "uuid-string",
    "name": "Classic Leather Tote Bag",
    "category_id": "category-uuid",
    "category_name": "Handbags",
    "price": 299.99,
    "description": "Timeless leather tote bag...",
    "images": ["image1.jpg", "image2.jpg"],
    "specifications": {
      "material": "Italian Leather",
      "color": "Cognac Brown",
      "size": "Large"
    },
    "is_active": true,
    "created_at": "2024-01-01T00:00:00.000Z",
    "updated_at": "2024-01-01T00:00:00.000Z"
  }
}
```

### POST /products
Create a new product (Admin only). **Requires admin authentication.**

**Security Features:**
- Input sanitization to prevent injection attacks
- Price validation (must be greater than 0)
- Product name validation (minimum 3 characters)
- Images array validation
- Tracks which admin created the product

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "name": "New Product",
  "category_id": "category-uuid",
  "price": 199.99,
  "description": "Product description",
  "images": ["image1.jpg", "image2.jpg"],
  "specifications": {
    "material": "Leather",
    "color": "Black",
    "size": "Medium"
  },
  "is_active": true
}
```

**Required Fields:**
- `name`: Product name
- `category_id`: Valid category ID
- `price`: Product price (number)
- `description`: Product description

**Response:**
```json
{
  "success": true,
  "product": {
    "id": "uuid-string",
    "name": "New Product",
    "category_id": "category-uuid",
    "category_name": "Category Name",
    "price": 199.99,
    "description": "Product description",
    "images": ["image1.jpg", "image2.jpg"],
    "specifications": {
      "material": "Leather",
      "color": "Black",
      "size": "Medium"
    },
    "is_active": true,
    "created_at": "2024-01-01T00:00:00.000Z",
    "updated_at": "2024-01-01T00:00:00.000Z"
  }
}
```

### PUT /products/{product_id}
Update a product (Admin only). **Requires admin authentication.**

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "name": "Updated Product Name",
  "price": 249.99,
  "description": "Updated description",
  "is_active": false
}
```

**Response:**
```json
{
  "success": true,
  "product": {
    "id": "uuid-string",
    "name": "Updated Product Name",
    "category_id": "category-uuid",
    "category_name": "Category Name",
    "price": 249.99,
    "description": "Updated description",
    "images": ["image1.jpg", "image2.jpg"],
    "specifications": {
      "material": "Leather",
      "color": "Black",
      "size": "Medium"
    },
    "is_active": false,
    "created_at": "2024-01-01T00:00:00.000Z",
    "updated_at": "2024-01-01T00:00:00.000Z"
  }
}
```

### DELETE /products/{product_id}
Delete a product (Admin only). **Requires admin authentication.**

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "success": true,
  "message": "Product deleted successfully"
}
```

---

## 4. RFQ (Request for Quote)

### POST /rfq
Submit a new RFQ request.

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "company": "Fashion Store Inc",
  "requirements": "Custom designed handbags for our boutique",
  "additional_info": "We need eco-friendly materials",
  "product_category": "Handbags",
  "quantity": "100 pieces",
  "budget": "$50,000",
  "timeline": "3 months"
}
```

**Required Fields:**
- `name`: Customer name
- `email`: Customer email
- `phone`: Customer phone number
- `company`: Company name
- `requirements`: Detailed requirements

**Response:**
```json
{
  "success": true,
  "message": "RFQ submitted successfully",
  "rfq_id": "uuid-string"
}
```

**Email Notifications:**
- Admin receives notification email with RFQ details
- Customer receives confirmation email

### GET /rfq
Get all RFQ requests (Admin only).

**Query Parameters:**
- `status` (optional): Filter by status
- `limit` (optional): Number of requests to return (default: 50)
- `skip` (optional): Number of requests to skip (default: 0)

**Response:**
```json
{
  "success": true,
  "rfq_requests": [
    {
      "id": "uuid-string",
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+1234567890",
      "company": "Fashion Store Inc",
      "requirements": "Custom designed handbags...",
      "additional_info": "We need eco-friendly materials",
      "product_category": "Handbags",
      "quantity": "100 pieces",
      "budget": "$50,000",
      "timeline": "3 months",
      "status": "new",
      "created_at": "2024-01-01T00:00:00.000Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "skip": 0
}
```

### PUT /rfq/{rfq_id}
Update RFQ status (Admin only).

**Request Body:**
```json
{
  "status": "reviewing",
  "notes": "Under review by design team"
}
```

**Valid Status Values:**
- `new`: New request
- `reviewing`: Under review
- `quoted`: Quote provided
- `closed`: Request closed
- `won`: Deal won
- `lost`: Deal lost

**Response:**
```json
{
  "success": true,
  "message": "RFQ status updated successfully"
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "success": false,
  "error": "Required field 'name' is missing"
}
```

### 404 Not Found
```json
{
  "success": false,
  "error": "Product not found"
}
```

### 500 Internal Server Error
```json
{
  "success": false,
  "error": "Database connection failed"
}
```

---

## Usage Examples

### Using cURL

**Create a Category:**
```bash
curl -X POST http://localhost:5000/api/categories \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Fashion Accessories",
    "description": "Stylish fashion accessories"
  }'
```

**Create a Product:**
```bash
curl -X POST http://localhost:5000/api/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Designer Handbag",
    "category_id": "category-uuid-here",
    "price": 299.99,
    "description": "Luxury designer handbag"
  }'
```

**Submit RFQ:**
```bash
curl -X POST http://localhost:5000/api/rfq \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890",
    "company": "Fashion Store",
    "requirements": "Custom handbags"
  }'
```

### Using JavaScript/Fetch

**Get Products:**
```javascript
fetch('http://localhost:5000/api/products')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('Products:', data.products);
    }
  });
```

**Create Product:**
```javascript
fetch('http://localhost:5000/api/products', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    name: 'New Product',
    category_id: 'category-uuid',
    price: 199.99,
    description: 'Product description'
  })
})
.then(response => response.json())
.then(data => {
  if (data.success) {
    console.log('Product created:', data.product);
  }
});
```

---

## Rate Limiting
Currently, no rate limiting is implemented. Consider implementing rate limiting for production use.

## CORS
CORS is enabled for all origins in development. Configure appropriately for production.

## Security Considerations
- Implement authentication for admin endpoints
- Use HTTPS in production
- Validate and sanitize all input data
- Implement proper error handling
- Use environment variables for sensitive data
