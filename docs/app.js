var prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
var supportsIntersectionObserver = 'IntersectionObserver' in window;
var liveRegion;
var liveRegionTimer;

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
    var defaultText = btn.getAttribute('data-default-label') || btn.textContent.trim() || 'Copy';
    btn.textContent = copied ? 'Copied' : 'Copy failed';
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
        rfl.addColorStop(0, 'rgba(255,255,255,0.18)');
        rfl.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = rfl;
        g.fillRect(0, 0, s, s);

        // Top specular highlight — the signature glass shine
        var hl = g.createRadialGradient(cx - r * 0.28, cy - r * 0.32, r * 0.02, cx - r * 0.15, cy - r * 0.2, r * 0.5);
        hl.addColorStop(0, 'rgba(255,255,255,0.95)');
        hl.addColorStop(0.15, 'rgba(255,255,255,0.55)');
        hl.addColorStop(0.5, 'rgba(255,255,255,0.1)');
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
    
    var dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2));
    var width = 0, height = 0;
    var slots = [];
    var marbles = [];
    var marbleRadius = 12;
    var board = {x: 0, y: 0, radius: 0};
    var currentLoop = 0;
    var lastAt = performance.now();
    var loopTimer = 0;
    
    var loopCounter = document.getElementById('loopCounter');
    var coverageCounter = document.getElementById('coverageCounter');
    
    function buildBoard() {
        slots = hexGridInCircle(board.x, board.y, board.radius, marbleRadius);
        slots.forEach(s => s.assigned = false);
        marbles = [];
        currentLoop = 0;
        updateCounters();
    }
    
    function resizeCanvas() {
        var rect = canvas.getBoundingClientRect();
        if (!rect.width) return;
        width = rect.width; height = rect.height;
        canvas.width = width * dpr; canvas.height = height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        
        board.x = width / 2;
        board.y = height / 2;
        board.radius = Math.min(width, height) * 0.42;
        marbleRadius = Math.max(10, board.radius * 0.08);
        
        buildBoard();
    }
    
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();
    
    function throwWave() {
        var unassigned = slots.filter(s => !s.assigned);
        if (unassigned.length === 0) {
            setTimeout(buildBoard, 4000);
            return;
        }
        
        currentLoop++;
        var toThrow = Math.ceil(unassigned.length * (0.15 + Math.random() * 0.2));
        if (unassigned.length < 6) toThrow = unassigned.length;
        
        shuffleArr(unassigned);
        
        for(var i=0; i<toThrow; i++) {
            var slot = unassigned[i];
            slot.assigned = true;
            marbles.push({
                x: board.x + (Math.random() - 0.5) * board.radius * 1.8,
                y: -marbleRadius * 4 - Math.random() * 150,
                vx: (Math.random() - 0.5) * 16,
                vy: 8 + Math.random() * 15,
                target: slot,
                settled: false,
                seed: Math.floor(Math.random() * 99999),
                pattern: MarbleFactory.PATTERNS[Math.floor(Math.random() * MarbleFactory.PATTERNS.length)],
                palIdx: Math.floor(Math.random() * MarbleFactory.PALETTES.length)
            });
        }
        updateCounters();
    }
    
    function updateCounters() {
        if(loopCounter) loopCounter.textContent = currentLoop;
        if(coverageCounter) {
            var pct = slots.length ? Math.round((slots.filter(s=>s.assigned).length / slots.length) * 100) : 0;
            coverageCounter.textContent = pct + '%';
        }
    }
    
    function tick(now) {
        var dt = Math.min(32, now - lastAt);
        lastAt = now;
        
        ctx.clearRect(0, 0, width, height);
        
        // Base plate
        ctx.beginPath();
        ctx.arc(board.x, board.y, board.radius * 1.05, 0, Math.PI * 2);
        var bg = ctx.createRadialGradient(board.x, board.y, 0, board.x, board.y, board.radius * 1.05);
        bg.addColorStop(0, 'rgba(30,30,28,0.6)');
        bg.addColorStop(1, 'rgba(15,15,14,0.8)');
        ctx.fillStyle = bg;
        ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 1;
        ctx.stroke();
        
        slots.forEach(s => {
            drawGroove(ctx, s.x, s.y, marbleRadius);
        });
        
        marbles.forEach(m => {
            if (!m.settled) {
                var dx = m.target.x - m.x;
                var dy = m.target.y - m.y;
                var dist = Math.sqrt(dx*dx + dy*dy);
                
                var chaos = dist > marbleRadius * 2 ? (Math.random() - 0.5) * 4.5 : 0;
                
                m.vx += dx * 0.012 + chaos;
                m.vy += dy * 0.012 + chaos;
                
                m.vx *= 0.86;
                m.vy *= 0.86;
                
                m.x += m.vx;
                m.y += m.vy;
                
                if (dist < 1.5 && Math.abs(m.vx) < 0.5 && Math.abs(m.vy) < 0.5) {
                    m.settled = true;
                    m.x = m.target.x;
                    m.y = m.target.y;
                }
            }
        });
        
        var renderList = marbles.slice().sort((a,b) => a.y - b.y);
        
        renderList.forEach(m => {
            var sprite = MarbleFactory.createSprite(marbleRadius, m.palIdx, m.pattern, m.seed);
            var speed = Math.sqrt(m.vx*m.vx + m.vy*m.vy);
            var hover = m.settled ? 0 : Math.min(18, Math.max(0, speed * 1.5));
            
            if (hover > 0) {
                ctx.beginPath();
                ctx.ellipse(m.x, m.y + marbleRadius * 0.8, marbleRadius * 0.7, marbleRadius * 0.35, 0, 0, Math.PI*2);
                ctx.fillStyle = 'rgba(0,0,0,' + (0.35 - hover/60) + ')';
                ctx.fill();
            }
            
            ctx.drawImage(sprite, m.x - sprite.width/2, m.y - hover - sprite.height/2);
        });
        
        loopTimer -= dt;
        if (loopTimer <= 0 && marbles.length < slots.length) {
            throwWave();
            loopTimer = 1600 + Math.random() * 1200; 
        }
        
        requestAnimationFrame(tick);
    }
    
    loopTimer = 800;
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
        btn.setAttribute('data-default-label', btn.textContent.trim() || 'Copy');
        btn.addEventListener('click', function () {
            var code = btn.parentElement && btn.parentElement.querySelector('code');
            var text = code ? code.innerText : '';
            copyText(text).then(function (copied) {
                flashCopyButton(btn, copied);
                announceUiMessage(copied ? 'Code block copied to clipboard.' : 'Copy failed. Select the command and copy it manually.');
            });
        });
    });
})();

// ============ CURL BANNER COPY ============
(function () {
    var btn = document.querySelector('.cb-copy');
    if (!btn) return;
    btn.setAttribute('data-default-label', btn.textContent.trim() || 'Copy');
    btn.addEventListener('click', function () {
        var cmd = btn.getAttribute('data-copy');
        copyText(cmd).then(function (copied) {
            flashCopyButton(btn, copied);
            announceUiMessage(copied ? 'Install command copied to clipboard.' : 'Copy failed. Select the install command and copy it manually.');
        });
    });
})();

// ============ HERO TERMINAL COPY (pointer tooltip) ============
(function () {
    var copyables = document.querySelectorAll('.hterm-prompt[data-copy], .hterm-row[data-copy]');
    if (!copyables.length) return;
    var tip = document.createElement('div');
    tip.className = 'hterm-tip';
    tip.textContent = 'Copy';
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
            showTip(x, y, copied ? 'Copied' : 'Copy failed', copied ? 'ok' : 'err');
            announceUiMessage(copied ? 'Command copied to clipboard.' : 'Copy failed. Select the command and copy it manually.');
            clearTimeout(hideTimer);
            hideTimer = setTimeout(hideTip, copied ? 1200 : 1600);
        });
    }

    copyables.forEach(function (el) {
        var value = el.getAttribute('data-copy') || '';
        el.setAttribute('role', 'button');
        el.setAttribute('tabindex', '0');
        el.setAttribute('aria-label', 'Copy command: ' + value);
        el.addEventListener('mouseenter', function (e) {
            clearTimeout(hideTimer);
            showTip(e.clientX, e.clientY, 'Copy');
        });
        el.addEventListener('mousemove', function (e) {
            if (tip.classList.contains('ok') || tip.classList.contains('err')) return;
            tip.style.left = e.clientX + 'px';
            tip.style.top = e.clientY + 'px';
        });
        el.addEventListener('focus', function () {
            var r = el.getBoundingClientRect();
            showTip(r.left + r.width / 2, r.top, 'Copy');
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
    bar.className = 'scroll-progress';
    document.body.appendChild(bar);
    window.addEventListener('scroll', function () {
        var h = document.documentElement.scrollHeight - window.innerHeight;
        bar.style.width = h > 0 ? (window.scrollY / h * 100) + '%' : '0';
    }, {passive: true});
})();

// ============ 3D CARD TILT ON HOVER ============
(function () {
    var finePointer = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    if (prefersReducedMotion || !finePointer) return;
    var cards = document.querySelectorAll('.card');
    cards.forEach(function (card) {
        var rafId = 0;
        var nextTransform = 'perspective(700px) rotateY(0) rotateX(0) scale(1)';

        function applyTransform() {
            rafId = 0;
            card.style.transform = nextTransform;
        }

        card.addEventListener('mousemove', function (e) {
            var r = card.getBoundingClientRect();
            var x = (e.clientX - r.left) / r.width - 0.5;
            var y = (e.clientY - r.top) / r.height - 0.5;
            nextTransform = 'perspective(700px) rotateY(' + x * 6 + 'deg) rotateX(' + (-y * 6) + 'deg) scale(1.01)';
            if (!rafId) rafId = requestAnimationFrame(applyTransform);
        });
        card.addEventListener('mouseleave', function () {
            nextTransform = 'perspective(700px) rotateY(0) rotateX(0) scale(1)';
            if (!rafId) rafId = requestAnimationFrame(applyTransform);
        });
    });
})();

// ============ HOVER CURL BANNER ============ 
(function () {
    var curlTimeout = null;
    var getBtn = document.getElementById('nav-get-link');
    var curlBanner = document.querySelector('.curl-banner');
    if (!getBtn || !curlBanner) return;

    function showBanner() {
        clearTimeout(curlTimeout);
        curlBanner.classList.add('is-visible');
    }

    function hideBanner() {
        curlTimeout = setTimeout(function () {
            curlBanner.classList.remove('is-visible');
        }, 220);
    }

    getBtn.addEventListener('mouseenter', showBanner);
    getBtn.addEventListener('mouseleave', hideBanner);
    getBtn.addEventListener('focus', showBanner);
    getBtn.addEventListener('blur', hideBanner);

    curlBanner.addEventListener('mouseenter', showBanner);
    curlBanner.addEventListener('mouseleave', hideBanner);
    curlBanner.addEventListener('focusin', showBanner);
    curlBanner.addEventListener('focusout', hideBanner);
})();
