const state = { config: null, quote: null, selectedSeats: new Set() };
const currency = value => `₹${Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function showView(viewName) {
  document.querySelectorAll('.site-view').forEach(view => view.classList.toggle('active-view', view.id === `${viewName}-view`));
  document.querySelectorAll('.nav-link').forEach(link => link.classList.toggle('active', link.dataset.view === viewName));
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (viewName === 'bookings') renderHistory();
}

function renderHistory() {
  const history = JSON.parse(localStorage.getItem('auriga-bookings') || '[]');
  const container = document.querySelector('#booking-history');
  if (!history.length) return;
  container.innerHTML = history.map(booking => `<article class="history-card"><div class="history-poster art-midnight"><span>FRIDAY<br>NIGHT</span></div><div class="history-info"><p class="eyebrow">CONFIRMED · ${booking.booking_id}</p><h2>Friday Night at the Multiplex</h2><p>${booking.customer.name} · ${booking.seats.join(', ')}</p><small>Today · 9:30 PM · Screen 04</small></div><strong>${currency(booking.total)}</strong></article>`).join('');
}

function rememberBooking(booking) {
  const history = JSON.parse(localStorage.getItem('auriga-bookings') || '[]');
  history.unshift(booking);
  localStorage.setItem('auriga-bookings', JSON.stringify(history.slice(0, 10)));
}

function renderPriceReport(report) {
  const imported = report.imported.map(item => `<li><strong>${item.class}</strong> ${currency(item.price)}</li>`).join('') || '<li>None</li>';
  const duplicates = report.deduplicated.map(item => `<li>Line ${item.line}: ${item.class} ignored (${currency(item.ignored)}); kept ${currency(item.kept)}</li>`).join('') || '<li>None</li>';
  const rejected = report.rejected.map(item => `<li>Line ${item.line}: ${item.value} · ${item.reason}</li>`).join('') || '<li>None</li>';
  document.querySelector('#price-report').innerHTML = `<div class="report-head"><p class="eyebrow">IMPORT COMPLETE</p><span>${report.imported.length} accepted</span></div><h2>Clean price list</h2><ul class="report-list">${imported}</ul><h3>De-duplicated <span>${report.deduplicated.length}</span></h3><ul class="report-list muted-list">${duplicates}</ul><h3>Rejected <span>${report.rejected.length}</span></h3><ul class="report-list rejected-list">${rejected}</ul>`;
}

async function importPrices(event) {
  event.preventDefault();
  const file = document.querySelector('#price-file').files[0];
  const content = file ? await file.text() : document.querySelector('#price-content').value;
  try {
    renderPriceReport(await request('/api/prices/import', { method: 'POST', body: JSON.stringify({ content }) }));
  } catch (error) { document.querySelector('#price-report').textContent = error.message; }
}

function renderLiveMovies(catalog) {
  const cards = catalog.movies.map((movie, index) => `<article class="movie-card ${index === 0 ? 'featured-card' : ''}"><div class="movie-art ${movie.poster.startsWith('http') ? '' : movie.poster}" ${movie.poster.startsWith('http') ? `style="background-image:url('${movie.poster}');background-size:cover;background-position:center"` : ''}><span>${movie.title.toUpperCase()}</span><small>${movie.genre.toUpperCase()} · ${movie.duration.toUpperCase()}</small></div><div class="movie-card-info"><div><h3>${movie.title}</h3><p>${movie.genre} · ${movie.duration} · ${movie.rating}</p><b>${movie.showtime} · Screen ${movie.screen}</b></div><button class="book-small" data-view="booking">Book now</button></div></article>`).join('');
  document.querySelectorAll('.expanded-grid, #home-movie-grid').forEach(grid => { grid.innerHTML = cards; });
  const status = document.querySelector('#catalog-status');
  if (status) status.textContent = catalog.live ? 'LIVE NOW' : 'Auriga schedule';
  bindViewActions();
}

function bindViewActions() {
  document.querySelectorAll('[data-view]').forEach(element => {
    if (element.dataset.bound) return;
    element.dataset.bound = 'true';
    element.addEventListener('click', () => showView(element.dataset.view));
  });
  document.querySelectorAll('[data-book-show]').forEach(element => {
    if (element.dataset.bound) return;
    element.dataset.bound = 'true';
    element.addEventListener('click', () => showView('booking'));
  });
}

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Something went wrong');
  return data;
}

function showError(message) {
  const alert = document.querySelector('#alert');
  alert.textContent = message;
  alert.hidden = false;
}

function clearError() { document.querySelector('#alert').hidden = true; }

function renderSeatMap() {
  const map = document.querySelector('#seat-map');
  map.innerHTML = Object.entries(state.config.tiers).map(([tier, details]) => {
    const seats = state.config.seats.filter(seat => seat.tier === tier);
    return `<section class="seat-zone" data-tier="${tier}">
      <div class="zone-heading"><span class="tier-dot tier-${tier.toLowerCase()}"></span><strong>${tier}</strong><span>${currency(details.price)} · ${details.available} available</span></div>
      <div class="seat-grid">${seats.map(seat => `<button type="button" class="seat ${seat.available ? '' : 'taken'} ${state.selectedSeats.has(seat.id) ? 'selected' : ''}" data-seat="${seat.id}" ${seat.available ? '' : 'disabled'}>${seat.id}</button>`).join('')}</div>
    </section>`;
  }).join('');
}

function renderSelectedSeats() {
  const container = document.querySelector('#selected-seats');
  const seats = [...state.selectedSeats].sort();
  document.querySelector('#seat-summary').textContent = seats.length ? `${seats.length} seat${seats.length === 1 ? '' : 's'} · ${seats.join(', ')}` : 'No seats selected';
  container.innerHTML = `<span class="selected-label">Selected seats</span>${seats.length ? seats.map(seat => `<button type="button" class="seat-chip" data-remove-seat="${seat}">${seat} ×</button>`).join('') : '<span class="selected-empty">Choose seats from the map</span>'}`;
  document.querySelector('#seat-total').textContent = seats.length;
}

function toggleSeat(event) {
  const button = event.target.closest('[data-seat]');
  const remove = event.target.closest('[data-remove-seat]');
  const seatId = button?.dataset.seat || remove?.dataset.removeSeat;
  if (!seatId) return;
  if (state.selectedSeats.has(seatId)) state.selectedSeats.delete(seatId);
  else state.selectedSeats.add(seatId);
  renderSeatMap();
  renderSelectedSeats();
  updateQuote();
}

function selectedSeats() { return [...state.selectedSeats]; }

async function updateQuote() {
  clearError();
  const seats = selectedSeats();
  if (!seats.length) {
    state.quote = null;
    document.querySelector('#empty-receipt').hidden = false;
    document.querySelector('#receipt').hidden = true;
    return;
  }
  try {
    state.quote = await request('/api/quote', { method: 'POST', body: JSON.stringify({ seats, member: document.querySelector('#member').checked }) });
    renderReceipt(state.quote);
  } catch (error) { showError(error.message); }
}

function renderReceipt(quote) {
  document.querySelector('#empty-receipt').hidden = true;
  document.querySelector('#receipt').hidden = false;
  document.querySelector('#ticket-lines').innerHTML = quote.ticket_lines.map(line => `<div class="receipt-row"><span>${line.label}</span><strong>${currency(line.amount)}</strong></div>`).join('');
  document.querySelector('#receipt-seats').textContent = quote.seats.join(', ');
  document.querySelector('#subtotal').textContent = currency(quote.subtotal);
  document.querySelector('#festival-discount').textContent = `− ${currency(quote.festival_discount)}`;
  document.querySelector('#member-discount').textContent = `− ${currency(quote.member_discount)}`;
  document.querySelector('#fee').textContent = currency(quote.convenience_fee);
  document.querySelector('#gst').textContent = currency(quote.gst);
  document.querySelector('#total').textContent = currency(quote.total);
}

function customerDetails() {
  const name = document.querySelector('#guest-name').value.trim();
  const phone = document.querySelector('#guest-phone').value.trim();
  if (!name) throw new Error('Enter the guest name before confirming');
  if (phone && !/^\d{10}$/.test(phone)) throw new Error('Enter a valid 10-digit mobile number');
  return { name, phone };
}

async function confirmBooking() {
  if (!state.quote) return;
  try {
    const customer = customerDetails();
    const button = document.querySelector('#book-button');
    button.disabled = true;
    button.innerHTML = 'Confirming...';
    const result = await request('/api/book', { method: 'POST', body: JSON.stringify({ seats: selectedSeats(), member: state.quote.member, customer }) });
    document.querySelector('#booking-ref').textContent = result.booking_id || 'BOOKING CONFIRMED';
    document.querySelector('#success-message').textContent = `${customer.name}, your seats are held. Keep this reference for the counter.`;
    document.querySelector('#success-seats').textContent = result.seats.join(' · ');
    rememberBooking(result);
    document.querySelector('#success-modal').hidden = false;
  } catch (error) {
    showError(error.message);
    return;
  } finally {
    const button = document.querySelector('#book-button');
    button.disabled = false;
    button.innerHTML = 'Confirm booking <span>→</span>';
  }
}

async function loadConfig() {
  state.config = await request('/api/config');
  document.querySelector('#cinema-name').textContent = state.config.cinema;
  document.querySelector('#show-time').textContent = state.config.showtime;
  document.querySelector('#festival-value').textContent = currency(state.config.festival_discount);
  document.querySelector('#member-rate').textContent = state.config.member_discount_rate;
  document.querySelector('#member-cap').textContent = Number(state.config.member_discount_cap).toLocaleString('en-IN');
  document.querySelector('#gst-rate').textContent = state.config.gst_rate;
  renderSeatMap();
  renderSelectedSeats();
  try {
    const catalog = await request('/api/movies');
    renderLiveMovies(catalog);
  } catch (error) {
    console.warn('Live movie catalogue unavailable; using built-in schedule.', error);
  }
}

bindViewActions();
document.querySelector('#seat-map').addEventListener('click', toggleSeat);
document.querySelector('#selected-seats').addEventListener('click', toggleSeat);
document.querySelector('#member').addEventListener('change', updateQuote);
document.querySelector('#book-button').addEventListener('click', confirmBooking);
document.querySelector('#open-seat-picker').addEventListener('click', () => document.querySelector('#seat-picker-modal').hidden = false);
document.querySelector('#close-seat-picker').addEventListener('click', () => document.querySelector('#seat-picker-modal').hidden = true);
document.querySelector('#done-seat-picker').addEventListener('click', () => document.querySelector('#seat-picker-modal').hidden = true);
document.querySelector('#close-modal').addEventListener('click', () => document.querySelector('#success-modal').hidden = true);
document.querySelector('#new-booking').addEventListener('click', () => window.location.reload());
document.querySelector('#price-import-form').addEventListener('submit', importPrices);
document.querySelector('#price-file').addEventListener('change', event => { document.querySelector('#file-name').textContent = event.target.files[0]?.name || 'or paste rows below'; });
loadConfig().catch(error => showError(error.message));
showView('home');
