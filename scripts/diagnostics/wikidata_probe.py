import json
import urllib.parse
import urllib.request

UA = {"User-Agent": "icd11-eval/1.0 (local research)"}


def get(url: str) -> dict:
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    entity = get("https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q12156&props=claims&format=json")
    claims = entity["entities"]["Q12156"]["claims"]
    print("malaria Q12156 has ICD-related claims:", [pid for pid in claims if pid in ("P7807", "P494", "P557")])
    for pid in ("P7807", "P494"):
        if pid in claims:
            for statement in claims[pid][:3]:
                print(" ", pid, statement["mainsnak"].get("datavalue", {}).get("value"))

    query = """
    SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE {
      ?item wdt:P7807 ?code .
    }
    """
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query, "format": "json"})
    result = get(url)
    print("items with P7807:", result["results"]["bindings"])

    sample = """
    SELECT ?item ?itemLabel ?code WHERE {
      ?item wdt:P7807 ?code .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    } LIMIT 5
    """
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": sample, "format": "json"})
    for row in get(url)["results"]["bindings"]:
        print("sample", row["itemLabel"]["value"], "|", row["code"]["value"])


if __name__ == "__main__":
    main()
