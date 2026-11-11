import json
import urllib.error
import urllib.request

UA = {
    "User-Agent": "icd11-eval/1.0",
    "Accept": "application/json",
    "Accept-Language": "en",
}
URLS = [
    "https://id.who.int/icd/release/11/mms/257068234",
    "https://id.who.int/icd/entity/1439886552",
    "https://icd.who.int/browse11/l-m/en",
]


def main() -> None:
    for url in URLS:
        request = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                body = response.read(4000).decode("utf-8", "replace")
                print(f"{url} -> {response.status} {response.headers.get('content-type')}")
                print(body[:400].replace("\n", " "))
        except urllib.error.HTTPError as error:
            print(f"{url} -> HTTP {error.code} {error.reason}")
            try:
                print(error.read(300).decode("utf-8", "replace").replace("\n", " "))
            except Exception:
                pass
        except Exception as error:
            print(f"{url} -> {type(error).__name__}: {error}")
        print("-" * 60)


if __name__ == "__main__":
    main()
