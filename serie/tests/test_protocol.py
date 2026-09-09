"""Grammaire d'enveloppe : checksum, habillage, validation de la réponse.

Ces tests figent le comportement **actuel** de protocol.py. L'étape 3 du
chantier vide ce fichier de tout ce qui touche au slot ; les cas qui portent
sur read_command et digital_read_command déménageront alors avec eux.
"""
import unittest

from dcon import protocol


class ChecksumAscii(unittest.TestCase):
    """Somme des octets ASCII tronquée à un octet, en deux hexa majuscules."""

    def test_valeurs_de_reference(self):
        # Calculées à la main sur des trames réelles, pas produites par le code.
        self.assertEqual(protocol.checksum_ascii("#01S0"), "07")
        self.assertEqual(protocol.checksum_ascii("$01S26"), "40")
        self.assertEqual(protocol.checksum_ascii(">+000123"), "8F")

    def test_toujours_deux_caracteres_majuscules(self):
        for texte in ("", "#", "#01S0", ">" + "9" * 40):
            resultat = protocol.checksum_ascii(texte)
            self.assertEqual(len(resultat), 2, texte)
            self.assertEqual(resultat, resultat.upper(), texte)

    def test_chaine_vide_donne_zero(self):
        self.assertEqual(protocol.checksum_ascii(""), "00")

    def test_repli_au_dela_de_255(self):
        # 'A' vaut 65 : quatre 'A' font 260, soit 0x04 une fois tronqué.
        self.assertEqual(protocol.checksum_ascii("AAAA"), "04")


class BuildFrame(unittest.TestCase):

    def test_avec_checksum(self):
        self.assertEqual(protocol.build_frame("#01S0"), "#01S007\r")

    def test_sans_checksum(self):
        self.assertEqual(protocol.build_frame("#01S0", checksum=False), "#01S0\r")

    def test_espaces_retires_et_majuscules_forcees(self):
        self.assertEqual(protocol.build_frame("  #01s0  ", checksum=False), "#01S0\r")

    def test_checksum_calculee_sur_le_corps_deja_majuscule(self):
        # Sinon la checksum d'une commande saisie en minuscules serait fausse.
        self.assertEqual(protocol.build_frame(" #01s0 "), "#01S007\r")

    def test_terminateur_toujours_present(self):
        for checksum in (True, False):
            self.assertTrue(protocol.build_frame("#01S0", checksum).endswith("\r"))


class Commandes(unittest.TestCase):

    def test_lecture_analogique(self):
        self.assertEqual(protocol.read_command("01", 0), "#01S0")
        self.assertEqual(protocol.read_command("0A", 3), "#0AS3")

    def test_lecture_tout_ou_rien(self):
        # Le 6 final est imposé par la documentation du module.
        self.assertEqual(protocol.digital_read_command("01", 2), "$01S26")

    def test_commande_analogique_habillee(self):
        self.assertEqual(protocol.build_command("01", 0), "#01S007\r")
        self.assertEqual(protocol.build_command("01", 0, checksum=False), "#01S0\r")

    def test_adresse_par_defaut(self):
        self.assertEqual(protocol.DEFAULT_ADDRESS, "01")
        self.assertTrue(protocol.read_command().startswith("#01S"))

    def test_trame_d_activation_de_checksum(self):
        # Reprise telle quelle de la documentation : elle ne se recompose pas.
        self.assertEqual(protocol.ENABLE_CHECKSUM, "%01000840")


class VerifyFrame(unittest.TestCase):

    def test_sans_checksum_rend_la_charge_utile(self):
        self.assertEqual(
            protocol.verify_frame(">+000123", checksum=False), "+000123"
        )

    def test_avec_checksum_juste(self):
        self.assertEqual(protocol.verify_frame(">+0001238F"), "+000123")

    def test_checksum_fausse(self):
        with self.assertRaises(ValueError) as levee:
            protocol.verify_frame(">+00012300")
        self.assertIn("Checksum", str(levee.exception))

    def test_checksum_acceptee_en_minuscules(self):
        self.assertEqual(protocol.verify_frame(">+0001238f"), "+000123")

    def test_reponse_trop_courte_avec_checksum(self):
        # Moins de quatre caractères : il n'y a pas de quoi découper.
        with self.assertRaises(ValueError) as levee:
            protocol.verify_frame(">07", checksum=True)
        self.assertIn("trop courte", str(levee.exception))

    def test_reponse_trop_courte_sans_checksum(self):
        with self.assertRaises(ValueError) as levee:
            protocol.verify_frame(">", checksum=False)
        self.assertIn("trop courte", str(levee.exception))

    def test_accuse_attendu_absent(self):
        # Réponse tout ou rien lue avec l'accusé analogique : refus.
        with self.assertRaises(ValueError) as levee:
            protocol.verify_frame("!0001", checksum=False, ack=protocol.ACK)
        self.assertIn("'>'", str(levee.exception))

    def test_accuse_tout_ou_rien(self):
        self.assertEqual(
            protocol.verify_frame("!0001", checksum=False,
                                  ack=protocol.CONFIG_ACK),
            "0001",
        )

    def test_refus_du_module(self):
        # Un '?' à la place de l'accusé : le module a refusé la commande.
        with self.assertRaises(ValueError):
            protocol.verify_frame("?01", checksum=False)

    def test_charge_utile_vide_acceptee(self):
        self.assertEqual(protocol.verify_frame(">!", checksum=False), "!")


if __name__ == "__main__":
    unittest.main()
