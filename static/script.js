document.addEventListener('DOMContentLoaded', () => {
    const artistInput = document.getElementById('artist');
    const titleInput = document.getElementById('title');
    const processBtn = document.getElementById('process-btn');
    const resultsSection = document.getElementById('results-section');
    const lyricsContainer = document.getElementById('lyrics-container');
    const statusPanel = document.getElementById('status-panel');
    const statusText = document.getElementById('status-text');
    
    const songTitleDisplay = document.getElementById('song-title-display');
    const songArtistDisplay = document.getElementById('song-artist-display');
    const langBadge = document.getElementById('lang-badge');

    processBtn.addEventListener('click', async () => {
        const artist = artistInput.value.trim();
        const title = titleInput.value.trim();

        if (!artist || !title) return;

        // Reset UI
        resultsSection.classList.add('hidden');
        statusPanel.classList.remove('hidden');
        statusText.innerText = 'Initializing lyrics processing...';
        lyricsContainer.innerHTML = '';

        try {
            statusText.innerText = `Fetching "${title}" by ${artist}...`;
            
            const response = await fetch('/process_single', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ artist, title })
            });

            if (!response.ok) throw new Error('Pipeline service error');

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            renderResults(data);
            
        } catch (err) {
            statusText.innerText = 'Error: ' + err.message;
            statusText.style.color = '#ef4444';
        }
    });

    function renderResults(song) {
        statusPanel.classList.add('hidden');
        resultsSection.classList.remove('hidden');

        songTitleDisplay.innerText = song.title;
        songArtistDisplay.innerText = song.artist;
        langBadge.innerText = song.language.toUpperCase();

        song.lyrics.forEach((line, index) => {
            const card = document.createElement('div');
            card.className = 'karaoke-card';
            card.style.animationDelay = `${index * 0.05}s`;
            
            if (!line.line || !line.line.trim()) {
                card.classList.add('blank');
            } else {
                // Line
                const lineMain = document.createElement('div');
                lineMain.className = 'line-main';
                lineMain.innerText = line.line;
                card.appendChild(lineMain);

                // Romanization (if different)
                if (line.romanized && line.romanized.toLowerCase() !== line.line.toLowerCase()) {
                    const roman = document.createElement('div');
                    roman.className = 'line-roman';
                    roman.innerHTML = `<span class="card-label">Pronunciation</span>${line.romanized}`;
                    card.appendChild(roman);
                }

                // Translation
                if (line.translation) {
                    const trans = document.createElement('div');
                    trans.className = 'line-trans';
                    trans.innerHTML = `<span class="card-label">Translation</span>${line.translation}`;
                    card.appendChild(trans);
                }
            }
            
            lyricsContainer.appendChild(card);
        });
        
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
});
