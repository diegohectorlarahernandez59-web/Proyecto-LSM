from utils.glossary import Glossary
from utils.fingerspelling import FingerspellingHandler

class TextToSign:
    def __init__(self):
        self.glossary = Glossary()
        self.fingerspelling = FingerspellingHandler()

    def translate_glossses(self, gloss_list):
        """
        Toma una lista de glosas, busca su archivo visual asociado o prepara deletreo.
        """
        if not gloss_list:
            return []

        sign_sequence = []
        for gloss in gloss_list:
            asset_path = self.glossary.get_sign_asset(gloss)
            if asset_path:
                sign_sequence.append({
                    "type": "sign",
                    "gloss": gloss,
                    "asset": asset_path
                })
            else:
                # Respaldo: deletreo dactilológico letra por letra si no está en el glosario
                letters = self.fingerspelling.get_letters(gloss)
                sign_sequence.append({
                    "type": "fingerspelling",
                    "gloss": gloss,
                    "letters": letters
                })

        return sign_sequence