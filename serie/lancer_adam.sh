#!/bin/sh
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

echo "ADAM-5000 / ADAM-5081 / ADAM-5050"
echo
echo "1 - Lecture continue temporisée d'un module ADAM-5081"
echo "2 - Visualiser les 16 entrées/sorties d'un module ADAM-5050"
echo "3 - Activer le checksum du module"
printf "Choix [1-3] : "
read action

case "$action" in
  1|2|3) ;;
  *) echo "Choix invalide."; exit 1 ;;
esac

. "$SCRIPT_DIR/choisir_port.sh"

# Le paquet doit être lancé avec -m depuis son dossier parent : donner le
# répertoire ou le fichier __main__.py à python3 casserait les imports relatifs.
cd "$SCRIPT_DIR" || exit 1

echo
echo "Vitesse actuelle du module :"
echo "1 - 9600 bauds (valeur d'usine)"
echo "2 - 38400 bauds (valeur par défaut)"
echo "3 - 19200 bauds"
echo "4 - 115200 bauds"
printf "Choix [1-4, défaut 2] : "
read v

case "$v" in
  1) BAUD="9600" ;;
  ""|2) BAUD="38400" ;;
  3) BAUD="19200" ;;
  4) BAUD="115200" ;;
  *) echo "Choix invalide."; exit 1 ;;
esac

if [ "$action" = "3" ]; then
  echo
  echo "Activation du checksum : commande %01000840"
  echo "Elle suppose l'adresse 01, et un checksum actuellement désactivé :"
  echo "elle part donc elle-même sans checksum. Elle règle aussi le module"
  echo "sur 38400 bauds, quelle que soit la vitesse choisie ci-dessus, qui"
  echo "ne sert qu'à se faire entendre du module tel qu'il est aujourd'hui."
  echo "Selon le modèle, INIT* peut devoir être relié à GND."
  printf "Confirmer ? [o/N] : "
  read rep

  case "$rep" in
    o|O)
      $USE_SUDO python3 -m dcon \
        --port "$PORT" \
        --baud "$BAUD" \
        --enable-checksum \
        --timeout 2
      ;;
    *)
      echo "Opération annulée."
      ;;
  esac

  exit $?
fi

MODULE=""
if [ "$action" = "2" ]; then
  echo
  printf "Slot occupé par le module ADAM-5050 [0-3] : "
  read slot

  case "$slot" in
    0|1|2|3) ;;
    *) echo "Slot invalide."; exit 1 ;;
  esac

  MODULE="--5050 --slot $slot"
  DEFAUT_INTERVALLE="1"
else
  DEFAUT_INTERVALLE="2"
fi

echo
echo "État actuel du checksum sur le module :"
echo "1 - Activé"
echo "2 - Désactivé"
printf "Choix [1-2] : "
read c

case "$c" in
  1) CS="" ;;
  2) CS="--no-checksum" ;;
  *) echo "Choix invalide."; exit 1 ;;
esac

printf "Intervalle entre mesures en secondes [%s] : " "$DEFAUT_INTERVALLE"
read inter
[ -z "$inter" ] && inter="$DEFAUT_INTERVALLE"

printf "Délai avant nouvelle tentative en secondes [0.5] : "
read retrydelay
[ -z "$retrydelay" ] && retrydelay="0.5"

$USE_SUDO python3 -m dcon \
  --port "$PORT" \
  --baud "$BAUD" \
  --interval "$inter" \
  --retry-delay "$retrydelay" \
  --retries 5 \
  --timeout 2 \
  $MODULE \
  $CS
