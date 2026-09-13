# VoxDirector AI — Running Instructions (Docker Compose)

Everything below assumes you only run `docker` / `docker compose` commands —
no Python, no Node, nothing else to install by hand. Follow the steps in
order; each one builds on the last.

## Prerequisites

- **Docker Desktop** installed and running (Windows/Mac) or **Docker Engine
  + Compose plugin** (Linux). If `docker compose version` prints a version
  number in your terminal, you're ready.
- The project folder on the machine you're running this from (`git clone`
  or copy it over).
- A Gemini API key for your own first test run — free, from
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey). (More on
  keys in step 4 — each tester can later use their own.)

## Step 1 — Configure your `.env` file

From the project root:

```bash
cp .env.example .env
```

Open `.env` in any text editor and set just one line:

```
GEMINI_API_KEY=<paste your key here>
```

Leave `NEXT_PUBLIC_API_URL` **blank** and leave everything else in `.env`
as-is (the other variables belong to an unrelated part of this repo). Don't
set `NEXT_PUBLIC_API_URL` to `http://localhost:8000` — that was a mistake in
an earlier version of this guide and causes `ERR_CONNECTION_REFUSED` in the
browser, since that port isn't reachable from outside Docker in this setup;
everything goes through nginx on port 80 instead.

## Step 2 — Build and start everything

```bash
docker compose up --build
```

This builds three containers (backend, frontend, nginx) and starts them.
**The first run takes a while** — the backend image installs several
gigabytes of ML dependencies (this only happens once; later runs reuse the
cached layers and take seconds). You'll see build output scroll by, then
lines like:

```
voxdirector-backend   | INFO:     Application startup complete.
voxdirector-frontend  | ✓ Ready in ...ms
voxdirector-nginx     | ...
```

That means all three are up. Leave this terminal open — it's showing live
logs. To run in the background instead, use `docker compose up --build -d`
and check logs later with `docker compose logs -f`.

## Step 3 — Open it

Go to **http://localhost** in your browser. That's the whole app — nginx
routes the page itself and all API/WebSocket traffic to the right container
automatically, so this one URL is all anyone needs, including your 3 beta
testers once this is on a real VPS with a domain instead of `localhost`.

## Step 4 — API keys (BYOK)

Each person's requests use **their own** Gemini API key, not a shared
server key:

- The `GEMINI_API_KEY` you put in `.env` is only a **fallback** — used if
  someone hasn't set their own key yet.
- In the app, click **"Cài đặt dữ liệu"** (top right) → scroll to **"Gemini
  API key riêng (BYOK)"** → paste a key → **"Lưu key"**. It's saved in that
  browser only (not sent to or stored on the server beyond the single
  request being processed) and used automatically from then on.
- Tell your 3 testers to do this once with their own key — that way nobody
  shares your personal quota (free tier is 20 requests/day per model, which
  is easy to burn through with several people sharing one key).

## Stopping / restarting

```bash
docker compose down          # stop and remove all 3 containers
docker compose up            # start again (no rebuild — fast)
docker compose up --build    # start again AND rebuild (after you change code)
docker compose logs -f backend   # watch just the backend's logs
docker compose logs -f frontend  # watch just the frontend's logs
```

`docker compose down` does **not** delete your data — the glossary database
and job outputs live in named Docker volumes that persist across restarts.
To wipe those too: `docker compose down -v` (only do this if you actually
want a clean slate).

## Checking it's actually working

```bash
curl http://localhost/api/voices
```

Should print JSON (the voice list). `Connection refused` means the
containers aren't up yet — check `docker compose ps` and `docker compose
logs`.

## Moving this to a rented VPS later

Same commands, run on the VPS instead of your machine, plus pointing a
domain at it and getting an HTTPS certificate — that part is a few extra
one-time steps, covered separately in `deploy/README.md`.
