# PLACERHIVE — Railway Ready Package

This is a production-ready version of PLACERHIVE prepared for Railway.

## What was fixed / improved

- Gunicorn production server (Procfile included)
- Proper `$PORT` binding
- Admin password set to your chosen value
- Safer secret key handling
- File upload type validation (CV, proof, photos, logo)
- Fixed API auth for logged-in users (`/api/application/mine`)
- Reduced personal data exposure on public application tracking
- Data directory support for Railway volumes (`DATA_DIR`)
- Cleaner datetime handling
- Session cookie hardening

## Admin access

- URL: `https://your-app.up.railway.app/admin`
- Password: `Chibuike12to13#`

(You can still override it later with the `ADMIN_PASSWORD` environment variable.)

---

## Deploy on Railway (recommended method — GitHub)

### 1. Create a GitHub repository
1. Go to https://github.com/new
2. Create a new **public** or **private** repository (e.g. `placerhive`)
3. Upload **all files inside this folder** (the contents of `PLACERHIVE_RAILWAY_READY`) to the root of the repository.

Important: `app.py`, `Procfile`, `requirements.txt` and the `templates/` + `static/` folders must be at the root of the repo.

### 2. Deploy on Railway
1. Go to https://railway.app and sign in (GitHub login is easiest)
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `placerhive` repository
4. Railway will detect Python and start building

### 3. Generate a public domain
1. Click your service
2. Go to **Settings** → **Networking**
3. Click **Generate Domain**
4. Your site will be live at `https://xxxx.up.railway.app`

### 4. (Strongly recommended) Add a Volume for the database
SQLite files are lost on every redeploy unless you use a volume.

1. In your Railway project → **New** → **Volume**
2. Mount path: `/data`
3. Size: 1 GB is enough to start
4. Then add this **Environment Variable** to your service:

| Variable     | Value   |
|--------------|---------|
| `DATA_DIR`   | `/data` |

Redeploy after adding the volume.

### 5. Optional but recommended environment variables

| Variable          | Suggested value                          | Purpose                    |
|-------------------|------------------------------------------|----------------------------|
| `SECRET_KEY`      | long random string                       | Session security           |
| `ADMIN_PASSWORD`  | `Chibuike12to13#` (or stronger)          | Admin login                |
| `PAYMENT_AMOUNT`  | `299.00`                                 | Default payment amount     |
| `DATA_DIR`        | `/data`                                  | Persistent storage         |

---

## Alternative: Deploy with Railway CLI (no GitHub)

```bash
# Install CLI
npm install -g @railway/cli

# Login
railway login

# Inside this folder
railway init
railway up
railway domain
```

---

## After deployment — test checklist

1. Open the homepage
2. Search jobs
3. Submit a job application (Seek a Job)
4. Submit an employer request → payment flow
5. Go to `/admin` and log in with `Chibuike12to13#`
6. Verify you can see applications and payments

---

## Important notes

- The database and uploaded files will **only** survive redeploys if you attach a Volume and set `DATA_DIR=/data`.
- Never commit your real `SECRET_KEY` or change the admin password in the code after going live — use environment variables.
- Bank details are still in `app.py`. Change them there if needed.

---

Built for Railway · PLACERHIVE Complete Pro
