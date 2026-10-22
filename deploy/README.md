# Deployment

The live site runs on one small Linux server, shared with other services. GitHub Actions builds the image ([Containerfile](Containerfile)) and pushes it to `ghcr.io/oim7510/oim-shop`; the server only pulls it. Nothing is built on the server.

## Files

- [oim-shop.container](oim-shop.container): the container, as a Quadlet unit for rootless podman. It publishes the app on `127.0.0.1:8100`, keeps the database on the volume `oim-shop-data`, and caps the container at 200 MB of memory and half a CPU.
- [oim-shop-sync.service](oim-shop-sync.service) and [oim-shop-sync.timer](oim-shop-sync.timer): run `oim-shop sync` inside the container every hour.

These are the copies of record: edit them here, then copy them to the server.

## First setup

As the user that runs the app:

```bash
# Keep user services running after logout; without this the container and the timer stop.
sudo loginctl enable-linger "$USER"

mkdir -p ~/.config/containers/systemd ~/.config/systemd/user
cp oim-shop.container ~/.config/containers/systemd/
cp oim-shop-sync.service oim-shop-sync.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start oim-shop
systemctl --user enable --now oim-shop-sync.timer
```

Caddy terminates HTTPS for `oim-shop.zhili.dev` behind Cloudflare and proxies to `127.0.0.1:8100`. It accepts connections only from Cloudflare's addresses, which is what makes the `CF-Connecting-IP` header trustworthy for the app's rate limit.

## Deploy a new image

```bash
podman pull ghcr.io/oim7510/oim-shop:latest
systemctl --user restart oim-shop
curl -s http://127.0.0.1:8100/api/health
```

## Check it

```bash
systemctl --user status oim-shop
journalctl --user -u oim-shop -n 50
systemctl --user show oim-shop -p MemoryCurrent -p MemoryPeak
systemctl --user list-timers oim-shop-sync.timer
```
