# Checklist release'u: mechanika krok po kroku

Korzystaj z tego. Nie pomijaj kroków. Użytkownicy znajdą każde pominięcie.

## Przed release'em (24 h wcześniej)

- [ ] **Numer wersji ustalony.** Wersjonowanie semantyczne: MAJOR.MINOR.PATCH. Czy to zmiana łamiąca? (MAJOR) Nowa
      funkcja? (MINOR) Poprawka błędu? (PATCH)
- [ ] **Changelog napisany.** Uwzględnij: co się zmieniło, dlaczego, zmiany łamiące pogrubione, ścieżkę migracji, jeśli potrzebna.
- [ ] **Wszystkie testy przechodzą.** `npm test`, `cargo test`, `pytest` — cokolwiek używa twój stack. Zielono w CI/CD.
- [ ] **Kod zreviewowany.** Druga para oczu na istotnych zmianach.
- [ ] **Zależności zaktualizowane i zaudytowane.** `npm audit`, `cargo audit` lub odpowiednik. Przypnij zależności krytyczne dla bezpieczeństwa.
- [ ] **README zgodne z rzeczywistością.** Quickstart wciąż działa. Przykłady wciąż się uruchamiają. Linki nie dają 404.
- [ ] **Plik LICENSE istnieje i jest poprawny.** MIT, Apache 2.0, GPL lub własny. Wybierz jeden i się go trzymaj.
- [ ] **SECURITY.md istnieje.** E-mail do zgłaszania podatności, oczekiwany czas reakcji, harmonogram disclosure.
- [ ] **Docs zbudowane i działające.** Wszystkie linki się rozwiązują. Żadnych zepsutych obrazków. Docs API wygenerowane.

## Dzień release'u (1–2 godziny)

- [ ] **Podbij wersję w plikach źródłowych.** `package.json`, `Cargo.toml`, `setup.py`, plik wersji — cokolwiek używa twój język.
      Dokładnie jedno źródło prawdy.
- [ ] **Zbuduj artefakty.** Skompiluj, zbundluj, stwórz dystrybuowalne. Plik binarny, wheel, JAR, obraz Dockera — cokolwiek.
- [ ] **Przetestuj artefakt lokalnie.** Zainstaluj go na zimno z artefaktu, nie ze źródła. Czy działa?
- [ ] **Zacommituj podbicie wersji.** Komunikat commita: "Release v1.2.3" (jasny, minimalny).
- [ ] **Otaguj commit.** `git tag -a v1.2.3 -m "Release 1.2.3"` (tagi anotowane, nie lightweight).
- [ ] **Wypchnij commit i tag.** `git push origin main && git push origin v1.2.3`

## Publikacja (30 minut)

**Jeśli paczka npm:**

- [ ] `npm publish`
- [ ] Zweryfikuj w rejestrze npm: https://www.npmjs.com/package/@yourorg/yourpkg
- [ ] Pojawienie się zajmuje ~30 s. Poczekaj i sprawdź.

**Jeśli crate Rusta:**

- [ ] `cargo publish`
- [ ] Zweryfikuj na crates.io. Zajmuje 1–5 minut.

**Jeśli paczka Pythona:**

- [ ] Zbuduj: `python -m build`
- [ ] Wgraj: `twine upload dist/*`
- [ ] Zweryfikuj na PyPI.

**Jeśli obraz Dockera:**

- [ ] Zbuduj: `docker build -t yourorg/yourimage:v1.2.3 .`
- [ ] Otaguj latest: `docker tag yourorg/yourimage:v1.2.3 yourorg/yourimage:latest`
- [ ] Wypchnij: `docker push yourorg/yourimage:v1.2.3 && docker push yourorg/yourimage:latest`
- [ ] Zweryfikuj w rejestrze.

**Jeśli GitHub Release:**

- [ ] Wejdź w zakładkę Releases.
- [ ] Kliknij "Draft a new release."
- [ ] Wybierz tag: v1.2.3
- [ ] Tytuł: "Release 1.2.3"
- [ ] Opis: Skopiuj z changeloga. Uwzględnij najważniejsze punkty, zmiany łamiące, ścieżkę migracji.
- [ ] Dołącz pliki binarne, jeśli potrzebne (prebuildowane dla typowych platform).
- [ ] Opublikuj.

## Weryfikacja po release'ie (natychmiast)

- [ ] **Użytkownicy potrafią zainstalować z opublikowanego źródła.** Zrób to sam, na zimno, od zera:
  - `npm install @yourorg/yourpkg` z nowego katalogu
  - `cargo add yourpkg`
  - `pip install yourpkg`
  - `docker run yourimage:v1.2.3 --help`
- [ ] **Strona dokumentacji jest zdeployowana i poprawna.** Docs linkują do nowej wersji, przykłady używają nowego API.
- [ ] **Quickstart w README działa.** Wykonaj go dokładnie. Jeśli utkniesz, popraw docs.
- [ ] **Notatki release'u są widoczne.** Strona GitHub Releases pokazuje twój release z opisem.

## Go-to-market (2–6 godzin)

- [ ] **Changelog opublikowany.** Na twojej stronie, w GitHub Releases lub w obu.
- [ ] **Ogłoszenie na Twitterze/X.** Hook + link do notatek release'u. Otaguj odpowiednie społeczności.
- [ ] **Lista mailingowa powiadomiona** (jeśli ją masz). Krótka informacja o podbiciu wersji z najważniejszymi punktami.
- [ ] **Kanały społeczności.** Odpowiednie Discord, Slack, fora, subreddity. Jeden post, nie spam.
- [ ] **Komunikacja wewnętrzna/zespołowa.** Wrzuć ship post na swoim workspace. Świętuj release.

## Tydzień po release'ie

- [ ] **Monitoruj issues/zgłoszenia.** Napraw krytyczne błędy w patchu v1.2.4 natychmiast.
- [ ] **Pętla feedbacku od użytkowników.** Czy ktoś zgłosił problemy? Czy skorzystali z funkcji?
- [ ] **Zweryfikuj, że docs są dokładne.** Sprawdź feedback, że docs nie zgadzają się z rzeczywistością.
- [ ] **Zaplanuj następny release.** Refinement backlogu, priorytetyzacja kolejnej pracy.

---

## Częste błędy (nie rób tego)

- **Zapomnienie o wypchnięciu tagów.** Zrobiłeś release lokalnie. Nikt inny tego nie widzi. `git push origin v1.2.3`
- **Publikacja do złego rejestru.** Wersja płatna na darmowym tierze albo na odwrót. Sprawdź swoją konfigurację.
- **Zepsute docs w notatkach release'u.** Literówki, martwe linki, nieaktualne przykłady. Użytkownicy widzą to jako pierwsze.
- **Brak changeloga.** Użytkownicy nie wiedzą, co się zmieniło ani czy ich to dotyczy. Poświęć 20 minut. Warto.
- **Release bez testowania artefaktu.** Przetestowałeś kod źródłowy. Artefakt jest inny. Przetestuj go.
- **Zapomnienie o aktualizacji wersji wszędzie.** package.json, ale nie version.ts. Każdego myli.
- **Brak ogłoszenia.** Cichy ship = brak adopcji. Powiedz ludziom.

---

## Szablon: ogłoszenie release'u

```
Version X.Y.Z is live.

Highlights:
- Feature A: [one sentence, why it matters]
- Feature B: [one sentence, why it matters]
- Fixes: [list of major bugs fixed]

Breaking changes:
- Old API removed. Use NewAPI instead. [link to migration guide]

Thanks to [contributors]. Download from [link to release].

Feedback? Open an issue on GitHub.
```

Wrzuć to na Twittera, e-mail, GitHub Releases, Hacker News, swojego bloga. Dostosuj długość do platformy.
