(function () {
    var prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var DPR_CAP = prefersReducedMotion ? 1.25 : 2;

    var PHASES = [
        {
            name: 'scaffold',
            label: 'Scaffold',
            eyebrow: 'Phase 0 · Setup',
            title: 'Define the board geometry',
            description: 'Choose the foundation. Before any code runs, we must agree on the shape and capacity of the workspace.',
            detail: 'Board shape · density configuration',
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
        case 'scaffold':
            return 'vc-scaffold';
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
            return 'Adjust throw power and batch size, then throw to converge the board.';
        }
        if (phaseDef.name === 'agents') {
            return 'Select specialist count and spawn them into the grooves.';
        }
        if (phaseDef.name === 'scaffold') {
            return 'Configure the board geometry and density before starting the loop.';
        }
        if (phaseDef.name === 'hydrate') {
            return 'Fill the remaining critical gaps with deterministic precision.';
        }
        if (phaseDef.name === 'decorate') {
            return 'Apply final polish pass to saturate colors and sharpen the finish.';
        }
        if (phaseDef.name === 'ship') {
            return 'Launch the finished surface and release the loop to the market.';
        }
        return phaseDef.description;
    }

    function buildShowcaseMarkup(layout) {
        return [
            '<div class="framework-playground framework-playground--' + layout + '">',
            '  <div class="framework-playground__meta">',
            '    <div class="framework-playground__meta-copy">',
            '      <p class="framework-playground__kicker">Framework Playground</p>',
            '      <h3 class="framework-playground__heading">Manual teaching surface</h3>',
            '      <p class="framework-playground__lede">Board-first, manual-only. Choose a phase and use the operators to command the board.</p>',
            '    </div>',
            '  </div>',
            '  <div class="framework-playground__body">',
            '    <section class="framework-playground__board-column">',
            '      <p class="framework-playground__pressline">',
            '        <span class="framework-playground__press-kicker" data-framework-phase-eyebrow>Phase 0 · Setup</span>',
            '        <span class="framework-playground__press-copy" data-framework-phase-press>Define the board geometry.</span>',
            '      </p>',
            '      <div class="framework-playground__stage">',
            '        <canvas class="framework-playground__canvas" aria-hidden="true"></canvas>',
            '        <div class="framework-playground__overlay" aria-hidden="true">',
            '          <span>Phase <strong data-framework-phase-label>Scaffold</strong></span>',
            '          <span>Converge <strong data-framework-coverage>0%</strong></span>',
            '          <span>Marbles <strong data-framework-marbles>0</strong></span>',
            '        </div>',
            '        <p class="framework-playground__prompt" aria-hidden="true">',
            '          <span class="framework-playground__prompt-mark">$ &gt;</span>',
            '          <span class="framework-playground__prompt-command" data-framework-command>vc-scaffold</span>',
            '        </p>',
            '      </div>',
            '    </section>',
            '    <aside class="framework-playground__side-column">',
            '      <p class="framework-playground__side-kicker">Operators</p>',
            '      <div class="framework-playground__controls" data-framework-controls></div>',
            '      <p class="framework-playground__side-kicker" style="margin-top: 1rem;">Choose Phase</p>',
            '      <div class="framework-playground__rail-shell">',
            '        <div class="framework-playground__rail framework-playground__rail--stack" data-framework-rail></div>',
            '      </div>',
            '      <p class="framework-playground__side-copy" data-framework-phase-hint style="margin-top: 1rem;"></p>',
            '    </aside>',
            '  </div>',
            '</div>'
        ].join('');
    }

    function initFrameworkPlayground(root, rootIndex) {
        if (!root || root.dataset.frameworkReady === 'true') return;
        root.dataset.frameworkReady = 'true';

        var layout = root.getAttribute('data-framework-layout') || 'standalone';
        var startPhaseName = root.getAttribute('data-framework-start') || 'scaffold';
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

        var boardShape = 0; // index in SHAPES
        var boardDensity = 1.0;
        var marbleBatchSize = 8;
        var agentBatchSize = 3;
        var hydrateBatchSize = 5;
        var polishIntensity = 0.0;
        var marblePower = 1.0;
        var shipGlow = 0;

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
                        var q = (2/3 * dx) / (boardRadius * 0.8);
                        var r = (-1/3 * dx + Math.sqrt(3)/3 * dy) / (boardRadius * 0.8);
                        var s = -q-r;
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

        function renderPhaseControls(phaseIdx) {
            var p = PHASES[phaseIdx];
            controlsEl.innerHTML = '';
            
            var wrap = document.createElement('div');
            wrap.className = 'framework-playground__controls-inner';
            wrap.style.display = 'grid';
            wrap.style.gap = '0.75rem';

            if (p.name === 'scaffold') {
                var shapeRow = document.createElement('div');
                shapeRow.style.display = 'flex';
                shapeRow.style.alignItems = 'center';
                shapeRow.style.justifyContent = 'space-between';
                shapeRow.innerHTML = '<span style="font-size:0.7rem; color:var(--steel-dark); font-family:var(--font-mono);">LAYOUT</span>';

                var shapeNav = document.createElement('div');
                shapeNav.style.display = 'flex';
                shapeNav.style.gap = '0.35rem';

                var prevShape = document.createElement('button');
                prevShape.className = 'framework-playground__control-btn';
                prevShape.innerHTML = '&lt;';
                prevShape.onclick = function() {
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
                nextShape.innerHTML = '&gt;';
                nextShape.onclick = function() {
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
                densityRow.innerHTML = '<label style="font-size:0.7rem; color:var(--steel-dark); font-family:var(--font-mono);">DENSITY: ' + boardDensity.toFixed(1) + '</label>';
                var densitySlider = document.createElement('input');
                densitySlider.type = 'range';
                densitySlider.min = '0.5';
                densitySlider.max = '2.0';
                densitySlider.step = '0.1';
                densitySlider.value = boardDensity;
                densitySlider.oninput = function() {
                    boardDensity = parseFloat(this.value);
                    buildSlots();
                    render();
                    renderPhaseControls(phaseIdx);
                };
                densityRow.appendChild(densitySlider);
                wrap.appendChild(densityRow);

                var acceptBtn = document.createElement('button');
                acceptBtn.className = 'framework-playground__action-btn';
                acceptBtn.textContent = 'ACCEPT GEOMETRY';
                acceptBtn.onclick = function() { showPhase(phaseIdx + 1); };
                wrap.appendChild(acceptBtn);
            } else if (p.name === 'agents') {
                var agentBatchRow = document.createElement('div');
                agentBatchRow.style.display = 'grid';
                agentBatchRow.style.gap = '0.35rem';
                agentBatchRow.innerHTML = '<label style="font-size:0.7rem; color:var(--steel-dark); font-family:var(--font-mono);">SPECIALIST COUNT: ' + agentBatchSize + '</label>';
                var agentSlider = document.createElement('input');
                agentSlider.type = 'range';
                agentSlider.min = '1';
                agentSlider.max = '10';
                agentSlider.value = agentBatchSize;
                agentSlider.oninput = function() {
                    agentBatchSize = parseInt(this.value);
                    renderPhaseControls(phaseIdx);
                };
                agentBatchRow.appendChild(agentSlider);
                wrap.appendChild(agentBatchRow);

                var spawnBtn = document.createElement('button');
                spawnBtn.className = 'framework-playground__action-btn';
                spawnBtn.textContent = 'SPAWN AGENTS';
                spawnBtn.onclick = function() {
                    var empty = slots.filter(function (s) { return s.visible && !s.filled; });
                    for (var i = 0; i < Math.min(agentBatchSize, empty.length); i++) {
                        var idx = Math.floor(Math.random() * empty.length);
                        marbles.push(spawnMarble(empty[idx], 0.1, 'ocean'));
                        empty.splice(idx, 1);
                    }
                    startMotionLoop();
                };
                wrap.appendChild(spawnBtn);

                var nextBtn = document.createElement('button');
                nextBtn.className = 'framework-playground__action-btn';
                nextBtn.style.background = 'rgba(163, 184, 199, 0.12)';
                nextBtn.textContent = 'PROCEED TO MARBLES';
                nextBtn.onclick = function() { showPhase(phaseIdx + 1); };
                wrap.appendChild(nextBtn);
            } else if (p.name === 'marbles') {
                var batchRow = document.createElement('div');
                batchRow.style.display = 'grid';
                batchRow.style.gap = '0.35rem';
                batchRow.innerHTML = '<label style="font-size:0.7rem; color:var(--steel-dark); font-family:var(--font-mono);">BATCH SIZE: ' + marbleBatchSize + '</label>';
                var batchSlider = document.createElement('input');
                batchSlider.type = 'range';
                batchSlider.min = '1';
                batchSlider.max = '30';
                batchSlider.value = marbleBatchSize;
                batchSlider.oninput = function() {
                    marbleBatchSize = parseInt(this.value);
                    renderPhaseControls(phaseIdx);
                };
                batchRow.appendChild(batchSlider);
                wrap.appendChild(batchRow);

                var powerRow = document.createElement('div');
                powerRow.style.display = 'grid';
                powerRow.style.gap = '0.35rem';
                powerRow.innerHTML = '<label style="font-size:0.7rem; color:var(--steel-dark); font-family:var(--font-mono);">POWER: ' + marblePower.toFixed(1) + '</label>';
                var powerSlider = document.createElement('input');
                powerSlider.type = 'range';
                powerSlider.min = '0.5';
                powerSlider.max = '3.0';
                powerSlider.step = '0.1';
                powerSlider.value = marblePower;
                powerSlider.oninput = function() {
                    marblePower = parseFloat(this.value);
                    renderPhaseControls(phaseIdx);
                };
                powerRow.appendChild(powerSlider);
                wrap.appendChild(powerRow);

                var throwBtn = document.createElement('button');
                throwBtn.className = 'framework-playground__action-btn';
                throwBtn.textContent = 'THROW BATCH';
                throwBtn.onclick = function() { throwManualBatch(); };
                wrap.appendChild(throwBtn);

                var nextBtn = document.createElement('button');
                nextBtn.className = 'framework-playground__action-btn';
                nextBtn.style.background = 'rgba(163, 184, 199, 0.12)';
                nextBtn.textContent = 'PROCEED TO OVERFLOW';
                nextBtn.onclick = function() { showPhase(phaseIdx + 1); };
                wrap.appendChild(nextBtn);
            } else if (p.name === 'hydrate') {
                var hydroBatchRow = document.createElement('div');
                hydroBatchRow.style.display = 'grid';
                hydroBatchRow.style.gap = '0.35rem';
                hydroBatchRow.innerHTML = '<label style="font-size:0.7rem; color:var(--steel-dark); font-family:var(--font-mono);">PRECISION FILL: ' + hydrateBatchSize + '</label>';
                var hydroSlider = document.createElement('input');
                hydroSlider.type = 'range'; hydroSlider.min = '1'; hydroSlider.max = '10';
                hydroSlider.value = hydrateBatchSize;
                hydroSlider.oninput = function() { hydrateBatchSize = parseInt(this.value); renderPhaseControls(phaseIdx); };
                hydroBatchRow.appendChild(hydroSlider);
                wrap.appendChild(hydroBatchRow);

                var fillBtn = document.createElement('button');
                fillBtn.className = 'framework-playground__action-btn';
                fillBtn.textContent = 'FILL GAPS';
                fillBtn.onclick = function() {
                    var gaps = slots.filter(function (s) { return s.visible && !s.filled; });
                    for (var i = 0; i < Math.min(hydrateBatchSize, gaps.length); i++) {
                        marbles.push(spawnMarble(gaps[i], 0.05, 'forest'));
                    }
                    startMotionLoop();
                };
                wrap.appendChild(fillBtn);

                var nextBtn = document.createElement('button');
                nextBtn.className = 'framework-playground__action-btn';
                nextBtn.style.background = 'rgba(163, 184, 199, 0.12)';
                nextBtn.textContent = 'PROCEED TO DECORATE';
                nextBtn.onclick = function() { showPhase(phaseIdx + 1); };
                wrap.appendChild(nextBtn);
            } else if (p.name === 'decorate') {
                var polishRow = document.createElement('div');
                polishRow.style.display = 'grid';
                polishRow.style.gap = '0.35rem';
                polishRow.innerHTML = '<label style="font-size:0.7rem; color:var(--steel-dark); font-family:var(--font-mono);">POLISH INTENSITY: ' + Math.round(polishIntensity * 100) + '%</label>';
                var polishSlider = document.createElement('input');
                polishSlider.type = 'range'; polishSlider.min = '0'; polishSlider.max = '1'; polishSlider.step = '0.01';
                polishSlider.value = polishIntensity;
                polishSlider.oninput = function() { 
                    polishIntensity = parseFloat(this.value); 
                    marbles.forEach(function(m) { if(m.settled) m.saturation = 0.6 + polishIntensity * 0.4; });
                    render();
                    renderPhaseControls(phaseIdx); 
                };
                polishRow.appendChild(polishSlider);
                wrap.appendChild(polishRow);

                var applyBtn = document.createElement('button');
                applyBtn.className = 'framework-playground__action-btn';
                applyBtn.textContent = 'APPLY FINISH';
                applyBtn.onclick = function() { showPhase(phaseIdx + 1); };
                wrap.appendChild(applyBtn);
            } else if (p.name === 'ship') {
                var launchBtn = document.createElement('button');
                launchBtn.className = 'framework-playground__action-btn';
                launchBtn.style.borderColor = 'var(--patina)';
                launchBtn.style.color = 'var(--patina)';
                launchBtn.style.background = 'rgba(90, 163, 163, 0.12)';
                launchBtn.textContent = 'LAUNCH PRODUCT';
                launchBtn.onclick = function() { 
                    shipGlow = 1.0;
                    startMotionLoop();
                    setTimeout(function() { showPhase(0); }, 2000);
                };
                wrap.appendChild(launchBtn);
            } else {

                var nextBtn = document.createElement('button');
                nextBtn.className = 'framework-playground__action-btn';
                nextBtn.textContent = phaseIdx < PHASES.length - 1 ? 'PROCEED TO ' + PHASES[phaseIdx + 1].label.toUpperCase() : 'RESTART LOOP';
                nextBtn.onclick = function() { showPhase((phaseIdx + 1) % PHASES.length); };
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
            commandEl.textContent = phaseCommand(phaseDef);
            hintEl.textContent = phaseHint(phaseDef);
            coverageEl.classList.toggle('is-hot', coveragePct > 100);
            commandEl.classList.toggle('is-live', phaseDef.name === 'marbles' || phaseDef.name === 'agents' || phaseDef.name === 'hydrate');
            syncRail(scrollToActive);
            renderPhaseControls(phase);
        }

        function resetCycle() {
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

        function updatePhase(dt, isSimulating) {
            var p = PHASES[phase];
            phaseTime += dt;
            if (isSimulating) {
                throwTimer -= dt;
            }
            syncSlotVisibility();

            switch (p.name) {
            case 'scaffold':
                boardAlpha = Math.min(1, phaseTime / 400);
                grooveRevealProgress = 1; // Always show grooves in scaffold for configuration feedback
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
                var progress = phaseTime / p.duration;
                if (isSimulating && throwTimer <= 0) {
                    var empty = slots.filter(function (s) {
                        return !s.filled && s.visible;
                    });
                    for (var i = 0; i < Math.min(marbleBatchSize, empty.length); i++) {
                        var idx = Math.floor(Math.random() * empty.length);
                        marbles.push(spawnMarble(empty[idx], 0.3 + progress * 0.5));
                        empty.splice(idx, 1);
                    }
                    throwTimer = 300 - progress * 150;
                }
                break;
            case 'overflow':
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
            case 'ship':
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

            if (boardAlpha > 0) {
                ctx.globalAlpha = boardAlpha;
                ctx.beginPath();
                var shape = SHAPES[boardShape];
                if (shape === 'circle') {
                    ctx.arc(centerX, centerY, boardRadius * 1.05, 0, Math.PI * 2);
                } else if (shape === 'square') {
                    ctx.rect(centerX - boardRadius * 1.05, centerY - boardRadius * 1.05, boardRadius * 2.1, boardRadius * 2.1);
                } else if (shape === 'hexagon') {
                    for (var i = 0; i < 6; i++) {
                        var angle = (i * Math.PI) / 3;
                        var hx = centerX + boardRadius * 1.1 * Math.cos(angle);
                        var hy = centerY + boardRadius * 1.1 * Math.sin(angle);
                        if (i === 0) ctx.moveTo(hx, hy); else ctx.lineTo(hx, hy);
                    }
                    ctx.closePath();
                }
                
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
                updatePhase(16, true);
            }
        }

        function hasMovingBodies() {
            var p = PHASES[phase];
            if (phaseTime < p.duration) return true;
            if (p.name === 'error') return true;
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
                }).length,
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
