(function() {
    // DOM elements
    const statusEl = document.getElementById('status');
    const nowPlayingEl = document.getElementById('now-playing');
    const trackTitleEl = document.getElementById('track-title');
    const controlsEl = document.getElementById('controls');
    const prevBtn = document.getElementById('prev-btn');
    const playBtn = document.getElementById('play-btn');
    const nextBtn = document.getElementById('next-btn');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressEl = document.getElementById('progress');
    const timeEl = document.getElementById('time');
    const playlistEl = document.getElementById('playlist');
    const trackListEl = document.getElementById('track-list');
    const audio = document.getElementById('audio');

    // State
    let tracks = [];
    let currentIndex = 0;
    let playlistData = null;

    // Get API base URL (same origin)
    const API_BASE = window.location.origin;

    // Get playlist URL from query param
    function getPlaylistUrl() {
        const params = new URLSearchParams(window.location.search);
        const playlistParam = params.get('playlist');
        if (playlistParam) {
            // Could be full URL or just playlist ID
            if (playlistParam.startsWith('http')) {
                return playlistParam;
            }
            return `https://www.youtube.com/playlist?list=${playlistParam}`;
        }
        return null;
    }

    // Format time in M:SS
    function formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // Update status message
    function setStatus(msg, isError = false) {
        statusEl.textContent = msg;
        statusEl.className = isError ? 'status error' : 'status';
    }

    // Show player UI
    function showPlayer() {
        statusEl.style.display = 'none';
        nowPlayingEl.style.display = 'block';
        controlsEl.style.display = 'flex';
        progressContainer.style.display = 'block';
        playlistEl.style.display = 'block';
    }

    // Render track list
    function renderTrackList() {
        trackListEl.innerHTML = '';
        tracks.forEach((track, i) => {
            const li = document.createElement('li');
            li.textContent = `${i + 1}. ${track.title}`;
            li.dataset.index = i;

            if (track.status === 'pending' || track.status === 'processing') {
                li.className = 'pending';
            } else if (track.status === 'error') {
                li.className = 'error';
            } else if (i === currentIndex) {
                li.className = 'active';
            }

            li.addEventListener('click', () => {
                if (track.status === 'complete') {
                    playTrack(i);
                }
            });

            trackListEl.appendChild(li);
        });
    }

    // Play specific track
    function playTrack(index) {
        if (index < 0 || index >= tracks.length) return;

        const track = tracks[index];
        if (track.status !== 'complete' || !track.r2_url) return;

        currentIndex = index;
        audio.src = track.r2_url;
        audio.play();

        trackTitleEl.textContent = track.title;
        playBtn.innerHTML = '&#10074;&#10074;'; // Pause icon

        renderTrackList();
    }

    // Update button states
    function updateButtons() {
        const hasReadyTracks = tracks.some(t => t.status === 'complete');
        playBtn.disabled = !hasReadyTracks;
        prevBtn.disabled = currentIndex <= 0 || !hasReadyTracks;

        const nextReady = tracks.slice(currentIndex + 1).some(t => t.status === 'complete');
        nextBtn.disabled = !nextReady;
    }

    // Submit playlist and get tracks
    async function loadPlaylist(url) {
        setStatus('Loading playlist...');

        try {
            const response = await fetch(`${API_BASE}/api/playlist`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!response.ok) {
                throw new Error('Failed to load playlist');
            }

            playlistData = await response.json();
            tracks = playlistData.tracks;

            if (tracks.length === 0) {
                setStatus('No tracks found', true);
                return;
            }

            // Check if any tracks are ready
            const hasReady = tracks.some(t => t.status === 'complete');

            if (hasReady) {
                showPlayer();
                renderTrackList();
                updateButtons();
            } else if (playlistData.status === 'pending' || playlistData.status === 'processing') {
                setStatus('Processing tracks...');
                pollForUpdates();
            } else if (playlistData.status === 'error') {
                setStatus('Failed to process playlist', true);
            }

        } catch (err) {
            setStatus('Error: ' + err.message, true);
        }
    }

    // Poll for playlist updates
    async function pollForUpdates() {
        if (!playlistData) return;

        try {
            const response = await fetch(`${API_BASE}/api/playlist/${playlistData.id}`);
            if (!response.ok) return;

            playlistData = await response.json();
            tracks = playlistData.tracks;

            const hasReady = tracks.some(t => t.status === 'complete');
            const allDone = tracks.every(t => t.status === 'complete' || t.status === 'error');

            if (hasReady) {
                showPlayer();
                renderTrackList();
                updateButtons();
            }

            if (!allDone) {
                // Keep polling
                setTimeout(pollForUpdates, 3000);
            } else {
                renderTrackList();
            }

        } catch (err) {
            // Retry on error
            setTimeout(pollForUpdates, 5000);
        }
    }

    // Event: Play/Pause
    playBtn.addEventListener('click', () => {
        if (audio.paused) {
            if (audio.src) {
                audio.play();
            } else {
                // Find first ready track
                const firstReady = tracks.findIndex(t => t.status === 'complete');
                if (firstReady >= 0) {
                    playTrack(firstReady);
                }
            }
        } else {
            audio.pause();
        }
    });

    // Event: Previous
    prevBtn.addEventListener('click', () => {
        for (let i = currentIndex - 1; i >= 0; i--) {
            if (tracks[i].status === 'complete') {
                playTrack(i);
                break;
            }
        }
    });

    // Event: Next
    nextBtn.addEventListener('click', () => {
        for (let i = currentIndex + 1; i < tracks.length; i++) {
            if (tracks[i].status === 'complete') {
                playTrack(i);
                break;
            }
        }
    });

    // Event: Audio play/pause state
    audio.addEventListener('play', () => {
        playBtn.innerHTML = '&#10074;&#10074;';
    });

    audio.addEventListener('pause', () => {
        playBtn.innerHTML = '&#9654;';
    });

    // Event: Audio ended - play next
    audio.addEventListener('ended', () => {
        for (let i = currentIndex + 1; i < tracks.length; i++) {
            if (tracks[i].status === 'complete') {
                playTrack(i);
                return;
            }
        }
        // No more tracks, reset
        playBtn.innerHTML = '&#9654;';
    });

    // Event: Progress update
    audio.addEventListener('timeupdate', () => {
        if (audio.duration) {
            const pct = (audio.currentTime / audio.duration) * 100;
            progressEl.style.width = pct + '%';
            timeEl.textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
        }
    });

    // Event: Click on progress bar to seek
    progressBar.addEventListener('click', (e) => {
        if (!audio.duration) return;
        const rect = progressBar.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        audio.currentTime = pct * audio.duration;
    });

    // Initialize
    const playlistUrl = getPlaylistUrl();
    if (playlistUrl) {
        loadPlaylist(playlistUrl);
    } else {
        setStatus('No playlist specified', true);
    }
})();
