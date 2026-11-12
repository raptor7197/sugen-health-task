"""Clinical vocabulary normalisation shared by the index and the query.

Everything here is general medical terminology: spelling variation, standard
abbreviations, and lay synonyms for common conditions. Nothing is derived from the
labelled notes, so it transfers to unseen clinics rather than memorising them.
"""
from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

# Spelling variants are folded systematically instead of listed pairwise, so the same
# rule covers anaemia/anemia, oedema/edema, diarrhoea/diarrhea, tumour/tumor.
_FOLD_RULES: tuple[tuple[str, str], ...] = (
    ("ae", "e"),
    ("oe", "e"),
    ("our", "or"),
    ("yse", "yze"),
    ("ysed", "yzed"),
    ("isation", "ization"),
    ("ise", "ize"),
    ("ised", "ized"),
    ("ising", "izing"),
)

# Lay and historical names mapped to the term the MMS titles use.
SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("candidiasis", "thrush", "monilia", "moniliasis", "yeast"),
    ("haemorrhoid", "piles"),
    ("haemorrhoids", "piles"),
    ("zoster", "shingles"),
    ("varicella", "chickenpox", "chickenpox"),
    ("pertussis", "whooping cough"),
    ("rubella", "german measles"),
    ("rubeola", "measles"),
    ("parotitis", "mumps"),
    ("dermatophytosis", "ringworm", "tinea"),
    ("tinea", "ringworm"),
    ("mononucleosis", "glandular fever", "kissing disease"),
    ("tonsillitis", "tonsils"),
    ("pharyngitis", "sore throat"),
    ("nasopharyngitis", "common cold", "coryza"),
    ("sinusitis", "sinus"),
    ("otitis", "ear infection"),
    ("conjunctivitis", "red eye", "pink eye"),
    ("cystitis", "bladder infection", "waterworks"),
    ("pyelonephritis", "kidney infection"),
    ("pneumonia", "chest infection"),
    ("bronchitis", "chesty cough"),
    ("gastroenteritis", "gastro", "stomach flu", "diarrhoea and vomiting"),
    ("diarrhoea", "diarrhea", "loose stools"),
    ("constipation", "hard stools"),
    ("dyspepsia", "indigestion"),
    ("reflux", "heartburn", "gerd", "gord"),
    ("peptic", "pud", "ulcer"),
    ("cholecystitis", "gallbladder infection"),
    ("cholelithiasis", "gallstones"),
    ("appendicitis", "appendix"),
    ("hernia", "rupture"),
    ("haematuria", "blood in urine"),
    ("dysuria", "painful urination", "burning urine"),
    ("haemoptysis", "coughing blood"),
    ("epistaxis", "nosebleed", "nose bleed"),
    ("syncope", "fainting", "collapse"),
    ("seizure", "convulsion", "fits", "fitting"),
    ("epilepsy", "seizures"),
    ("migraine", "migraine headache"),
    ("tension", "stress headache"),
    ("hypertension", "htn", "high blood pressure", "raised bp"),
    ("hypotension", "low blood pressure"),
    ("diabetes", "dm", "sugar disease", "sugar"),
    ("hypoglycaemia", "hypoglycemia", "low sugar", "hypo"),
    ("hyperglycaemia", "high sugar"),
    ("thyrotoxicosis", "hyperthyroidism", "overactive thyroid"),
    ("hypothyroidism", "underactive thyroid", "myxoedema", "myxedema"),
    ("goitre", "goiter", "enlarged thyroid"),
    ("anaemia", "anemia", "low haemoglobin", "low hb", "low blood"),
    ("malaria", "malariae"),
    ("tuberculosis", "tb", "ptb", "kochs"),
    ("hiv", "human immunodeficiency virus"),
    ("syphilis", "chancre"),
    ("gonorrhoea", "gonorrhoea", "gonorrhea", "clap"),
    ("chlamydia", "chlamydial"),
    ("trichomoniasis", "trichomonas"),
    ("herpes", "herpes"),
    ("warts", "verruca", "verrucae"),
    ("scabies", "itch mite"),
    ("pediculosis", "lice", "head lice"),
    ("dengue", "breakbone fever"),
    ("typhoid", "enteric fever"),
    ("cholera", "cholera"),
    ("malnutrition", "undernutrition", "wasting"),
    ("obesity", "overweight", "obese"),
    ("dysmenorrhoea", "dysmenorrhea", "period pain", "menstrual pain", "painful periods"),
    ("menorrhagia", "heavy periods", "heavy menstrual bleeding"),
    ("amenorrhoea", "amenorrhea", "no periods"),
    ("menopause", "menopausal"),
    ("preeclampsia", "pre eclampsia", "pre-eclampsia", "pre eclamptic"),
    ("eclampsia", "eclamptic"),
    ("abortion", "miscarriage"),
    ("pregnancy", "gravid", "antenatal", "pregnant"),
    ("labour", "labor"),
    ("prostatitis", "prostate infection"),
    ("bph", "benign prostatic hyperplasia", "enlarged prostate"),
    ("osteoarthritis", "oa", "wear and tear arthritis"),
    ("rheumatoid", "ra"),
    ("gout", "podagra", "urate"),
    ("osteoporosis", "brittle bones"),
    ("fracture", "broken bone"),
    ("sprain", "twisted"),
    ("dermatitis", "eczema"),
    ("psoriasis", "psoriatic"),
    ("urticaria", "hives", "nettle rash"),
    ("cellulitis", "skin infection"),
    ("abscess", "boil", "pus collection"),
    ("impetigo", "school sores"),
    ("molluscum", "water warts"),
    ("melanoma", "skin cancer"),
    ("cataract", "cloudy lens"),
    ("glaucoma", "raised eye pressure"),
    ("otitis externa", "swimmer ear"),
    ("vertigo", "dizziness", "spinning"),
    ("insomnia", "cannot sleep"),
    ("depression", "depressive", "low mood"),
    ("anxiety", "anxious", "panic"),
    ("psychosis", "psychotic"),
    ("dementia", "memory loss"),
    ("stroke", "cva", "cerebrovascular"),
    ("ischaemic", "ischemic"),
    ("infarction", "infarct"),
    ("angina", "chest tightness on exertion"),
    ("fibrillation", "af", "irregular pulse"),
    ("failure", "insufficiency"),
    ("thrombosis", "clot", "dvt"),
    ("embolism", "embolus"),
    ("sepsis", "septicaemia", "septicemia", "blood poisoning"),
    ("shock", "hypoperfusion"),
    ("dehydration", "dry"),
    ("fever", "pyrexia", "febrile", "temperature"),
    ("cough", "tussis"),
    ("dyspnoea", "dyspnea", "breathlessness", "shortness of breath", "sob"),
    ("tachycardia", "fast pulse", "rapid pulse"),
    ("bradycardia", "slow pulse"),
    ("oedema", "edema", "swelling", "swollen"),
    ("pruritus", "itching", "itchy"),
    ("erythema", "redness", "red"),
    ("vomiting", "emesis", "vomit"),
    ("nausea", "nauseated"),
    ("headache", "cephalgia"),
    ("arthralgia", "joint pain"),
    ("myalgia", "muscle pain", "body aches"),
    ("malaise", "lethargy", "fatigue", "tiredness"),
    ("weight loss", "losing weight"),
    ("lymphadenopathy", "enlarged lymph nodes", "swollen glands"),
    ("splenomegaly", "enlarged spleen"),
    ("hepatomegaly", "enlarged liver"),
    ("jaundice", "yellow eyes", "yellow skin"),
    ("ascites", "abdominal fluid"),
    ("dysphagia", "difficulty swallowing"),
    ("haematemesis", "vomiting blood"),
    ("melena", "melaena", "black stools"),
)

# Standard clinical abbreviations that are unambiguous enough to expand safely.
ABBREVIATIONS: dict[str, str] = {
    "urti": "upper respiratory tract infection",
    "uri": "upper respiratory tract infection",
    "uti": "urinary tract infection",
    "luti": "lower urinary tract infection",
    "t2dm": "type 2 diabetes mellitus",
    "t1dm": "type 1 diabetes mellitus",
    "dm": "diabetes mellitus",
    "htn": "hypertension",
    "cap": "community acquired pneumonia",
    "copd": "chronic obstructive pulmonary disease",
    "gerd": "gastro oesophageal reflux disease",
    "gord": "gastro oesophageal reflux disease",
    "pud": "peptic ulcer disease",
    "pid": "pelvic inflammatory disease",
    "dvt": "deep vein thrombosis",
    "pe": "pulmonary embolism",
    "af": "atrial fibrillation",
    "ckd": "chronic kidney disease",
    "aki": "acute kidney injury",
    "cva": "stroke",
    "ihd": "ischaemic heart disease",
    "mi": "myocardial infarction",
    "hf": "heart failure",
    "ccf": "congestive cardiac failure",
    "tb": "tuberculosis",
    "ptb": "pulmonary tuberculosis",
    "sti": "sexually transmitted infection",
    "pph": "postpartum haemorrhage",
    "gdm": "gestational diabetes mellitus",
    "bph": "benign prostatic hyperplasia",
    "mps": "malaria parasite smear",
    "mrdt": "malaria rapid diagnostic test",
}


def _fold(token: str) -> str:
    for source, target in _FOLD_RULES:
        if source in token:
            token = token.replace(source, target)
    if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "is", "us", "ics")):
        token = token[:-1]
    return token


_SYNONYM: dict[str, str] = {}
for group in SYNONYM_GROUPS:
    canonical = _fold(TOKEN_RE.findall(group[0])[0]) if TOKEN_RE.findall(group[0]) else group[0]
    for term in group:
        for piece in TOKEN_RE.findall(term):
            _SYNONYM.setdefault(_fold(piece), canonical)


def canonical_tokens(text: str) -> list[str]:
    """Lower-case, fold spelling, expand abbreviations, and map to canonical terms."""
    lowered = text.lower()
    expanded = lowered
    for abbreviation, full in ABBREVIATIONS.items():
        expanded = re.sub(rf"\b{re.escape(abbreviation)}\b", f" {full} ", expanded)
    tokens: list[str] = []
    for token in TOKEN_RE.findall(expanded):
        folded = _fold(token)
        tokens.append(_SYNONYM.get(folded, folded))
    return tokens
