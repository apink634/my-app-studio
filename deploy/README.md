# Deploy the RAG app to my server (rag.anncarlos.me)

This runs the tested App Studio code as one container behind the server's
**existing** Traefik. It starts no new proxy, opens no new ports and does not
touch the calculator or my Apache sites. Secrets live only in `deploy/rag.env`
on the server.

## 0 · Before you start

- DNS: `nslookup rag.anncarlos.me` should answer `167.172.158.254`. If not, add an
  **A record** `rag` → `167.172.158.254` where `anncarlos.me`'s DNS is managed
  (the same place as the `calc` record), then wait a few minutes.
- A Groq API key from console.groq.com → API Keys. Don't paste it in chat or commit it.

## 1 · On the server: get the code

```bash
ssh YOUR_USER@167.172.158.254
git clone https://github.com/apink634/my-app-studio.git ~/my-app-studio
cd ~/my-app-studio
git switch rag-001-build      # or stay on main once the PR is merged
git log -1 --oneline          # write down this commit for the record
```

## 2 · Settings

```bash
sudo docker network ls        # find the Traefik network: usually hosting-web (or web)
printf 'APP_HOST=rag.anncarlos.me\nTRAEFIK_NETWORK=hosting-web\n' > .env
cp deploy/rag.env.example deploy/rag.env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # copy this for APP_SECRET
nano deploy/rag.env           # paste APP_SECRET and GROQ_API_KEY, save
chmod 600 deploy/rag.env .env
```

Use whatever network name `docker network ls` actually shows for Traefik.

## 3 · Build and start

```bash
sudo docker compose config --quiet && echo "compose file OK"
sudo docker compose build     # several minutes the first time (downloads the embedding model)
sudo docker compose up -d
sudo docker compose ps        # wait until STATUS says (healthy)
curl -s https://rag.anncarlos.me/health
```

## 4 · Import, build the graph, and check

```bash
sudo docker compose exec rag python -m app.rag import
sudo docker compose exec rag python -m app.rag import   # repeat: every source should say "unchanged"
sudo docker compose exec rag python -m app.rag graph    # about a minute; waits on rate limits
sudo docker compose exec rag python -m app.rag report > ~/rag-report.json
sudo docker compose exec rag python -m app.rag ask "What are common diabetes symptoms?"
```

Save each command's output (no secrets are printed). These are the import
record, repeat-import check and sample representation for the review.

## 5 · Browser checks

1. Open https://rag.anncarlos.me/rag/sources and confirm all five sources show chunks.
2. Sign up, log in, open https://rag.anncarlos.me/rag and ask the five evaluation questions.
3. On each answer page, click a cited source and check that the passage says it.
4. Restart: `sudo docker compose restart rag`, then reload `/rag/sources` and an old
   answer link. They should still be there (the data is in the `rag-data` volume).

## Updating later

```bash
cd ~/my-app-studio && git pull && sudo docker compose up -d --build
```

## If something fails

- `docker compose ps` says unhealthy → `sudo docker compose logs --tail 50 rag`.
- Browser shows 404 from Traefik → the network name in `.env` is wrong, or DNS isn't ready.
- `import` says "returned no summary" → copy the exact message. A page URL or the
  MedlinePlus web service format may need a fix.
- Answers say the service is unavailable → check `GROQ_API_KEY` in `deploy/rag.env`, then
  `sudo docker compose up -d` to reload it.
