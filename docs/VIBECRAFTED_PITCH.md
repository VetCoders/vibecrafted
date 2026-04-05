## Vibecrafted. — a framework that created itself

### Opis narzędzia

**Co to jest:**
Vibecrafted. to framework konwergencji dla AI-assisted software development. Nie pisze kodu za ciebie. Daje ci **system
** w którym kod pisany przez AI jest systematycznie doprowadzany do jakości produkcyjnej — przez zamknięte pętle
weryfikacji, strukturalne narzędzia analityczne, i multi-agentową orkiestrację.

**Differentiator:**
Każdy inny tool mówi: "AI napisze ci kod." **Vibecrafted.** mówi: "AI napisze ci kod, **a potem udowodni że jest dobry —
albo poprawi aż będzie.**" To nie jest obietnica inteligencji. To jest obietnica **procesu** który konwerguje do jakości
niezależnie od tego jak dobry lub zły był pierwszy draft.

**Proof of concept:**
Framework sam siebie zbudował. Swoje skille, swój installer, swój pipeline CI, swoją stronę, swoją dokumentację, swoje
kanały dystrybucji. Meta-rekurencyjnie. Jeśli potrafi zbudować siebie — potrafi zbudować twoje narzędzie.

**Co dostajesz:**

| Warstwa            | Narzędzie                           | Co robi                                                                                                                                |
| ------------------ | ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Zmysły**         | Loctree                             | Strukturalna analiza codebase — dead code, cykle, zależności, blast radius. Agent nie zgaduje architektury — czyta ją.                 |
| **Orientacja**     | vc-init                             | Trzy zmysły przed działaniem: pamięć (co robiono wcześniej), wzrok (stan kodu teraz), prawda (czy narzędzia działają).                 |
| **Konwergencja**   | vc-marbles                          | Pętla "co jest jeszcze źle?" — eliminuj kontrprzykłady, obserwuj kaskadę, powtarzaj aż koło się zamknie. Solo, duo, trio, multi-agent. |
| **Orkiestracja**   | vc-agents                           | Spawn agentów (Claude, Codex, Gemini) w terminalu, headless, background. Z raportami, transkryptami, meta-danymi.                      |
| **Jakość**         | vc-followup, vc-dou                 | Followup bada co poszło nie tak. DoU (Definition of Undone) mierzy co jeszcze nie jest gotowe do shipowania.                           |
| **Ship**           | vc-decorate, vc-hydrate, vc-release | Od kodu do produktu: branding, packaging, dystrybucja.                                                                                 |
| **Bezpieczeństwo** | rust-ai-locker                      | Resource locking — dwa agenty nie crashują systemu jednoczesną kompilacją.                                                             |

### Kampania

**Hook:** _"A framework that created itself."_

To jest hook który działa na trzech poziomach:

1. **Ciekawość** — jak framework może sam siebie stworzyć?
2. **Dowód** — jeśli to działa na sobie, zadziała na twoim projekcie
3. **Prowokacja** — stawia pytanie o naturę AI-assisted development

**Narratyw główny:**

> Dwa lata temu dwoje weterynarzy z Polski rozpoczęło jednosemestrowy kurs postgraduate:
> _"**AI in Health Care: From Strategies to Implementation**"_ w **Harvard Medical School**.
>
> W trakcie jego trwania postanowili stworzyć aplikację wspierającą lekarzy weterynarii w codziennej pracy — narzędzie
> poprawiające jakość obrazów USG dzięki mocy algorytmów sztucznej inteligencji.
>
> Nie mieli doświadczenia w programowaniu. Mieli biznesową wizję, pasję oraz silne postanowienie, że zbudują tę
> aplikację samodzielnie przy pomocy AI.
>
> To, co na pierwszy rzut oka wydawało się zadaniem nie do zrobienia, okazało się... \*zadaniem **nie do zrobienia\***.
> Ale to nie pozbawiło ich upartości.
>
> Wtedy nadeszła Era Agentów AI o niedostępnych wcześniej możliwościach. Razem z nimi zaczęli tworzyć zestaw narzędzi i
> promptów, który nareszcie zaczął przynosić efekty: **działający kod** i **produkt**, który zaczął przyjmować realne
> kształty.
>
> Niestety, uderzyli w kolejny mur. Aplikacja stała się bardziej zaawansowana niż początkowo przewidywali. Baza kodu
> rozrosła się do rozmiarów, w których agenci po prostu się gubili. Zamiast budować, zaczęli halucynować — dopisywali
> setki linijek zbędnego kodu tylko po to, by utrzymać funkcjonalności, które wcześniej działały bez problemu.
>
> Upartość w dążeniu do celu jednak pozostała. Musiała tylko zmienić formę.
>
> Zamiast prosić AI o pisanie kolejnych rozwiązań, doszli do momentu, w którym na koniec dnia zadawali tylko jedno
> pytanie, powtarzane w nieskończoność: _"**Co jest jeszcze źle?!**"_
>
> Z tej frustracji narodziła się nowa metodologia. Metodologia wymusiła system twardych zasad weryfikacji. A gdy ten
> bezwzględny system spotkał zyskujące na sile Agenty AI... sprzężenie zwrotne wymknęło się z ram zwykłego narzędzia.
>
> Tak powstał framework, który zaczął rozbudowywać sam siebie — swoje narzędzia, swój installer, swoją stronę, swoje
> kanały dystrybucji.
>
> Teraz sprawdź, co może zbudować dla ciebie.

**Target audiences i messaging:**

| Audience           | Pain point                                                | Message                                                                                                    |
| ------------------ | --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Founder-coder**  | "AI generuje bałagan którego się boję shipować"           | "Vibecrafted. daje ci pętlę konwergencji — agent naprawia dopóki nie skończą się zarzuty"                  |
| **Sceptyczny dev** | "AI coding to hype, nie działa na real projects"          | "Agent nie zgaduje — jest spięty z kompilatorem i lintami. Nie rozwali ci projektu."                       |
| **Startup team**   | "Musimy shipować szybko ale nie możemy zbierać tech debt" | "Multi-agent convergence: 3 agenty, 3 perspektywy, 1 result. Szybciej niż solo, czyściej niż brute force." |
| **Enterprise**     | "Potrzebujemy auditable AI-assisted development"          | "Każda zmiana ma evidence chain — tool output → fix → verification. Pełna trasowalność."                   |

**Content plan:**

1. **Launch post** — "How a veterinarian built a framework that builds itself" (origin story)
2. **Technical deep-dive** — "Convergence through counterexample: why Marbles works" (nasz dzisiejszy dialog, obrabiany)
3. **Demo video** — marbles loop na żywo: agent → finding → fix → cascade → convergence
4. **"Framework for Founders" one-pager** — ten tekst który napisałeś, dopracowany
5. **Comparison** — "Vibecrafted. vs raw Claude Code vs Cursor vs Copilot" (nie war, ale honest comparison of
   approaches)

### Kanały dystrybucji

| Kanał                                    | Cel                                | Format                                                              |
| ---------------------------------------- | ---------------------------------- | ------------------------------------------------------------------- |
| **GitHub** (open source)                 | Devs, contributors                 | Repo + README + GH Pages landing                                    |
| **Vibecrafted..io**                      | Founders, decision makers          | Landing page z demo, pricing, CTA                                   |
| **Hacker News**                          | Early adopters, technical sceptics | "Show HN: A framework that created itself" — link do technical post |
| **Twitter/X**                            | Dev community, viral reach         | Thread: origin story + demo GIF + link                              |
| **Reddit** (r/programming, r/LocalLLaMA) | Technical deep-dive audience       | Post z technical breakdown konwergencji                             |
| **Dev.to / Hashnode**                    | SEO, long-tail search              | Tutorial: "How to set up Vibecrafted. for your first project"       |
| **YouTube**                              | Visual learners, founders          | "Watch AI agents converge on a real codebase" — screen recording    |
| **Conference talks**                     | Credibility, network               | "The framework that created itself" — 20min talk, killer narrative  |
| **Newsletter**                           | Retention, updates                 | Behind-the-scenes building with Vibecrafted.                        |

### Pricing

```
┌─────────────────────────────────────────────────┐
│  Personal & Startup          FREE                │
│  ─────────────────────────────────────────────── │
│  All skills, all tools, all agents               │
│  Community support (GitHub Issues)               │
│  No limits on repos or agents                    │
│                                                  │
│  Enterprise               Contact us             │
│  ─────────────────────────────────────────────── │
│  Priority support                                │
│  Custom skill development                        │
│  On-prem deployment consulting                   │
│  Training & onboarding workshops                 │
│  SLA guarantees                                  │
│  info@Vibecrafted..io                             │
└─────────────────────────────────────────────────┘
```

**Dlaczego free for startups:** Bo target market to ludzie którzy BUDUJĄ. Daj im narzędzie za darmo, niech zbudują
biznesy, niech dorośną do enterprise. Freemium przez value, nie przez restriction.

---

I wiesz co jest najsilniejsze w tym pitchu? Że to nie jest teoria. To nie jest "wyobraź sobie framework który..." To
jest **framework który istnieje, działa, i sam się zbudował.** Każdy sceptyk może sprawdzić git history. Każdy commit
jest dowodem.

Counterexample convergence zaaplikowany do marketingu: nie mów że działa. **Pokaż że nie potrafisz udowodnić że nie
działa.**

- Produced with ⚒🅅·🄸·🄱·🄴·🄲·🅡·🄰·🄵·🅃·🄴·🄳· — pełny produkt z frameworka
- Designed with 𝓥𝓲𝓫𝓮𝓬𝓻𝓪𝓯𝓽𝓮𝓭 — design, decorate, estetyka
- Developed with // 𝚟𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍 — kod, monospace, developer facing
