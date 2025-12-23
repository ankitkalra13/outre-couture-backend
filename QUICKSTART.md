# 🚀 Quick Start - Deploy to Render in 5 Minutes

## Step 1: Push to Git (1 minute)

```bash
git add .
git commit -m "Configure for Render deployment"
git push origin main
```

## Step 2: Create Render Service (2 minutes)

1. Go to: https://dashboard.render.com
2. Click: **"New +" → "Blueprint"**
3. Connect your repository
4. Click: **"Apply"**

✅ Render will create 3 services automatically!

## Step 3: Set Environment Variables (2 minutes)

For **each** of the 3 services, add these in Render Dashboard:

### Required Variables:

```
MONGO_URI = mongodb+srv://username:0yQ4N2JY1hJVsadsadsad@cluster.dadad.mongodb.net/user_name?retryWrites=true&w=majority
FRONTEND_URL = https://your-frontend-url.com
```

### Optional (for email):

```
MAIL_USERNAME = your-email@gmail.com
MAIL_PASSWORD = your-gmail-app-password
MAIL_DEFAULT_SENDER = your-email@gmail.com
```

## Step 4: Verify (30 seconds)

Test your API:

```bash
curl https://outre-couture-backend-dev.onrender.com/api/health
```

Expected: `{"success": true, "status": "healthy"}`

---

## 🎉 Done!

Your backend is now live on Render!

- 🟢 **Dev**: `https://outre-couture-backend-dev.onrender.com`
- 🟡 **Staging**: `https://outre-couture-backend-staging.onrender.com`
- 🔴 **Production**: `https://outre-couture-backend-prod.onrender.com`

---

## 📚 Need More Help?

- **Detailed Guide**: See `RENDER_DEPLOYMENT.md`
- **Checklist**: See `DEPLOYMENT_CHECKLIST.md`
- **Complete Setup**: See `SETUP_COMPLETE.md`

## ⚠️ Important Notes

1. **MongoDB Atlas**: Whitelist Render IPs (0.0.0.0/0) in Network Access
2. **Free Tier**: Cold starts take 30-60 seconds after inactivity
3. **Gmail**: Use App Password, not regular password (requires 2FA)
4. **Update Frontend**: Point to your new Render URLs

---

**Questions?** Check the other documentation files for detailed help!
