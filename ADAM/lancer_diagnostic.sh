#!/bin/sh
# Diagnostic à lancer quand le module reste muet : cherche la vitesse,
# l'état du checksum, l'adresse et le slot, sans rien modifier.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

echo "=========================================="
echo " Diagnostic ADAM-5000"
echo "=========================================="
echo
echo "Balayage en lecture seule : seules des interrogations sont envoyées."
echo "Aucune commande de configuration, le module n'est pas modifié."

. "$SCRIPT_DIR/choisir_port.sh"

echo
printf "Adresse supposée du module [01] : "
read adresse
[ -z "$adresse" ] && adresse="01"

echo
echo "Le balayage des vitesses dure environ une minute."
echo "Faut-il, s'il ne trouve rien, chercher aussi l'adresse ?"
echo "1 - Non, s'arrêter là"
echo "2 - Oui, essayer les 256 adresses (deux minutes de plus)"
printf "Choix [1-2, défaut 1] : "
read suite

case "$suite" in
  2) ADRESSES="--scan-addresses" ;;
  ""|1) ADRESSES="" ;;
  *) echo "Choix invalide."; exit 1 ;;
esac

# Le paquet doit être lancé avec -m depuis son dossier parent : donner le
# répertoire ou le fichier __main__.py à python3 casserait les imports relatifs.
cd "$SCRIPT_DIR" || exit 1

echo
$USE_SUDO python3 -m adam5000 \
  --port "$PORT" \
  --address "$adresse" \
  --scan \
  $ADRESSES
