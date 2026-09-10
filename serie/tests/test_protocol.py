"""Grammaire d'enveloppe : checksum, habillage, validation de la réponse.

Ces tests ne portent plus que sur l'enveloppe : habillage, checksum, contrôle
de l'accusé. L'étape 3 du chantier a sorti d'ici les cas qui touchaient au
slot — read_command, digital_read_command, ENABLE_CHECKSUM — ils sont dans
test_familles.py avec les fonctions qu'ils couvrent.
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
