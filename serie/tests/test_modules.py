"""Décodage de la charge utile, un module à la fois.

Ces tests figent le comportement **actuel**, y compris ce que l'étape 9 doit
corriger. Les cas concernés portent la mention BOGUE FIGÉ : quand l'étape 9
passera, ce sont eux qui changeront, et le diff dira exactement ce qui a bougé.
"""
import unittest

from dcon import modules


class Constantes(unittest.TestCase):
    """Hypothèses actuelles sur le matériel câblé, pas des vérités."""

    def test_valeurs_actuelles(self):
        # EXPECTED_CHANNELS = 8 contredit « l'ADAM-5081 compte 4 voies » : la
        # décision 8 du TODO tranche par déduction sur la longueur reçue.
        self.assertEqual(modules.EXPECTED_CHANNELS, 8)
        self.assertEqual(modules.EXPECTED_WIDTH, 10)
        self.assertEqual(modules.IO_CHANNELS, 16)
        self.assertEqual(modules.IO_WORD_LENGTH, 4)
        self.assertEqual(modules.IO_SLOTS, 4)

    def test_modules_geres(self):
        self.assertEqual(set(modules.SUPPORTED_MODULES), {"5050", "5081"})


class Parse5081(unittest.TestCase):

    def charge(self, voies=8, largeur=10):
        """Une charge utile de la bonne longueur, une valeur par voie."""
        return "".join(str(v % 10) * largeur for v in range(voies))

    def test_longueur_exacte(self):
        valeurs = modules.parse_5081(self.charge())
        self.assertEqual(len(valeurs), 8)
        self.assertEqual(valeurs[0], 0)
        self.assertEqual(valeurs[1], 1111111111)

    def test_longueur_trop_courte(self):
        with self.assertRaises(ValueError) as levee:
            modules.parse_5081("0" * 79)
        self.assertIn("79", str(levee.exception))

    def test_longueur_trop_longue(self):
        with self.assertRaises(ValueError):
            modules.parse_5081("0" * 81)

    def test_donnees_non_numeriques(self):
        # Un signe suffit à faire échouer : le découpage actuel ne l'admet pas.
        with self.assertRaises(ValueError) as levee:
            modules.parse_5081("+" + "0" * 79)
        self.assertIn("numériques", str(levee.exception))

    def test_decoupage_parametrable(self):
        valeurs = modules.parse_5081(self.charge(4, 10), channels=4, width=10)
        self.assertEqual(valeurs, [0, 1111111111, 2222222222, 3333333333])

    def test_quatre_voies_refusees_par_defaut(self):
        # 40 caractères pour 4 voies de 10 : refusé tant que le défaut vaut 8.
        # C'est ce cas que la décision 8 fera passer.
        with self.assertRaises(ValueError):
            modules.parse_5081(self.charge(4, 10))


class Parse5050(unittest.TestCase):

    def test_voie_zero_est_le_bit_de_poids_faible(self):
        etats = modules.parse_5050("0001")
        self.assertEqual(etats[0], 1)
        self.assertEqual(etats[1:], [0] * 15)

    def test_toutes_les_voies_a_zero(self):
        self.assertEqual(modules.parse_5050("0000"), [0] * 16)

    def test_toutes_les_voies_a_un(self):
        self.assertEqual(modules.parse_5050("FFFF"), [1] * 16)

    def test_toujours_seize_voies(self):
        self.assertEqual(len(modules.parse_5050("0001")), 16)

    def test_minuscules_acceptees(self):
        self.assertEqual(modules.parse_5050("ffff"), [1] * 16)

    def test_adresse_reemise_en_tete(self):
        # Certains modules réémettent l'adresse, d'autres non.
        self.assertEqual(modules.parse_5050("010001"), modules.parse_5050("0001"))

    def test_adresse_personnalisee(self):
        self.assertEqual(
            modules.parse_5050("0A0001", address="0A"),
            modules.parse_5050("0001"),
        )

    def test_second_octet_porte_les_voies_hautes(self):
        # 0x0200 : seule la voie 9 est active. On évite « 0100 », qui percute
        # le bogue d'amputation de l'adresse figé plus bas.
        etats = modules.parse_5050("0200")
        self.assertEqual(etats[9], 1)
        self.assertEqual(sum(etats), 1)

    def test_mot_illisible(self):
        with self.assertRaises(ValueError) as levee:
            modules.parse_5050("ZZZZ")
        self.assertIn("illisible", str(levee.exception))

    def test_mot_trop_court(self):
        with self.assertRaises(ValueError):
            modules.parse_5050("00")

    def test_reliquat_apres_le_mot_ignore(self):
        self.assertEqual(modules.parse_5050("0001ABCD"), modules.parse_5050("0001"))


class Parse5050BoguesFiges(unittest.TestCase):
    """BOGUE FIGÉ — corrigé à l'étape 9, ces deux tests changeront alors.

    parse_5050 retire l'adresse dès que la charge utile commence comme elle,
    sans vérifier qu'il restera assez de caractères. Un mot d'état qui commence
    par « 01 » sur un module d'adresse 01 est donc amputé, puis rejeté.
    """

    def test_mot_d_etat_commencant_comme_l_adresse_est_mange(self):
        # « 0100 » est un mot d'état valide : voie 8 à 1, les autres à 0.
        # Il devrait rendre 16 états ; aujourd'hui il lève.
        with self.assertRaises(ValueError) as levee:
            modules.parse_5050("0100")
        self.assertIn("illisible", str(levee.exception))

    def test_meme_mot_accepte_sous_une_autre_adresse(self):
        # La preuve que c'est l'adresse qui gêne, pas le mot.
        etats = modules.parse_5050("0100", address="0A")
        self.assertEqual(etats[8], 1)


class PossibleLayouts(unittest.TestCase):

    def test_decoupages_entiers_seulement(self):
        decoupages = modules.possible_layouts("12345678")
        voies = [d[0] for d in decoupages]
        self.assertEqual(voies, [1, 2, 4, 8])  # 16 ne divise pas 8

    def test_forme_du_resultat(self):
        voies, largeur, champs = modules.possible_layouts("12345678")[1]
        self.assertEqual((voies, largeur), (2, 4))
        self.assertEqual(champs, ["1234", "5678"])

    def test_charge_vide(self):
        self.assertEqual(modules.possible_layouts(""), [])

    def test_candidats_imposes(self):
        decoupages = modules.possible_layouts("12345678", candidates=(4,))
        self.assertEqual(len(decoupages), 1)
        self.assertEqual(decoupages[0][0], 4)

    def test_champs_repetes_signalent_un_mauvais_decoupage(self):
        # Propriété exploitée par le diagnostic : la répétition trahit la coupe.
        _, _, champs = modules.possible_layouts("11112222", candidates=(4,))[0]
        self.assertEqual(champs, ["11", "11", "22", "22"])


if __name__ == "__main__":
    unittest.main()
