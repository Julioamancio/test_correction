import sys

# Diagnóstico automático de dependência
try:
    from spellchecker import SpellChecker
except ImportError:
    print("❌ O pacote 'pyspellchecker' não está instalado no seu ambiente.")
    print("🔧 Solucione com: pip install pyspellchecker")
    sys.exit(1)

def corrigir_texto(texto):
    spell = SpellChecker(language="pt")
    palavras = texto.split()
    palavras_corrigidas = []
    for palavra in palavras:
        palavra_corrigida = spell.correction(palavra)
        if palavra_corrigida is None:
            palavra_corrigida = palavra
        palavras_corrigidas.append(palavra_corrigida)
    return " ".join(palavras_corrigidas)

if __name__ == "__main__":
    texto_ocr = "Sex tópico me. lembrou o garato. Toby Little,"
    print("🔍 Texto original:", texto_ocr)
    print("✅ Texto corrigido:", corrigir_texto(texto_ocr))