# Realia deploya: Caddy vs Docker vs Nginx

Kiedy czego używać. Realne koszty. Bez abstrakcji.

## Nginx

**Co to jest:** Wiekowy, szybki, sprawdzony w boju reverse proxy i serwer WWW. Obsługuje miliony równoczesnych połączeń.
Standard devops.

**Jak to skonfigurować:**

1. Wynajmij VPS ($5–20/miesiąc).
2. `apt-get install nginx`
3. Napisz pliki konfiguracyjne w `/etc/nginx/sites-available/`
4. Skonfiguruj certyfikat Let's Encrypt: `certbot --nginx`
5. Aktualizacje ogarniaj sam.

**Realny koszt:**

- Oprogramowanie: Darmowe.
- Twój czas tygodniowo: 30 min–2 h (rotacja logów, odnawianie certyfikatów, łatki bezpieczeństwa, poprawki konfiguracji).
- Serwer: $5–100/miesiąc w zależności od ruchu.

**Najlepsze do:**

- Zespołów z osobą od ops.
- Usług o dużym ruchu, gdzie trzeba wycisnąć każdą milisekundę.
- Sytuacji, gdy już to znasz i działa.

**Dlaczego nie:**

- Konfiguracja jest ręczna, powtarzalna.
- Składnia konfiguracji jest zawiła (ale do nauczenia).
- Zarządzanie certyfikatami to jeszcze jedna rzecz, której nie wolno spartolić.

**Skala:** tysiące–dziesiątki tysięcy równoczesnych połączeń na serwer.

---

## Docker

**Co to jest:** Runtime kontenerów. Odtwarzalny deployment. Twoja aplikacja + zależności = jeden obraz. Gwarantowane działanie tak
samo wszędzie.

**Jak to skonfigurować:**

1. Napisz Dockerfile.
2. Przetestuj lokalnie: `docker build . && docker run -p 8080:3000 myimage`
3. Wypchnij do rejestru (Docker Hub, ECR itp.): `docker push myimage:v1.0`
4. Na serwerze docelowym: `docker pull myimage:v1.0 && docker run -d myimage:v1.0`
5. Orkiestruj przez Compose (pojedynczy serwer) lub Kubernetes (wiele serwerów).

**Realny koszt:**

- Oprogramowanie: Darmowe.
- Rejestr (Docker Hub): Darmowy tier lub $5–20/miesiąc za prywatne repozytoria.
- Compute: Cokolwiek, na czym to uruchamiasz. Tak samo jak bez Dockera.
- Twój czas tygodniowo: 30 min (deploye są szybkie, ale infrą zarządzasz sam).

**Najlepsze do:**

- Zespołów dowożących szybko, zmieniających cele deployu.
- Myślenia cloud-native (AWS, GCP, Heroku, Railway).
- Sytuacji, gdy chcesz zero dryfu konfiguracji między dev a prod.

**Dlaczego nie:**

- Krzywa uczenia jest realna (Dockerfile, compose, rejestry).
- Dokłada warstwę abstrakcji, gdy wszystko jest w porządku na jednym VPS.

**Skala:** setki–setki tysięcy równoczesnych połączeń w obrębie klastra.

---

## Caddy

**Co to jest:** Nowoczesny serwer HTTP. Automatyczny HTTPS. Minimalna konfiguracja. Wbudowany reverse proxy. Pojedynczy plik binarny, bez
zależności.

**Jak to skonfigurować:**

1. Pobierz plik binarny z caddyserver.com
2. Napisz Caddyfile (zwykle 3–10 linii): example.com reverseproxy localhost:3000
3. Uruchom: `caddy run`
4. Certyfikaty pojawiają się automatycznie przez Let's Encrypt.

**Realny koszt:**

- Oprogramowanie: Darmowe.
- Twój czas tygodniowo: 5–10 min (prawie nic).
- Serwer: $5–20/miesiąc w zależności od ruchu.

**Najlepsze do:**

- Projektów solo, MVP, projektów hobbystycznych.
- Nowych zespołów, które jeszcze nie nauczyły się ops.
- Podejścia „po prostu niech działa" z HTTPS i nie myśl o tym więcej.

**Dlaczego nie:**

- Nie sprawdzony w boju w skali Netfliksa (ale w porządku przy 10000 równoczesnych).
- Mniej pluginów/modułów niż Nginx.
- Mniej wiedzy ops w społeczności.

**Skala:** tysiące–dziesiątki tysięcy równoczesnych połączeń na serwer. W porządku do prawie wszystkiego, dopóki nie staniesz się Duży.

---

## Szybkie drzewo decyzyjne

```
Are you shipping an MVP or hobby project?
  → Yes → Caddy. 5 minutes, done.
  → No → Next question.

Do you have a dedicated ops/DevOps person?
  → Yes → Nginx or Kubernetes. Use what they know.
  → No → Next question.

Do you expect to scale across multiple servers/clouds?
  → Yes → Docker + Kubernetes (if your team can support it) or Docker + single cloud's managed container service.
  → No → Next question.

Do you already know Nginx?
  → Yes → Use Nginx. It works.
  → No → Use Caddy. Simpler.
```

---

## Przykłady ze świata rzeczywistego

**Produkt SaaS, 10 klientów, jeden serwer:**

- Caddy + VPS. Dowieź kod, zaktualizuj Caddyfile raz, uruchom `caddy reload`. Gotowe.
- Koszt: $15/miesiąc serwer + twój czas.
- Czas decyzji: 2 godziny.

**Biblioteka open-source z CI/CD:**

- Obraz Dockera na GitHub Actions → Docker Hub lub ghcr.io.
- Użytkownicy pullują i uruchamiają. Ty skupiasz się na kodzie.
- Koszt: Darmowy tier wystarcza.
- Czas decyzji: 4 godziny.

**API o dużym ruchu, skalujące się w wielu chmurach:**

- Kontenery Dockera na ECS/GKE/Kubernetes.
- Kontroler ALB/Ingress obsługuje routing.
- Nginx wewnątrz kontenerów, jeśli potrzebujesz drobnoziarnistej kontroli.
- Koszt: $100–1000+/miesiąc w zależności od ruchu.
- Czas decyzji: tygodnie (potrzebujesz wiedzy ops/infra).

**Narzędzie wewnętrzne, mały zespół:**

- Caddy jako reverse proxy do wielu usług backendowych.
- Pojedynczy VPS lub mały klaster Kubernetes.
- Koszt: $20–50/miesiąc.
- Czas decyzji: 1 dzień.

---

## Prawdziwe pytanie

**Ile złożoności ops jesteś gotów wziąć na siebie?**

- **0%:** Caddy lub static hosting (Vercel, Netlify).
- **30%:** Docker Compose na VPS.
- **70%:** Nginx na VPS z monitoringiem.
- **100%:** Kubernetes w wielu chmurach.

Wybierz poziom, który zdołasz utrzymać. Zepsuty deployment boli bardziej niż powolny deployment.

---

## Inwentarz wyeksponowanej powierzchni

Raport release'u musi zadeklarować każdą publiczną powierzchnię, którą produkt
eksponuje. To nie jest metachecklist; to faktyczny artefakt, który recenzent
AppSec, Semgrepa lub platformy przeczyta jako pierwszy.

Dla każdej usługi, którą release dowozi, uchwyć:

- **Proces** — nazwa (`api`, `worker`, `admin` itp.) oraz użytkownik runtime'u,
  jako który się wykonuje.
- **Adres bind** — `127.0.0.1` to wartość domyślna. Każde `0.0.0.0` to
  decyzja i musi się uzasadnić na piśmie.
- **Port** — dokładna liczba całkowita, nie „ten zwykły". Udokumentuj konflikty z
  innymi usługami na tym samym hoście.
- **Publiczny?** — tak lub nie. Usługi tylko wewnętrzne nie mogą być osiągalne
  z internetu.
- **Proxy z przodu** — Caddy, Nginx, cloudowy load balancer lub `none`.
  `none` dla usługi publicznej to czerwona flaga.
- **Terminator TLS** — proxy, aplikacja lub żaden. TLS terminowany w aplikacji tylko, gdy
  jest po temu powód; w przeciwnym razie terminuj na proxy.
- **Granica uwierzytelniania** — public, session cookie, bearer token, mTLS lub
  żadna. Skonfrontuj to z mapą route'ów; powierzchnia `admin` oznaczona jako
  `none` to kanoniczna pułapka.
- **Nagłówki brzegowe** — co proxy dodaje (`HSTS`, `CSP`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, allowlista CORS) i co
  zdejmuje. Ciche dziedziczenie domyślnych ustawień frameworka to nie opis.
- **Materializacja sekretu** — jak każdy sekret trafia do runtime'u: wstrzyknięcie env
  przy starcie, pobranie z menedżera sekretów, init-container lub żaden.
  Sekrety wpieczone w obrazy są niedozwolone.

Wzorce czerwonych flag, które inwentarz musi jawnie zanegować:

- powierzchnia admin lub debug zbindowana publicznie przez przypadek
- publiczna usługa na `:3000` / `:5173` / `:8000` bez proxy i TLS
- `CORS: *` na uwierzytelnionym API
- stacktrace'y lub bannery frameworka osiągalne z publicznego internetu
- pliki `.env` lub backupy serwowane przez statyczny handler
- sekrety obecne w artefaktach builda (`docker history`, `npm pack`, sdist)

Jeśli tabela zawiera wiersz, którego operator nie potrafi uzasadnić, deployment
nie jest gotowy. Wycofaj go, nie pchaj naprzód.
