# SpaceScan Production Deployment (`spacescan.me` + AWS EC2)

This guide deploys the **SpaceScan** static cockpit frontend on **GitHub Pages** at `https://spacescan.me` (`main` branch) and the **FastAPI + SSE** backend on **AWS EC2** at `https://api.spacescan.me` with automatic TLS and persistent storage.

---

## 1. Configure Namecheap DNS (`spacescan.me`)

Open **Namecheap** -> **Domain List** -> `spacescan.me` -> **Manage** -> **Advanced DNS**.
Remove any default **Parking Page** `CNAME` or **URL Redirect Record**, then add these exact records:

| Type | Host | Value | TTL | Target |
| :--- | :--- | :--- | :--- | :--- |
| `A Record` | `@` | `185.199.108.153` | Automatic | GitHub Pages (`spacescan.me`) |
| `A Record` | `@` | `185.199.109.153` | Automatic | GitHub Pages (`spacescan.me`) |
| `A Record` | `@` | `185.199.110.153` | Automatic | GitHub Pages (`spacescan.me`) |
| `A Record` | `@` | `185.199.111.153` | Automatic | GitHub Pages (`spacescan.me`) |
| `CNAME Record` | `www` | `willor16.github.io.` | Automatic | Redirects `www.spacescan.me` -> `spacescan.me` |
| `A Record` | `api` | `<YOUR_EC2_PUBLIC_IPV4>` | Automatic | AWS EC2 Backend (`https://api.spacescan.me`) |

---

## 2. Deploy Backend on AWS EC2 (`https://api.spacescan.me`)

`docker-compose.ec2.yml` bundles **Caddy** to obtain and renew a valid HTTPS certificate for `api.spacescan.me` automatically once the `api` DNS `A` record points to your EC2 instance.

### 2.1 EC2 Instance & Security Group
- **AMI:** Ubuntu 24.04 LTS (`t3.small` or `t3.micro`)
- **Inbound Security Group Rules:**
  - `TCP 22` (SSH from your IP)
  - `TCP 80` (`0.0.0.0/0` — required for automatic TLS verification and HTTP -> HTTPS redirect)
  - `TCP 443` and `UDP 443` (`0.0.0.0/0` — HTTPS API + live SSE streams)

### 2.2 Install Docker on Ubuntu EC2
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

### 2.3 Clone, Copy `.env`, and Launch
`.env.example` is already preconfigured with `API_DOMAIN=api.spacescan.me` and `SPACESCAN_CORS_ORIGINS=https://spacescan.me,https://www.spacescan.me`:

```bash
git clone <YOUR_REPO_CLONE_URL> spacescan
cd spacescan
cp .env.example .env
docker compose -f docker-compose.ec2.yml up -d --build
```

Verify readiness:
```bash
curl -fsS https://api.spacescan.me/api/v1/health
```

On first launch, the container initializes `/app/storage/spacescan.db` with the 47-day mission seed and audio recordings inside the `spacescan_storage` Docker volume. Subsequent restarts keep all recorded crew measurements intact.

---

## 3. Deploy Frontend on GitHub Pages (`https://spacescan.me`)

`frontend/public/CNAME` (`spacescan.me`) and `.github/workflows/deploy-pages.yml` (`NUXT_APP_BASE_URL=/` and `NUXT_PUBLIC_API_BASE=https://api.spacescan.me`) are preconfigured out of the box.

1. Open your GitHub repository -> **Settings** -> **Pages**.
2. Under **Build and deployment** -> **Source**, select **GitHub Actions**.
3. Under **Custom domain**, enter `spacescan.me`, click **Save**, wait for the DNS check to turn green, and enable **Enforce HTTPS**.
   *(GitHub Pages issues and renews its own TLS certificate automatically; no manual `.crt` upload is needed).*
4. Merge or push to `main` (or trigger **Actions** -> **Deploy Frontend to GitHub Pages** -> **Run workflow**).
5. Open `https://spacescan.me` and sign in with crew PINs (`ID-01`: `1042`, `ID-02`: `2084`, `ID-03`: `3190`, `ID-04`: `4275`).

*(Optional override)* If you ever need to point the frontend to a staging backend without editing files, set a repository variable `NUXT_PUBLIC_API_BASE` under **Settings** -> **Secrets and variables** -> **Actions** -> **Variables**.
