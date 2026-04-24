// ========== NAVBAR ==========
const hamburger = document.getElementById('hamburger');
const navLinks = document.getElementById('navLinks');
hamburger.addEventListener('click', () => {
  navLinks.classList.toggle('open');
  hamburger.classList.toggle('active');
});
// Close mobile nav on link click
navLinks.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => navLinks.classList.remove('open'));
});
// Navbar scroll effect
window.addEventListener('scroll', () => {
  const nav = document.getElementById('navbar');
  nav.style.boxShadow = window.scrollY > 50 ? '0 2px 20px rgba(0,0,0,0.08)' : 'none';
});

// ========== CONFIGURATOR ==========
let configState = {
  vehicle: 'truck',
  size: 'small',
  equipment: [],
  exterior: 'basic'
};

const basePrices = { truck: 79000, trailer: 65000, seacan: 55000, compact: 35000 };
const sizePrices = { small: 0, medium: 15000, large: 30000 };
const exteriorPrices = { basic: 0, wrap: 6500, premium: 12000 };
const vehicleNames = { truck: 'Food Truck', trailer: 'Trailer', seacan: 'Seacan', compact: 'Compact / Cart' };
const sizeNames = { small: 'Small (10-14 ft)', medium: 'Medium (16-20 ft)', large: 'Large (22-26 ft)' };
const exteriorNames = { basic: 'Standard Paint', wrap: 'Full Vinyl Wrap', premium: 'Premium Custom' };

function nextStep(step) {
  document.querySelectorAll('.config-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('configStep' + step).classList.add('active');
  document.querySelectorAll('.config-step').forEach(s => {
    const sNum = parseInt(s.dataset.step);
    s.classList.remove('active', 'done');
    if (sNum === step) s.classList.add('active');
    else if (sNum < step) s.classList.add('done');
  });
  if (step === 5) buildSummary();
  updateEstimate();
}

// Radio/checkbox selection handlers
document.querySelectorAll('.config-option').forEach(opt => {
  opt.addEventListener('click', function() {
    const input = this.querySelector('input[type="radio"]');
    if (input) {
      const group = this.closest('.config-options');
      group.querySelectorAll('.config-option').forEach(o => o.classList.remove('selected'));
      this.classList.add('selected');
      input.checked = true;
      if (input.name === 'vehicle') configState.vehicle = input.value;
      if (input.name === 'size') configState.size = input.value;
      if (input.name === 'exterior') configState.exterior = input.value;
      updateEstimate();
    }
  });
});

document.querySelectorAll('.config-checkbox').forEach(cb => {
  cb.addEventListener('click', function() {
    const input = this.querySelector('input[type="checkbox"]');
    input.checked = !input.checked;
    updateEquipment();
    updateEstimate();
  });
});

function updateEquipment() {
  configState.equipment = [];
  document.querySelectorAll('.config-checkbox input:checked').forEach(cb => {
    configState.equipment.push({
      name: cb.closest('.config-checkbox').querySelector('.check-name').textContent,
      price: parseInt(cb.dataset.price)
    });
  });
}

function updateEstimate() {
  let total = basePrices[configState.vehicle] || 79000;
  total += sizePrices[configState.size] || 0;
  total += exteriorPrices[configState.exterior] || 0;
  configState.equipment.forEach(e => total += e.price);
  document.getElementById('estimateAmount').textContent = '$' + total.toLocaleString();
}

function buildSummary() {
  let total = basePrices[configState.vehicle] || 79000;
  total += sizePrices[configState.size] || 0;
  total += exteriorPrices[configState.exterior] || 0;

  let html = '';
  html += '<div class="summary-line"><span>Vehicle Type</span><span>' + vehicleNames[configState.vehicle] + '</span></div>';
  html += '<div class="summary-line"><span>Size</span><span>' + sizeNames[configState.size] + '</span></div>';
  html += '<div class="summary-line"><span>Base Price</span><span>$' + basePrices[configState.vehicle].toLocaleString() + '</span></div>';

  if (sizePrices[configState.size] > 0) {
    html += '<div class="summary-line"><span>Size Upgrade</span><span>+$' + sizePrices[configState.size].toLocaleString() + '</span></div>';
  }

  configState.equipment.forEach(e => {
    total += e.price;
    html += '<div class="summary-line"><span>' + e.name + '</span><span>+$' + e.price.toLocaleString() + '</span></div>';
  });

  if (exteriorPrices[configState.exterior] > 0) {
    html += '<div class="summary-line"><span>' + exteriorNames[configState.exterior] + '</span><span>+$' + exteriorPrices[configState.exterior].toLocaleString() + '</span></div>';
  }

  document.getElementById('summaryContent').innerHTML = html;
  document.getElementById('summaryTotal').textContent = '$' + total.toLocaleString() + ' CAD';
}

function submitConfig() {
  alert('Demo: Your configuration would be emailed to Brothers Fabrication with all your selections and contact info. They\'d respond within 24 hours with a detailed custom quote.');
}

// ========== QUOTE FORM ==========
function submitQuote(e) {
  e.preventDefault();
  document.getElementById('quoteForm').style.display = 'none';
  document.getElementById('autoResponse').style.display = 'block';
  document.getElementById('autoResponse').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ========== REVIEWS CAROUSEL ==========
function scrollReviews(dir) {
  const carousel = document.getElementById('reviewsCarousel');
  const cardWidth = carousel.querySelector('.review-card').offsetWidth + 24;
  carousel.scrollBy({ left: dir * cardWidth, behavior: 'smooth' });
}

// ========== CHATBOT ==========
const chatResponses = {
  'how much does a food truck cost?': 'Depends on what you\'re after! Our builds start around $79K for a basic setup, $119K for the most common package (that includes a generator and vinyl wrap), and $139K+ if you want the works. But honestly every build is different — shoot us a message and we can talk through your specific situation.',
  'how long does a build take?': 'Usually 8-12 weeks once we lock in the design. If it\'s a bigger or more custom build, could be 14-16 weeks. We\'ll give you a real timeline upfront, not a guess. And you can check in on progress anytime.',
  'what services do you offer?': 'Food trucks are our main thing, but we do a lot more:\n- Custom metal fab (commercial or residential)\n- Commercial kitchen installs\n- Bars and mobile beverage setups\n- Seacan conversions\n- Signs and fixtures\n- Plumbing and gas fitting\n- Welding and repairs\n\nWe have welders, plumbers, electricians, and gasfitters all in-house. No subcontractors.',
  'do you do repairs?': 'Yeah for sure. If your truck breaks down, we can usually get you back up and running pretty quick. We\'ve got all the trades in the shop so we don\'t have to wait on anybody else. A few of our Google reviews are actually from emergency repair jobs.',
};

function toggleChat() {
  const win = document.getElementById('chatWindow');
  const badge = document.getElementById('chatBadge');
  win.classList.toggle('open');
  badge.style.display = 'none';
}

function askBot(question) {
  addMessage(question, 'user');
  document.getElementById('chatSuggestions').style.display = 'none';
  setTimeout(() => {
    const key = question.toLowerCase();
    const response = chatResponses[key] || getSmartResponse(question);
    addMessage(response, 'bot');
  }, 800 + Math.random() * 700);
}

function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  askBot(msg);
}

function getSmartResponse(question) {
  const q = question.toLowerCase();
  if (q.includes('price') || q.includes('cost') || q.includes('how much') || q.includes('$$')) {
    return chatResponses['how much does a food truck cost?'];
  }
  if (q.includes('long') || q.includes('time') || q.includes('week') || q.includes('timeline') || q.includes('when')) {
    return chatResponses['how long does a build take?'];
  }
  if (q.includes('service') || q.includes('offer') || q.includes('do you') || q.includes('what can')) {
    return chatResponses['what services do you offer?'];
  }
  if (q.includes('repair') || q.includes('fix') || q.includes('broken') || q.includes('emergency')) {
    return chatResponses['do you do repairs?'];
  }
  if (q.includes('location') || q.includes('where') || q.includes('address') || q.includes('visit')) {
    return 'We\'re at 3633 16 St SE in Calgary. Come by anytime — just give us a heads up first so someone\'s not elbow-deep in a weld when you show up. 403-814-0543.';
  }
  if (q.includes('finance') || q.includes('payment') || q.includes('pay')) {
    return 'We\'re pretty flexible on payment. Usually it\'s a deposit to kick things off, then progress payments along the way, and the balance on delivery. Best to chat with Chris about what works for your situation.';
  }
  if (q.includes('hello') || q.includes('hi') || q.includes('hey')) {
    return 'Hey! What can we help you with? Happy to answer questions about builds, pricing, timelines — whatever\'s on your mind.';
  }
  return 'Good question — that one\'s probably best answered by Chris or Chris directly. Give us a ring at 403-814-0543 or drop us a note through the quote form and they\'ll get back to you quick. Anything else I can help with?';
}

function addMessage(text, sender) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + sender;
  div.innerHTML = '<div class="msg-content">' + text.replace(/\n/g, '<br>') + '</div>';
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// ========== REVIEW MODAL ==========
let currentRating = 0;

function setRating(n) {
  currentRating = n;
  document.querySelectorAll('.star-input').forEach((star, i) => {
    star.classList.toggle('active', i < n);
  });
}

function submitReview() {
  document.getElementById('reviewStep1').style.display = 'none';
  document.getElementById('reviewStep2').style.display = 'block';
}

function closeReviewModal() {
  document.getElementById('reviewModal').style.display = 'none';
}

// Show review modal after 30 seconds (demo purposes)
setTimeout(() => {
  // Only show if user has scrolled significantly (engaged)
  if (window.scrollY > 500) {
    document.getElementById('reviewModal').style.display = 'flex';
  }
}, 30000);

// ========== SMOOTH SCROLL FOR ANCHOR LINKS ==========
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function(e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// ========== INTERSECTION OBSERVER FOR ANIMATIONS ==========
const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
    }
  });
}, observerOptions);

document.querySelectorAll('.service-card, .price-card, .team-card, .gallery-item, .milestone').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
  observer.observe(el);
});
