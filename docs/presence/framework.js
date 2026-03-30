(function () {
    var prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var DPR_CAP = prefersReducedMotion ? 1.25 : 2;

    var PHASES = [
        {
            name: 'init',
            label: 'Init',
            eyebrow: 'Phase 0 · Craft',
            title: 'Strike the board into reality',
            description: 'The surface appears as one decisive object. Before context, before code, the board itself has to exist.',
            detail: 'Board slam · zero coverage',
            duration: 1500,
            snapshotRatio: 0.28
        },
        {
            name: 'workflow',
            label: 'Workflow',
            eyebrow: 'Phase 1 · Craft',
            title: 'Reveal the grooves',
            description: 'The lanes emerge from the center out. Structure shows up before content so the next moves have somewhere true to land.',
            detail: 'Groove reveal · shape before filling',
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
            name: 'overflow',
            label: 'Overflow',
            eyebrow: 'Phase 2 · Converge',
            title: 'See what spills beyond the grooves',
            description: 'Too much energy creates excess. The board overfills, exposing the difference between apparent progress and real fit.',
            detail: 'Coverage can overshoot 100%',
            duration: 2500,
            snapshotRatio: 0.62
        },
        {
            name: 'error',
            label: 'P0',
            eyebrow: 'Phase 2 · Converge',
            title: 'Surface the red truth',
            description: 'The cycle pauses on a failure signal. Better to stop on reality than glide past a blocker because the animation looked convincing.',
            detail: 'P0 flash · convergence interrupted',
            duration: 1000,
            snapshotRatio: 0.48
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
            name: 'ship',
            label: 'Ship',
            eyebrow: 'Final Step · Release',
            title: 'Release the finished surface',
            description: 'The board glows, holds, and then fades for the next cycle. Shipping is not the absence of motion; it is a completed loop ready to start again.',
            detail: 'Stable board · reset for next cycle',
            duration: 3000,
            snapshotRatio: 0.34
        }
    ];

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
        hl.addColorStop(0, 'rgba(255,255,255,0.9)');
        hl.addColorStop(0.15, 'rgba(255,255,255,0.5)');
        hl.addColorStop(0.5, 'rgba(255,255,255,0.08)');
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
        switch (phaseDef.name) {
        case 'init':
            return 'vc-init';
        case 'workflow':
            return 'vc-workflow';
        case 'agents':
            return 'vc-agents';
        case 'marbles':
            return 'vc-marbles';
        case 'overflow':
        case 'error':
        case 'followup':
            return 'vc-followup';
        case 'prune':
            return 'vc-prune';
        case 'hydrate':
            return 'vc-hydrate';
        case 'decorate':
            return 'vc-decorate';
        case 'ship':
            return 'vc-release';
        default:
            return 'vibecrafted';
        }
    }

    function phaseHint(phaseDef) {
        if (phaseDef.name === 'marbles') {
            return 'Click Marbles again to throw another batch into the board.';
        }
        if (phaseDef.name === 'init') {
            return 'The command line starts here. Context comes before motion.';
        }
        return phaseDef.description;
    }

    function buildShowcaseMarkup(layout) {
        var headerTitle = layout === 'standalone'
            ? 'Command the board phase by phase'
            : 'A phase-by-phase board of the convergence loop';

        return [
            '<div class="framework-playground framework-playground--' + layout + '">',
            '  <div class="framework-playground__meta">',
            '    <div class="framework-playground__meta-copy">',
            '      <p class="framework-playground__kicker">Framework Playground</p>',
            '      <h3 class="framework-playground__heading">' + headerTitle + '</h3>',
            '      <p class="framework-playground__lede">Board-first, manual-only. Choose a phase, read the grooves, and let the board explain the loop.</p>',
            '    </div>',
            '  </div>',
            '  <div class="framework-playground__body">',
            '    <section class="framework-playground__board-column">',
            '      <p class="framework-playground__pressline">',
            '        <span class="framework-playground__press-kicker" data-framework-phase-eyebrow>Phase 0 · Craft</span>',
            '        <span class="framework-playground__press-copy" data-framework-phase-press>Strike the board into reality.</span>',
            '      </p>',
            '      <div class="framework-playground__stage">',
            '      <canvas class="framework-playground__canvas" aria-hidden="true"></canvas>',
            '      <div class="framework-playground__overlay" aria-hidden="true">',
            '        <span>Phase <strong data-framework-phase-label>Init</strong></span>',
            '        <span>Converge <strong data-framework-coverage>0%</strong></span>',
            '        <span>Marbles <strong data-framework-marbles>0</strong></span>',
            '      </div>',
            '        <p class="framework-playground__prompt" aria-hidden="true">',
            '          <span class="framework-playground__prompt-mark">$ &gt;</span>',
            '          <span class="framework-playground__prompt-command" data-framework-command>vc-init</span>',
            '        </p>',
            '      </div>',
            '    </section>',
            '    <aside class="framework-playground__side-column">',
            '      <p class="framework-playground__side-kicker">Phase Rail</p>',
            '      <p class="framework-playground__side-copy" data-framework-phase-hint>Click a phase to inspect the board. Click Marbles again to throw another batch.</p>',
            '      <div class="framework-playground__rail-shell">',
            '        <div class="framework-playground__rail framework-playground__rail--stack" data-framework-rail></div>',
            '      </div>',
            '    </aside>',
            '  </div>',
            '</div>'
        ].join('');
    }

    function initFrameworkPlayground(root, rootIndex) {
        if (!root || root.dataset.frameworkReady === 'true') return;
        root.dataset.frameworkReady = 'true';

        var layout = root.getAttribute('data-framework-layout') || 'inline';
        var startPhaseName = root.getAttribute('data-framework-start') || (layout === 'inline' ? 'marbles' : 'init');
        root.classList.add('framework-playground');
        root.classList.toggle('framework-playground--standalone', layout === 'standalone');

        root.innerHTML = buildShowcaseMarkup(layout);

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
            var sp = marbleRadius * 2.2;
            var rh = sp * 0.866;
            var row = 0;
            for (var y = centerY - boardRadius + marbleRadius; y <= centerY + boardRadius - marbleRadius; y += rh) {
                var off = (row % 2) ? sp / 2 : 0;
                for (var x = centerX - boardRadius + marbleRadius; x <= centerX + boardRadius - marbleRadius; x += sp) {
                    var px = x + off;
                    var dx = px - centerX;
                    var dy = y - centerY;
                    if (Math.sqrt(dx * dx + dy * dy) + marbleRadius * 0.85 <= boardRadius) {
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
            ctx.strokeStyle = 'rgba(0,0,0,0.12)';
            ctx.lineWidth = 0.8;
            ctx.stroke();
            ctx.globalAlpha = 1;
        }

        function spawnMarble(targetSlot, chaos, palKey) {
            var angle = Math.random() * Math.PI * 2;
            var dist = boardRadius * (0.6 + chaos * 0.8);
            return {
                x: centerX + Math.cos(angle) * dist,
                y: centerY + Math.sin(angle) * dist - boardRadius * chaos * 0.3,
                vx: (Math.random() - 0.5) * 14 * chaos,
                vy: (Math.random() - 0.5) * 10 * chaos + 3,
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
                vx: (Math.random() - 0.5) * 20,
                vy: 10 + Math.random() * 15,
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
            var attract = 0.012 + (m.target ? 0.008 : 0.004);
            m.vx += dx * attract;
            m.vy += dy * attract;
            m.vx *= 0.87;
            m.vy *= 0.87;
            m.x += m.vx * dt;
            m.y += m.vy * dt;
            if (dist < 2 && Math.abs(m.vx) < 0.8 && Math.abs(m.vy) < 0.8) {
                m.settled = true;
                m.x = tx;
                m.y = ty;
                if (m.target) m.target.filled = true;
            }
        }

        function updateCoverage() {
            var filled = slots.filter(function (slot) {
                return slot.filled;
            }).length;
            var total = slots.filter(function (slot) {
                return slot.visible;
            }).length;
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

        function updateUi(scrollToActive) {
            var phaseDef = PHASES[phase];
            phaseLabelEl.textContent = phaseDef.label;
            coverageEl.textContent = coveragePct + '%';
            marblesEl.textContent = marbles.length + overflowMarbles.length;
            eyebrowEl.textContent = phaseDef.eyebrow;
            pressEl.textContent = phaseDef.title + '.';
            commandEl.textContent = phaseCommand(phaseDef);
            hintEl.textContent = phaseHint(phaseDef);
            coverageEl.classList.toggle('is-hot', coveragePct > 100);
            commandEl.classList.toggle('is-live', phaseDef.name === 'marbles');
            syncRail(scrollToActive);
        }

        function resetCycle() {
            phase = 0;
            phaseTime = 0;
            throwTimer = 0;
            grooveRevealProgress = 0;
            boardAlpha = 0;
            shakeX = 0;
            shakeY = 0;
            coveragePct = 0;
            errorFlash = 0;
            buildSlots();
        }

        function syncSlotVisibility() {
            var visibleCount = Math.floor(grooveRevealProgress * slots.length);
            for (var i = 0; i < slots.length; i++) {
                slots[i].visible = slots[i].revealOrder < visibleCount;
            }
        }

        function updatePhase(dt) {
            var p = PHASES[phase];
            phaseTime += dt;
            throwTimer -= dt;
            syncSlotVisibility();

            switch (p.name) {
            case 'init':
                boardAlpha = Math.min(1, phaseTime / 400);
                if (phaseTime < 200) {
                    shakeX = (Math.random() - 0.5) * 4 * (1 - phaseTime / 200);
                    shakeY = (Math.random() - 0.5) * 4 * (1 - phaseTime / 200);
                } else {
                    shakeX = 0;
                    shakeY = 0;
                }
                break;
            case 'workflow':
                grooveRevealProgress = Math.min(1, phaseTime / (p.duration * 0.85));
                break;
            case 'agents':
                if (throwTimer <= 0) {
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
                var progress = phaseTime / p.duration;
                var batchSize = Math.ceil(2 + progress * 6);
                if (throwTimer <= 0) {
                    var empty = slots.filter(function (s) {
                        return !s.filled && s.visible;
                    });
                    for (var i = 0; i < Math.min(batchSize, empty.length); i++) {
                        var idx = Math.floor(Math.random() * empty.length);
                        marbles.push(spawnMarble(empty[idx], 0.3 + progress * 0.5));
                        empty.splice(idx, 1);
                    }
                    throwTimer = 300 - progress * 150;
                }
                break;
            case 'overflow':
                if (throwTimer <= 0) {
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
            case 'error':
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
                if (throwTimer <= 0) {
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
                    if (m.settled) m.saturation = Math.min(1, m.saturation + 0.003);
                });
                break;
            case 'ship':
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
            ctx.clearRect(0, 0, width, height);
            ctx.save();
            ctx.translate(shakeX, shakeY);

            if (boardAlpha > 0) {
                ctx.globalAlpha = boardAlpha;
                ctx.beginPath();
                ctx.arc(centerX, centerY, boardRadius * 1.05, 0, Math.PI * 2);
                var bg = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, boardRadius * 1.05);
                bg.addColorStop(0, 'rgba(40,40,38,0.7)');
                bg.addColorStop(1, 'rgba(20,20,18,0.9)');
                ctx.fillStyle = bg;
                ctx.fill();
                ctx.strokeStyle = 'rgba(242,239,221,0.06)';
                ctx.lineWidth = 1.5;
                ctx.stroke();
                ctx.globalAlpha = 1;
            }

            for (var i = 0; i < slots.length; i++) {
                var slot = slots[i];
                if (slot.visible && boardAlpha > 0) {
                    drawGroove(slot.x, slot.y, marbleRadius, boardAlpha * 0.8);
                }
            }

            if (errorFlash > 0) {
                ctx.globalAlpha = errorFlash * 0.15;
                ctx.fillStyle = '#e05544';
                ctx.fillRect(0, 0, width, height);
                ctx.globalAlpha = 1;
                if (errorFlash > 0.3) {
                    ctx.globalAlpha = errorFlash * 0.8;
                    ctx.font = 'bold ' + (boardRadius * 0.3) + 'px sans-serif';
                    ctx.fillStyle = '#e05544';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText('P0', centerX, centerY);
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

            ctx.restore();
            ctx.globalAlpha = 1;
            updateCoverage();
        }

        function advanceSimulation(ms) {
            var steps = Math.max(1, Math.round(ms / 16));
            for (var step = 0; step < steps; step++) {
                var all = marbles.concat(overflowMarbles);
                for (var i = 0; i < all.length; i++) updateMarble(all[i], 1);
                updatePhase(16);
            }
        }

        function hasMovingBodies() {
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

        function throwManualBatch() {
            if (PHASES[phase].name !== 'marbles') return;

            var empty = slots.filter(function (slot) {
                return slot.visible && !slot.filled;
            });
            var visible = slots.filter(function (slot) {
                return slot.visible;
            }).length;
            var filled = slots.filter(function (slot) {
                return slot.filled;
            }).length;
            var fillRatio = visible > 0 ? filled / visible : 0;
            var batchSize = Math.max(5, Math.min(12, Math.round(6 + fillRatio * 7)));

            for (var i = 0; i < batchSize; i++) {
                if (empty.length > 0) {
                    var idx = Math.floor(Math.random() * empty.length);
                    marbles.push(spawnMarble(empty[idx], 0.42 + fillRatio * 0.4));
                    empty.splice(idx, 1);
                } else {
                    overflowMarbles.push(spawnOverflow());
                }
            }

            if (fillRatio > 0.68) {
                overflowMarbles.push(spawnOverflow());
            }

            updateCoverage();
            render();
            updateUi(false);
            startMotionLoop();
        }

        function showPhase(target) {
            target = Math.max(0, Math.min(PHASES.length - 1, target));
            resetCycle();
            for (var i = 0; i <= target; i++) {
                phase = i;
                phaseTime = 0;
                throwTimer = 0;
                errorFlash = 0;
                advanceSimulation(PHASES[i].duration * (i === target ? (PHASES[i].snapshotRatio || 0.55) : 1));
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
                command: phaseCommand(PHASES[phase]),
                converge: coveragePct,
                marbles: marbles.length,
                overflow: overflowMarbles.length,
                slots: slots.length,
                filled: slots.filter(function (slot) {
                    return slot.filled;
                }).length
            });
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
            boardRadius = Math.min(width, height) * (layout === 'standalone' ? 0.36 : 0.38);
            marbleRadius = Math.max(6, boardRadius * 0.065);
            var currentPhase = phase;
            showPhase(currentPhase);
        }

        PHASES.forEach(function (phaseDef, index) {
            var button = document.createElement('button');
            button.className = 'framework-playground__chip';
            button.type = 'button';
            button.dataset.frameworkTooltip = phaseDef.title + ' — ' + phaseDef.description;
            button.setAttribute('aria-label', phaseDef.label + '. ' + phaseDef.title + '. ' + phaseDef.description);
            button.innerHTML = '<span class="framework-playground__chip-label">' + phaseDef.label + '</span>';
            button.addEventListener('click', function () {
                if (index === phase && phaseDef.name === 'marbles') {
                    throwManualBatch();
                    return;
                }
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
