"""Check non-english behaviour: ten dev notes hand-translated into spanish.

Gold codes are unchanged, so this is a direct read on the generalisation slice, which the
brief says is "not always in english". Not part of the official scorer.
"""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coder.catalog import Catalogue
from coder.engine import Coder

ROOT = Path(__file__).resolve().parents[1]
MMS = ROOT / "public/data/mms-2026-01.json"
TERMS = ROOT / "data/icd11_terms.json.gz"

TRANSLATED = [
    ("dev-001", ["1F40.Z"],
     "S: varón de 28 años, motorista de boda, refiere fiebre con escalofríos y tiritona de 3 días "
     "de evolución, cefalea frontal, dolores generalizados y poco apetito. No vómitos, no "
     "convulsiones, no confusión. Sin tos. O: alerta, T 38.9, FC 104, TA 118/76, FR 18, SatO2 98%. "
     "No pálido, sin ictericia. Punta esplénica palpable. Ix: gota gruesa positiva para "
     "P. falciparum trofozoítos. Diagnóstico: malaria falciparum no complicada."),
    ("dev-003", ["CA23.30"],
     "Paciente: mi pecho está apretado desde anoche, tengo sibilancias y el inhalador ya no me "
     "ayuda como antes. Médico: asma desde la infancia. La saturación es del noventa y cuatro por "
     "ciento, sibilancias bilaterales, flujo espiratorio al sesenta por ciento. Es una crisis "
     "asmática moderada. Damos salbutamol nebulizado con ipratropio y prednisolona cuarenta "
     "miligramos cinco días."),
    ("dev-004", ["1A07.Z"],
     "Mujer de 24 años, profesora. Fiebre de 10 días, tratada de malaria hace una semana sin "
     "mejoría. Fiebre en meseta, cefalea, molestia abdominal, estreñimiento, anorexia. "
     "Temperatura 39.2, bradicardia relativa, lengua saburral, abdomen blando doloroso. "
     "Hemocultivo: Salmonella Typhi. Diagnóstico: fiebre entérica, tifoidea confirmada por cultivo."),
    ("dev-005", ["1F23.10"],
     "Mujer de 27 años con picor vulvar y flujo blanco espeso como requesón de cinco días, "
     "terminó amoxicilina la semana pasada por amigdalitis. Eritema vulvar, placas blancas en la "
     "pared vaginal, sin olor. Diagnóstico: candidiasis vaginal. Óvulo de clotrimazol y fluconazol."),
    ("dev-006", ["1E90.0"],
     "Médico: hola mamá, qué le pasa a la niña. Paciente: tiene seis años, manchas pequeñas que "
     "pican desde ayer, empezaron en la barriga y la espalda, algunas con agua dentro. Fiebre leve "
     "ayer. Hay lesiones en distintos estadios, algunas costras. Esto es varicela, sin "
     "complicaciones. Calamina y antihistamínico, no dar ibuprofeno, no ir al colegio hasta que "
     "todas las lesiones tengan costra."),
    ("dev-007", ["CA40.Z"],
     "Varón de 55 años, hipertenso en tratamiento con amlodipino, tos productiva de cinco días, "
     "fiebre, dolor torácico pleurítico derecho, disnea de esfuerzo. T 38.4, FR 26, SatO2 92%, "
     "crepitantes en base derecha, broncofonía. Radiografía: opacidad en lóbulo inferior derecho. "
     "Diagnóstico: neumonía adquirida en la comunidad, lóbulo inferior derecho. Amoxicilina más "
     "azitromicina."),
    ("dev-019", ["1D80.0"],
     "Niño de 11 años con tumefacción dolorosa bilateral de la mejilla delante de las orejas de "
     "dos días, fiebre, dolor al masticar. No vacunado contra la parotiditis. Testículos normales, "
     "sin rigidez de nuca, abdomen blando. Diagnóstico: parotiditis epidémica. Paracetamol, dieta "
     "blanda, aislamiento escolar."),
    ("dev-033", ["FA25.2Z"],
     "Varón de 55 años con dolor súbito intenso e inflamación del primer dedo del pie, le despertó "
     "a las tres de la mañana tras una boda con carne y cerveza. Primera articulación "
     "metatarsofalángica roja, caliente, muy dolorosa. Ácido úrico 9.1 mg/dl. Impresión: gota "
     "aguda del primer dedo. Colchicina, indometacina con omeprazol, hielo, dieta."),
    ("dev-041", ["5A11"],
     "Varón de 52 años. Refiere poliuria, nicturia tres veces por noche y sed excesiva de dos "
     "meses, pérdida de seis kilos. Sin dolor abdominal, sin vómitos. Madre diabética. IMC 29.4, "
     "TA 128/82, sin aliento cetónico. Glucemia en ayunas 9.8 y 10.4 mmol/L, HbA1c elevada. "
     "Diagnóstico: diabetes mellitus tipo 2."),
    ("dev-005", ["1F23.10"],
     "Paciente de 27 años, consulta por prurito vaginal y leucorrea blanca grumosa. Antecedente de "
     "amigdalitis tratada con antibiótico. Al examen: eritema vulvar y placas blanquecinas. "
     "Impresión diagnóstica: candidiasis vulvovaginal."),
]


def evaluate(terms, label: str) -> None:
    catalogue = Catalogue.load(MMS)
    coder = Coder(catalogue, terms=terms)
    top1 = top3 = 0
    for note_id, gold, text in TRANSLATED:
        codes, _ = coder.predict(text)
        gold_set = set(gold)
        top1 += bool(codes and codes[0] in gold_set)
        top3 += bool(gold_set & set(codes[:3]))
    n = len(TRANSLATED)
    print(f"{label:18s} spanish top1={top1}/{n} ({top1/n:.2f}) top3={top3}/{n} ({top3/n:.2f})")


def main() -> None:
    with gzip.open(TERMS, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)
    terms = payload["codes"]
    print("languages in artefact:", payload.get("languages"))

    evaluate(None, "no terminology")
    evaluate(terms, "multilingual")


if __name__ == "__main__":
    main()
