"""Lecture du fichier de réglages : ce qui est accepté, ce qui est refusé.

Ces tests portent sur parse(), qui travaille sur un document déjà décodé : ils
ne touchent donc pas au disque. L'étape 7 fera évoluer le format (clé
« modules », slot facultatif) en gardant « slots » en lecture — ces cas-là
resteront donc valides.
"""
import unittest

from adam5000 import settings


def bloc(**remplace):
    """Un bloc valide, dont chaque test ne change que ce qui l'intéresse."""
    base = {"slot": 0, "module": "5081", "vitesse": 38400, "checksum": False}
    base.update(remplace)
    return base


def document(*blocs):
    return {"slots": list(blocs)}


class DocumentValide(unittest.TestCase):

    def test_un_bloc(self):
        reglages = settings.parse(document(bloc()))
        self.assertEqual(len(reglages), 1)
        self.assertEqual(reglages[0].slot, 0)
        self.assertEqual(reglages[0].module, "5081")
        self.assertEqual(reglages[0].baud, 38400)
        self.assertIs(reglages[0].checksum, False)

    def test_adresse_par_defaut_quand_absente(self):
        self.assertEqual(settings.parse(document(bloc()))[0].address, "01")

    def test_blocs_rendus_tries_par_slot(self):
        reglages = settings.parse(document(bloc(slot=2), bloc(slot=0)))
        self.assertEqual([r.slot for r in reglages], [0, 2])

    def test_reference_de_module_normalisee(self):
        for ecriture in ("5050", 5050, "ADAM-5050", " adam-5050 "):
            reglages = settings.parse(document(bloc(module=ecriture)))
            self.assertEqual(reglages[0].module, "5050", ecriture)

    def test_adresse_normalisee_en_majuscules(self):
        self.assertEqual(
            settings.parse(document(bloc(adresse="0a")))[0].address, "0A"
        )


class DocumentRefuse(unittest.TestCase):

    def refus(self, doc, attendu):
        with self.assertRaises(ValueError) as levee:
            settings.parse(doc)
        self.assertIn(attendu, str(levee.exception))

    def test_pas_un_objet(self):
        self.refus([], "objet JSON")

    def test_cle_slots_absente(self):
        self.refus({"modules": []}, "slots")

    def test_liste_vide(self):
        self.refus({"slots": []}, "au moins un bloc")

    def test_bloc_pas_un_objet(self):
        self.refus({"slots": ["5081"]}, "objet JSON est attendu")

    def test_cle_inconnue(self):
        self.refus(document(bloc(couleur="rouge")), "couleur")

    def test_cle_manquante(self):
        incomplet = bloc()
        del incomplet["vitesse"]
        self.refus(document(incomplet), "vitesse")

    def test_slot_en_double(self):
        self.refus(document(bloc(slot=1), bloc(slot=1, module="5050")),
                   "deux fois")

    def test_slot_hors_bornes(self):
        self.refus(document(bloc(slot=settings.IO_SLOTS)), "hors du fond")

    def test_slot_negatif(self):
        self.refus(document(bloc(slot=-1)), "hors du fond")

    def test_true_refuse_comme_slot(self):
        # bool est un int en Python : sans garde, true passerait pour le slot 1.
        self.refus(document(bloc(slot=True)), "entier")

    def test_slot_texte(self):
        self.refus(document(bloc(slot="0")), "entier")

    def test_vitesse_inconnue(self):
        self.refus(document(bloc(vitesse=31250)), "non gérée")

    def test_vitesse_texte(self):
        self.refus(document(bloc(vitesse="38400")), "entier")

    def test_module_inconnu(self):
        self.refus(document(bloc(module="5017")), "non géré")

    def test_checksum_pas_booleen(self):
        self.refus(document(bloc(checksum="oui")), "true ou false")

    def test_adresse_invalide(self):
        for mauvaise in ("1", "001", "ZZ", ""):
            with self.subTest(adresse=mauvaise):
                self.refus(document(bloc(adresse=mauvaise)), "invalide")


class FichierAbsent(unittest.TestCase):

    def test_message_clair(self):
        with self.assertRaises(ValueError) as levee:
            settings.load("/n/existe/pas/config.json")
        self.assertIn("introuvable", str(levee.exception))


if __name__ == "__main__":
    unittest.main()
