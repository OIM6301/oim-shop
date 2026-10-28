# Deployment

The live site runs on one small Linux server, shared with other services. GitHub Actions builds the image ([Containerfile](Containerfile)) and pushes it to `ghcr.io/oim7510/oim-shop`; the server only pulls it. Nothing is built on the server.

## Files

[oim-shop.container](oim-shop.container) is the container, as a Quadlet unit for rootless podman. It publishes the app on `127.0.0.1:8100`, keeps the database on the volume `oim-shop-data`, and caps the container at 200 MB of memory and half a CPU. It is the copy of record: edit it here, then copy it to the server.

## Signing in (v3)

Signing in needs two files on the server, neither of them in git:

- `~/.config/oim-shop.env` (600): `OIM_SHOP_GITHUB_CLIENT_ID=` and `OIM_SHOP_GITHUB_CLIENT_SECRET=`, from the project's GitHub OAuth App, whose callback is `https://oim-shop.zhili.dev/api/auth/callback`.
- `~/.config/oim-shop/allowed-users` (644, in a 700 directory): the GitHub usernames who may sign in, one per line, with `manager` after a manager's.

The unit reads both ([oim-shop.container](oim-shop.container)). Signing in needs every setting or none: with only some of them, the app stops at start and says which is missing.

The app reads the allowlist at every sign-in, so a change to it needs no restart, as long as you change the file in place: write to it with `>`, or edit it with an editor that saves in place, such as nano. The unit mounts the file itself, not its directory, so a file put in its place (with `mv`, or by an editor that saves a new file and renames it) leaves the container reading the old one until it restarts.

## End of term

Empty the allowlist but for the manager, then remove every rep who signed in, with their chosen names, and every order entered here. The manager's account, name and employee record stay, so next term's reps report to the same manager:

```bash
printf '%s manager\n' "$MANAGER" > ~/.config/oim-shop/allowed-users   # MANAGER: your GitHub username
systemctl --user restart oim-shop   # so the container surely reads the new list
podman exec oim-shop oim-shop forget-accounts
```

## Counting visits

The web app counts visits with [Umami](https://umami.is) when the image is built with two repository variables, `UMAMI_SCRIPT` (the URL of the Umami instance's `script.js`) and `UMAMI_WEBSITE_ID` (the site's id in it). Without them it counts nothing, and the privacy page does not mention it.

```bash
gh variable set UMAMI_SCRIPT --body "https://<your Umami>/script.js"
gh variable set UMAMI_WEBSITE_ID --body "<the website id>"
```

## Nightly reset

[oim-shop-reset.timer](oim-shop-reset.timer) runs [oim-shop-reset.service](oim-shop-reset.service) at 3:00 Boston time, which runs `oim-shop reset` inside the container.

```bash
cp oim-shop-reset.service oim-shop-reset.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now oim-shop-reset.timer
systemctl --user list-timers oim-shop-reset.timer
```

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
