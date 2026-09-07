#!/bin/sh
# Choix interactif du port série et des droits d'accès.
#
# Ce fichier ne se lance pas seul : il est inclus par les lanceurs
# (`. "$SCRIPT_DIR/choisir_port.sh"`) et leur laisse deux variables :
#   PORT      le port choisi
#   USE_SUDO  « sudo » s'il faut passer par là, vide sinon
#
# Inclus et non exécuté, car un sous-processus ne pourrait pas rendre ces
# variables à l'appelant. Les erreurs y coupent donc le lanceur lui-même,
# ce qui est bien le comportement voulu.

echo
echo "1 - USB / adaptateur USB-série"
echo "2 - Port série intégré"
printf "Choix [1-2] : "
read t

case "$t" in
  1)
    PORTS=""
    for p in /dev/ttyUSB* /dev/ttyACM*; do
      [ -e "$p" ] && PORTS="$PORTS $p"
    done
    ;;
  2)
    PORTS=""
    for p in /dev/ttyS*; do
      [ -e "$p" ] && PORTS="$PORTS $p"
    done
    ;;
  *)
    echo "Choix invalide."
    exit 1
    ;;
esac

[ -n "$PORTS" ] || { echo "Aucun port détecté."; exit 1; }

echo
i=1
for p in $PORTS; do
  echo "$i - $p"
  i=$((i+1))
done

printf "Numéro du port : "
read n

PORT=""
i=1
for p in $PORTS; do
  if [ "$i" = "$n" ]; then
    PORT="$p"
    break
  fi
  i=$((i+1))
done

[ -n "$PORT" ] || { echo "Port invalide."; exit 1; }

USE_SUDO=""
if [ ! -r "$PORT" ] || [ ! -w "$PORT" ]; then
  echo
  echo "Pas de droit d'accès au port."
  echo "1 - Ajouter l'utilisateur au groupe dialout"
  echo "2 - Lancer cette fois avec sudo"
  echo "3 - Annuler"
  printf "Choix [1-3] : "
  read d

  case "$d" in
    1)
      sudo usermod -aG dialout "$USER"
      echo "Déconnectez-vous complètement puis reconnectez-vous."
      exit 0
      ;;
    2)
      USE_SUDO="sudo"
      ;;
    3)
      exit 0
      ;;
    *)
      echo "Choix invalide."
      exit 1
      ;;
  esac
fi
