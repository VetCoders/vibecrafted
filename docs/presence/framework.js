(function () {
    var prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var DPR_CAP = prefersReducedMotion ? 1.25 : 2;
    var frameworkLocale = /^pl\b/i.test(document.documentElement.lang || '') ? 'pl' : 'en';
    var FRAMEWORK_I18N = {
        en: {
            overlayPhase: 'Phase',
            overlayConverge: 'Converge',
            overlayMarbles: 'Marbles',
            showcaseKicker: 'Framework Playground',
            showcaseHeading: 'Command the convergence board',
            showcaseLead: 'Board-first teaching surface. Trace the frame, tune the grooves, invite specialists, then let Marbles run the convergence batches.',
            defaultEyebrow: 'Phase 0 · Setup',
            defaultPressCopy: 'Define the board geometry.',
            operators: 'Operators',
            choosePhase: 'Choose Phase',
            alerts: {
                dou: {title: 'DoU', detail: 'Blockers surfaced'},
                review: {title: 'Review', detail: 'Weak fits exposed'}
            },
            hints: {
                workflow: 'Tune groove density until the board exposes the right amount of working capacity.',
                init: 'Bootstrap context so the first true grooves are cut from history instead of guessed from nothing.',
                research: 'Probe the lane choices before committing force. Research narrows the search space and marks the promising paths.',
                marbles: 'Set the marbles count and force, then let the board run the convergence sequence by itself.',
                agents: 'Select specialist count and spawn them into the grooves.',
                scaffold: 'Choose the outer frame first. Capacity comes later, once the board shape is real.',
                review: 'Run a stress pass on the first placements before the noisy convergence loops begin.',
                followup: 'Shake the board and see which claims of progress were never truly anchored.',
                prune: 'Remove weak or unnecessary fits so the board can converge around the stronger core.',
                dou: 'Flash the undone truth in red and expose what still blocks shipping.',
                hydrate: 'Fill the remaining critical gaps with deterministic precision.',
                decorate: 'Apply final polish pass to saturate colors and sharpen the finish.',
                release: 'Launch the finished surface and release the loop to the market.'
            },
            phaseOverrides: {}
        },
        pl: {
            overlayPhase: 'Faza',
            overlayConverge: 'Domknięcie',
            overlayMarbles: 'Marbles',
            showcaseKicker: 'Playground frameworku',
            showcaseHeading: 'Steruj planszą konwergencji',
            showcaseLead: 'Plansza jako powierzchnia nauki. Wyznacz ramę, dostrój rowki, zaproś specjalistów, a potem pozwól Marbles uruchomić batchowe domykanie.',
            defaultEyebrow: 'Faza 0 · Setup',
            defaultPressCopy: 'Zdefiniuj geometrię planszy.',
            operators: 'Operator',
            choosePhase: 'Wybierz fazę',
            alerts: {
                dou: {title: 'DoU', detail: 'Blokery ujawnione'},
                review: {title: 'Review', detail: 'Słabe dopasowania ujawnione'}
            },
            hints: {
                workflow: 'Dostrój gęstość rowków, aż plansza pokaże właściwą pojemność roboczą.',
                init: 'Zainicjuj kontekst, żeby pierwsze prawdziwe rowki były wycinane z historii zamiast zgadywane od zera.',
                research: 'Przetestuj możliwe tory, zanim dołożysz siłę. Research zawęża przestrzeń szukania i zaznacza obiecujące ścieżki.',
                marbles: 'Ustaw liczbę kulek i siłę, a potem pozwól planszy samodzielnie uruchomić sekwencję konwergencji.',
                agents: 'Wybierz liczbę specjalistów i wpuść ich w rowki.',
                scaffold: 'Najpierw wybierz zewnętrzną ramę. Pojemność przychodzi później, gdy kształt planszy jest już prawdziwy.',
                review: 'Uruchom pass stresowy dla pierwszych ułożeń, zanim zaczną się głośniejsze pętle domykania.',
                followup: 'Potrząśnij planszą i sprawdź, które deklaracje postępu nigdy nie były naprawdę osadzone.',
                prune: 'Usuń słabe albo zbędne dopasowania, żeby plansza mogła domknąć się wokół mocniejszego rdzenia.',
                dou: 'Pokaż na czerwono prawdę o niedomknięciu i ujawnij, co nadal blokuje release.',
                hydrate: 'Wypełnij pozostałe krytyczne luki z deterministyczną precyzją.',
                decorate: 'Nałóż końcowy polish pass, żeby nasycić kolory i wyostrzyć finish.',
                release: 'Wypuść gotową powierzchnię i uwolnij pętlę na rynek.'
            },
            phaseOverrides: {
                scaffold: {
                    eyebrow: 'Faza 0 · Setup',
                    title: 'Wyznacz zewnętrzną ramę',
                    description: 'Najpierw wyznacz granicę. Scaffold dotyczy tylko sylwetki planszy, zanim zdecydujemy, ile rowków ma unieść.',
                    detail: 'Szkielet układu · blokada geometrii'
                },
                init: {
                    eyebrow: 'Faza 1 · Twórz',
                    title: 'Wytraw pierwsze rowki',
                    description: 'Init zakotwicza planszę w rzeczywistości. Historia i struktura zaczynają wycinać prawdziwe rowki, żeby późniejsza praca miała gdzie lądować.',
                    detail: 'Ładowanie kontekstu · pierwsze rowki'
                },
                research: {
                    eyebrow: 'Faza 1 · Twórz',
                    title: 'Zmapuj wiarygodne tory',
                    description: 'Research bada przestrzeń opcji, zanim wejdziemy w throughput. Plansza zaczyna podświetlać, które rowki mają znaczenie, które są zmyłką i gdzie dołożyć kolejne ciśnienie.',
                    detail: 'Skan opcji · odkrywanie trasy'
                },
                workflow: {
                    eyebrow: 'Faza 1 · Twórz',
                    title: 'Ustaw gęstość rowków',
                    description: 'Tutaj definiujemy pojemność. Workflow decyduje, ile rowków plansza wystawi, żeby dalsza praca wpadała w prawdziwy model operacyjny zamiast pustej tekstury.',
                    detail: 'Liczba rowków · strojenie gęstości'
                },
                agents: {
                    eyebrow: 'Faza 1 · Twórz',
                    title: 'Wpuść pierwszych specjalistów',
                    description: 'Kilka celowych kulek ląduje czysto. Wczesna praca agentów ma być precyzyjna, a nie jak chaos rozpylony po planszy.',
                    detail: 'Niski chaos · oceaniczne kulki'
                },
                marbles: {
                    eyebrow: 'Faza 2 · Domykaj',
                    title: 'Dodaj siłę i zaakceptuj wariancję',
                    description: 'Docierają kolejne batch’e i rośnie entropia. To uczciwy środek: throughput przyspiesza, ale rośnie też szum.',
                    detail: 'Rzuty batchowe · rosnąca entropia'
                },
                review: {
                    eyebrow: 'Faza 2 · Domykaj',
                    title: 'Dociśnij poruszającą się planszę',
                    description: 'Review sprawdza, czy ułożony wzór naprawdę odpowiada intencji. Słabe dopasowania, spillover i podejrzane ułożenia stają się widoczne pod presją.',
                    detail: 'Brama jakości · wykrywanie słabych dopasowań'
                },
                followup: {
                    eyebrow: 'Faza 2 · Domykaj',
                    title: 'Strząśnij fałszywe sukcesy',
                    description: 'Luźne kulki zaczynają odpadać. Followup to moment, w którym głośne deklaracje sukcesu zderzają się z tym, co naprawdę się trzyma.',
                    detail: 'Grawitacyjne czyszczenie · nadmiar odpada'
                },
                prune: {
                    eyebrow: 'Faza 2 · Domykaj',
                    title: 'Przytnij do runtime’owego rdzenia',
                    description: 'Część pozornie solidnych elementów jest usuwana celowo. Prune otwiera luki na nowo, żeby plansza mogła domknąć się wokół mocniejszego kształtu.',
                    detail: 'Celowe luki · martwy ciężar znika'
                },
                dou: {
                    eyebrow: 'Faza 3 · Audyt',
                    title: 'Definition of Undone',
                    description: 'Wyciągnij na czerwono prawdę. Uruchom systematyczną analizę luk na całej powierzchni produktu, żeby zobaczyć, co nadal blokuje wysyłkę.',
                    detail: 'Plague check · audyt gotowości'
                },
                decorate: {
                    eyebrow: 'Faza 3 · Wdrażaj',
                    title: 'Zamień spójność w wykończenie',
                    description: 'Osadzone kulki zyskują nasycenie i ostrość. Decorate nie jest przypadkową ornamentyką; to końcowy pass spójności, który sprawia, że system czuje się intencjonalny.',
                    detail: 'Podbicie nasycenia · pass wykończenia'
                },
                hydrate: {
                    eyebrow: 'Faza 3 · Wdrażaj',
                    title: 'Wypełnij dokładnie brakujące szczeliny',
                    description: 'Tutaj ruch zmienia ton. Pozostałe luki są domykane deterministycznie, po jednym krytycznym dla launchu otworze naraz.',
                    detail: 'Precyzyjne wypełnienie · domknięcie pod rynek'
                },
                release: {
                    eyebrow: 'Krok końcowy · Release',
                    title: 'Wypuść kod na rynek',
                    description: 'Plansza rozświetla się, utrzymuje wzór, a potem blednie przed kolejnym cyklem. Shipping nie jest brakiem ruchu; to domknięta pętla gotowa, by zacząć od nowa.',
                    detail: 'Stabilna plansza · reset na kolejny cykl'
                }
            }
        }
    };
    var FRAMEWORK_TEXT = FRAMEWORK_I18N[frameworkLocale];

    var PHASES = [
        {
            name: 'scaffold',
            label: 'Scaffold',
            eyebrow: 'Phase 0 · Setup',
            title: 'Trace the outer frame',
            description: 'Set the boundary first. Scaffold is only about the silhouette of the board before we decide how many grooves it can carry.',
            detail: 'Layout shell · geometry lock',
            duration: 1500,
            snapshotRatio: 0.28
        },
        {
            name: 'init',
            label: 'Init',
            eyebrow: 'Phase 1 · Craft',
            title: 'Etch the first grooves',
            description: 'Init anchors the board in reality. History and structure start cutting true grooves into the frame so later work has somewhere real to land.',
            detail: 'Context load · first grooves',
            duration: 1600,
            snapshotRatio: 0.48
        },
        {
            name: 'research',
            label: 'Research',
            eyebrow: 'Phase 1 · Craft',
            title: 'Map the plausible lanes',
            description: 'Research explores the option space before we commit to throughput. The board starts highlighting which grooves matter, which are decoys, and where the next pressure should go.',
            detail: 'Option scan · route discovery',
            duration: 1800,
            snapshotRatio: 0.68
        },
        {
            name: 'workflow',
            label: 'Workflow',
            eyebrow: 'Phase 1 · Craft',
            title: 'Set groove density',
            description: 'Now define capacity. Workflow decides how many grooves the board exposes, so later work lands into a real operating model instead of empty texture.',
            detail: 'Groove count · density tuning',
            duration: 2000,
            snapshotRatio: 0.74
        },
        {
            name: 'agents',
            label: 'Agents',
            eyebrow: 'Phase 1 · Craft',
            title: 'Let the first specialists in',
            description: 'A few deliberate marbles land cleanly. Early agent work should feel precise, not like chaos sprayed across the board.',
            detail: 'Low-chaos placement · ocean marbles',
            duration: 2500,
            snapshotRatio: 0.86
        },
        {
            name: 'marbles',
            label: 'Marbles',
            eyebrow: 'Phase 2 · Converge',
            title: 'Add force, accept variance',
            description: 'More batches arrive and entropy climbs. This is the honest middle: throughput increases, but so does noise.',
            detail: 'Batch throws · growing entropy',
            duration: 3000,
            snapshotRatio: 0.58
        },
        {
            name: 'review',
            label: 'Review',
            eyebrow: 'Phase 2 · Converge',
            title: 'Stress the moving board',
            description: 'Review checks whether the landed pattern really matches the intent. Weak fits, spillover, and suspicious placements become visible under pressure.',
            detail: 'Quality gate · weak-fit detection',
            duration: 2500,
            snapshotRatio: 0.62
        },
        {
            name: 'followup',
            label: 'Followup',
            eyebrow: 'Phase 2 · Converge',
            title: 'Shake loose the false positives',
            description: 'Loose marbles start falling away. Followup is where noisy success claims get tested against what actually holds.',
            detail: 'Gravity purge · excess falls off',
            duration: 1500,
            snapshotRatio: 0.68
        },
        {
            name: 'prune',
            label: 'Prune',
            eyebrow: 'Phase 2 · Converge',
            title: 'Cut back to the runtime core',
            description: 'A few seemingly solid pieces are removed on purpose. Pruning reopens gaps so the board can converge around the stronger shape.',
            detail: 'Intentional gaps · dead weight exits',
            duration: 2000,
            snapshotRatio: 0.34
        },
        {
            name: 'dou',
            label: 'DoU',
            eyebrow: 'Phase 3 · Audit',
            title: 'Definition of Undone',
            description: 'Surface the red truth. Run a systematic gap analysis across the entire product surface to expose what still blocks shipping.',
            detail: 'Plague check · readiness audit',
            duration: 1500,
            snapshotRatio: 0.48
        },
        {
            name: 'decorate',
            label: 'Decorate',
            eyebrow: 'Phase 3 · Ship',
            title: 'Turn coherence into finish',
            description: 'The settled marbles saturate and sharpen. Decorate is not random ornament; it is the final coherence pass that makes the system feel intentional.',
            detail: 'Saturation lift · finish pass',
            duration: 2000,
            snapshotRatio: 0.72
        },
        {
            name: 'hydrate',
            label: 'Hydrate',
            eyebrow: 'Phase 3 · Ship',
            title: 'Fill the exact missing slots',
            description: 'Now the motion changes tone. The remaining gaps are handled deterministically, one launch-critical hole at a time.',
            detail: 'Precise fill · market-facing completion',
            duration: 2500,
            snapshotRatio: 0.68
        },
        {
            name: 'release',
            label: 'Release',
            eyebrow: 'Final Step · Release',
            title: 'Ship code to market',
            description: 'The board glows, holds, and then fades for the next cycle. Shipping is not the absence of motion; it is a completed loop ready to start again.',
            detail: 'Stable board · reset for next cycle',
            duration: 3000,
            snapshotRatio: 0.34
        }
    ];
    PHASES = PHASES.map(function (phaseDef) {
        return Object.assign({}, phaseDef, FRAMEWORK_TEXT.phaseOverrides[phaseDef.name] || {});
    });

    var SHAPES = ['circle', 'square', 'hexagon', 'spiral', 'waves', 'grid'];
    var PAL = {
        amber: {base: '#d46b3f', light: '#f4c89a'},
        ocean: {base: '#5b87a8', light: '#c2ddf0'},
        forest: {base: '#7d8e57', light: '#bdd4a0'},
        smoke: {base: '#9b9a95', light: '#e8e6dc'},
        rose: {base: '#c46b8a', light: '#f0c4d4'},
        violet: {base: '#8b7ec8', light: '#cdc4ef'},
        honey: {base: '#cc8844', light: '#f0d4a0'},
        teal: {base: '#5ba3a3', light: '#a8dede'}
    };
    var PAL_KEYS = Object.keys(PAL);
    var spriteCache = {};

    function mulberry32(a) {
        return function () {
            a |= 0;
            a = a + 0x6D2B79F5 | 0;
            var t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
    }

    function hexToRgb(hex) {
        var r = parseInt(hex.slice(1, 3), 16);
        var g = parseInt(hex.slice(3, 5), 16);
        var b = parseInt(hex.slice(5, 7), 16);
        return {r: r, g: g, b: b};
    }

    function rgbStr(c, a) {
        return 'rgba(' + c.r + ',' + c.g + ',' + c.b + ',' + (a || 1) + ')';
    }

    function lighten(c, n) {
        return {r: Math.min(255, c.r + n), g: Math.min(255, c.g + n), b: Math.min(255, c.b + n)};
    }

    function darken(c, n) {
        return {r: Math.max(0, c.r - n), g: Math.max(0, c.g - n), b: Math.max(0, c.b - n)};
    }

    function makeSprite(radius, palKey, seed) {
        var key = radius + ':' + palKey + ':' + seed;
        if (spriteCache[key]) return spriteCache[key];

        var pad = 4;
        var s = (radius * 2 + pad) * 2;
        var oc = document.createElement('canvas');
        oc.width = s;
        oc.height = s;
        var g = oc.getContext('2d');
        var cx = s / 2;
        var cy = s / 2;
        var r = radius;
        var p = PAL[palKey];
        var base = hexToRgb(p.base);
        var light = hexToRgb(p.light);
        var rng = mulberry32(seed);

        g.beginPath();
        g.ellipse(cx + r * 0.05, cy + r * 0.82, r * 0.6, r * 0.18, 0, 0, Math.PI * 2);
        g.fillStyle = 'rgba(0,0,0,0.2)';
        g.fill();

        g.save();
        g.beginPath();
        g.arc(cx, cy, r, 0, Math.PI * 2);
        g.clip();

        var bg = g.createRadialGradient(cx - r * 0.3, cy - r * 0.35, r * 0.05, cx + r * 0.1, cy + r * 0.1, r * 1.1);
        bg.addColorStop(0, rgbStr(lighten(base, 60), 0.95));
        bg.addColorStop(0.35, rgbStr(base, 0.92));
        bg.addColorStop(0.7, rgbStr(darken(base, 25), 0.9));
        bg.addColorStop(1, rgbStr(darken(base, 55), 0.85));
        g.fillStyle = bg;
        g.fillRect(0, 0, s, s);

        g.save();
        g.translate(cx, cy);
        var tw = r * 0.15 + rng() * r * 0.1;
        g.beginPath();
        for (var t = 0; t < Math.PI * 3; t += 0.1) {
            var sr = r * 0.1 + (t / (Math.PI * 3)) * r * 0.8;
            var sx = Math.cos(rng() * 6 + t) * sr;
            var sy = Math.sin(rng() * 6 + t) * sr;
            if (t === 0) g.moveTo(sx, sy); else g.lineTo(sx, sy);
        }
        g.lineWidth = tw;
        g.strokeStyle = rgbStr(light, 0.4);
        g.lineCap = 'round';
        g.stroke();
        g.restore();

        var hl = g.createRadialGradient(cx - r * 0.28, cy - r * 0.32, r * 0.02, cx - r * 0.15, cy - r * 0.2, r * 0.5);
        hl.addColorStop(0, 'rgba(255,255,255,0.98)');
        hl.addColorStop(0.12, 'rgba(255,255,255,0.7)');
        hl.addColorStop(0.34, 'rgba(255,255,255,0.22)');
        hl.addColorStop(0.62, 'rgba(255,255,255,0.08)');
        hl.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = hl;
        g.fillRect(0, 0, s, s);

        var rim = g.createRadialGradient(cx, cy, r * 0.75, cx, cy, r);
        rim.addColorStop(0, 'rgba(0,0,0,0)');
        rim.addColorStop(0.8, 'rgba(0,0,0,0.06)');
        rim.addColorStop(1, 'rgba(0,0,0,0.25)');
        g.fillStyle = rim;
        g.fillRect(0, 0, s, s);
        g.restore();

        spriteCache[key] = oc;
        return oc;
    }

    function phaseCommand(phaseDef) {
        if (phaseDef.name === 'init') {
            return 'vibecrafted init claude';
        }
        if (phaseDef.name === 'agents') {
            return 'vibecrafted partner claude';
        }
        if (phaseDef.name === 'scaffold' || phaseDef.name === 'research' || phaseDef.name === 'workflow' || phaseDef.name === 'dou') {
            return 'vibecrafted ' + phaseDef.name + ' claude';
        }
        return 'vibecrafted ' + phaseDef.name + ' codex';
    }

    function phaseHint(phaseDef) {
        if (phaseDef.name === 'workflow') {
            return FRAMEWORK_TEXT.hints.workflow;
        }
        if (phaseDef.name === 'init') {
            return FRAMEWORK_TEXT.hints.init;
        }
        if (phaseDef.name === 'research') {
            return FRAMEWORK_TEXT.hints.research;
        }
        if (phaseDef.name === 'marbles') {
            return FRAMEWORK_TEXT.hints.marbles;
        }
        if (phaseDef.name === 'agents') {
            return FRAMEWORK_TEXT.hints.agents;
        }
        if (phaseDef.name === 'scaffold') {
            return FRAMEWORK_TEXT.hints.scaffold;
        }
        if (phaseDef.name === 'review') {
            return FRAMEWORK_TEXT.hints.review;
        }
        if (phaseDef.name === 'followup') {
            return FRAMEWORK_TEXT.hints.followup;
        }
        if (phaseDef.name === 'prune') {
            return FRAMEWORK_TEXT.hints.prune;
        }
        if (phaseDef.name === 'dou') {
            return FRAMEWORK_TEXT.hints.dou;
        }
        if (phaseDef.name === 'hydrate') {
            return FRAMEWORK_TEXT.hints.hydrate;
        }
        if (phaseDef.name === 'decorate') {
            return FRAMEWORK_TEXT.hints.decorate;
        }
        if (phaseDef.name === 'release') {
            return FRAMEWORK_TEXT.hints.release;
        }
        return phaseDef.description;
    }

    function buildShowcaseMarkup(layout) {
        var metaSection = layout === 'standalone'
            ? ''
            : [
                '  <div class="framework-playground__meta">',
                '    <div class="framework-playground__meta-copy">',
                '      <p class="framework-playground__kicker">' + FRAMEWORK_TEXT.showcaseKicker + '</p>',
                '      <h3 class="framework-playground__heading">' + FRAMEWORK_TEXT.showcaseHeading + '</h3>',
                '      <p class="framework-playground__lede">' + FRAMEWORK_TEXT.showcaseLead + '</p>',
                '    </div>',
                '  </div>'
            ].join('');
        return [
            '<div class="framework-playground framework-playground--' + layout + '">',
            metaSection,
            '  <div class="framework-playground__body">',
            '    <p class="framework-playground__pressline">',
            '      <span class="framework-playground__press-kicker" data-framework-phase-eyebrow>' + FRAMEWORK_TEXT.defaultEyebrow + '</span>',
            '      <span class="framework-playground__press-copy" data-framework-phase-press>' + FRAMEWORK_TEXT.defaultPressCopy + '</span>',
            '    </p>',
            '    <div class="framework-playground__board-column">',
            '      <div class="framework-playground__stage">',
            '        <canvas class="framework-playground__canvas" aria-hidden="true"></canvas>',
            '        <div class="framework-playground__overlay" aria-hidden="true">',
            '          <span>' + FRAMEWORK_TEXT.overlayPhase + ' <strong data-framework-phase-label>Scaffold</strong></span>',
            '          <span>' + FRAMEWORK_TEXT.overlayConverge + ' <strong data-framework-coverage>0%</strong></span>',
            '          <span>' + FRAMEWORK_TEXT.overlayMarbles + ' <strong data-framework-marbles>0</strong></span>',
            '        </div>',
            '        <p class="framework-playground__prompt" aria-hidden="true">',
            '          <span class="framework-playground__prompt-mark">$ &gt;</span>',
            '          <span class="framework-playground__prompt-command" data-framework-command>vibecrafted scaffold claude</span>',
            '        </p>',
            '      </div>',
            '    </div>',
            '    <aside class="framework-playground__side-column">',
            '      <p class="framework-playground__side-kicker">' + FRAMEWORK_TEXT.operators + '</p>',
            '      <p class="framework-playground__side-copy" data-framework-phase-hint></p>',
            '      <div class="framework-playground__controls" data-framework-controls></div>',
            '      <p class="framework-playground__side-kicker" style="margin-top: 0.35rem;">' + FRAMEWORK_TEXT.choosePhase + '</p>',
            '      <div class="framework-playground__rail-shell">',
            '        <div class="framework-playground__rail framework-playground__rail--stack" data-framework-rail></div>',
            '      </div>',
            '    </aside>',
            '  </div>',
            '</div>'
        ].join('');
    }

    function replaceRootMarkup(root, markup) {
        var parser = new window.DOMParser();
        var parsed = parser.parseFromString(markup, 'text/html');
        var fragment = document.createDocumentFragment();

        while (parsed.body.firstChild) {
            fragment.appendChild(parsed.body.firstChild);
        }

        root.replaceChildren(fragment);
    }

    function initFrameworkPlayground(root, rootIndex) {
        if (!root || root.dataset.frameworkReady === 'true') return;
        root.dataset.frameworkReady = 'true';

        var layout = root.getAttribute('data-framework-layout') || 'standalone';
        var startPhaseName = root.getAttribute('data-framework-start') || 'scaffold';
        root.classList.add('framework-playground');
        root.classList.toggle('framework-playground--standalone', layout === 'standalone');

        replaceRootMarkup(root, buildShowcaseMarkup(layout));

        var stage = root.querySelector('.framework-playground__stage');
        var canvas = root.querySelector('.framework-playground__canvas');
        var ctx = canvas.getContext('2d');
        if (!ctx) return;

        var phaseLabelEl = root.querySelector('[data-framework-phase-label]');
        var coverageEl = root.querySelector('[data-framework-coverage]');
        var marblesEl = root.querySelector('[data-framework-marbles]');
        var eyebrowEl = root.querySelector('[data-framework-phase-eyebrow]');
        var pressEl = root.querySelector('[data-framework-phase-press]');
        var commandEl = root.querySelector('[data-framework-command]');
        var hintEl = root.querySelector('[data-framework-phase-hint]');
        var rail = root.querySelector('[data-framework-rail]');
        var controlsEl = root.querySelector('[data-framework-controls]');

        var phaseButtons = [];
        var width = 0;
        var height = 0;
        var measuredWidth = 0;
        var measuredHeight = 0;
        var dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, DPR_CAP));
        var centerX = 0;
        var centerY = 0;
        var boardRadius = 0;
        var marbleRadius = 0;

        var phase = 0;
        var phaseTime = 0;
        var throwTimer = 0;
        var slots = [];
        var marbles = [];
        var overflowMarbles = [];
        var grooveRevealProgress = 0;
        var boardAlpha = 0;
        var shakeX = 0;
        var shakeY = 0;
        var coveragePct = 0;
        var errorFlash = 0;
        var frameHandle = 0;
        var lastFrameTs = 0;
        var pings = [];

        var boardShape = 0; // index in SHAPES
        var boardDensity = 1.0;
        var marbleBatchSize = 8;
        var marbleRunCount = 4;
        var marbleRunRemaining = 0;
        var agentBatchSize = 3;
        var hydrateBatchSize = 5;
        var polishIntensity = 0.0;
        var marblePower = 1.0;
        var shipGlow = 0;

        function currentPhaseCommand() {
            var phaseDef = PHASES[phase];
            if (phaseDef.name === 'scaffold') {
                return 'vibecrafted scaffold claude --prompt "Shape the board as ' + SHAPES[boardShape] + '"';
            }
            if (phaseDef.name === 'workflow') {
                return 'vibecrafted workflow claude --prompt "Tune groove density to ' + boardDensity.toFixed(1) + '"';
            }
            if (phaseDef.name === 'agents') {
                return 'vibecrafted partner claude --prompt "Spawn ' + agentBatchSize + ' specialist tracks"';
            }
            if (phaseDef.name === 'marbles') {
                return 'vibecrafted marbles codex --count ' + marbleRunCount + ' --depth 3';
            }
            return phaseCommand(phaseDef);
        }

        function currentAlertCopy() {
            var phaseDef = PHASES[phase];
            if (phaseDef.name === 'dou') {
                return FRAMEWORK_TEXT.alerts.dou;
            }
            if (phaseDef.name === 'review') {
                return FRAMEWORK_TEXT.alerts.review;
            }
            return {
                title: phaseDef.label,
                detail: phaseDef.title
            };
        }

        function countVisibleSlots() {
            return slots.filter(function (slot) {
                return slot.visible;
            }).length;
        }

        function countFilledSlots() {
            return slots.filter(function (slot) {
                return slot.filled;
            }).length;
        }

        function setRangePct(input, pct) {
            input.style.setProperty('--range-pct', pct + '%');
        }

        function createControlCaption(text, tagName) {
            var node = document.createElement(tagName || 'label');
            node.style.fontSize = '0.7rem';
            node.style.color = 'var(--steel-dark)';
            node.style.fontFamily = 'var(--font-mono)';
            node.textContent = text;
            return node;
        }

        function resolvePhaseIndex(name) {
            for (var i = 0; i < PHASES.length; i++) {
                if (PHASES[i].name === name || PHASES[i].label.toLowerCase() === String(name).toLowerCase()) {
                    return i;
                }
            }
            return 0;
        }

        function buildSlots() {
            slots = [];
            var sp = marbleRadius * (2.2 / boardDensity);
            var rh = sp * 0.866;
            var row = 0;
            var shape = SHAPES[boardShape];

            for (var y = centerY - boardRadius * 1.1; y <= centerY + boardRadius * 1.1; y += rh) {
                var off = (row % 2) ? sp / 2 : 0;
                for (var x = centerX - boardRadius * 1.1; x <= centerX + boardRadius * 1.1; x += sp) {
                    var px = x + off;
                    var dx = px - centerX;
                    var dy = y - centerY;
                    var isInside = false;

                    if (shape === 'circle') {
                        isInside = Math.sqrt(dx * dx + dy * dy) + marbleRadius * 0.85 <= boardRadius;
                    } else if (shape === 'square') {
                        isInside = Math.abs(dx) <= boardRadius * 0.85 && Math.abs(dy) <= boardRadius * 0.85;
                    } else if (shape === 'hexagon') {
                        var q = (2 / 3 * dx) / (boardRadius * 0.8);
                        var r = (-1 / 3 * dx + Math.sqrt(3) / 3 * dy) / (boardRadius * 0.8);
                        var s = -q - r;
                        isInside = Math.abs(q) <= 1 && Math.abs(r) <= 1 && Math.abs(s) <= 1;
                    } else if (shape === 'spiral') {
                        var angle = Math.atan2(dy, dx);
                        var dist = Math.sqrt(dx * dx + dy * dy);
                        var spiralDist = (angle + Math.PI * 10) * (boardRadius / 20);
                        isInside = Math.abs(dist - (spiralDist % boardRadius)) < sp * 0.5 && dist < boardRadius;
                    } else if (shape === 'waves') {
                        var wave = Math.sin(px * 0.05) * (boardRadius * 0.2);
                        isInside = Math.abs(dy - wave) < sp * 0.8 && Math.abs(dx) < boardRadius * 0.9;
                    } else if (shape === 'grid') {
                        isInside = Math.abs(dx) < boardRadius && Math.abs(dy) < boardRadius;
                    }

                    if (isInside) {
                        slots.push({x: px, y: y, filled: false, revealOrder: 0, visible: false});
                    }
                }
                row++;
            }
            slots.sort(function (a, b) {
                var da = Math.sqrt((a.x - centerX) * (a.x - centerX) + (a.y - centerY) * (a.y - centerY));
                var db = Math.sqrt((b.x - centerX) * (b.x - centerX) + (b.y - centerY) * (b.y - centerY));
                return da - db;
            });
            for (var i = 0; i < slots.length; i++) slots[i].revealOrder = i;
            marbles = [];
            overflowMarbles = [];
            pings = [];
        }

        function drawGroove(x, y, r, alpha) {
            ctx.globalAlpha = alpha;
            ctx.beginPath();
            ctx.arc(x, y, r * 0.95, 0, Math.PI * 2);
            var sg = ctx.createRadialGradient(x - r * 0.1, y - r * 0.1, r * 0.2, x, y, r * 0.95);
            sg.addColorStop(0, 'rgba(0,0,0,0.28)');
            sg.addColorStop(0.6, 'rgba(0,0,0,0.18)');
            sg.addColorStop(1, 'rgba(0,0,0,0.05)');
            ctx.fillStyle = sg;
            ctx.fill();
            ctx.beginPath();
            ctx.arc(x, y, r * 0.72, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(242,239,221,0.04)';
            ctx.lineWidth = 0.8;
            ctx.stroke();
            ctx.globalAlpha = 1;
        }

        function traceBoardShape(radiusScale) {
            var shape = SHAPES[boardShape];
            var radius = boardRadius * (radiusScale || 1);

            if (shape === 'circle' || shape === 'spiral' || shape === 'waves') {
                ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
                return;
            }

            if (shape === 'square' || shape === 'grid') {
                ctx.rect(centerX - radius * 0.92, centerY - radius * 0.92, radius * 1.84, radius * 1.84);
                return;
            }

            if (shape === 'hexagon') {
                for (var i = 0; i < 6; i++) {
                    var angle = (i * Math.PI) / 3 - Math.PI / 6;
                    var hx = centerX + radius * Math.cos(angle);
                    var hy = centerY + radius * Math.sin(angle);
                    if (i === 0) ctx.moveTo(hx, hy); else ctx.lineTo(hx, hy);
                }
                ctx.closePath();
                return;
            }

            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        }

        function drawBoardFrame(alpha, frameOnly) {
            if (alpha <= 0) return;

            ctx.save();
            if (!frameOnly) {
                ctx.beginPath();
                traceBoardShape(1);
                var interior = ctx.createRadialGradient(centerX, centerY, boardRadius * 0.18, centerX, centerY, boardRadius * 1.02);
                interior.addColorStop(0, 'rgba(12, 12, 13,' + (0.42 * alpha) + ')');
                interior.addColorStop(1, 'rgba(6, 7, 9,' + (0.22 * alpha) + ')');
                ctx.fillStyle = interior;
                ctx.fill();
            }

            ctx.beginPath();
            traceBoardShape(1);
            ctx.strokeStyle = frameOnly ? 'rgba(242, 239, 221,' + (0.18 * alpha) + ')' : 'rgba(242, 239, 221,' + (0.1 * alpha) + ')';
            ctx.lineWidth = frameOnly ? Math.max(1.2, marbleRadius * 0.08) : Math.max(1.4, marbleRadius * 0.12);
            ctx.stroke();
            ctx.restore();
        }

        function drawPing(p, dt) {
            p.life -= dt * 0.002;
            if (p.life <= 0) return false;
            ctx.save();
            ctx.globalAlpha = p.life * 0.6;
            ctx.beginPath();
            ctx.arc(p.x, p.y, marbleRadius * (1 + (1 - p.life) * 1.5), 0, Math.PI * 2);
            ctx.strokeStyle = p.color || 'rgba(244, 200, 154, 0.8)';
            ctx.lineWidth = 2 * p.life;
            ctx.stroke();
            ctx.restore();
            return true;
        }

        function spawnMarble(targetSlot, chaos, palKey) {
            var angle = Math.random() * Math.PI * 2;
            var dist = boardRadius * (0.6 + chaos * 0.8);
            return {
                x: centerX + Math.cos(angle) * dist,
                y: centerY + Math.sin(angle) * dist - boardRadius * chaos * 0.3,
                vx: (Math.random() - 0.5) * 14 * chaos * marblePower,
                vy: (Math.random() - 0.5) * 10 * chaos * marblePower + 3,
                target: targetSlot,
                settled: false,
                seed: Math.floor(Math.random() * 99999),
                pal: palKey || PAL_KEYS[Math.floor(Math.random() * PAL_KEYS.length)],
                alpha: 1,
                saturation: 0.6
            };
        }

        function spawnOverflow() {
            var angle = Math.random() * Math.PI * 2;
            var dist = boardRadius * 1.2;
            return {
                x: centerX + Math.cos(angle) * dist,
                y: centerY - boardRadius * 0.5 - Math.random() * 100,
                vx: (Math.random() - 0.5) * 20 * marblePower,
                vy: (10 + Math.random() * 15) * marblePower,
                settled: false,
                seed: Math.floor(Math.random() * 99999),
                pal: PAL_KEYS[Math.floor(Math.random() * PAL_KEYS.length)],
                alpha: 1,
                saturation: 0.5,
                landY: centerY + (Math.random() - 0.5) * boardRadius * 0.8,
                landX: centerX + (Math.random() - 0.5) * boardRadius * 0.8
            };
        }

        function updateMarble(m, dt) {
            if (m.settled) return;
            var tx = m.target ? m.target.x : m.landX;
            var ty = m.target ? m.target.y : m.landY;
            var dx = tx - m.x;
            var dy = ty - m.y;
            var dist = Math.sqrt(dx * dx + dy * dy);

            // Magnetic pull: stronger as it gets closer
            var pullMagnitude = m.target ? (dist < 40 ? 0.04 : 0.015) : 0.008;
            m.vx += dx * pullMagnitude;
            m.vy += dy * pullMagnitude;

            // Damping increases as it gets closer to target
            var damping = m.target && dist < 10 ? 0.75 : 0.88;
            m.vx *= damping;
            m.vy *= damping;

            m.x += m.vx * dt;
            m.y += m.vy * dt;

            if (dist < 1.5 && Math.abs(m.vx) < 0.5 && Math.abs(m.vy) < 0.5) {
                m.settled = true;
                m.x = tx;
                m.y = ty;
                if (m.target) {
                    m.target.filled = true;
                    pings.push({x: tx, y: ty, life: 1, color: PAL[m.pal].light});
                }
            }
        }

        function updateCoverage() {
            var filled = countFilledSlots();
            var total = countVisibleSlots();
            var overflow = overflowMarbles.filter(function (m) {
                return m.settled;
            }).length;
            coveragePct = total > 0 ? Math.round(((filled + overflow) / total) * 100) : 0;
        }

        function syncRail(scrollToActive) {
            for (var i = 0; i < phaseButtons.length; i++) {
                phaseButtons[i].classList.toggle('is-active', i === phase);
                phaseButtons[i].classList.toggle('is-done', i < phase);
                phaseButtons[i].setAttribute('aria-pressed', i === phase ? 'true' : 'false');
            }
            if (!scrollToActive || !phaseButtons[phase]) return;
            if (rail.scrollWidth <= rail.clientWidth + 8) return;
            phaseButtons[phase].scrollIntoView({
                behavior: prefersReducedMotion ? 'auto' : 'smooth',
                inline: 'center',
                block: 'nearest'
            });
        }

        function renderPhaseControls(phaseIdx) {
            var p = PHASES[phaseIdx];
            controlsEl.replaceChildren();

            var wrap = document.createElement('div');
            wrap.className = 'framework-playground__controls-inner';

            if (p.name === 'scaffold') {
                var shapeRow = document.createElement('div');
                shapeRow.style.display = 'flex';
                shapeRow.style.alignItems = 'center';
                shapeRow.style.justifyContent = 'space-between';
                shapeRow.appendChild(createControlCaption('LAYOUT', 'span'));

                var shapeNav = document.createElement('div');
                shapeNav.style.display = 'flex';
                shapeNav.style.gap = '0.35rem';

                var prevShape = document.createElement('button');
                prevShape.className = 'framework-playground__control-btn';
                prevShape.textContent = '<';
                prevShape.onclick = function () {
                    boardShape = (boardShape - 1 + SHAPES.length) % SHAPES.length;
                    buildSlots();
                    render();
                    renderPhaseControls(phaseIdx);
                };

                var shapeLabel = document.createElement('span');
                shapeLabel.style.fontSize = '0.72rem';
                shapeLabel.style.minWidth = '5rem';
                shapeLabel.style.textAlign = 'center';
                shapeLabel.style.fontFamily = 'var(--font-mono)';
                shapeLabel.textContent = SHAPES[boardShape].toUpperCase();

                var nextShape = document.createElement('button');
                nextShape.className = 'framework-playground__control-btn';
                nextShape.textContent = '>';
                nextShape.onclick = function () {
                    boardShape = (boardShape + 1) % SHAPES.length;
                    buildSlots();
                    render();
                    renderPhaseControls(phaseIdx);
                };

                shapeNav.appendChild(prevShape);
                shapeNav.appendChild(shapeLabel);
                shapeNav.appendChild(nextShape);
                shapeRow.appendChild(shapeNav);
                wrap.appendChild(shapeRow);

                var densityRow = document.createElement('div');
                densityRow.style.display = 'grid';
                densityRow.style.gap = '0.35rem';
                densityRow.appendChild(createControlCaption('FRAME: ' + SHAPES[boardShape].toUpperCase()));
                var frameNote = document.createElement('div');
                frameNote.className = 'framework-playground__side-copy';
                frameNote.textContent = 'Lock the boundary first. Groove count belongs to Workflow.';
                densityRow.appendChild(frameNote);
                wrap.appendChild(densityRow);

                var acceptBtn = document.createElement('button');
                acceptBtn.className = 'framework-playground__action-btn';
                acceptBtn.textContent = 'ACCEPT FRAME';
                acceptBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(acceptBtn);
            } else if (p.name === 'init') {
                var initBtn = document.createElement('button');
                initBtn.className = 'framework-playground__action-btn';
                initBtn.textContent = 'BOOTSTRAP CONTEXT';
                initBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(initBtn);
            } else if (p.name === 'research') {
                var researchBtn = document.createElement('button');
                researchBtn.className = 'framework-playground__action-btn';
                researchBtn.textContent = 'RUN RESEARCH';
                researchBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(researchBtn);
            } else if (p.name === 'workflow') {
                var densityRow = document.createElement('div');
                densityRow.style.display = 'grid';
                densityRow.style.gap = '0.35rem';
                densityRow.appendChild(createControlCaption('DENSITY: ' + boardDensity.toFixed(1) + ' · GROOVES: ' + slots.length));
                var densitySlider = document.createElement('input');
                densitySlider.type = 'range';
                densitySlider.min = '0.5';
                densitySlider.max = '2.0';
                densitySlider.step = '0.1';
                densitySlider.value = boardDensity;
                setRangePct(densitySlider, (boardDensity - 0.5) / 1.5 * 100);
                densitySlider.oninput = function () {
                    boardDensity = parseFloat(this.value);
                    setRangePct(this, (boardDensity - 0.5) / 1.5 * 100);
                    buildSlots();
                    grooveRevealProgress = 1;
                    syncSlotVisibility();
                    render();
                    renderPhaseControls(phaseIdx);
                };
                densityRow.appendChild(densitySlider);
                wrap.appendChild(densityRow);

                var acceptBtn = document.createElement('button');
                acceptBtn.className = 'framework-playground__action-btn';
                acceptBtn.textContent = 'LOCK GROOVES';
                acceptBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(acceptBtn);
            } else if (p.name === 'agents') {
                var agentBatchRow = document.createElement('div');
                agentBatchRow.style.display = 'grid';
                agentBatchRow.style.gap = '0.35rem';
                agentBatchRow.appendChild(createControlCaption('SPECIALIST COUNT: ' + agentBatchSize));
                var agentSlider = document.createElement('input');
                agentSlider.type = 'range';
                agentSlider.min = '1';
                agentSlider.max = '10';
                agentSlider.value = agentBatchSize;
                setRangePct(agentSlider, (agentBatchSize - 1) / 9 * 100);
                agentSlider.oninput = function () {
                    agentBatchSize = parseInt(this.value);
                    setRangePct(this, (agentBatchSize - 1) / 9 * 100);
                    renderPhaseControls(phaseIdx);
                };
                agentBatchRow.appendChild(agentSlider);
                wrap.appendChild(agentBatchRow);

                var spawnBtn = document.createElement('button');
                spawnBtn.className = 'framework-playground__action-btn';
                spawnBtn.textContent = 'SPAWN AGENTS';
                spawnBtn.onclick = runAgentSpawn;
                wrap.appendChild(spawnBtn);

                var nextBtn = document.createElement('button');
                nextBtn.className = 'framework-playground__action-btn framework-playground__action-btn--muted';
                nextBtn.textContent = 'PROCEED TO MARBLES';
                nextBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(nextBtn);
            } else if (p.name === 'review') {
                var reviewBtn = document.createElement('button');
                reviewBtn.className = 'framework-playground__action-btn';
                reviewBtn.textContent = 'RUN REVIEW';
                reviewBtn.onclick = runReviewPass;
                wrap.appendChild(reviewBtn);

                var reviewNextBtn = document.createElement('button');
                reviewNextBtn.className = 'framework-playground__action-btn framework-playground__action-btn--muted';
                reviewNextBtn.textContent = 'PROCEED TO FOLLOWUP';
                reviewNextBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(reviewNextBtn);
            } else if (p.name === 'marbles') {
                var batchRow = document.createElement('div');
                batchRow.style.display = 'grid';
                batchRow.style.gap = '0.35rem';
                batchRow.appendChild(createControlCaption('--COUNT: ' + marbleRunCount));
                var batchSlider = document.createElement('input');
                batchSlider.type = 'range';
                batchSlider.min = '1';
                batchSlider.max = '8';
                batchSlider.value = marbleRunCount;
                setRangePct(batchSlider, (marbleRunCount - 1) / 7 * 100);
                batchSlider.oninput = function () {
                    marbleRunCount = parseInt(this.value);
                    setRangePct(this, (marbleRunCount - 1) / 7 * 100);
                    renderPhaseControls(phaseIdx);
                    commandEl.textContent = currentPhaseCommand();
                };
                batchRow.appendChild(batchSlider);
                wrap.appendChild(batchRow);

                var powerRow = document.createElement('div');
                powerRow.style.display = 'grid';
                powerRow.style.gap = '0.35rem';
                powerRow.appendChild(createControlCaption('POWER: ' + marblePower.toFixed(1)));
                var powerSlider = document.createElement('input');
                powerSlider.type = 'range';
                powerSlider.min = '0.5';
                powerSlider.max = '3.0';
                powerSlider.step = '0.1';
                powerSlider.value = marblePower;
                setRangePct(powerSlider, (marblePower - 0.5) / 2.5 * 100);
                powerSlider.oninput = function () {
                    marblePower = parseFloat(this.value);
                    setRangePct(this, (marblePower - 0.5) / 2.5 * 100);
                    renderPhaseControls(phaseIdx);
                };
                powerRow.appendChild(powerSlider);
                wrap.appendChild(powerRow);

                var throwBtn = document.createElement('button');
                throwBtn.className = 'framework-playground__action-btn';
                throwBtn.textContent = 'RUN MARBLES';
                throwBtn.dataset.frameworkAction = 'run-marbles';
                throwBtn.onclick = runMarblesSequence;
                wrap.appendChild(throwBtn);

                var nextBtn = document.createElement('button');
                nextBtn.className = 'framework-playground__action-btn framework-playground__action-btn--muted';
                nextBtn.textContent = 'PROCEED TO REVIEW';
                nextBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(nextBtn);
            } else if (p.name === 'followup') {
                var followBtn = document.createElement('button');
                followBtn.className = 'framework-playground__action-btn';
                followBtn.textContent = 'RUN FOLLOWUP';
                followBtn.onclick = rerunCurrentPhase;
                wrap.appendChild(followBtn);

                var followNextBtn = document.createElement('button');
                followNextBtn.className = 'framework-playground__action-btn framework-playground__action-btn--muted';
                followNextBtn.textContent = 'PROCEED TO PRUNE';
                followNextBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(followNextBtn);
            } else if (p.name === 'prune') {
                var pruneBtn = document.createElement('button');
                pruneBtn.className = 'framework-playground__action-btn';
                pruneBtn.textContent = 'PRUNE WEAK FITS';
                pruneBtn.onclick = rerunCurrentPhase;
                wrap.appendChild(pruneBtn);

                var pruneNextBtn = document.createElement('button');
                pruneNextBtn.className = 'framework-playground__action-btn framework-playground__action-btn--muted';
                pruneNextBtn.textContent = 'PROCEED TO DOU';
                pruneNextBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(pruneNextBtn);
            } else if (p.name === 'dou') {
                var douBtn = document.createElement('button');
                douBtn.className = 'framework-playground__action-btn';
                douBtn.textContent = 'SURFACE DOU';
                douBtn.onclick = rerunCurrentPhase;
                wrap.appendChild(douBtn);

                var douNextBtn = document.createElement('button');
                douNextBtn.className = 'framework-playground__action-btn framework-playground__action-btn--muted';
                douNextBtn.textContent = 'PROCEED TO DECORATE';
                douNextBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(douNextBtn);
            } else if (p.name === 'hydrate') {
                var hydroBatchRow = document.createElement('div');
                hydroBatchRow.style.display = 'grid';
                hydroBatchRow.style.gap = '0.35rem';
                hydroBatchRow.appendChild(createControlCaption('PRECISION FILL: ' + hydrateBatchSize));
                var hydroSlider = document.createElement('input');
                hydroSlider.type = 'range';
                hydroSlider.min = '1';
                hydroSlider.max = '10';
                hydroSlider.value = hydrateBatchSize;
                setRangePct(hydroSlider, (hydrateBatchSize - 1) / 9 * 100);
                hydroSlider.oninput = function () {
                    setRangePct(this, (this.value - 1) / 9 * 100);
                    hydrateBatchSize = parseInt(this.value);
                    renderPhaseControls(phaseIdx);
                };
                hydroBatchRow.appendChild(hydroSlider);
                wrap.appendChild(hydroBatchRow);

                var fillBtn = document.createElement('button');
                fillBtn.className = 'framework-playground__action-btn';
                fillBtn.textContent = 'FILL GAPS';
                fillBtn.onclick = runHydratePass;
                wrap.appendChild(fillBtn);

                var nextBtn = document.createElement('button');
                nextBtn.className = 'framework-playground__action-btn framework-playground__action-btn--muted';
                nextBtn.textContent = 'PROCEED TO RELEASE';
                nextBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(nextBtn);
            } else if (p.name === 'decorate') {
                var polishRow = document.createElement('div');
                polishRow.style.display = 'grid';
                polishRow.style.gap = '0.35rem';
                polishRow.appendChild(createControlCaption('POLISH INTENSITY: ' + Math.round(polishIntensity * 100) + '%'));
                var polishSlider = document.createElement('input');
                polishSlider.type = 'range';
                polishSlider.min = '0';
                polishSlider.max = '1';
                polishSlider.step = '0.01';
                polishSlider.value = polishIntensity;
                setRangePct(polishSlider, polishIntensity * 100);
                polishSlider.oninput = function () {
                    polishIntensity = parseFloat(this.value);
                    setRangePct(this, polishIntensity * 100);
                    marbles.forEach(function (m) {
                        if (m.settled) m.saturation = 0.6 + polishIntensity * 0.4;
                    });
                    render();
                    renderPhaseControls(phaseIdx);
                };
                polishRow.appendChild(polishSlider);
                wrap.appendChild(polishRow);

                var applyBtn = document.createElement('button');
                applyBtn.className = 'framework-playground__action-btn';
                applyBtn.textContent = 'APPLY FINISH';
                applyBtn.onclick = rerunCurrentPhase;
                wrap.appendChild(applyBtn);

                var decorateNextBtn = document.createElement('button');
                decorateNextBtn.className = 'framework-playground__action-btn framework-playground__action-btn--muted';
                decorateNextBtn.textContent = 'PROCEED TO HYDRATE';
                decorateNextBtn.onclick = function () {
                    showPhase(phaseIdx + 1);
                };
                wrap.appendChild(decorateNextBtn);
            } else if (p.name === 'release') {
                var launchBtn = document.createElement('button');
                launchBtn.className = 'framework-playground__action-btn';
                launchBtn.style.borderColor = 'var(--patina)';
                launchBtn.style.color = 'var(--patina)';
                launchBtn.style.background = 'rgba(90, 163, 163, 0.12)';
                launchBtn.textContent = 'RELEASE LOOP';
                launchBtn.onclick = function () {
                    shipGlow = 1.0;
                    startMotionLoop();
                    setTimeout(function () {
                        showPhase(0, true);
                    }, 2000);
                };
                wrap.appendChild(launchBtn);
            } else {
                var nextBtn = document.createElement('button');
                nextBtn.className = 'framework-playground__action-btn';
                nextBtn.textContent = phaseIdx < PHASES.length - 1 ? 'PROCEED TO ' + PHASES[phaseIdx + 1].label.toUpperCase() : 'RESTART LOOP';
                nextBtn.onclick = function () {
                    showPhase((phaseIdx + 1) % PHASES.length);
                };
                wrap.appendChild(nextBtn);
            }

            controlsEl.appendChild(wrap);
        }

        function updateUi(scrollToActive) {
            var phaseDef = PHASES[phase];
            phaseLabelEl.textContent = phaseDef.label;
            coverageEl.textContent = coveragePct + '%';
            marblesEl.textContent = marbles.length + overflowMarbles.length;
            eyebrowEl.textContent = phaseDef.eyebrow;
            pressEl.textContent = phaseDef.title + '.';
            commandEl.textContent = currentPhaseCommand();
            hintEl.textContent = phaseHint(phaseDef);
            coverageEl.classList.toggle('is-hot', coveragePct > 100);
            commandEl.classList.toggle('is-live', phaseDef.name === 'marbles' || phaseDef.name === 'agents' || phaseDef.name === 'hydrate');
            syncRail(scrollToActive);
            renderPhaseControls(phase);
        }

        function triggerPhaseAction() {
            var p = PHASES[phase];
            if (p.name === 'agents') {
                runAgentSpawn();
            } else if (p.name === 'review') {
                runReviewPass();
            } else if (p.name === 'marbles') {
                runMarblesSequence();
            } else if (p.name === 'hydrate') {
                runHydratePass();
            } else if (p.name === 'followup' || p.name === 'prune' || p.name === 'dou' || p.name === 'decorate') {
                rerunCurrentPhase();
            } else if (p.name === 'scaffold' || p.name === 'init' || p.name === 'research' || p.name === 'workflow') {
                showPhase(phase + 1);
            } else if (p.name === 'release') {
                shipGlow = 1.0;
                startMotionLoop();
                setTimeout(function () {
                    showPhase(0, true);
                }, 2000);
            }
        }

        function rerunCurrentPhase() {
            phaseTime = 0;
            throwTimer = 0;
            errorFlash = 0;
            if (PHASES[phase].name === 'release') {
                shipGlow = 1;
            }
            render();
            updateUi(false);
            startMotionLoop();
        }

        function runAgentSpawn() {
            var empty = slots.filter(function (s) {
                return s.visible && !s.filled;
            });
            for (var i = 0; i < Math.min(agentBatchSize, empty.length); i++) {
                var idx = Math.floor(Math.random() * empty.length);
                marbles.push(spawnMarble(empty[idx], 0.1, 'ocean'));
                empty.splice(idx, 1);
            }
            render();
            updateUi(false);
            startMotionLoop();
        }

        function runReviewPass() {
            var candidates = slots.filter(function (s) {
                return s.visible && !s.filled;
            });
            var reviewThrows = Math.min(Math.max(2, agentBatchSize), candidates.length);
            for (var i = 0; i < reviewThrows; i++) {
                var idx = Math.floor(Math.random() * candidates.length);
                marbles.push(spawnMarble(candidates[idx], 0.32, 'smoke'));
                candidates.splice(idx, 1);
            }
            overflowMarbles.push(spawnOverflow());
            if (Math.random() > 0.45) {
                overflowMarbles.push(spawnOverflow());
            }
            render();
            updateUi(false);
            startMotionLoop();
        }

        function runHydratePass() {
            var gaps = slots.filter(function (s) {
                return s.visible && !s.filled;
            });
            for (var i = 0; i < Math.min(hydrateBatchSize, gaps.length); i++) {
                marbles.push(spawnMarble(gaps[i], 0.05, 'forest'));
            }
            render();
            updateUi(false);
            startMotionLoop();
        }

        function spawnMarbleWave() {
            var empty = slots.filter(function (slot) {
                return slot.visible && !slot.filled;
            });
            var visible = countVisibleSlots();
            var filled = countFilledSlots();
            var fillRatio = visible > 0 ? filled / visible : 0;
            var batchSize = marbleBatchSize;

            for (var i = 0; i < batchSize; i++) {
                if (empty.length > 0) {
                    var idx = Math.floor(Math.random() * empty.length);
                    marbles.push(spawnMarble(empty[idx], 0.42 + fillRatio * 0.4));
                    empty.splice(idx, 1);
                } else {
                    overflowMarbles.push(spawnOverflow());
                }
            }

            if (fillRatio > 0.8) {
                overflowMarbles.push(spawnOverflow());
            }
        }

        function runMarblesSequence() {
            if (PHASES[phase].name !== 'marbles') return;
            marbleRunRemaining = marbleRunCount;
            throwTimer = 0;
            render();
            updateUi(false);
            startMotionLoop();
        }

        function resetCycle(hardReset) {
            phaseTime = 0;
            throwTimer = 0;
            errorFlash = 0;
            shipGlow = 0;
            marbleRunRemaining = 0;
            pings = [];
            if (hardReset) {
                grooveRevealProgress = 0;
                boardAlpha = 0;
                shakeX = 0;
                shakeY = 0;
                coveragePct = 0;
                marbles = [];
                overflowMarbles = [];
                buildSlots();
            }
        }

        function syncSlotVisibility() {
            var visibleCount = Math.floor(grooveRevealProgress * slots.length);
            for (var i = 0; i < slots.length; i++) {
                slots[i].visible = slots[i].revealOrder < visibleCount || phase > resolvePhaseIndex('workflow');
            }
        }

        function updatePhase(dt, isSimulating) {
            var p = PHASES[phase];
            phaseTime += dt;
            throwTimer -= dt;
            syncSlotVisibility();

            switch (p.name) {
                case 'scaffold':
                    boardAlpha = Math.min(1, phaseTime / 400);
                    grooveRevealProgress = 0;
                    if (phaseTime < 200) {
                        shakeX = (Math.random() - 0.5) * 4 * (1 - phaseTime / 200);
                        shakeY = (Math.random() - 0.5) * 4 * (1 - phaseTime / 200);
                    } else {
                        shakeX = 0;
                        shakeY = 0;
                    }
                    break;
                case 'init':
                    boardAlpha = Math.max(boardAlpha, 1);
                    grooveRevealProgress = Math.min(0.18, phaseTime / p.duration * 0.18);
                    break;
                case 'research':
                    boardAlpha = Math.max(boardAlpha, 1);
                    grooveRevealProgress = Math.min(0.42, phaseTime / p.duration * 0.42);
                    break;
                case 'workflow':
                    boardAlpha = Math.max(boardAlpha, 1);
                    grooveRevealProgress = Math.min(1, phaseTime / (p.duration * 0.65));
                    break;
                case 'agents':
                    if (isSimulating && throwTimer <= 0) {
                        var precise = slots.filter(function (s) {
                            return !s.filled && s.visible;
                        });
                        if (precise.length > 0) {
                            marbles.push(spawnMarble(precise[Math.floor(Math.random() * precise.length)], 0.15, 'ocean'));
                        }
                        throwTimer = 400 + Math.random() * 300;
                    }
                    break;
                case 'marbles':
                    if (!isSimulating && marbleRunRemaining > 0 && throwTimer <= 0) {
                        spawnMarbleWave();
                        marbleRunRemaining--;
                        throwTimer = Math.max(260, 720 - marblePower * 140);
                    }
                    break;
                case 'review':
                    if (isSimulating && throwTimer <= 0) {
                        var overflowSlots = slots.filter(function (s) {
                            return !s.filled && s.visible;
                        });
                        if (overflowSlots.length > 0) {
                            marbles.push(spawnMarble(overflowSlots[Math.floor(Math.random() * overflowSlots.length)], 0.8));
                        }
                        for (var o = 0; o < 3 + Math.floor(Math.random() * 4); o++) {
                            overflowMarbles.push(spawnOverflow());
                        }
                        throwTimer = 200;
                    }
                    break;
                case 'dou':
                    errorFlash = Math.sin(phaseTime * 0.015) * 0.5 + 0.5;
                    break;
                case 'followup':
                    if (phaseTime < 400) {
                        shakeX = Math.sin(phaseTime * 0.08) * 3 * (1 - phaseTime / 400);
                        shakeY = Math.cos(phaseTime * 0.06) * 2 * (1 - phaseTime / 400);
                    } else {
                        shakeX *= 0.9;
                        shakeY *= 0.9;
                    }
                    overflowMarbles.forEach(function (m) {
                        if (m.settled) {
                            m.vy += 0.5;
                            m.y += m.vy;
                            m.alpha = Math.max(0, m.alpha - 0.008);
                        }
                    });
                    overflowMarbles = overflowMarbles.filter(function (m) {
                        return m.alpha > 0.01;
                    });
                    break;
                case 'prune':
                    if (phaseTime < 100) {
                        var filled = slots.filter(function (s) {
                            return s.filled;
                        });
                        var toLose = Math.min(5, Math.ceil(filled.length * 0.06));
                        for (var l = 0; l < toLose; l++) {
                            var pick = filled[Math.floor(Math.random() * filled.length)];
                            pick.filled = false;
                            for (var j = marbles.length - 1; j >= 0; j--) {
                                if (marbles[j].target === pick && marbles[j].settled) {
                                    marbles[j].settled = false;
                                    marbles[j].vy = -5 - Math.random() * 5;
                                    marbles[j].vx = (Math.random() - 0.5) * 8;
                                    marbles[j].target = null;
                                    marbles[j].landY = height + 50;
                                    marbles[j].landX = marbles[j].x;
                                    break;
                                }
                            }
                        }
                    }
                    marbles.forEach(function (m) {
                        if (!m.settled && !m.target) {
                            m.vy += 0.3;
                            m.y += m.vy;
                            m.alpha = Math.max(0, m.alpha - 0.005);
                        }
                    });
                    marbles = marbles.filter(function (m) {
                        return m.alpha > 0.01 || m.settled;
                    });
                    break;
                case 'hydrate':
                    if (isSimulating && throwTimer <= 0) {
                        var gaps = slots.filter(function (s) {
                            return !s.filled && s.visible;
                        });
                        if (gaps.length > 0) {
                            marbles.push(spawnMarble(gaps[0], 0.05, 'forest'));
                        }
                        throwTimer = 500;
                    }
                    break;
                case 'decorate':
                    marbles.forEach(function (m) {
                        if (m.settled) m.saturation = Math.min(1, 0.6 + polishIntensity * 0.4 + phaseTime * 0.0001);
                    });
                    break;
                case 'release':
                    if (shipGlow > 0) {
                        shipGlow = Math.max(0, shipGlow - 0.015);
                    }
                    if (phaseTime > p.duration * 0.7) {
                        boardAlpha = Math.max(0, boardAlpha - 0.01);
                        marbles.forEach(function (m) {
                            m.alpha = Math.max(0, m.alpha - 0.008);
                        });
                    }
                    break;
            }

            syncSlotVisibility();

        }

        function render() {
            syncSlotVisibility();
            ctx.clearRect(0, 0, width, height);
            ctx.save();
            ctx.translate(shakeX, shakeY);

            drawBoardFrame(Math.max(boardAlpha, phase === 0 ? 0.88 : boardAlpha));

            if (boardAlpha > 0) {
                // High coverage glow
                if (coveragePct > 90) {
                    var shape = SHAPES[boardShape];
                    ctx.save();
                    ctx.globalAlpha = (coveragePct - 90) / 10 * 0.3 * boardAlpha;
                    ctx.beginPath();
                    if (shape === 'circle') ctx.arc(centerX, centerY, boardRadius * 1.05, 0, Math.PI * 2);
                    else if (shape === 'square') ctx.rect(centerX - boardRadius * 1.05, centerY - boardRadius * 1.05, boardRadius * 2.1, boardRadius * 2.1);
                    else if (shape === 'hexagon') {
                        for (var i = 0; i < 6; i++) {
                            var angle = (i * Math.PI) / 3;
                            var hx = centerX + boardRadius * 1.1 * Math.cos(angle);
                            var hy = centerY + boardRadius * 1.1 * Math.sin(angle);
                            if (i === 0) ctx.moveTo(hx, hy); else ctx.lineTo(hx, hy);
                        }
                        ctx.closePath();
                    }
                    ctx.strokeStyle = 'rgba(184, 115, 51, 0.4)';
                    ctx.lineWidth = 3;
                    ctx.stroke();
                    ctx.restore();
                }
            }

            for (var i = 0; i < slots.length; i++) {
                var slot = slots[i];
                if (slot.visible && boardAlpha > 0) {
                    drawGroove(slot.x, slot.y, marbleRadius, boardAlpha * 0.8);
                }
            }

            // Draw pings
            for (var p = pings.length - 1; p >= 0; p--) {
                if (!drawPing(pings[p], 0)) {
                    pings.splice(p, 1);
                }
            }

            if (errorFlash > 0) {
                ctx.globalAlpha = errorFlash * 0.15;
                ctx.fillStyle = '#e05544';
                ctx.fillRect(0, 0, width, height);
                ctx.globalAlpha = 1;
                if (errorFlash > 0.3) {
                    var alertCopy = currentAlertCopy();
                    ctx.globalAlpha = errorFlash * 0.8;
                    ctx.font = '700 ' + (boardRadius * 0.24) + 'px "IBM Plex Mono", "JetBrains Mono", monospace';
                    ctx.fillStyle = '#e05544';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(alertCopy.title, centerX, centerY - boardRadius * 0.02);
                    ctx.globalAlpha = errorFlash * 0.95;
                    ctx.font = '600 ' + (boardRadius * 0.07) + 'px "Poppins", sans-serif';
                    ctx.fillStyle = 'rgba(255, 214, 208, 0.96)';
                    ctx.fillText(alertCopy.detail, centerX, centerY + boardRadius * 0.14);
                    ctx.globalAlpha = 1;
                }
            }

            var allMarbles = marbles.concat(overflowMarbles).sort(function (a, b) {
                return a.y - b.y;
            });

            for (var m = 0; m < allMarbles.length; m++) {
                var marble = allMarbles[m];
                if (marble.alpha <= 0) continue;
                var sprite = makeSprite(marbleRadius, marble.pal, marble.seed);
                var speed = Math.sqrt(marble.vx * marble.vx + marble.vy * marble.vy);
                var hover = marble.settled ? 0 : Math.min(marbleRadius, speed * 1.2);
                if (hover > 1) {
                    ctx.globalAlpha = marble.alpha * 0.3;
                    ctx.beginPath();
                    ctx.ellipse(marble.x, marble.y + marbleRadius * 0.6, marbleRadius * 0.6, marbleRadius * 0.25, 0, 0, Math.PI * 2);
                    ctx.fillStyle = 'rgba(0,0,0,1)';
                    ctx.fill();
                }
                ctx.globalAlpha = marble.alpha * marble.saturation;
                ctx.drawImage(sprite, marble.x - sprite.width / 2, marble.y - hover - sprite.height / 2);
            }

            if (shipGlow > 0) {
                ctx.globalAlpha = shipGlow * 0.4;
                ctx.beginPath();
                ctx.arc(centerX, centerY, boardRadius * 1.2, 0, Math.PI * 2);
                var gg = ctx.createRadialGradient(centerX, centerY, boardRadius * 0.8, centerX, centerY, boardRadius * 1.2);
                gg.addColorStop(0, 'rgba(90, 163, 163, 0)');
                gg.addColorStop(0.5, 'rgba(90, 163, 163, 0.8)');
                gg.addColorStop(1, 'rgba(90, 163, 163, 0)');
                ctx.fillStyle = gg;
                ctx.fill();
                ctx.globalAlpha = 1;
            }

            ctx.restore();
            ctx.globalAlpha = 1;
            updateCoverage();
        }

        function advanceSimulation(ms) {
            var steps = Math.max(1, Math.round(ms / 16));
            for (var step = 0; step < steps; step++) {
                var all = marbles.concat(overflowMarbles);
                for (var i = 0; i < all.length; i++) updateMarble(all[i], 1);
                for (var p = pings.length - 1; p >= 0; p--) {
                    pings[p].life -= 16 * 0.002;
                    if (pings[p].life <= 0) pings.splice(p, 1);
                }
                updatePhase(16, true);
            }
        }

        function hasMovingBodies() {
            var p = PHASES[phase];
            if (phaseTime < p.duration) return true;
            if (p.name === 'dou') return true;
            if (p.name === 'marbles' && marbleRunRemaining > 0) return true;
            if (pings.length > 0) return true;
            var all = marbles.concat(overflowMarbles);
            for (var i = 0; i < all.length; i++) {
                if (!all[i].settled && all[i].alpha > 0.01) return true;
            }
            return false;
        }

        function advanceMotion(ms) {
            var steps = Math.max(1, Math.round(ms / 16));
            for (var step = 0; step < steps; step++) {
                var all = marbles.concat(overflowMarbles);
                for (var i = 0; i < all.length; i++) updateMarble(all[i], 1);
                for (var p = pings.length - 1; p >= 0; p--) {
                    pings[p].life -= 16 * 0.002;
                    if (pings[p].life <= 0) pings.splice(p, 1);
                }
                updatePhase(16, false);
            }
            render();
            updateUi(false);
        }

        function startMotionLoop() {
            if (!hasMovingBodies()) {
                frameHandle = 0;
                lastFrameTs = 0;
                return;
            }

            function tick(ts) {
                if (!lastFrameTs) lastFrameTs = ts;
                var dt = Math.min(32, ts - lastFrameTs);
                lastFrameTs = ts;
                if (dt > 0) advanceMotion(dt);
                if (hasMovingBodies()) {
                    frameHandle = window.requestAnimationFrame(tick);
                } else {
                    frameHandle = 0;
                    lastFrameTs = 0;
                }
            }

            if (frameHandle) window.cancelAnimationFrame(frameHandle);
            frameHandle = window.requestAnimationFrame(tick);
        }

        function showPhase(target, hardReset) {
            target = Math.max(0, Math.min(PHASES.length - 1, target));
            resetCycle(hardReset);

            if (hardReset) {
                for (var i = 0; i <= target; i++) {
                    phase = i;
                    phaseTime = 0;
                    throwTimer = 0;
                    errorFlash = 0;
                    advanceSimulation(PHASES[i].duration * (i === target ? (PHASES[i].snapshotRatio || 0.55) : 1));
                }
            }

            phase = target;
            render();
            updateUi(true);
            startMotionLoop();
        }

        function renderToText() {
            updateCoverage();
            return JSON.stringify({
                phase: PHASES[phase].name,
                phaseIndex: phase,
                command: currentPhaseCommand(),
                converge: coveragePct,
                marbles: marbles.length,
                overflow: overflowMarbles.length,
                marbleRunCount: marbleRunCount,
                marbleRunsRemaining: marbleRunRemaining,
                slots: slots.length,
                visibleSlots: countVisibleSlots(),
                filled: countFilledSlots(),
                shape: SHAPES[boardShape],
                density: boardDensity
            }, null, 2);
        }

        function resize() {
            var rect = stage.getBoundingClientRect();
            if (!rect.width || !rect.height) return;
            if (Math.abs(rect.width - measuredWidth) < 1 && Math.abs(rect.height - measuredHeight) < 1) return;
            measuredWidth = rect.width;
            measuredHeight = rect.height;
            width = rect.width;
            height = rect.height;
            dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, DPR_CAP));
            canvas.width = width * dpr;
            canvas.height = height * dpr;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            centerX = width / 2;
            centerY = height / 2;
            boardRadius = Math.min(width, height) * (layout === 'standalone' ? 0.43 : 0.38);
            marbleRadius = Math.max(6, boardRadius * (layout === 'standalone' ? 0.056 : 0.065));
            buildSlots();
            var currentPhase = phase;
            showPhase(currentPhase);
        }

        PHASES.forEach(function (phaseDef, index) {
            var button = document.createElement('button');
            button.className = 'framework-playground__chip';
            button.type = 'button';
            button.dataset.frameworkPhase = phaseDef.name;
            button.dataset.frameworkTooltip = phaseDef.title + ' — ' + phaseDef.description;
            button.setAttribute('aria-label', phaseDef.label + '. ' + phaseDef.title + '. ' + phaseDef.description);
            var buttonLabel = document.createElement('span');
            buttonLabel.className = 'framework-playground__chip-label';
            buttonLabel.textContent = phaseDef.label;
            button.appendChild(buttonLabel);
            button.addEventListener('click', function () {
                showPhase(index);
            });
            rail.appendChild(button);
            phaseButtons.push(button);
        });

        window.addEventListener('resize', resize);
        phase = resolvePhaseIndex(startPhaseName);
        resize();
        updateUi(true);

        root.renderFrameworkToText = renderToText;
        if (!window.render_framework_showcase_to_text) {
            window.render_framework_showcase_to_text = renderToText;
            window.advance_framework_showcase = function (ms) {
                advanceMotion(ms || 1000);
            };
            window.render_game_to_text = renderToText;
            window.advanceTime = function (ms) {
                advanceMotion(ms || 1000);
            };
        }
        root.dataset.frameworkInstance = String(rootIndex);
    }

    Array.prototype.forEach.call(document.querySelectorAll('[data-framework-playground]'), initFrameworkPlayground);
})();
