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

        if (!artist || !title) {
            alert('Please enter both artist and title.');
            return;
        }

        // Reset UI
        resultsSection.classList.add('hidden');
        statusPanel.classList.remove('hidden');
        statusText.innerText = 'Initializing lyrics processing...';
        lyricsContainer.innerHTML = '';

        try {
            statusText.innerText = `Fetching "${title}" by ${artist}...`;
            
            const response = await fetch('/process_single', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ artist, title })
            });

            if (!response.ok) {
                throw new Error('Pipeline error: ' + response.statusText);
            }

            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            // Render Results
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

        song.lyrics.forEach(line => {
            const lineEl = document.createElement('div');
            lineEl.className = 'lyric-line';
            
            if (!line.line || !line.line.trim()) {
                lineEl.classList.add('blank');
            } else {
                const original = document.createElement('div');
                original.className = 'original-text';
                original.innerText = line.line;
                lineEl.appendChild(original);

                if (line.romanized && line.romanized !== line.line) {
                    const roman = document.createElement('div');
                    roman.className = 'romanized-text';
                    roman.innerText = line.romanized;
                    lineEl.appendChild(roman);
                }

                if (line.translation) {
                    const trans = document.createElement('div');
                    trans.className = 'translated-text';
                    trans.innerText = line.translation;
                    lineEl.appendChild(trans);
                }
            }
            
            lyricsContainer.appendChild(lineEl);
        });
        
        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
});
