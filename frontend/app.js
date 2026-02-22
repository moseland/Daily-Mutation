/**
 * Morning Mutation - Frontend Application
 * Handles fetching broadcast data, filtering by category, and rendering the UI.
 */
let globalNewsData = [];
let currentFilter = 'All';

document.addEventListener('DOMContentLoaded', () => {
    fetchBroadcastData();
});

/**
 * Parses a date string safely. 
 * If it's a "YYYY-MM-DD" string, it treats it as local time instead of UTC 
 * to prevent off-by-one errors in different timezones.
 */
function parseLocalDate(dateStr) {
    if (!dateStr) return new Date();
    // If it has 'T', it's already an ISO string with time info
    if (dateStr.includes('T')) return new Date(dateStr);

    const parts = dateStr.split('-');
    if (parts.length === 3) {
        // new Date(year, monthIndex, day)
        return new Date(parts[0], parts[1] - 1, parts[2]);
    }
    return new Date(dateStr);
}

async function fetchBroadcastData() {
    try {
        // Fetch JSON exported from main.py
        const response = await fetch('output/broadcast_data.json');

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        renderUI(data);
    } catch (error) {
        console.error('Error fetching broadcast data:', error);
        document.getElementById('broadcast-date').textContent = 'Error loading latest broadcast.';
        document.getElementById('weather-content').innerHTML = '<p class="w-label">Failed to load weather data.</p>';
        document.getElementById('news-feed').innerHTML = '<div class="glass-panel feed-loader">Failed to load news stories. Please ensure the backend has run successfully.</div>';
    }
}

function renderUI(data) {
    // Render Date
    const dateObj = parseLocalDate(data.date);
    const dateStr = dateObj.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        timeZone: 'America/New_York'
    });
    document.getElementById('broadcast-date').textContent = `Broadcast: ${dateStr}`;

    // Render Weather
    renderWeather(data.weather);

    // Store news data and render
    globalNewsData = data.news || [];
    renderFilters();
    renderNewsFeed();
}

function renderWeather(weather) {
    const container = document.getElementById('weather-content');
    const title = document.getElementById('weather-title');

    if (!weather || !weather.today) {
        container.innerHTML = '<p class="w-label">Weather data unavailable</p>';
        return;
    }

    if (weather.city && weather.state) {
        title.textContent = `Weather in ${weather.city}, ${weather.state}`;
    }

    // Main today display
    let html = `
        <div class="weather-stat">
            <span class="w-label">Today's High / Low</span>
            <span class="w-val">${Math.round(weather.today.max_temp)}°F / ${Math.round(weather.today.min_temp)}°F</span>
        </div>
        <div class="w-desc">${weather.today.description}</div>
    `;

    // Extended Forecast Section
    if (weather.upcoming && weather.upcoming.length > 0) {
        // Filter out any upcoming days that match Today's date to avoid redundancy
        const upcomingDays = weather.upcoming.filter(day => day.date !== weather.today.date);

        if (upcomingDays.length > 0) {
            html += `<div class="extended-forecast">
                <h4>Later this week</h4>
                <div class="forecast-grid">`;

            upcomingDays.forEach(day => {
                const d = parseLocalDate(day.date);
                const dayName = d.toLocaleDateString('en-US', {
                    weekday: 'short',
                    timeZone: 'America/New_York'
                });
                html += `
                <div class="forecast-day">
                    <span class="f-name">${dayName}</span>
                    <span class="f-temp">${Math.round(day.max_temp)}°F</span>
                    <span class="f-desc" title="${day.description}">${day.description}</span>
                </div>
            `;
            });

            html += `</div></div>`;
        }
    }

    container.innerHTML = html;
}

function renderFilters() {
    const filtersContainer = document.getElementById('category-filters');
    filtersContainer.innerHTML = '';

    if (globalNewsData.length === 0) return;

    // Extract unique categories from all clusters
    const allCategories = new Set();
    globalNewsData.forEach(item => {
        if (item.categories && Array.isArray(item.categories)) {
            item.categories.forEach(c => allCategories.add(c));
        } else {
            allCategories.add('World');
        }
    });
    const categories = ['All', ...Array.from(allCategories).sort()];

    categories.forEach(cat => {
        const btn = document.createElement('button');
        const isActive = cat === currentFilter;
        btn.className = `filter-btn ${isActive ? 'active' : ''}`;
        btn.textContent = cat;
        btn.onclick = () => {
            currentFilter = cat;
            renderFilters(); // Re-render to update active class
            renderNewsFeed();
        };
        filtersContainer.appendChild(btn);
    });
}

function renderNewsFeed() {
    const feedContainer = document.getElementById('news-feed');
    feedContainer.innerHTML = '';

    const filteredNews = currentFilter === 'All'
        ? globalNewsData
        : globalNewsData.filter(item => {
            const cats = item.categories || ['World'];
            return cats.includes(currentFilter);
        });

    if (filteredNews.length === 0) {
        feedContainer.innerHTML = '<div class="glass-panel feed-loader">No news found for today.</div>';
        return;
    }

    filteredNews.forEach(cluster => {
        // Create category block
        const catBlock = document.createElement('div');
        catBlock.className = 'category-block';

        // Header: Show all categories as tags
        const header = document.createElement('div');
        header.className = 'category-tags';
        const cats = cluster.categories || ['World'];
        cats.forEach(c => {
            const tag = document.createElement('span');
            tag.className = 'category-tag';
            tag.textContent = c;
            header.appendChild(tag);
        });
        catBlock.appendChild(header);

        // Card
        const card = document.createElement('div');
        card.className = 'news-card glass-panel';

        // Summary text
        const summary = document.createElement('div');
        summary.className = 'news-summary';
        // Parse markdown using marked.js
        summary.innerHTML = marked.parse(cluster.summary);
        card.appendChild(summary);

        // Article Links
        if (cluster.articles && cluster.articles.length > 0) {
            const linksContainer = document.createElement('div');
            linksContainer.className = 'article-links';

            const linksHeader = document.createElement('h4');
            linksHeader.textContent = 'Source Articles';
            linksContainer.appendChild(linksHeader);

            cluster.articles.forEach(article => {
                if (article.url && article.title) {
                    const link = document.createElement('a');
                    link.className = 'article-link';
                    link.href = article.url;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    link.textContent = article.title;
                    linksContainer.appendChild(link);
                }
            });

            card.appendChild(linksContainer);
        }

        catBlock.appendChild(card);
        feedContainer.appendChild(catBlock);
    });
}