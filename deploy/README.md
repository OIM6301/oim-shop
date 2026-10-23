# Deployment

The live site runs on one small Linux server, shared with other services. GitHub Actions builds the image ([Containerfile](Containerfile)) and pushes it to `ghcr.io/oim7510/oim-shop`; the server only pulls it. Nothing is built on the server.

## Files

[oim-shop.container](oim-shop.container) is the container, as a Quadlet unit for rootless podman. It publishes the app on `127.0.0.1:8100`, keeps the database on the volume `oim-shop-data`, and caps the container at 200 MB of memory and half a CPU. It is the copy of record: edit it here, then copy it to the server.

## First setup

As the user that runs the app:

```bash
# Keep user services running after logout; without this the container stops.
sudo loginctl enable-linger "$USER"

mkdir -p ~/.config/containers/systemd
cp oim-shop.container ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user start oim-shop
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
```
