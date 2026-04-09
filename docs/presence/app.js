var prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
var supportsIntersectionObserver = 'IntersectionObserver' in window;
var liveRegion;
var liveRegionTimer;
var appLocale = ((document.documentElement && document.documentElement.lang) || 'en').toLowerCase();
var isPolishLocale = appLocale.indexOf('pl') === 0;
var uiStrings = isPolishLocale ? {
    copy: 'Kopiuj',
    copied: 'Skopiowano',
    copyFailed: 'Błąd kopiowania',
    codeCopied: 'Blok kodu został skopiowany do schowka.',
    copyCodeFallback: 'Kopiowanie się nie udało. Zaznacz polecenie i skopiuj je ręcznie.',
    installCopied: 'Polecenie instalacji zostało skopiowane do schowka.',
    copyInstallFallback: 'Kopiowanie się nie udało. Zaznacz polecenie instalacji i skopiuj je ręcznie.',
    commandCopied: 'Polecenie zostało skopiowane do schowka.',
    copyCommandFallback: 'Kopiowanie się nie udało. Zaznacz polecenie i skopiuj je ręcznie.',
    copyCommandAriaPrefix: 'Skopiuj polecenie: ',
    pipelineCopied: 'Kod pipeline został skopiowany.',
    tooltipCopy: 'Kopiuj',
    previewUnavailable: 'Podgląd jest niedostępny.'
} : {
    copy: 'Copy',
    copied: 'Copied',
    copyFailed: 'Copy failed',
    codeCopied: 'Code block copied to clipboard.',
    copyCodeFallback: 'Copy failed. Select the command and copy it manually.',
    installCopied: 'Install command copied to clipboard.',
    copyInstallFallback: 'Copy failed. Select the install command and copy it manually.',
    commandCopied: 'Command copied to clipboard.',
    copyCommandFallback: 'Copy failed. Select the command and copy it manually.',
    copyCommandAriaPrefix: 'Copy command: ',
    pipelineCopied: 'Pipeline code copied.',
    tooltipCopy: 'Copy',
    previewUnavailable: 'Preview unavailable.'
};

function getLiveRegion() {
    if (liveRegion) return liveRegion;
    liveRegion = document.createElement('div');
    liveRegion.className = 'sr-only';
    liveRegion.setAttribute('aria-live', 'polite');
    liveRegion.setAttribute('aria-atomic', 'true');
    document.body.appendChild(liveRegion);
    return liveRegion;
}

function announceUiMessage(message) {
    if (!message) return;
    var region = getLiveRegion();
    clearTimeout(liveRegionTimer);
    region.textContent = '';
    liveRegionTimer = setTimeout(function () {
        region.textContent = message;
    }, 40);
}

function fallbackCopyText(text) {
    if (!text) return false;
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.top = '-9999px';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.focus();
    area.select();
    area.setSelectionRange(0, area.value.length);
    var copied = false;
    try {
        copied = document.execCommand('copy');
    } catch (err) {
        copied = false;
    }
    document.body.removeChild(area);
    return copied;
}

function copyText(text) {
    if (!text) return Promise.resolve(false);
    if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) {
        return navigator.clipboard.writeText(text).then(function () {
            return true;
        }).catch(function () {
            return fallbackCopyText(text);
        });
    }
    return Promise.resolve(fallbackCopyText(text));
}

function flashCopyButton(btn, copied) {
    if (!btn) return;
    var defaultText = btn.getAttribute('data-default-label') || btn.textContent.trim() || uiStrings.copy;
    btn.textContent = copied ? uiStrings.copied : uiStrings.copyFailed;
    btn.classList.toggle('is-copied', copied);
    btn.classList.toggle('is-error', !copied);
    clearTimeout(btn._copyTimer);
    btn._copyTimer = setTimeout(function () {
        btn.textContent = defaultText;
        btn.classList.remove('is-copied', 'is-error');
    }, copied ? 1400 : 1800);
}

// ============ GLASS MARBLE RENDERER (shared) ============
var MarbleFactory = (function () {
    // Color helpers
    function hexToRgb(hex) {
        var r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16),
            b = parseInt(hex.slice(5, 7), 16);
        return {r: r, g: g, b: b};
    }

    function rgbStr(c, a) {
        return 'rgba(' + c.r + ',' + c.g + ',' + c.b + ',' + (a || 1) + ')';
    }

    function lighten(c, pct) {
        return {r: Math.min(255, c.r + pct), g: Math.min(255, c.g + pct), b: Math.min(255, c.b + pct)};
    }

    function darken(c, pct) {
        return {r: Math.max(0, c.r - pct), g: Math.max(0, c.g - pct), b: Math.max(0, c.b - pct)};
    }

    function blend(a, b, t) {
        return {
            r: Math.round(a.r + (b.r - a.r) * t),
            g: Math.round(a.g + (b.g - a.g) * t),
            b: Math.round(a.b + (b.b - a.b) * t)
        };
    }

    var PALETTES = [
        {base: '#d97757', accent: '#f4c89a', name: 'amber'},
        {base: '#6a9bcc', accent: '#c2ddf0', name: 'ocean'},
        {base: '#788c5d', accent: '#bdd4a0', name: 'forest'},
        {base: '#b0aea5', accent: '#e8e6dc', name: 'smoke'},
        {base: '#c46b8a', accent: '#f0c4d4', name: 'rose'},
        {base: '#8b7ec8', accent: '#cdc4ef', name: 'amethyst'},
        {base: '#cc8844', accent: '#f0d4a0', name: 'honey'},
        {base: '#5ba3a3', accent: '#a8dede', name: 'teal'}
    ];
    var PATTERNS = ['catseye', 'swirl', 'galaxy', 'clear', 'solid'];

    function createSprite(radius, paletteIdx, patternType, seed) {
        var pad = 4;
        var s = (radius * 2 + pad) * 2;
        var oc = document.createElement('canvas');
        oc.width = s;
        oc.height = s;
        var g = oc.getContext('2d');
        var cx = s / 2, cy = s / 2, r = radius;
        var pal = PALETTES[paletteIdx % PALETTES.length];
        var base = hexToRgb(pal.base);
        var accent = hexToRgb(pal.accent);
        var rng = mulberry32(seed);

        // Shadow
        g.beginPath();
        g.ellipse(cx + r * 0.05, cy + r * 0.82, r * 0.6, r * 0.18, 0, 0, Math.PI * 2);
        g.fillStyle = 'rgba(0,0,0,0.22)';
        g.fill();

        // Base sphere gradient
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

        // Pattern layer (inside clip)
        if (patternType === 'catseye') {
            // Single ribbon/vein across the marble
            var angle = rng() * Math.PI;
            g.save();
            g.translate(cx, cy);
            g.rotate(angle);
            var ribW = r * 0.22 + rng() * r * 0.15;
            var ribG = g.createLinearGradient(0, -ribW * 1.5, 0, ribW * 1.5);
            ribG.addColorStop(0, 'rgba(255,255,255,0)');
            ribG.addColorStop(0.25, rgbStr(accent, 0.7));
            ribG.addColorStop(0.5, rgbStr(lighten(accent, 40), 0.85));
            ribG.addColorStop(0.75, rgbStr(accent, 0.7));
            ribG.addColorStop(1, 'rgba(255,255,255,0)');
            g.fillStyle = ribG;
            g.fillRect(-r * 1.1, -ribW, r * 2.2, ribW * 2);
            // thin bright center line
            g.strokeStyle = rgbStr(lighten(accent, 60), 0.5);
            g.lineWidth = 1;
            g.beginPath();
            g.moveTo(-r * 0.9, 0);
            g.lineTo(r * 0.9, 0);
            g.stroke();
            g.restore();
        } else if (patternType === 'swirl') {
            // Two spiral bands of color
            g.save();
            g.translate(cx, cy);
            var sAngle = rng() * Math.PI * 2;
            for (var si = 0; si < 2; si++) {
                g.beginPath();
                var tw = r * 0.12 + rng() * r * 0.1;
                for (var t = 0; t < Math.PI * 3; t += 0.08) {
                    var sr = r * 0.1 + (t / (Math.PI * 3)) * r * 0.85;
                    var sx = Math.cos(sAngle + t) * sr;
                    var sy = Math.sin(sAngle + t) * sr;
                    if (t === 0) g.moveTo(sx, sy); else g.lineTo(sx, sy);
                }
                g.lineWidth = tw;
                var sCol = si === 0 ? accent : lighten(base, 35);
                g.strokeStyle = rgbStr(sCol, 0.55);
                g.lineCap = 'round';
                g.stroke();
                sAngle += Math.PI * 0.7;
            }
            g.restore();
        } else if (patternType === 'galaxy') {
            // Speckled dots inside like a galaxy marble
            g.save();
            g.translate(cx, cy);
            var dotCount = 15 + Math.floor(rng() * 20);
            for (var di = 0; di < dotCount; di++) {
                var da = rng() * Math.PI * 2;
                var dd = rng() * r * 0.8;
                var dr = 0.5 + rng() * 2;
                var dc = rng() > 0.5 ? accent : lighten(base, 40);
                g.beginPath();
                g.arc(Math.cos(da) * dd, Math.sin(da) * dd, dr, 0, Math.PI * 2);
                g.fillStyle = rgbStr(dc, 0.4 + rng() * 0.35);
                g.fill();
            }
            // Central glow
            var gg = g.createRadialGradient(0, 0, 0, 0, 0, r * 0.4);
            gg.addColorStop(0, rgbStr(accent, 0.25));
            gg.addColorStop(1, 'rgba(0,0,0,0)');
            g.fillStyle = gg;
            g.beginPath();
            g.arc(0, 0, r * 0.4, 0, Math.PI * 2);
            g.fill();
            g.restore();
        } else if (patternType === 'clear') {
            // Mostly transparent glass with colored core
            g.fillStyle = 'rgba(255,255,255,0.12)';
            g.fillRect(0, 0, s, s);
            var cg = g.createRadialGradient(cx, cy, 0, cx, cy, r * 0.45);
            cg.addColorStop(0, rgbStr(accent, 0.6));
            cg.addColorStop(0.6, rgbStr(base, 0.35));
            cg.addColorStop(1, 'rgba(0,0,0,0)');
            g.fillStyle = cg;
            g.beginPath();
            g.arc(cx, cy, r * 0.5, 0, Math.PI * 2);
            g.fill();
        }
        // solid = no extra pattern, just the base gradient

        // Glass internal refraction — subtle secondary highlight at bottom
        var rfl = g.createRadialGradient(cx + r * 0.2, cy + r * 0.35, r * 0.02, cx + r * 0.15, cy + r * 0.3, r * 0.45);
        rfl.addColorStop(0, 'rgba(255,255,255,0.26)');
        rfl.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = rfl;
        g.fillRect(0, 0, s, s);

        // Top specular highlight — the signature glass shine
        var hl = g.createRadialGradient(cx - r * 0.28, cy - r * 0.32, r * 0.02, cx - r * 0.15, cy - r * 0.2, r * 0.5);
        hl.addColorStop(0, 'rgba(255,255,255,0.98)');
        hl.addColorStop(0.12, 'rgba(255,255,255,0.72)');
        hl.addColorStop(0.34, 'rgba(255,255,255,0.24)');
        hl.addColorStop(0.62, 'rgba(255,255,255,0.08)');
        hl.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = hl;
        g.fillRect(0, 0, s, s);

        // Edge darkening rim
        var rim = g.createRadialGradient(cx, cy, r * 0.75, cx, cy, r);
        rim.addColorStop(0, 'rgba(0,0,0,0)');
        rim.addColorStop(0.8, 'rgba(0,0,0,0.08)');
        rim.addColorStop(1, 'rgba(0,0,0,0.28)');
        g.fillStyle = rim;
        g.fillRect(0, 0, s, s);

        g.restore(); // clip
        return oc;
    }

    // seeded PRNG (Mulberry32)
    function mulberry32(a) {
        return function () {
            a |= 0;
            a = a + 0x6D2B79F5 | 0;
            var t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
    }

    return {
        PALETTES: PALETTES,
        PATTERNS: PATTERNS,
        createSprite: createSprite,
        mulberry32: mulberry32
    };
})();

// ============ SOLITAIRE BOARD UTILS (shared) ============
function hexGridInCircle(cx, cy, R, mr) {
    var pos = [], sp = mr * 2.12, rh = sp * 0.866, row = 0;
    for (var y = cy - R + mr; y <= cy + R - mr; y += rh) {
        var off = (row % 2) ? sp / 2 : 0;
        for (var x = cx - R + mr; x <= cx + R - mr; x += sp) {
            var px = x + off, dx = px - cx, dy = y - cy;
            if (Math.sqrt(dx * dx + dy * dy) + mr * 0.85 <= R) pos.push({x: px, y: y});
        }
        row++;
    }
    return pos;
}

// Draw a carved wooden groove — concentric rings like a real solitaire board
function drawGroove(ctx, x, y, r) {
    // Outer shadow ring (depth illusion)
    ctx.beginPath();
    ctx.arc(x, y, r * 0.95, 0, Math.PI * 2);
    var sg = ctx.createRadialGradient(x - r * 0.1, y - r * 0.1, r * 0.2, x, y, r * 0.95);
    sg.addColorStop(0, 'rgba(0,0,0,0.28)');
    sg.addColorStop(0.6, 'rgba(0,0,0,0.18)');
    sg.addColorStop(1, 'rgba(0,0,0,0.05)');
    ctx.fillStyle = sg;
    ctx.fill();
    // Concentric ring — the lathe mark
    ctx.beginPath();
    ctx.arc(x, y, r * 0.72, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(0,0,0,0.12)';
    ctx.lineWidth = 0.8;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(x, y, r * 0.5, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(0,0,0,0.08)';
    ctx.lineWidth = 0.5;
    ctx.stroke();
    // Top-left light catch on the rim (like photo reference)
    ctx.beginPath();
    ctx.arc(x, y, r * 0.88, Math.PI * 0.9, Math.PI * 1.6);
    ctx.strokeStyle = 'rgba(176,174,165,0.07)';
    ctx.lineWidth = 1;
    ctx.stroke();
}

function shuffleArr(a) {
    for (var i = a.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var t = a[i];
        a[i] = a[j];
        a[j] = t;
    }
    return a;
}

// ============ HERO MARBLE SHOWCASE (PHYSICS CONVERGENCE) ============
(function () {
    var canvas = document.getElementById('marbleCanvas');
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext('2d');

    var isSafari = /Safari/i.test(navigator.userAgent) && !/Chrome|Chromium|CriOS|EdgiOS|FxiOS/i.test(navigator.userAgent);
    var dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, isSafari ? 1.5 : 2));
    var width = 0, height = 0;
    var slots = [];
    var marbles = [];
    var marbleRadius = 12;
    var board = {x: 0, y: 0, radius: 0};
    var boardLayer = document.createElement('canvas');
    var boardLayerCtx = boardLayer.getContext('2d');
    var currentLoop = 0;
    var targetLoops = 3;
    var targetCoverage = 1;
    var lastAt = performance.now();
    var loopTimer = 0;
    var morphing = false;
    var fadeOutAlpha = 1;

    var loopCounter = document.getElementById('loopCounter');
    var coverageCounter = document.getElementById('coverageCounter');

    function rand(min, max) {
        return min + Math.random() * (max - min);
    }

    function pickLoopGoal() {
        return 3 + Math.floor(Math.random() * 5);
    }

    function pickCoverageGoal() {
        return 1 + rand(0, 0.10);
    }

    // Shape generators — your app is a canvas, you define the shape, agents fill the gaps
    var shapeIndex = 0;

    function buildPredicateShape(cx, cy, R, mr, predicate) {
        return hexGridInCircle(cx, cy, R, mr).filter(function (point) {
            var nx = (point.x - cx) / R;
            var ny = (point.y - cy) / R;
            return predicate(nx, ny, point);
        });
    }

    function circleDistance(nx, ny) {
        return Math.sqrt(nx * nx + ny * ny);
    }

    function inRoundedCross(nx, ny, armHalfWidth, armReach) {
        return (
            (Math.abs(nx) <= armHalfWidth && Math.abs(ny) <= armReach) ||
            (Math.abs(ny) <= armHalfWidth && Math.abs(nx) <= armReach)
        );
    }

    function pickNextShapeIndex(current) {
        if (SHAPES.length <= 1) return current;
        var next = current;
        while (next === current) {
            next = Math.floor(Math.random() * SHAPES.length);
        }
        return next;
    }

    var SHAPES = [
        {
            name: 'circle',
            build: function (cx, cy, R, mr) {
                return hexGridInCircle(cx, cy, R, mr);
            }
        },
        {
            name: 'ring',
            build: function (cx, cy, R, mr) {
                return buildPredicateShape(cx, cy, R, mr, function (nx, ny) {
                    var d = circleDistance(nx, ny);
                    return d >= 0.46 && d <= 0.9;
                });
            }
        },
        {
            name: 'triangle',
            build: function (cx, cy, R, mr) {
                var pos = [], sp = mr * 2.12, rh = sp * 0.866;
                var h = R * 1.6, base = R * 1.8;
                var topY = cy - h * 0.45;
                for (var y = topY; y <= topY + h; y += rh) {
                    var progress = (y - topY) / h;
                    var rowW = progress * base;
                    for (var x = cx - rowW / 2; x <= cx + rowW / 2; x += sp) {
                        pos.push({x: x, y: y});
                    }
                }
                return pos;
            }
        },
        {
            name: 'diamond',
            build: function (cx, cy, R, mr) {
                return buildPredicateShape(cx, cy, R, mr, function (nx, ny) {
                    return (Math.abs(nx) + Math.abs(ny) * 0.92) <= 0.98;
                });
            }
        },
        {
            name: 'star',
            build: function (cx, cy, R, mr) {
                return buildPredicateShape(cx, cy, R, mr, function (nx, ny) {
                    var a = Math.atan2(ny, nx);
                    var d = circleDistance(nx, ny);
                    var r = 0.86 * (0.45 + 0.55 * Math.pow(Math.abs(Math.cos(2.5 * a - Math.PI / 2)), 0.6));
                    return d <= r;
                });
            }
        },
        {
            name: 'red-cross',
            build: function (cx, cy, R, mr) {
                return buildPredicateShape(cx, cy, R, mr, function (nx, ny) {
                    return inRoundedCross(nx, ny, 0.16, 0.74);
                });
            }
        },
        {
            name: 'cross-in-circle',
            build: function (cx, cy, R, mr) {
                return buildPredicateShape(cx, cy, R, mr, function (nx, ny) {
                    var d = circleDistance(nx, ny);
                    return (d >= 0.66 && d <= 0.9) || inRoundedCross(nx, ny, 0.12, 0.58);
                });
            }
        },
        {
            name: 'hexagon',
            build: function (cx, cy, R, mr) {
                return buildPredicateShape(cx, cy, R, mr, function (nx, ny) {
                    return (Math.abs(nx) * 0.9 + Math.abs(ny) * 0.58) <= 0.92;
                });
            }
        },
        {
            name: 'crescent',
            build: function (cx, cy, R, mr) {
                return buildPredicateShape(cx, cy, R, mr, function (nx, ny) {
                    var outer = circleDistance(nx + 0.12, ny);
                    var inner = circleDistance(nx - 0.22, ny);
                    return outer <= 0.88 && inner >= 0.54;
                });
            }
        }
    ];

    function buildBoard() {
        var shapeDef = SHAPES[shapeIndex % SHAPES.length];
        slots = shapeDef.build(board.x, board.y, board.radius, marbleRadius);
        slots.forEach(s => s.assigned = false);
        marbles = [];
        currentLoop = 0;
        targetLoops = pickLoopGoal();
        targetCoverage = pickCoverageGoal();
        renderBoardLayer();
        updateCounters();
    }

    function renderBoardLayer() {
        if (!boardLayerCtx) return;
        boardLayer.width = width * dpr;
        boardLayer.height = height * dpr;
        boardLayerCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
        boardLayerCtx.clearRect(0, 0, width, height);

        // Procedural background removed to reveal CSS stone background

        slots.forEach(function (slot) {
            drawGroove(boardLayerCtx, slot.x, slot.y, marbleRadius);
        });
    }

    function resizeCanvas() {
        var rect = canvas.getBoundingClientRect();
        if (!rect.width) return;
        width = rect.width;
        height = rect.height;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        board.x = width / 2;
        board.y = height / 2;
        board.radius = Math.min(width, height) * 0.42;
        marbleRadius = Math.max(10, board.radius * 0.08);

        buildBoard();
    }

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    function settledCount() {
        var settled = 0;
        for (var i = 0; i < marbles.length; i++) {
            if (marbles[i].settled) settled++;
        }
        return settled;
    }

    function convergenceRatio() {
        if (!slots.length) return 0;
        return settledCount() / slots.length;
    }

    function displayCoverageRatio() {
        var settled = convergenceRatio();
        if (!slots.length) return 0;
        var overshootProgress = Math.max(0, settled - 0.92) / 0.08;
        var overshoot = (targetCoverage - 1) * Math.min(1, overshootProgress);
        return Math.min(targetCoverage, settled + overshoot);
    }

    function allMarblesSettled() {
        for (var i = 0; i < marbles.length; i++) {
            if (!marbles[i].settled) return false;
        }
        return true;
    }

    function startMorph() {
        if (morphing) return;
        morphing = true;
        fadeOutAlpha = 1;
        var fadeInterval = setInterval(function () {
            fadeOutAlpha -= 0.015;
            if (fadeOutAlpha <= 0) {
                clearInterval(fadeInterval);
                fadeOutAlpha = 1;
                shapeIndex = pickNextShapeIndex(shapeIndex);
                morphing = false;
                buildBoard();
            }
        }, 16);
    }

    function throwWave() {
        if (morphing) return;
        var unassigned = slots.filter(function (slot) {
            return !slot.assigned;
        });
        if (!unassigned.length) return;

        var nextLoop = currentLoop + 1;
        var remainingLoops = Math.max(1, targetLoops - currentLoop);
        var reserveForLater = Math.max(0, remainingLoops - 1);
        var baseline = Math.ceil(unassigned.length / remainingLoops);
        var variance = rand(0.82, 1.18);
        var pacingBias = nextLoop <= 2 ? 1.1 : rand(0.92, 1.06);
        var toThrow = Math.max(1, Math.round(baseline * variance * pacingBias));

        if (remainingLoops > 1) {
            toThrow = Math.min(toThrow, Math.max(1, unassigned.length - reserveForLater));
        } else {
            toThrow = unassigned.length;
        }

        currentLoop = nextLoop;
        var progress = 1 - (unassigned.length / slots.length);

        shuffleArr(unassigned);

        // Chaos decreases with progress
        var chaosLevel = 1 - progress * 0.8; // 1.0 early → 0.2 late

        for (var i = 0; i < toThrow; i++) {
            var slot = unassigned[i];
            slot.assigned = true;
            // Early: wild spawn positions. Late: closer to target.
            var spawnSpread = board.radius * (1.2 + chaosLevel * 0.8);
            var angle = Math.random() * Math.PI * 2;
            var startX = board.x + Math.cos(angle) * spawnSpread;
            var startY = board.y + Math.sin(angle) * spawnSpread - board.radius * chaosLevel * 0.5;
            var mSeed = Math.floor(Math.random() * 99999);
            var mPattern = MarbleFactory.PATTERNS[Math.floor(Math.random() * MarbleFactory.PATTERNS.length)];
            var mPalIdx = Math.floor(Math.random() * MarbleFactory.PALETTES.length);
            marbles.push({
                x: startX,
                y: startY,
                vx: (Math.random() - 0.5) * 16 * chaosLevel,
                vy: (Math.random() - 0.5) * 12 * chaosLevel + 4,
                z: 40 + Math.random() * 120 + chaosLevel * 100,
                vz: (Math.random() - 0.2) * 8,
                target: slot,
                settled: false,
                chaosLevel: chaosLevel,
                seed: mSeed,
                pattern: mPattern,
                palIdx: mPalIdx,
                sprite: MarbleFactory.createSprite(marbleRadius, mPalIdx, mPattern, mSeed)
            });
        }

        // During early waves: some settled marbles get nudged out to keep the motion alive.
        if (progress < 0.6 && marbles.length > 3 && currentLoop < targetLoops) {
            var dislodgeChance = (1 - progress) * 0.08;
            for (var j = marbles.length - 1; j >= 0; j--) {
                var m = marbles[j];
                if (m.settled && Math.random() < dislodgeChance) {
                    m.settled = false;
                    m.target.assigned = false;
                    var kickAngle = Math.random() * Math.PI * 2;
                    m.vx = Math.cos(kickAngle) * (6 + Math.random() * 8);
                    m.vy = Math.sin(kickAngle) * (6 + Math.random() * 8) - 4;
                    m.z = 2 + Math.random() * 10;
                    m.vz = 6 + Math.random() * 8;
                    // Reassign to a random empty slot
                    var empties = slots.filter(function (s) {
                        return !s.assigned;
                    });
                    if (empties.length > 0) {
                        var newSlot = empties[Math.floor(Math.random() * empties.length)];
                        newSlot.assigned = true;
                        m.target = newSlot;
                    } else {
                        m.target.assigned = true; // put it back
                        m.settled = true;
                    }
                    break; // max 1 dislodge per wave
                }
            }
        }
        updateCounters();
    }

    function updateCounters() {
        if (loopCounter) loopCounter.textContent = marbles.length;
        if (coverageCounter) {
            var pct = slots.length ? Math.round(displayCoverageRatio() * 100) : 0;
            coverageCounter.textContent = pct + '%';
        }
    }

    function tick(now) {
        var dt = Math.min(32, now - lastAt);
        lastAt = now;

        ctx.clearRect(0, 0, width, height);
        if (boardLayer.width && boardLayer.height) {
            ctx.drawImage(boardLayer, 0, 0, width, height);
        }

        // Remove marbles that flew way off screen
        marbles = marbles.filter(function (m) {
            if (m.settled) return true;
            var inBounds = m.x > -100 && m.x < width + 100 && m.y > -300 && m.y < height + 100;
            if (!inBounds && m.target) {
                m.target.assigned = false;
            }
            return inBounds;
        });

        var conv = convergenceRatio();

        marbles.forEach(m => {
            if (!m.settled) {
                var dx = m.target.x - m.x;
                var dy = m.target.y - m.y;
                var dist = Math.sqrt(dx * dx + dy * dy);

                if (m.z === undefined) {
                    m.z = 0;
                    m.vz = 0;
                }
                m.vz -= 1.0;
                m.z += m.vz;
                if (m.z < 0) {
                    m.z = 0;
                    if (Math.abs(m.vz) > 2.0) {
                        m.vz = -m.vz * 0.38;
                    } else {
                        m.vz = 0;
                    }
                }
                var inAir = m.z > 0;

                var mChaos = (m.chaosLevel || 0.5) * (1 - conv * 0.8);
                var jitter = dist > marbleRadius * 2.4 ? (Math.random() - 0.5) * 3.2 * mChaos : 0;

                var attract = (0.018 + conv * 0.02) * (inAir ? 0.25 : 1.0);
                m.vx += dx * attract + jitter;
                m.vy += dy * attract + jitter;

                if (dist < marbleRadius * 0.9) {
                    m.vx *= 0.82;
                    m.vy *= 0.82;
                }

                var friction = 0.87 + conv * 0.05;
                if (inAir) friction = 0.97;

                m.vx *= friction;
                m.vy *= friction;

                m.x += m.vx;
                m.y += m.vy;

                if (dist < 2.0 && Math.abs(m.vx) < 0.8 && Math.abs(m.vy) < 0.8 && m.z <= 0) {
                    m.settled = true;
                    m.x = m.target.x;
                    m.y = m.target.y;
                }
            }
        });

        var renderList = marbles.slice().sort((a, b) => a.y - b.y);

        renderList.forEach(m => {
            var sprite = m.sprite;
            var speed = m.vx !== undefined ? Math.sqrt(m.vx * m.vx + m.vy * m.vy) : 0;
            var hover = m.z || 0;

            // Marble alpha: settled marbles are brighter as convergence increases
            var mAlpha = m.settled ? (0.7 + conv * 0.3) : (0.5 + Math.min(speed * 0.03, 0.4));
            mAlpha *= fadeOutAlpha; // fade on shape complete

            if (hover > 0 || speed > 0.5) {
                var shadowScale = Math.max(0.4, 1 - hover / 180);
                var shadowW = marbleRadius * 0.8 * shadowScale;
                var shadowH = marbleRadius * 0.4 * shadowScale;
                var shadowAlpha = Math.max(0.05, 0.4 - hover / 250);

                ctx.globalAlpha = mAlpha * shadowAlpha;
                ctx.beginPath();
                ctx.ellipse(m.x, m.y + marbleRadius * 0.6 + hover * 0.15, shadowW, shadowH, 0, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(0,0,0,1)';
                ctx.fill();
            }

            ctx.globalAlpha = mAlpha;
            ctx.drawImage(sprite, m.x - sprite.width / 2, m.y - hover - sprite.height / 2);
        });
        ctx.globalAlpha = 1;

        if (!morphing && convergenceRatio() >= 1 && currentLoop >= targetLoops && allMarblesSettled()) {
            startMorph();
        } else {
            loopTimer -= dt;
            if (loopTimer <= 0) {
                throwWave();
                loopTimer = 1200 + Math.random() * 900;
            }
        }
        updateCounters();

        requestAnimationFrame(tick);
    }

    loopTimer = 700 + Math.random() * 300;
    requestAnimationFrame(tick);
})();

// ============ DIFFUSION CANVAS (solitaire convergence, dimmed + hover spotlight) ============
(function () {
    var c = document.getElementById('diffusionCanvas');
    if (!c || !c.getContext) return;
    var ctx = c.getContext('2d');
    if (!ctx) return;
    var DPR = Math.min(window.devicePixelRatio || 1, 2);
    var cw, slots = [], MR, HOVER_R, currentLoop = 0, totalSlots = 0;
    var loopFill = [0, 0.15, 0.40, 0.65, 0.85, 1.0];
    var filled = {}, noise = {};
    var mx = -1, my = -1;
    var DIM = 0.22, BRIGHT = 0.92;

    c.addEventListener('mousemove', function (e) {
        var r = c.getBoundingClientRect();
        mx = (e.clientX - r.left) / (r.right - r.left) * cw;
        my = (e.clientY - r.top) / (r.bottom - r.top) * cw;
    });
    c.addEventListener('mouseleave', function () {
        mx = -1;
        my = -1;
    });

    function prox(x, y) {
        if (mx < 0) return 0;
        var dx = x - mx, dy = y - my, d = Math.sqrt(dx * dx + dy * dy);
        return Math.max(0, 1 - d / HOVER_R);
    }

    function resize() {
        var sz = Math.min(c.offsetWidth, c.offsetHeight);
        c.width = sz * DPR;
        c.height = sz * DPR;
        cw = c.width;
    }

    function buildBoard() {
        var R = cw * 0.40;
        MR = Math.max(4, R * 0.052);
        HOVER_R = MR * 9;
        var positions = hexGridInCircle(cw / 2, cw / 2, R, MR);
        slots = positions.map(function (p) {
            return {x: p.x, y: p.y, marble: null};
        });
        totalSlots = slots.length;
        filled = {};
        noise = {};
        currentLoop = 0;
    }

    function fillBoardFully() {
        for (var i = 0; i < slots.length; i++) {
            slots[i].marble = makeMarble(5);
            filled[i] = true;
        }
        currentLoop = 5;
    }

    function makeMarble(loop) {
        var palIdx = loop % MarbleFactory.PALETTES.length;
        var pat = MarbleFactory.PATTERNS[Math.floor(Math.random() * MarbleFactory.PATTERNS.length)];
        var seed = Math.floor(Math.random() * 999999);
        return {
            sprite: MarbleFactory.createSprite(MR, palIdx, pat, seed),
            alpha: 0,
            drop: 1.0 + Math.random() * 2.5,
            dropSpeed: 0.03 + Math.random() * 0.04,
            shaking: false, shakeT: 0
        };
    }

    function countFilled() {
        var n = 0;
        for (var k in filled) if (filled[k] && slots[k].marble && !slots[k].marble.shaking) n++;
        return n;
    }

    function advanceLoop() {
        if (currentLoop >= 5) {
            setTimeout(function () {
                buildBoard();
                setTimeout(advanceLoop, 600);
            }, 3000);
            return;
        }
        currentLoop++;
        var target = Math.round(totalSlots * loopFill[currentLoop]);
        if (currentLoop >= 2) {
            var nk = Object.keys(noise);
            var shakeN = Math.min(nk.length, 1 + Math.floor(Math.random() * 2));
            for (var i = 0; i < shakeN; i++) {
                var idx = nk[i];
                if (slots[idx] && slots[idx].marble) {
                    slots[idx].marble.shaking = true;
                    slots[idx].marble.shakeT = 0;
                    delete filled[idx];
                    delete noise[idx];
                }
            }
        }
        var empties = [];
        for (var i = 0; i < slots.length; i++) {
            if (!filled[i]) empties.push(i);
        }
        shuffleArr(empties);
        var cur = countFilled();
        var toFill = Math.max(0, target - cur);
        var noiseRate = (currentLoop <= 2) ? 0.06 : 0;
        for (var i = 0; i < Math.min(toFill, empties.length); i++) {
            var idx = empties[i];
            slots[idx].marble = makeMarble(currentLoop);
            filled[idx] = true;
            if (Math.random() < noiseRate) noise[idx] = true;
        }
        setTimeout(advanceLoop, 2200);
    }

    function render() {
        ctx.clearRect(0, 0, cw, cw);
        ctx.beginPath();
        ctx.arc(cw / 2, cw / 2, cw * 0.41, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(176,174,165,0.08)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        // Empty grooves — dimmed with hover spotlight
        for (var i = 0; i < slots.length; i++) {
            var s = slots[i];
            if (!s.marble || s.marble.shaking) {
                var p = prox(s.x, s.y);
                ctx.globalAlpha = DIM + p * (BRIGHT - DIM);
                drawGroove(ctx, s.x, s.y, MR);
            }
        }
        ctx.globalAlpha = 1;
        // Marbles — dimmed with hover spotlight
        for (var i = 0; i < slots.length; i++) {
            var s = slots[i];
            if (!s.marble) continue;
            var m = s.marble;
            if (m.shaking) {
                m.shakeT += 0.04;
                if (m.shakeT >= 1) {
                    s.marble = null;
                    continue;
                }
                var wobble = Math.sin(m.shakeT * 18) * MR * 0.4 * (1 - m.shakeT);
                var p = prox(s.x, s.y);
                ctx.globalAlpha = (DIM + p * (BRIGHT - DIM)) * (1 - m.shakeT * m.shakeT);
                ctx.drawImage(m.sprite, s.x + wobble - m.sprite.width / 2, s.y - m.sprite.height / 2);
                continue;
            }
            m.drop = Math.max(0, m.drop - m.dropSpeed);
            var yOff = -MR * 2 * m.drop * m.drop;
            var p = prox(s.x, s.y);
            var ta = DIM + p * (BRIGHT - DIM);
            m.alpha += (ta - m.alpha) * 0.07;
            if (m.drop < 0.2) {
                ctx.globalAlpha = 0.12 * (1 - m.drop / 0.2) * m.alpha;
                ctx.beginPath();
                ctx.ellipse(s.x, s.y + MR * 0.12, MR * 0.55, MR * 0.18, 0, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(0,0,0,1)';
                ctx.fill();
            }
            ctx.globalAlpha = m.alpha;
            ctx.drawImage(m.sprite, s.x - m.sprite.width / 2, s.y + yOff - m.sprite.height / 2);
        }
        ctx.globalAlpha = 1;
        // Coverage + loop text (always fully visible)
        var vis = countFilled();
        var pct = totalSlots > 0 ? Math.round((vis / totalSlots) * 100) : 0;
        if (currentLoop >= 5 && Object.keys(filled).length >= totalSlots) pct = 100;
        ctx.font = 'bold ' + (cw * 0.09) + 'px Poppins,Arial';
        ctx.fillStyle = '#faf9f5';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(pct + '%', cw / 2, cw / 2 - cw * 0.02);
        ctx.font = (cw * 0.038) + 'px Poppins,Arial';
        ctx.fillStyle = '#b0aea5';
        ctx.fillText(currentLoop > 0 ? 'Loop ' + currentLoop : 'Board', cw / 2, cw / 2 + cw * 0.07);
        requestAnimationFrame(render);
    }

    window.addEventListener('resize', function () {
        resize();
        buildBoard();
    });
    resize();
    buildBoard();
    render();
    setTimeout(advanceLoop, 800);
})();

// ============ TRAJECTORY BAR ANIMATION ============
(function () {
    var target = document.getElementById('trajectoryBars');
    if (!target) return;

    function animateBars() {
        var bars = target.querySelectorAll('.bar');
        bars.forEach(function (bar, i) {
            setTimeout(function () {
                bar.style.height = bar.getAttribute('data-h') + '%';
            }, prefersReducedMotion ? 0 : i * 300);
        });
    }

    if (prefersReducedMotion || !supportsIntersectionObserver) {
        animateBars();
        return;
    }
    var animated = false;
    var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
            if (e.isIntersecting && !animated) {
                animated = true;
                animateBars();
            }
        });
    }, {threshold: 0.3});
    obs.observe(target);
})();

// ============ SCROLL ANIMATIONS ============
(function () {
    var items = document.querySelectorAll('.fade-up');
    if (!items.length) return;
    if (prefersReducedMotion || !supportsIntersectionObserver) {
        items.forEach(function (el) {
            el.classList.add('visible');
        });
        return;
    }
    var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
            if (e.isIntersecting) e.target.classList.add('visible');
        });
    }, {threshold: 0.12});
    items.forEach(function (el) {
        obs.observe(el);
    });
})();

// ============ COPY CODE ============
(function () {
    var buttons = document.querySelectorAll('.copy-btn');
    buttons.forEach(function (btn) {
        btn.setAttribute('data-default-label', btn.textContent.trim() || uiStrings.copy);
        btn.addEventListener('click', function () {
            var code = btn.parentElement && btn.parentElement.querySelector('code');
            var text = code ? code.innerText : '';
            copyText(text).then(function (copied) {
                flashCopyButton(btn, copied);
                announceUiMessage(copied ? uiStrings.codeCopied : uiStrings.copyCodeFallback);
            });
        });
    });
})();

// ============ CURL BANNER COPY ============
(function () {
    var buttons = document.querySelectorAll('.cb-copy');
    if (!buttons.length) return;
    buttons.forEach(function (btn) {
        btn.setAttribute('data-default-label', btn.getAttribute('data-default-label') || btn.textContent.trim() || uiStrings.copy);
        btn.addEventListener('click', function () {
            var cmd = btn.getAttribute('data-copy');
            copyText(cmd).then(function (copied) {
                flashCopyButton(btn, copied);
                announceUiMessage(copied ? uiStrings.installCopied : uiStrings.copyInstallFallback);
            });
        });
    });
})();

// ============ HERO TERMINAL COPY (pointer tooltip) ============
(function () {
    var copyables = document.querySelectorAll('.hterm-prompt[data-copy], .hterm-row[data-copy]');
    if (!copyables.length) return;
    var tip = document.createElement('div');
    tip.className = 'hterm-tip';
    tip.textContent = uiStrings.tooltipCopy;
    tip.setAttribute('aria-hidden', 'true');
    document.body.appendChild(tip);
    var hideTimer;

    function showTip(x, y, text, state) {
        tip.textContent = text;
        tip.classList.toggle('ok', state === 'ok');
        tip.classList.toggle('err', state === 'err');
        tip.style.left = x + 'px';
        tip.style.top = y + 'px';
        tip.classList.add('on');
    }

    function hideTip() {
        tip.classList.remove('on', 'ok', 'err');
    }

    function copyFromElement(el, x, y) {
        var value = el.getAttribute('data-copy');
        copyText(value).then(function (copied) {
            showTip(x, y, copied ? uiStrings.copied : uiStrings.copyFailed, copied ? 'ok' : 'err');
            announceUiMessage(copied ? uiStrings.commandCopied : uiStrings.copyCommandFallback);
            clearTimeout(hideTimer);
            hideTimer = setTimeout(hideTip, copied ? 1200 : 1600);
        });
    }

    copyables.forEach(function (el) {
        var value = el.getAttribute('data-copy') || '';
        el.setAttribute('role', 'button');
        el.setAttribute('tabindex', '0');
        el.setAttribute('aria-label', uiStrings.copyCommandAriaPrefix + value);
        el.addEventListener('mouseenter', function (e) {
            clearTimeout(hideTimer);
            showTip(e.clientX, e.clientY, uiStrings.tooltipCopy);
        });
        el.addEventListener('mousemove', function (e) {
            if (tip.classList.contains('ok') || tip.classList.contains('err')) return;
            tip.style.left = e.clientX + 'px';
            tip.style.top = e.clientY + 'px';
        });
        el.addEventListener('focus', function () {
            var r = el.getBoundingClientRect();
            showTip(r.left + r.width / 2, r.top, uiStrings.tooltipCopy);
        });
        el.addEventListener('blur', function () {
            clearTimeout(hideTimer);
            hideTip();
        });
        el.addEventListener('mouseleave', function () {
            clearTimeout(hideTimer);
            hideTimer = setTimeout(hideTip, 80);
        });
        el.addEventListener('click', function (e) {
            copyFromElement(el, e.clientX, e.clientY);
        });
        el.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                var r = el.getBoundingClientRect();
                copyFromElement(el, r.right - 20, r.top);
            }
        });
    });
})();

// ============ SCROLL PROGRESS BAR ============
(function () {
    var bar = document.createElement('div');
    var ticking = false;
    bar.className = 'scroll-progress';
    document.body.appendChild(bar);

    function updateBar() {
        ticking = false;
        var h = document.documentElement.scrollHeight - window.innerHeight;
        bar.style.width = h > 0 ? (window.scrollY / h * 100) + '%' : '0';
    }

    function queueUpdate() {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(updateBar);
    }

    updateBar();
    window.addEventListener('scroll', queueUpdate, {passive: true});
    window.addEventListener('resize', queueUpdate);
})();

// ============ FRAMEWORK STRIP ARROWS ============
(function () {
    var wrap = document.querySelector('.framework-strip-wrap');
    var strip = document.querySelector('.framework-strip');
    var leftBtn = document.querySelector('.strip-arrow--left');
    var rightBtn = document.querySelector('.strip-arrow--right');
    if (!wrap || !strip || !leftBtn || !rightBtn) return;

    var originals = Array.prototype.slice.call(strip.children);
    if (!originals.length) return;
    var cycleWidth = 0;
    var resetQueued = false;
    var targetScrollLeft = 0;
    var velocity = 0;
    var animationFrame = 0;
    var isMomentumScroll = false;

    function cloneCard(card) {
        var clone = card.cloneNode(true);
        clone.setAttribute('aria-hidden', 'true');
        clone.classList.add('card--clone');
        return clone;
    }

    function seedInfiniteStrip() {
        var before = document.createDocumentFragment();
        var after = document.createDocumentFragment();

        originals.forEach(function (card) {
            before.appendChild(cloneCard(card));
            after.appendChild(cloneCard(card));
        });

        strip.insertBefore(before, strip.firstChild);
        strip.appendChild(after);
    }

    function measureCycleWidth() {
        var styles = window.getComputedStyle(strip);
        var gap = parseFloat(styles.columnGap || styles.gap || 0);
        cycleWidth = originals.reduce(function (sum, card, index) {
            return sum + card.getBoundingClientRect().width + (index < originals.length - 1 ? gap : 0);
        }, 0);
    }

    function normalizeScrollLeft(value) {
        if (!cycleWidth) return value;
        while (value < cycleWidth * 0.5) {
            value += cycleWidth;
        }
        while (value > cycleWidth * 1.5) {
            value -= cycleWidth;
        }
        return value;
    }

    function jumpToMiddle(force) {
        measureCycleWidth();
        if (!cycleWidth) return;
        if (force) {
            strip.scrollLeft = cycleWidth;
            targetScrollLeft = cycleWidth;
            return;
        }
        strip.scrollLeft = normalizeScrollLeft(strip.scrollLeft);
        targetScrollLeft = normalizeScrollLeft(targetScrollLeft || strip.scrollLeft);
    }

    function queueWrap() {
        if (resetQueued) return;
        resetQueued = true;
        requestAnimationFrame(function () {
            resetQueued = false;
            jumpToMiddle(false);
        });
    }

    function getScrollAmount() {
        var card = originals[0];
        var styles = window.getComputedStyle(strip);
        var gap = parseFloat(styles.columnGap || styles.gap || 0);
        var width = card ? card.getBoundingClientRect().width : 300;
        return width + gap;
    }

    function stopMomentum() {
        velocity = 0;
        if (!animationFrame) return;
        cancelAnimationFrame(animationFrame);
        animationFrame = 0;
    }

    function stepMomentum() {
        animationFrame = 0;
        measureCycleWidth();
        if (!cycleWidth) return;

        var current = strip.scrollLeft;
        var delta = targetScrollLeft - current;
        var attraction = prefersReducedMotion ? 0.18 : 0.11;
        var damping = prefersReducedMotion ? 0.56 : 0.82;

        velocity += delta * attraction;
        velocity *= damping;

        if (Math.abs(delta) < 0.35 && Math.abs(velocity) < 0.16) {
            isMomentumScroll = true;
            strip.scrollLeft = targetScrollLeft;
            queueWrap();
            isMomentumScroll = false;
            velocity = 0;
            return;
        }

        isMomentumScroll = true;
        strip.scrollLeft = current + velocity;
        queueWrap();
        animationFrame = requestAnimationFrame(stepMomentum);
    }

    function ensureMomentum() {
        if (prefersReducedMotion) {
            stopMomentum();
            strip.scrollLeft = targetScrollLeft;
            queueWrap();
            return;
        }
        if (!animationFrame) {
            animationFrame = requestAnimationFrame(stepMomentum);
        }
    }

    function pushMomentum(distance, impulseMultiplier) {
        measureCycleWidth();
        if (!cycleWidth) return;
        targetScrollLeft = normalizeScrollLeft((targetScrollLeft || strip.scrollLeft) + distance);
        velocity += distance * impulseMultiplier;
        ensureMomentum();
    }

    function scrollStrip(direction) {
        var amount = getScrollAmount() * (prefersReducedMotion ? 1 : 1.15);
        pushMomentum(direction * amount, prefersReducedMotion ? 0.02 : 0.04);
    }

    seedInfiniteStrip();
    jumpToMiddle(true);

    leftBtn.addEventListener('click', function () {
        scrollStrip(-1);
    });

    rightBtn.addEventListener('click', function () {
        scrollStrip(1);
    });

    strip.addEventListener('pointerdown', function () {
        stopMomentum();
        targetScrollLeft = strip.scrollLeft;
    });

    strip.addEventListener('touchstart', function () {
        stopMomentum();
        targetScrollLeft = strip.scrollLeft;
    }, {passive: true});

    strip.addEventListener('scroll', function () {
        if (!isMomentumScroll) {
            targetScrollLeft = strip.scrollLeft;
        }
        queueWrap();
        isMomentumScroll = false;
    }, {passive: true});

    wrap.addEventListener('wheel', function (event) {
        var delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
        if (!delta) return;
        event.preventDefault();
        pushMomentum(delta, prefersReducedMotion ? 0.02 : 0.035);
    }, {passive: false});

    window.addEventListener('resize', function () {
        stopMomentum();
        jumpToMiddle(false);
    });
})();

// ============ FOOTER DRAWER STABILIZER ============
(function () {
    var footer = document.querySelector('.footer-shell');
    if (!footer || !window.matchMedia || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;

    var closeTimer = 0;

    function openDrawer() {
        if (closeTimer) {
            clearTimeout(closeTimer);
            closeTimer = 0;
        }
        footer.setAttribute('data-drawer-open', 'true');
    }

    function closeDrawerSoon() {
        if (closeTimer) clearTimeout(closeTimer);
        closeTimer = window.setTimeout(function () {
            footer.removeAttribute('data-drawer-open');
            closeTimer = 0;
        }, 120);
    }

    footer.addEventListener('pointerenter', openDrawer);
    footer.addEventListener('pointerleave', closeDrawerSoon);
    footer.addEventListener('focusin', openDrawer);
    footer.addEventListener('focusout', function (event) {
        if (footer.contains(event.relatedTarget)) return;
        closeDrawerSoon();
    });

    window.addEventListener('blur', function () {
        if (closeTimer) clearTimeout(closeTimer);
        closeTimer = 0;
        footer.removeAttribute('data-drawer-open');
    });
})();

// ============ MERMAID COPY ============
(function () {
    var btn = document.querySelector('.mmd-copy');
    if (!btn) return;
    btn.setAttribute('data-default-label', uiStrings.copy);
    var code = btn.parentElement && btn.parentElement.querySelector('code');
    if (!code) return;
    btn.addEventListener('click', function () {
        copyText(code.textContent).then(function (ok) {
            flashCopyButton(btn, ok);
            announceUiMessage(ok ? uiStrings.pipelineCopied : uiStrings.copyFailed);
        });
    });
})();

// ============ MERMAID TOGGLE ============
(function () {
    var toggleBtn = document.querySelector('.mmd-toggle');
    var splitBtn = document.querySelector('.mmd-split');
    var shell = document.querySelector('.mmd-shell');
    var codeBlock = shell ? shell.querySelector('code') : null;
    var codePane = shell ? shell.querySelector('.mmd-code') : null;
    var previewPane = shell ? shell.querySelector('.mmd-preview') : null;

    if (!toggleBtn || !shell || !codeBlock || !codePane || !previewPane) return;

    var mermaidInitialized = false;
    var switchTimer = null;

    function showMermaidUnavailable() {
        previewPane.textContent = uiStrings.previewUnavailable;
        lockMermaidShellHeight();
    }

    function measurePaneHeight(pane, paneWidth) {
        var prevDisplay = pane.style.display;
        var prevPosition = pane.style.position;
        var prevVisibility = pane.style.visibility;
        var prevPointerEvents = pane.style.pointerEvents;
        var prevInset = pane.style.inset;
        var prevWidth = pane.style.width;
        var prevMaxWidth = pane.style.maxWidth;

        pane.style.display = 'block';
        pane.style.position = 'absolute';
        pane.style.visibility = 'hidden';
        pane.style.pointerEvents = 'none';
        pane.style.inset = '0 auto auto 0';
        pane.style.width = Math.max(0, paneWidth) + 'px';
        pane.style.maxWidth = Math.max(0, paneWidth) + 'px';

        var measured = Math.ceil(pane.scrollHeight || pane.getBoundingClientRect().height || 0);

        pane.style.display = prevDisplay;
        pane.style.position = prevPosition;
        pane.style.visibility = prevVisibility;
        pane.style.pointerEvents = prevPointerEvents;
        pane.style.inset = prevInset;
        pane.style.width = prevWidth;
        pane.style.maxWidth = prevMaxWidth;

        return measured;
    }

    function lockMermaidShellHeight() {
        var shellStyles = window.getComputedStyle(shell);
        var shellInnerWidth = shell.clientWidth
            - parseFloat(shellStyles.paddingLeft || 0)
            - parseFloat(shellStyles.paddingRight || 0);
        var shellExtra = parseFloat(shellStyles.paddingTop || 0) + parseFloat(shellStyles.paddingBottom || 0);
        var codeHeight = measurePaneHeight(codePane, shellInnerWidth);
        var previewHeight = measurePaneHeight(previewPane, shellInnerWidth);
        var stableHeight = Math.max(codeHeight, previewHeight);
        if (stableHeight > 0) {
            shell.style.minHeight = (stableHeight + shellExtra) + 'px';
            previewPane.style.minHeight = stableHeight + 'px';
        } else {
            previewPane.style.minHeight = '';
        }
    }

    function renderMermaidPreview(svgMarkup) {
        var parser = new DOMParser();
        var parsed = parser.parseFromString(svgMarkup, 'image/svg+xml');
        var svg = parsed.documentElement;

        if (parsed.querySelector('parsererror') || !svg || svg.nodeName.toLowerCase() !== 'svg') {
            showMermaidUnavailable();
            return;
        }

        Array.prototype.forEach.call(
            svg.querySelectorAll('script, foreignObject'),
            function (node) {
                node.remove();
            }
        );

        Array.prototype.forEach.call(svg.querySelectorAll('*'), function (node) {
            Array.prototype.forEach.call(node.attributes || [], function (attr) {
                var name = attr.name.toLowerCase();
                var value = (attr.value || '').trim().toLowerCase();
                if (
                    name.indexOf('on') === 0 ||
                    ((name === 'href' || name === 'xlink:href') && value.indexOf('javascript:') === 0)
                ) {
                    node.removeAttribute(attr.name);
                }
            });
        });

        previewPane.textContent = '';
        previewPane.appendChild(document.importNode(svg, true));
        requestAnimationFrame(lockMermaidShellHeight);
    }

    function initMermaid() {
        if (!mermaidInitialized && window.mermaid) {
            try {
                mermaid.initialize({
                    startOnLoad: false,
                    theme: 'base',
                    themeVariables: {
                        darkMode: true,
                        background: '#0e0e11',
                        primaryColor: '#1a1d22',
                        primaryTextColor: '#e5ecf5',
                        primaryBorderColor: '#d4905c',
                        secondaryColor: '#14171b',
                        secondaryTextColor: '#e5ecf5',
                        secondaryBorderColor: '#a3b8c7',
                        tertiaryColor: '#122018',
                        tertiaryTextColor: '#e5ecf5',
                        tertiaryBorderColor: '#5a8a7a',
                        lineColor: '#c4d4e0',
                        arrowheadColor: '#c4d4e0',
                        clusterBkg: '#14171b',
                        clusterBorder: '#5a8a7a',
                        edgeLabelBackground: '#0e0e11',
                        nodeTextColor: '#e5ecf5',
                        mainBkg: '#1a1d22',
                        fontFamily: 'JetBrains Mono, monospace'
                    },
                    flowchart: {
                        htmlLabels: false,
                        curve: 'linear'
                    }
                });
                var rawText = codeBlock.innerText || codeBlock.textContent;
                mermaid.render('mermaid-graph-1', rawText).then(function (result) {
                    renderMermaidPreview(result.svg);
                }).catch(function () {
                    showMermaidUnavailable();
                });
                mermaidInitialized = true;
            } catch (err) {
                showMermaidUnavailable();
            }
        }
    }

    function setMode(newMode) {
        shell.setAttribute('data-mode', newMode);
        if (newMode === 'preview') {
            toggleBtn.style.color = 'var(--orange)';
            toggleBtn.style.borderColor = 'var(--orange)';
            if (splitBtn) {
                splitBtn.style.color = '';
                splitBtn.style.borderColor = '';
            }
            initMermaid();
        } else if (newMode === 'split') {
            if (splitBtn) {
                splitBtn.style.color = 'var(--orange)';
                splitBtn.style.borderColor = 'var(--orange)';
            }
            toggleBtn.style.color = '';
            toggleBtn.style.borderColor = '';
            initMermaid();
        } else {
            // code
            toggleBtn.style.color = '';
            toggleBtn.style.borderColor = '';
            if (splitBtn) {
                splitBtn.style.color = '';
                splitBtn.style.borderColor = '';
            }
        }
        requestAnimationFrame(lockMermaidShellHeight);
    }

    function animateModeChange(newMode) {
        clearTimeout(switchTimer);
        shell.classList.add('is-switching');
        switchTimer = setTimeout(function () {
            setMode(newMode);
            requestAnimationFrame(function () {
                shell.classList.remove('is-switching');
            });
        }, 120);
    }

    toggleBtn.addEventListener('click', function () {
        var mode = shell.getAttribute('data-mode');
        animateModeChange(mode === 'preview' ? 'code' : 'preview');
    });

    if (splitBtn) {
        splitBtn.addEventListener('click', function () {
            var mode = shell.getAttribute('data-mode');
            animateModeChange(mode === 'split' ? 'code' : 'split');
        });
    }

    lockMermaidShellHeight();
    window.addEventListener('resize', function () {
        requestAnimationFrame(lockMermaidShellHeight);
    });
})();

// ============ HOVER CURL BANNER ============ 
(function () {
    var curlTimeout = null;
    var lastScrollY = window.scrollY || 0;
    var getZone = document.querySelector('.nav-get-zone');
    var curlBanner = document.querySelector('.curl-banner');
    if (!getZone || !curlBanner) return;

    function showBanner() {
        clearTimeout(curlTimeout);
        curlBanner.classList.add('is-visible');
    }

    function hideBanner(delay) {
        var hideDelay = typeof delay === 'number' ? delay : 220;
        clearTimeout(curlTimeout);
        curlTimeout = setTimeout(function () {
            curlBanner.classList.remove('is-visible');
        }, hideDelay);
    }

    getZone.addEventListener('mouseenter', showBanner);
    getZone.addEventListener('mouseleave', function () {
        hideBanner(240);
    });
    getZone.addEventListener('focusin', showBanner);
    getZone.addEventListener('focusout', function () {
        hideBanner(240);
    });

    curlBanner.addEventListener('mouseenter', showBanner);
    curlBanner.addEventListener('mouseleave', function () {
        hideBanner(240);
    });
    curlBanner.addEventListener('focusin', showBanner);
    curlBanner.addEventListener('focusout', function () {
        hideBanner(240);
    });

    window.addEventListener('scroll', function () {
        var currentY = window.scrollY || 0;
        if (currentY > lastScrollY + 6) {
            hideBanner(180);
        }
        lastScrollY = currentY;
    }, {passive: true});

    window.addEventListener('wheel', function (event) {
        if (event.deltaY > 0) {
            hideBanner(180);
        }
    }, {passive: true});
})();

// ============ MODAL SURFACES ============
(function () {
    var triggers = document.querySelectorAll('[data-modal-open]');
    var modals = document.querySelectorAll('.surface-modal');
    if (!triggers.length || !modals.length) return;

    var activeModal = null;
    var lastTrigger = null;
    var modalTransitionMs = 250;
    var focusableSelector = [
        'a[href]',
        'button:not([disabled])',
        'input:not([disabled])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])'
    ].join(', ');

    function setModalHidden(modal, hidden) {
        if (!modal) return;
        modal.hidden = hidden;
        modal.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    }

    function modalFocusables(modal) {
        var panel = modal && modal.querySelector('.surface-modal__panel');
        if (!panel) return [];
        return Array.prototype.filter.call(panel.querySelectorAll(focusableSelector), function (node) {
            return !node.hidden && node.getAttribute('aria-hidden') !== 'true' && node.tabIndex !== -1;
        });
    }

    function openModal(modal, trigger) {
        if (!modal) return;
        if (activeModal && activeModal !== modal) {
            closeModal(true);
        }

        lastTrigger = trigger || lastTrigger;
        activeModal = modal;
        setModalHidden(modal, false);
        document.body.classList.add('modal-open');

        requestAnimationFrame(function () {
            modal.classList.add('is-visible');
            var panel = modal.querySelector('.surface-modal__panel');
            if (panel) panel.focus();
        });
    }

    function closeModal(skipFocusRestore) {
        if (!activeModal) return;
        var modal = activeModal;
        activeModal = null;
        modal.classList.remove('is-visible');
        document.body.classList.remove('modal-open');

        setTimeout(function () {
            setModalHidden(modal, true);
            if (!skipFocusRestore && lastTrigger && typeof lastTrigger.focus === 'function') {
                lastTrigger.focus();
            }
        }, modalTransitionMs);
    }

    triggers.forEach(function (trigger) {
        trigger.addEventListener('click', function (event) {
            var modalId = trigger.getAttribute('data-modal-open');
            var modal = modalId ? document.getElementById(modalId) : null;
            if (!modal) return;
            if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
                return;
            }
            event.preventDefault();
            openModal(modal, trigger);
        });
    });

    modals.forEach(function (modal) {
        setModalHidden(modal, true);
        modal.addEventListener('click', function (event) {
            if (event.target === modal || event.target.hasAttribute('data-modal-close') ||
                event.target.classList.contains('surface-modal__backdrop')) {
                closeModal(false);
            }
        });
    });

    document.addEventListener('keydown', function (event) {
        if (!activeModal) return;
        if (event.key === 'Tab') {
            var panel = activeModal.querySelector('.surface-modal__panel');
            var focusables = modalFocusables(activeModal);
            if (!panel) return;
            if (!focusables.length) {
                event.preventDefault();
                panel.focus();
                return;
            }
            var first = focusables[0];
            var last = focusables[focusables.length - 1];
            if (event.shiftKey) {
                if (document.activeElement === first || document.activeElement === panel) {
                    event.preventDefault();
                    last.focus();
                }
            } else if (document.activeElement === last || !panel.contains(document.activeElement)) {
                event.preventDefault();
                first.focus();
            }
        }
        if (event.key === 'Escape') {
            event.preventDefault();
            closeModal(false);
        }
    });
})();
