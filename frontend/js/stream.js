/**
 * stream.js — Streaming activity module
 * Handles video URL loading, initial handshakes, and real-time chunk/range step
 * generation synchronized with video playback and seeking.
 */

(function () {
  'use strict';

  const API_BASE = '';
  const SAMPLE_URL = 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4';

  let _currentStreamUrl = '';
  let _isPlaying = false;
  let _isHls = false;
  let _chunkIndex = 0;
  let _lastDispatchedTime = -1;
  let _isFetchingChunk = false;

  function getEl(id) { return document.getElementById(id); }

  function setStreamStatus(text) {
    const el = getEl('stream-status-label');
    if (el) el.textContent = text;
  }

  function showVideo(src) {
    const video       = getEl('stream-video');
    const placeholder = getEl('video-placeholder');
    const playBtn     = getEl('btn-stream-play');

    if (placeholder) placeholder.style.display = 'none';
    if (video) {
      video.style.display = 'block';
      video.src = src;
      video.load();
    }
    if (playBtn) playBtn.disabled = false;
  }

  function hideVideo() {
    const video       = getEl('stream-video');
    const placeholder = getEl('video-placeholder');
    const playBtn     = getEl('btn-stream-play');
    if (video) {
      video.pause();
      video.style.display = 'none';
      video.src = '';
    }
    if (placeholder) placeholder.style.display = '';
    if (playBtn) {
      playBtn.disabled = true;
      playBtn.textContent = '[ PLAY ]';
    }
    _chunkIndex = 0;
    _lastDispatchedTime = -1;
  }

  async function requestChunk(timeSec, isSeek = false) {
    if (_isFetchingChunk) return;
    _isFetchingChunk = true;
    _chunkIndex++;

    try {
      const res = await fetch(`${API_BASE}/api/stream/chunk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: _currentStreamUrl,
          chunk_index: _chunkIndex,
          time_sec: timeSec,
          is_seek: isSeek,
          is_hls: _isHls,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.steps && data.steps.length > 0) {
          window.visualizer.appendSteps(data.steps, { live: true });
        }
      }
    } catch (err) {
      console.warn('Chunk step dispatch error:', err);
    } finally {
      _isFetchingChunk = false;
    }
  }

  const streamModule = {
    async loadStream() {
      const urlInput = getEl('stream-url-input');
      const loadBtn  = getEl('btn-stream-load');

      let url = urlInput?.value?.trim() || SAMPLE_URL;
      if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url;
        if (urlInput) urlInput.value = url;
      }

      _currentStreamUrl = url;
      _chunkIndex = 0;
      _lastDispatchedTime = -1;

      if (loadBtn) loadBtn.disabled = true;
      setStreamStatus('[ CONNECTING... ]');
      hideVideo();
      window.visualizer.showLoading('DNS lookup & TCP/TLS handshake in progress…', false);

      try {
        const res = await fetch(`${API_BASE}/api/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
        });

        if (!res.ok) throw new Error(`Server error: ${res.status}`);

        const data = await res.json();
        _isHls = data.is_hls === true;

        if (data.success) {
          showVideo(data.stream_url);
          setStreamStatus('[ READY - PLAY TO STREAM CHUNKS ]');
          window.app.toast('Connection established. Press [PLAY] to start stream.', 'info');
        } else {
          setStreamStatus('[ LOAD FAILED ]');
          window.app.toast(data.error || 'Failed to load stream', 'error');
        }

        // Load ONLY the initial handshake & metadata steps.
        // Chunks will arrive in real time as video plays!
        if (data.steps && data.steps.length > 0) {
          window.visualizer.loadSteps(data.steps, { fast: true });
        }

      } catch (err) {
        setStreamStatus('[ ERROR ]');
        window.visualizer.showError(`Failed to load stream: ${err.message}`);
        window.app.toast(err.message, 'error');
      } finally {
        if (loadBtn) loadBtn.disabled = false;
      }
    },

    togglePlay() {
      const video = getEl('stream-video');
      const btn   = getEl('btn-stream-play');
      if (!video || video.style.display === 'none') return;

      if (_isPlaying) {
        video.pause();
        _isPlaying = false;
        if (btn) btn.textContent = '[ PLAY ]';
        setStreamStatus('[ PAUSED ]');
      } else {
        video.play().catch(() => {});
        _isPlaying = true;
        if (btn) btn.textContent = '[ PAUSE ]';
        setStreamStatus('[ STREAMING LIVE ]');
      }
    },

    changeQuality(quality) {
      setStreamStatus(`[ QUALITY: ${quality} ]`);
      window.app.toast(`Adaptive bitrate: switching to ${quality}`, 'info');

      // Append adaptive bitrate switch step to visualizer
      const qualitySteps = [
        {
          phase: 'HTTP',
          direction: 'client→server',
          label: `HTTP GET — /stream/variants/${quality}.m3u8`,
          detail: `GET /stream/variants/${quality}.m3u8 HTTP/1.1\r\nAccept: application/vnd.apple.mpegurl\r\n\r\n[Player requests adaptive bitrate playlist for ${quality}]`,
          highlight_fields: [
            { key: 'Target Quality', value: quality },
            { key: 'Action', value: 'ABR Switch' },
          ],
          timestamp_ms: Math.round((getEl('stream-video')?.currentTime || 0) * 1000),
        },
        {
          phase: 'HTTP',
          direction: 'server→client',
          label: `200 OK — Quality variant ${quality} active`,
          detail: `HTTP/1.1 200 OK\r\nContent-Type: application/vnd.apple.mpegurl\r\n\r\n[Player switched bitrate profile smoothly without rebuffering]`,
          highlight_fields: [
            { key: 'Status', value: '200 OK' },
            { key: 'Profile', value: quality },
          ],
          timestamp_ms: Math.round((getEl('stream-video')?.currentTime || 0) * 1000 + 40),
        },
      ];
      window.visualizer.appendSteps(qualitySteps, { live: true });
    },
  };

  // Wire up video events for real-time live chunk simulation
  document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('stream-video');
    const btn   = document.getElementById('btn-stream-play');
    const input = document.getElementById('stream-url-input');

    if (video) {
      video.addEventListener('play', () => {
        _isPlaying = true;
        if (btn) btn.textContent = '[ PAUSE ]';
        setStreamStatus('[ STREAMING LIVE ]');

        // Immediately request initial buffer chunk if starting from 0
        if (_lastDispatchedTime < 0) {
          _lastDispatchedTime = 0;
          requestChunk(0, false);
        }
      });

      video.addEventListener('pause', () => {
        _isPlaying = false;
        if (btn) btn.textContent = '[ PLAY ]';
        setStreamStatus('[ PAUSED ]');
      });

      video.addEventListener('ended', () => {
        _isPlaying = false;
        if (btn) btn.textContent = '[ PLAY ]';
        setStreamStatus('[ STREAM ENDED ]');
      });

      // Synchronize live chunks with actual video playback progression
      video.addEventListener('timeupdate', () => {
        if (!_isPlaying) return;
        const currentSec = Math.floor(video.currentTime);

        // Every 2 seconds of playback, trigger the next chunk request
        if (currentSec % 2 === 0 && currentSec !== _lastDispatchedTime) {
          _lastDispatchedTime = currentSec;
          requestChunk(video.currentTime, false);
        }
      });

      // User sought ahead or back in timeline: issue seek range request
      video.addEventListener('seeked', () => {
        _lastDispatchedTime = Math.floor(video.currentTime);
        requestChunk(video.currentTime, true);
        window.app.toast(`Buffer seeked to ${formatTime(video.currentTime)}`, 'info');
      });
    }

    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') streamModule.loadStream();
      });
    }
  });

  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  }

  window.streamModule = streamModule;
})();
