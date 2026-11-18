#!/bin/bash
# Run BY USER on VM103: sudo bash install.sh        (or: sudo bash install.sh --remove)
# Creates the jarvis-deploy account whose single SSH key (from jarvis-dev 192.0.2.165 only) can do
# exactly what jarvis-deploy-shell / jarvis-deploy-root allow. Agreed with User on 18.11.2026.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
U=jarvis-deploy; HOME_DIR=/var/lib/jarvis-deploy
KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICHwXVix6XzeCEsBxwsA4VKyxg4Ob/6jzIo+NavVn4SD claude@jarvis-dev deploy->vm103'
FROM=192.0.2.165
[ "$(id -u)" = 0 ] || { echo "sudo required"; exit 2; }
if [ "${1:-}" = --remove ]; then
  rm -f /etc/sudoers.d/jarvis-deploy /usr/local/sbin/jarvis-deploy-shell /usr/local/sbin/jarvis-deploy-root
  id "$U" >/dev/null 2>&1 && userdel -r "$U" 2>/dev/null || true
  rm -rf "$HOME_DIR"; echo "✅ accès jarvis-deploy supprimé"; exit 0
fi
id "$U" >/dev/null 2>&1 || useradd --system --home-dir "$HOME_DIR" --create-home --shell /bin/bash --comment "Claude deploy (restricted)" "$U"
passwd -l "$U" >/dev/null
install -d -o root -g root -m 0755 "$HOME_DIR"
install -d -o "$U" -g "$U" -m 0755 "$HOME_DIR/inbox"
install -d -o root -g "$U" -m 0750 "$HOME_DIR/.ssh"
install -o root -g root -m 0755 "$HERE/jarvis-deploy-shell" /usr/local/sbin/jarvis-deploy-shell
install -o root -g root -m 0755 "$HERE/jarvis-deploy-root" /usr/local/sbin/jarvis-deploy-root
printf 'restrict,from="%s",command="/usr/local/sbin/jarvis-deploy-shell" %s\n' "$FROM" "$KEY" > "$HOME_DIR/.ssh/authorized_keys"
chown root:"$U" "$HOME_DIR/.ssh/authorized_keys"; chmod 0640 "$HOME_DIR/.ssh/authorized_keys"
echo "$U ALL=(root) NOPASSWD: /usr/local/sbin/jarvis-deploy-root" > /etc/sudoers.d/.jarvis-deploy.new
chmod 0440 /etc/sudoers.d/.jarvis-deploy.new
visudo -cf /etc/sudoers.d/.jarvis-deploy.new >/dev/null && mv /etc/sudoers.d/.jarvis-deploy.new /etc/sudoers.d/jarvis-deploy
echo "== sshd : utilisateurs autorisés (si une liste existe, ajouter jarvis-deploy)"
sshd -T 2>/dev/null | grep -iE '^(allowusers|allowgroups|authorizedkeysfile|pubkeyauthentication) ' || true
echo "✅ jarvis-deploy installé : clé limitée à $FROM, commandes de jarvis-deploy-shell seulement."
echo "   Retrait à tout moment : sudo bash $0 --remove"
