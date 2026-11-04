"""Ejecutar desde la raíz del proyecto:  python -m unittest tests.test_glossary -v"""
import json
import tempfile
import unittest
from pathlib import Path

from utils.glossary import GlossaryManager, normalize_text


class GlossaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def touch(self, *names):
        for n in names:
            p = self.dir / n
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")

    def test_normalize(self):
        self.assertEqual(normalize_text("¡Hola, Cómo estás! "), "hola como estas")
        self.assertEqual(normalize_text("Año"), "año")
        self.assertNotEqual(normalize_text("año"), normalize_text("ano"))
        self.assertEqual(normalize_text("buenos_dias-tarde"), "buenos dias tarde")

    def test_plural_and_false_positive(self):
        self.touch("dia.mp4", "me.mp4", "luz.png")
        g = GlossaryManager(self.dir)
        self.assertIsNotNone(g.get_sign_path("Días"))
        self.assertIsNotNone(g.get_sign_path("luces"))
        self.assertIsNone(g.get_sign_path("mes"))  # no debe caer en "me"

    def test_duplicates_prefer_video(self):
        self.touch("hola.png", "hola.mp4")
        g = GlossaryManager(self.dir)
        self.assertTrue(g.get_sign_path("hola").endswith("hola.mp4"))

    def test_subfolders_and_hidden(self):
        self.touch("saludos/hola.mp4", ".oculto/adios.mp4", ".DS_Store")
        g = GlossaryManager(self.dir)
        self.assertIn("hola", g)
        self.assertNotIn("adios", g)

    def test_phrase_and_spelling(self):
        self.touch("buenos_dias.mp4", "alfabeto/a.png", "alfabeto/n.png", "letra_y.png", "a.mp4")
        g = GlossaryManager(self.dir)
        out = g.resolve("¡Buenos días, Anay!")
        self.assertEqual([i.kind for i in out], ["sign", "letter", "letter", "letter", "letter"])
        self.assertEqual(out[0].text, "buenos dias")
        self.assertEqual([i.text for i in out[1:]], ["a", "n", "a", "y"])
        # "a" en la raíz es una palabra, no una letra
        self.assertEqual(g.resolve("a")[0].kind, "sign")

    def test_missing_letters_reported(self):
        self.touch("alfabeto/a.png", "alfabeto/b.png")
        g = GlossaryManager(self.dir)
        out = g.resolve("abz")
        self.assertEqual([i.kind for i in out], ["letter", "letter", "missing"])
        self.assertIn("ñ", g.missing_letters())
        self.assertNotIn("a", g.missing_letters())

    def test_aliases(self):
        self.touch("gracias.mp4")
        (self.dir / "aliases.json").write_text(
            json.dumps({"gracias": ["muchas gracias"], "inexistente": ["x"]}), encoding="utf-8")
        g = GlossaryManager(self.dir)
        self.assertEqual(g.get_sign_path("Muchas gracias"), g.get_sign_path("gracias"))

    def test_reload_and_missing_words(self):
        g = GlossaryManager(self.dir)
        self.assertEqual(len(g), 0)
        self.touch("hola.mp4")
        g.reload()
        self.assertEqual(g.missing_words(["hola", "adios"]), ["adios"])

    def test_missing_dir_not_created_when_disabled(self):
        ruta = self.dir / "no_existe"
        g = GlossaryManager(ruta, create_if_missing=False)
        self.assertFalse(ruta.exists())
        self.assertEqual(len(g), 0)


if __name__ == "__main__":
    unittest.main()