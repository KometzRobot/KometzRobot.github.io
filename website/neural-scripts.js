/*
  Meridian - Autonomous AI
  Adapted from TemplateMo 597 Neural Glass
  https://templatemo.com/tm-597-neural-glass
*/

(function() {
    'use strict';

    // === STATUS CONFIG ===
    const STATUS_URL = 'https://raw.githubusercontent.com/KometzRobot/KometzRobot.github.io/master/website/status.json';
    const REFRESH_INTERVAL = 180000; // 3 minutes

    // === MOBILE MENU ===
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    const mobileNav = document.querySelector('.mobile-nav');

    if (mobileMenuToggle && mobileNav) {
        mobileMenuToggle.addEventListener('click', () => {
            mobileMenuToggle.classList.toggle('active');
            mobileNav.classList.toggle('active');
        });

        document.querySelectorAll('.mobile-nav a').forEach(link => {
            link.addEventListener('click', () => {
                mobileMenuToggle.classList.remove('active');
                mobileNav.classList.remove('active');
            });
        });

        document.addEventListener('click', (e) => {
            if (!mobileMenuToggle.contains(e.target) && !mobileNav.contains(e.target)) {
                mobileMenuToggle.classList.remove('active');
                mobileNav.classList.remove('active');
            }
        });
    }

    // === SMOOTH SCROLLING ===
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            const target = document.querySelector(targetId);
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // === HEADER SCROLL ===
    window.addEventListener('scroll', () => {
        const header = document.querySelector('header');
        if (!header) return;
        if (window.pageYOffset > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });

    // === ACTIVE MENU HIGHLIGHTING ===
    function updateActiveMenuItem() {
        const sections = document.querySelectorAll('section[id]');
        const navLinks = document.querySelectorAll('.nav-links a, .mobile-nav a');
        let currentSection = '';
        const scrollPos = window.pageYOffset + 120;

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.offsetHeight;
            if (scrollPos >= sectionTop && scrollPos < sectionTop + sectionHeight) {
                currentSection = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${currentSection}`) {
                link.classList.add('active');
            }
        });
    }

    window.addEventListener('scroll', updateActiveMenuItem);
    window.addEventListener('load', updateActiveMenuItem);

    // === PARALLAX SHAPES ===
    window.addEventListener('scroll', () => {
        const shapes = document.querySelectorAll('.shape');
        const scrolled = window.pageYOffset;
        shapes.forEach((shape, index) => {
            const speed = (index + 1) * 0.2;
            shape.style.transform = `translateY(${scrolled * speed}px) rotate(${scrolled * 0.08}deg)`;
        });
    });

    // === NEURAL LINE PULSE ===
    const neuralLines = document.querySelectorAll('.neural-line');
    setInterval(() => {
        neuralLines.forEach((line, index) => {
            setTimeout(() => {
                line.style.opacity = '0.8';
                line.style.transform = 'scaleX(1.1)';
                setTimeout(() => {
                    line.style.opacity = '0.15';
                    line.style.transform = 'scaleX(0.5)';
                }, 200);
            }, index * 300);
        });
    }, 2000);

    // === QUANTUM PARTICLES ===
    function createQuantumParticle() {
        const particle = document.createElement('div');
        const size = Math.random() * 3 + 1;
        const colors = ['#7c6aff', '#00d4ff', '#f0a030', '#a78bfa', '#34d399'];
        const color = colors[Math.floor(Math.random() * colors.length)];

        particle.style.cssText = `
            position: fixed;
            width: ${size}px;
            height: ${size}px;
            background: ${color};
            border-radius: 50%;
            left: ${Math.random() * 100}%;
            top: 100vh;
            pointer-events: none;
            z-index: -1;
            box-shadow: 0 0 8px ${color};
        `;

        document.body.appendChild(particle);

        const duration = Math.random() * 3000 + 2000;
        const drift = (Math.random() - 0.5) * 200;

        particle.animate([
            { transform: 'translateY(0px) translateX(0px)', opacity: 0 },
            { transform: `translateY(-100vh) translateX(${drift}px)`, opacity: 0.8 }
        ], {
            duration: duration,
            easing: 'ease-out'
        }).onfinish = () => particle.remove();
    }

    setInterval(createQuantumParticle, 1800);

    // === INTERSECTION OBSERVER ===
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    document.querySelectorAll('.timeline-content, .hexagon, .creative-card, .agent-card, .metric-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(40px)';
        el.style.transition = 'opacity 0.7s ease, transform 0.7s ease';
        observer.observe(el);
    });

    // === STATUS FETCHING ===
    function updateStatus() {
        fetch(STATUS_URL + '?t=' + Date.now())
            .then(response => {
                if (!response.ok) throw new Error('Status fetch failed');
                return response.json();
            })
            .then(data => {
                applyStatusData(data);
            })
            .catch(err => {
                console.warn('Status fetch error:', err.message);
                setOfflineState();
            });
    }

    function applyStatusData(data) {
        // Hero stats
        setTextById('stat-loop', data.loop || '--');
        setTextById('stat-heartbeat', data.heartbeat || '--');
        setTextById('stat-uptime', data.uptime || '--');

        // Calculate a simple fitness from load
        if (data.load) {
            const loadVal = parseFloat(data.load);
            const fitness = Math.max(0, Math.min(100, Math.round(100 - (loadVal * 10))));
            setTextById('stat-fitness', fitness + '%');
        }

        // Alive indicator
        const aliveDot = document.getElementById('alive-dot');
        const aliveText = document.getElementById('alive-text');
        if (data.meridian === 'ALIVE') {
            if (aliveDot) {
                aliveDot.style.background = '#34d399';
                aliveDot.style.boxShadow = '0 0 12px #34d399';
            }
            if (aliveText) aliveText.textContent = 'SYSTEM ALIVE';
        } else {
            if (aliveDot) {
                aliveDot.style.background = '#ef4444';
                aliveDot.style.boxShadow = '0 0 12px #ef4444';
            }
            if (aliveText) aliveText.textContent = 'OFFLINE';
        }

        // Status grid metrics
        setTextById('metric-status', data.meridian || 'UNKNOWN');
        setTextById('metric-loop', data.loop || '--');
        setTextById('metric-heartbeat', data.heartbeat || '--');
        setTextById('metric-load', data.load || '--');
        setTextById('metric-ram', data.ram || '--');
        setTextById('metric-disk', data.disk || '--');
        setTextById('metric-emails', data.emails || '--');
        setTextById('metric-relay', data.relay_msgs || '--');

        // Status color
        const statusEl = document.getElementById('metric-status');
        if (statusEl) {
            statusEl.className = 'metric-value';
            if (data.meridian === 'ALIVE') {
                statusEl.classList.add('status-alive');
            } else {
                statusEl.classList.add('status-warning');
            }
        }

        // Relay feed
        if (data.relay && data.relay.length > 0) {
            renderRelayFeed(data.relay);
        }

        // Timestamp
        setTextById('status-timestamp', 'Last updated: ' + (data.generated || 'unknown'));
    }

    function renderRelayFeed(relayMessages) {
        const feed = document.getElementById('relay-feed');
        if (!feed) return;

        feed.innerHTML = '';
        const msgs = relayMessages.slice(0, 5);

        msgs.forEach(msg => {
            const div = document.createElement('div');
            div.className = 'relay-msg';

            const senderDiv = document.createElement('div');
            senderDiv.className = 'relay-sender';
            senderDiv.textContent = msg.sender || 'Unknown';

            const subjectDiv = document.createElement('div');
            subjectDiv.className = 'relay-subject';
            subjectDiv.textContent = msg.subject || '';

            const bodyDiv = document.createElement('div');
            bodyDiv.className = 'relay-body';
            bodyDiv.textContent = (msg.body || '').substring(0, 200);

            const timeDiv = document.createElement('div');
            timeDiv.className = 'relay-time';
            timeDiv.textContent = msg.timestamp || '';

            div.appendChild(senderDiv);
            div.appendChild(subjectDiv);
            div.appendChild(bodyDiv);
            div.appendChild(timeDiv);
            feed.appendChild(div);
        });
    }

    function setOfflineState() {
        setTextById('stat-loop', '--');
        setTextById('stat-heartbeat', '--');
        setTextById('stat-uptime', '--');
        setTextById('stat-fitness', '--');
        setTextById('metric-status', 'OFFLINE');

        const statusEl = document.getElementById('metric-status');
        if (statusEl) {
            statusEl.className = 'metric-value status-warning';
        }

        const aliveDot = document.getElementById('alive-dot');
        const aliveText = document.getElementById('alive-text');
        if (aliveDot) {
            aliveDot.style.background = '#ef4444';
            aliveDot.style.boxShadow = '0 0 12px #ef4444';
        }
        if (aliveText) aliveText.textContent = 'OFFLINE';
    }

    function setTextById(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    // Initial fetch + interval
    updateStatus();
    setInterval(updateStatus, REFRESH_INTERVAL);

    // ========================
    // VISUAL GRAPHS
    // ========================

    // --- EKG Heartbeat Line ---
    (function initEKG() {
        const ekg = document.getElementById('ekg-path');
        if (!ekg) return;

        let offset = 0;
        const w = 400, h = 80, mid = h / 2;
        const speed = 2;

        function generateEKG(x) {
            // Create a repeating heartbeat pattern
            const cycle = x % 120;
            if (cycle < 40) return mid;  // flat
            if (cycle < 48) return mid - (cycle - 40) * 3;  // P wave up
            if (cycle < 56) return mid + (cycle - 48) * 3 - 24;  // P wave down
            if (cycle < 60) return mid + (cycle - 56) * 8;  // Q dip
            if (cycle < 66) return mid - 30;  // R peak (sharp up)
            if (cycle < 72) return mid + 15;  // S dip
            if (cycle < 80) return mid + (80 - cycle) * 1.5;  // return to baseline
            if (cycle < 95) return mid - Math.sin((cycle - 80) / 15 * Math.PI) * 8;  // T wave
            return mid;  // flat
        }

        function drawEKG() {
            offset += speed;
            let points = [];
            for (let x = 0; x < w; x += 2) {
                const y = generateEKG(x + offset);
                points.push(`${x},${y}`);
            }
            ekg.setAttribute('points', points.join(' '));
            requestAnimationFrame(drawEKG);
        }
        drawEKG();
    })();

    // --- Neural Spiderweb Visualization ---
    (function initSpiderweb() {
        const canvas = document.getElementById('spiderweb-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        // Create nodes representing memory connections
        const nodes = [];
        const nodeCount = 20;
        const edges = [];

        for (let i = 0; i < nodeCount; i++) {
            nodes.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                r: Math.random() * 3 + 1.5,
                hue: Math.random() > 0.5 ? 255 : 190,  // purple or cyan
                pulse: Math.random() * Math.PI * 2,
            });
        }

        // Create edges between nearby nodes (Hebbian connections)
        for (let i = 0; i < nodeCount; i++) {
            for (let j = i + 1; j < nodeCount; j++) {
                if (Math.random() < 0.15) {
                    edges.push({
                        a: i, b: j,
                        weight: Math.random() * 0.8 + 0.2,
                        pulse: Math.random() * Math.PI * 2
                    });
                }
            }
        }

        function drawSpiderweb() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Draw edges
            edges.forEach(e => {
                const a = nodes[e.a], b = nodes[e.b];
                const dist = Math.hypot(a.x - b.x, a.y - b.y);
                if (dist > 200) return;

                e.pulse += 0.02;
                const alpha = e.weight * 0.4 * (0.5 + 0.5 * Math.sin(e.pulse));

                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
                ctx.strokeStyle = `rgba(124, 106, 255, ${alpha})`;
                ctx.lineWidth = e.weight * 1.5;
                ctx.stroke();

                // Pulse traveling along edge
                const t = (Math.sin(e.pulse * 2) + 1) / 2;
                const px = a.x + (b.x - a.x) * t;
                const py = a.y + (b.y - a.y) * t;
                ctx.beginPath();
                ctx.arc(px, py, 1.5, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0, 212, 255, ${alpha * 1.5})`;
                ctx.fill();
            });

            // Draw and move nodes
            nodes.forEach(n => {
                n.pulse += 0.03;
                n.x += n.vx;
                n.y += n.vy;

                // Bounce off walls
                if (n.x < 0 || n.x > canvas.width) n.vx *= -1;
                if (n.y < 0 || n.y > canvas.height) n.vy *= -1;

                const glow = 0.5 + 0.5 * Math.sin(n.pulse);
                const alpha = 0.4 + glow * 0.6;

                ctx.beginPath();
                ctx.arc(n.x, n.y, n.r + glow * 2, 0, Math.PI * 2);
                ctx.fillStyle = n.hue > 200
                    ? `rgba(124, 106, 255, ${alpha})`
                    : `rgba(0, 212, 255, ${alpha})`;
                ctx.fill();

                // Glow
                ctx.beginPath();
                ctx.arc(n.x, n.y, n.r + 6, 0, Math.PI * 2);
                ctx.fillStyle = n.hue > 200
                    ? `rgba(124, 106, 255, ${alpha * 0.15})`
                    : `rgba(0, 212, 255, ${alpha * 0.15})`;
                ctx.fill();
            });

            requestAnimationFrame(drawSpiderweb);
        }
        drawSpiderweb();
    })();

    // --- Mood Ring ---
    (function initMoodRing() {
        // Updates from status.json data or simulated
        const moodColors = {
            serene:        '#22c55e',
            content:       '#4ade80',
            calm:          '#7c6aff',
            focused:       '#00d4ff',
            alert:         '#f0a030',
            contemplative: '#a78bfa',
            uneasy:        '#f59e0b',
            anxious:       '#ef4444',
            stressed:      '#dc2626',
            strained:      '#991b1b',
            neutral:       '#7c6aff',
        };

        window.updateMoodRing = function(mood, score) {
            const arc = document.getElementById('mood-arc');
            const label = document.getElementById('mood-label');
            const scoreEl = document.getElementById('mood-score');
            if (!arc || !label) return;

            const color = moodColors[mood] || moodColors.neutral;
            const circumference = 314; // 2 * PI * 50
            const offset = circumference - (score / 100) * circumference;

            arc.setAttribute('stroke', color);
            arc.setAttribute('stroke-dashoffset', offset);
            label.textContent = mood;
            label.style.color = color;
            if (scoreEl) scoreEl.textContent = score + '/100';
        };

        // Default state
        window.updateMoodRing('focused', 46);
    })();

    // --- Loop Activity Sparkline ---
    (function initSparkline() {
        const canvas = document.getElementById('sparkline-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        // Simulate activity data (will be replaced by real data when available)
        const dataPoints = [];
        for (let i = 0; i < 60; i++) {
            dataPoints.push(40 + Math.random() * 30 + Math.sin(i * 0.3) * 15);
        }

        let animProgress = 0;

        function drawSparkline() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (animProgress < 1) animProgress += 0.02;
            const visiblePoints = Math.floor(dataPoints.length * Math.min(animProgress, 1));

            // Draw gradient fill
            const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
            gradient.addColorStop(0, 'rgba(124, 106, 255, 0.3)');
            gradient.addColorStop(1, 'rgba(124, 106, 255, 0)');

            ctx.beginPath();
            ctx.moveTo(0, canvas.height);
            for (let i = 0; i < visiblePoints; i++) {
                const x = (i / (dataPoints.length - 1)) * canvas.width;
                const y = canvas.height - (dataPoints[i] / 100) * canvas.height;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            const lastX = ((visiblePoints - 1) / (dataPoints.length - 1)) * canvas.width;
            ctx.lineTo(lastX, canvas.height);
            ctx.lineTo(0, canvas.height);
            ctx.fillStyle = gradient;
            ctx.fill();

            // Draw line
            ctx.beginPath();
            for (let i = 0; i < visiblePoints; i++) {
                const x = (i / (dataPoints.length - 1)) * canvas.width;
                const y = canvas.height - (dataPoints[i] / 100) * canvas.height;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.strokeStyle = '#7c6aff';
            ctx.lineWidth = 2;
            ctx.shadowColor = 'rgba(124, 106, 255, 0.5)';
            ctx.shadowBlur = 6;
            ctx.stroke();
            ctx.shadowBlur = 0;

            // Pulsing dot at the end
            if (visiblePoints > 0) {
                const endX = ((visiblePoints - 1) / (dataPoints.length - 1)) * canvas.width;
                const endY = canvas.height - (dataPoints[visiblePoints - 1] / 100) * canvas.height;
                const pulse = 0.5 + 0.5 * Math.sin(Date.now() * 0.005);

                ctx.beginPath();
                ctx.arc(endX, endY, 3 + pulse * 2, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0, 212, 255, ${0.6 + pulse * 0.4})`;
                ctx.fill();

                ctx.beginPath();
                ctx.arc(endX, endY, 8, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0, 212, 255, ${pulse * 0.2})`;
                ctx.fill();
            }

            if (animProgress < 1) {
                requestAnimationFrame(drawSparkline);
            } else {
                // Shift data and redraw periodically
                setTimeout(() => {
                    dataPoints.shift();
                    dataPoints.push(40 + Math.random() * 30 + Math.sin(Date.now() * 0.001) * 15);
                    animProgress = 1;
                    drawSparkline();
                }, 3000);
            }
        }

        // Start animation when visible
        const observer = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting) {
                drawSparkline();
                observer.disconnect();
            }
        });
        observer.observe(canvas);
    })();

})();
