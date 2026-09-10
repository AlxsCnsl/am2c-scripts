"""Grammaire de lecture du fond de panier ADAM-5000 : les trames demandées.

Ces cas viennent de test_protocol.py, d'où l'étape 3 du chantier les a sortis
avec les fonctions qu'ils couvrent. Ils figent les trames caractère par
caractère : l'étape 4, qui découpe `familles.py` en paquet `familles/`, ne doit
rien changer à ce qu'elles valent.
"""
import unittest

from dcon import familles, protocol


class Commandes(unittest.TestCase):

    def test_lecture_analogique(self):
        self.assertEqual(familles.read_command("01", 0), "#01S0")
        self.assertEqual(familles.read_command("0A", 3), "#0AS3")

    def test_lecture_tout_ou_rien(self):
        # Le 6 final est imposé par la documentation du module.
        self.assertEqual(familles.digital_read_command("01", 2), "$01S26")

    def test_commande_analogique_habillee(self):
        self.assertEqual(familles.build_command("01", 0), "#01S007\r")
        self.assertEqual(familles.build_command("01", 0, checksum=False), "#01S0\r")

    def test_adresse_par_defaut(self):
        self.assertEqual(protocol.DEFAULT_ADDRESS, "01")
        self.assertTrue(familles.read_command().startswith("#01S"))

    def test_trame_d_activation_de_checksum(self):
        # Reprise telle quelle de la documentation : elle ne se recompose pas.
        self.assertEqual(familles.ENABLE_CHECKSUM, "%01000840")


if __name__ == "__main__":
    unittest.main()
