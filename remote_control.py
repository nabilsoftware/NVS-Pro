"""
Nabil Video Studio Pro - Remote Control Server
Complete rebuild with separate Local/Internet server modes
"""

import os
import sys
import json
import socket
import threading
import subprocess
from pathlib import Path

# Check and install requirements
def check_requirements():
    """Check if required packages are installed"""
    missing = []
    try:
        import flask
    except ImportError:
        missing.append('flask')
    return missing

def install_requirements():
    """Install required packages"""
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'flask'], check=True)

# Import flask after check
try:
    from flask import Flask, render_template_string, jsonify, request, send_file
except ImportError:
    Flask = None
    render_template_string = None
    jsonify = None
    request = None
    send_file = None

# Get local IP address
def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ============================================================================
# HTML TEMPLATES - Modern Dark Theme
# ============================================================================

BASE_CSS = """
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --border-color: #30363d;
    --text-primary: #c9d1d9;
    --text-secondary: #8b949e;
    --accent-green: #238636;
    --accent-green-hover: #2ea043;
    --accent-blue: #1f6feb;
    --accent-blue-hover: #388bfd;
    --success: #3fb950;
    --error: #f85149;
    --warning: #d29922;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    -webkit-tap-highlight-color: transparent;
}

.container {
    max-width: 480px;
    margin: 0 auto;
    padding: 16px;
    min-height: 100vh;
}

/* Header */
.header {
    text-align: center;
    padding: 24px 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 24px;
}

.header h1 {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 4px;
    background: linear-gradient(135deg, #58a6ff, #3fb950);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.header p {
    color: var(--text-secondary);
    font-size: 0.875rem;
}

/* Status Badge */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
    margin-top: 12px;
}

.status-badge.connected {
    background: rgba(63, 185, 80, 0.15);
    color: var(--success);
    border: 1px solid rgba(63, 185, 80, 0.3);
}

.status-badge .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Cards */
.card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
}

.card-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}

.card-header .icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
}

.card-header .icon.green { background: rgba(35, 134, 54, 0.2); }
.card-header .icon.blue { background: rgba(31, 111, 235, 0.2); }
.card-header .icon.orange { background: rgba(210, 153, 34, 0.2); }

.card-header h2 {
    font-size: 1rem;
    font-weight: 600;
}

.card-header p {
    color: var(--text-secondary);
    font-size: 0.75rem;
}

/* Step Indicator */
.steps {
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-bottom: 24px;
}

.step {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.875rem;
    font-weight: 600;
    background: var(--bg-tertiary);
    border: 2px solid var(--border-color);
    color: var(--text-secondary);
    transition: all 0.3s ease;
}

.step.active {
    background: var(--accent-green);
    border-color: var(--accent-green);
    color: white;
}

.step.done {
    background: var(--success);
    border-color: var(--success);
    color: white;
}

.step-line {
    width: 40px;
    height: 2px;
    background: var(--border-color);
    align-self: center;
}

/* Category Chips */
.category-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.chip {
    padding: 10px 16px;
    border-radius: 8px;
    background: var(--bg-tertiary);
    border: 2px solid var(--border-color);
    color: var(--text-primary);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    -webkit-user-select: none;
    user-select: none;
}

.chip:active {
    transform: scale(0.95);
}

.chip.selected {
    background: rgba(35, 134, 54, 0.2);
    border-color: var(--accent-green);
    color: var(--success);
}

/* Channel List */
.channel-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.channel-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 16px;
    background: var(--bg-tertiary);
    border: 2px solid var(--border-color);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    -webkit-user-select: none;
    user-select: none;
}

.channel-item:active {
    transform: scale(0.98);
}

.channel-item.selected {
    background: rgba(35, 134, 54, 0.15);
    border-color: var(--accent-green);
}

.channel-item .checkbox {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    border: 2px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    flex-shrink: 0;
}

.channel-item.selected .checkbox {
    background: var(--accent-green);
    border-color: var(--accent-green);
}

.channel-item .checkbox::after {
    content: '';
    width: 6px;
    height: 10px;
    border: 2px solid white;
    border-top: none;
    border-left: none;
    transform: rotate(45deg) translateY(-1px);
    opacity: 0;
    transition: opacity 0.2s ease;
}

.channel-item.selected .checkbox::after {
    opacity: 1;
}

.channel-item .info {
    flex: 1;
}

.channel-item .name {
    font-weight: 600;
    font-size: 0.9375rem;
}

.channel-item .category {
    color: var(--text-secondary);
    font-size: 0.75rem;
    margin-top: 2px;
}

/* Folder List */
.folder-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.folder-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--bg-tertiary);
    border: 2px solid var(--border-color);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.folder-item:active {
    transform: scale(0.98);
}

.folder-item.selected {
    background: rgba(31, 111, 235, 0.15);
    border-color: var(--accent-blue);
}

.folder-item .checkbox {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    border: 2px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    flex-shrink: 0;
}

.folder-item.selected .checkbox {
    background: var(--accent-blue);
    border-color: var(--accent-blue);
}

.folder-item.selected .checkbox::after {
    content: '';
    width: 6px;
    height: 10px;
    border: 2px solid white;
    border-top: none;
    border-left: none;
    transform: rotate(45deg) translateY(-1px);
}

.folder-item .folder-icon {
    font-size: 1.25rem;
}

.folder-item .info {
    flex: 1;
}

.folder-item .name {
    font-weight: 500;
    font-size: 0.875rem;
}

.folder-item .count {
    color: var(--text-secondary);
    font-size: 0.75rem;
}

/* Options */
.options-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.option-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid var(--border-color);
}

.option-item:last-child {
    border-bottom: none;
}

.option-item .label {
    font-size: 0.9375rem;
}

/* Toggle Switch */
.toggle {
    width: 48px;
    height: 28px;
    background: var(--bg-tertiary);
    border-radius: 14px;
    position: relative;
    cursor: pointer;
    transition: background 0.3s ease;
    border: 2px solid var(--border-color);
}

.toggle.active {
    background: var(--accent-green);
    border-color: var(--accent-green);
}

.toggle::after {
    content: '';
    position: absolute;
    width: 20px;
    height: 20px;
    background: white;
    border-radius: 50%;
    top: 2px;
    left: 2px;
    transition: transform 0.3s ease;
}

.toggle.active::after {
    transform: translateX(20px);
}

/* Summary */
.summary {
    background: var(--bg-tertiary);
    border-radius: 10px;
    padding: 16px;
    margin-top: 16px;
}

.summary-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    font-size: 0.875rem;
}

.summary-row .label {
    color: var(--text-secondary);
}

.summary-row .value {
    font-weight: 600;
}

/* Buttons */
.btn {
    width: 100%;
    padding: 16px;
    border: none;
    border-radius: 12px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.btn:active {
    transform: scale(0.98);
}

.btn-primary {
    background: var(--accent-green);
    color: white;
}

.btn-primary:hover {
    background: var(--accent-green-hover);
}

.btn-primary:disabled {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    cursor: not-allowed;
}

.btn-secondary {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
}

.btn-danger {
    background: rgba(248, 81, 73, 0.15);
    color: var(--error);
    border: 1px solid rgba(248, 81, 73, 0.3);
}

/* Navigation */
.nav-buttons {
    display: flex;
    gap: 12px;
    margin-top: 24px;
}

.nav-buttons .btn {
    flex: 1;
}

/* Progress */
.progress-container {
    margin: 24px 0;
}

.progress-bar {
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-green), var(--accent-blue));
    border-radius: 4px;
    transition: width 0.5s ease;
}

.progress-text {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
    font-size: 0.875rem;
    color: var(--text-secondary);
}

/* Log */
.log-container {
    background: var(--bg-tertiary);
    border-radius: 10px;
    padding: 12px;
    max-height: 200px;
    overflow-y: auto;
    font-family: 'Courier New', monospace;
    font-size: 0.75rem;
}

.log-entry {
    padding: 4px 0;
    border-bottom: 1px solid var(--border-color);
}

.log-entry:last-child {
    border-bottom: none;
}

.log-time {
    color: var(--text-secondary);
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 32px;
    color: var(--text-secondary);
}

.empty-state .icon {
    font-size: 3rem;
    margin-bottom: 16px;
    opacity: 0.5;
}

/* Loading */
.loading {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
}

.spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: var(--accent-green);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Toast */
.toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    padding: 12px 24px;
    border-radius: 10px;
    font-size: 0.875rem;
    opacity: 0;
    transition: all 0.3s ease;
    z-index: 1000;
}

.toast.show {
    transform: translateX(-50%) translateY(0);
    opacity: 1;
}

.toast.success {
    border-color: var(--success);
    color: var(--success);
}

.toast.error {
    border-color: var(--error);
    color: var(--error);
}
"""

HOME_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Nabil Video Studio - Remote</title>
    <style>{{ css }}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Nabil Video Studio</h1>
            <p>Remote Control</p>
            <div class="status-badge connected">
                <span class="dot"></span>
                Connected to PC
            </div>
        </div>

        <div class="card" onclick="location.href='/run'">
            <div class="card-header">
                <div class="icon green">&#9654;</div>
                <div>
                    <h2>Run Pipeline</h2>
                    <p>Start video processing</p>
                </div>
            </div>
        </div>

        <div class="card" onclick="location.href='/status'">
            <div class="card-header">
                <div class="icon blue">&#128202;</div>
                <div>
                    <h2>Pipeline Status</h2>
                    <p>View current progress</p>
                </div>
            </div>
        </div>

        <div class="card" onclick="location.href='/step2crop'">
            <div class="card-header">
                <div class="icon" style="color: #9C27B0;">&#9986;</div>
                <div>
                    <h2>Crop Interview</h2>
                    <p>Manual crop for Step 2</p>
                </div>
            </div>
        </div>

        <div class="card" onclick="triggerTestCrop()" id="testCropCard" style="border: 2px dashed #ff9800;">
            <div class="card-header">
                <div class="icon" style="color: #ff9800;">&#128276;</div>
                <div>
                    <h2>TEST: Trigger Crop Alert</h2>
                    <p>Test the notification system</p>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="icon orange">&#9881;</div>
                <div>
                    <h2>Quick Info</h2>
                    <p>System overview</p>
                </div>
            </div>
            <div class="summary">
                <div class="summary-row">
                    <span class="label">Profiles</span>
                    <span class="value">{{ profile_count }}</span>
                </div>
                <div class="summary-row">
                    <span class="label">Categories</span>
                    <span class="value">{{ category_count }}</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Crop Alert Popup (hidden by default) -->
    <div id="cropAlert" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.9); z-index:9999; display:flex; align-items:center; justify-content:center;">
        <div style="background:linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border:3px solid #4CAF50; border-radius:20px; padding:40px; text-align:center; max-width:90%; animation: pulse 1s infinite;">
            <div style="font-size:80px; margin-bottom:20px;">&#9986;</div>
            <h2 style="color:#4CAF50; font-size:28px; margin-bottom:10px;">CROP READY!</h2>
            <p style="color:#c9d1d9; font-size:18px; margin-bottom:30px;">Tap to crop <span id="cropVideoCount">0</span> videos</p>
            <button onclick="goToCrop()" style="background:linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color:white; border:none; padding:20px 60px; font-size:22px; font-weight:bold; border-radius:15px; cursor:pointer; box-shadow: 0 8px 25px rgba(76,175,80,0.4);">
                START CROPPING
            </button>
            <p style="color:#888; font-size:14px; margin-top:20px;">Pipeline is waiting for your input...</p>
        </div>
    </div>

    <style>
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.02); }
        }
        #cropAlert { display: none !important; }
        #cropAlert.show { display: flex !important; }
    </style>

    <script>
        let cropAlertShown = false;
        let audioContext = null;

        // Create beep sound
        function playBeep() {
            try {
                if (!audioContext) {
                    audioContext = new (window.AudioContext || window.webkitAudioContext)();
                }
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();
                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);
                oscillator.frequency.value = 800;
                oscillator.type = 'sine';
                gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + 0.5);

                // Play 3 beeps
                setTimeout(() => {
                    const osc2 = audioContext.createOscillator();
                    const gain2 = audioContext.createGain();
                    osc2.connect(gain2);
                    gain2.connect(audioContext.destination);
                    osc2.frequency.value = 1000;
                    osc2.type = 'sine';
                    gain2.gain.setValueAtTime(0.3, audioContext.currentTime);
                    gain2.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                    osc2.start(audioContext.currentTime);
                    osc2.stop(audioContext.currentTime + 0.5);
                }, 200);

                setTimeout(() => {
                    const osc3 = audioContext.createOscillator();
                    const gain3 = audioContext.createGain();
                    osc3.connect(gain3);
                    gain3.connect(audioContext.destination);
                    osc3.frequency.value = 1200;
                    osc3.type = 'sine';
                    gain3.gain.setValueAtTime(0.3, audioContext.currentTime);
                    gain3.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                    osc3.start(audioContext.currentTime);
                    osc3.stop(audioContext.currentTime + 0.5);
                }, 400);
            } catch(e) {
                console.log('Audio not supported');
            }
        }

        // Vibrate if supported
        function vibrate() {
            if (navigator.vibrate) {
                navigator.vibrate([200, 100, 200, 100, 200]);
            }
        }

        // Check for crop status
        async function checkCropStatus() {
            try {
                const response = await fetch('/api/step2crop/status');
                const data = await response.json();

                if (data.pending && !cropAlertShown) {
                    cropAlertShown = true;
                    document.getElementById('cropVideoCount').textContent = data.total || '?';
                    document.getElementById('cropAlert').classList.add('show');
                    playBeep();
                    vibrate();
                } else if (!data.pending) {
                    cropAlertShown = false;
                    document.getElementById('cropAlert').classList.remove('show');
                }
            } catch(e) {
                console.log('Status check failed');
            }
        }

        function goToCrop() {
            window.location.href = '/step2crop';
        }

        async function triggerTestCrop() {
            try {
                const response = await fetch('/api/test/crop', { method: 'POST' });
                const data = await response.json();
                console.log('Test crop triggered:', data);
                // Alert should appear within 2 seconds due to polling
            } catch(e) {
                alert('Failed to trigger test: ' + e.message);
            }
        }

        // Initialize audio context on first touch (required for mobile)
        document.addEventListener('touchstart', function() {
            if (!audioContext) {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
        }, { once: true });

        // Poll every 2 seconds
        setInterval(checkCropStatus, 2000);
        checkCropStatus(); // Check immediately
    </script>
</body>
</html>
"""

RUN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Run Pipeline - Remote</title>
    <style>{{ css }}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Run Pipeline</h1>
            <p>Configure and start processing</p>
        </div>

        <div class="steps">
            <div class="step active" id="step1">1</div>
            <div class="step-line"></div>
            <div class="step" id="step2">2</div>
            <div class="step-line"></div>
            <div class="step" id="step3">3</div>
            <div class="step-line"></div>
            <div class="step" id="step4">4</div>
        </div>

        <!-- Step 1: Category -->
        <div id="section1" class="card">
            <div class="card-header">
                <div class="icon green">&#128193;</div>
                <div>
                    <h2>Select Category</h2>
                    <p>Choose content category</p>
                </div>
            </div>
            <div class="category-chips" id="categoryChips">
                {% for cat in categories %}
                <div class="chip" onclick="selectCategory('{{ cat }}')" data-cat="{{ cat }}">{{ cat }}</div>
                {% endfor %}
            </div>
        </div>

        <!-- Step 2: Channels -->
        <div id="section2" class="card" style="display:none;">
            <div class="card-header">
                <div class="icon blue">&#128250;</div>
                <div>
                    <h2>Select Channels</h2>
                    <p>Choose one or more channels</p>
                </div>
            </div>
            <div class="channel-list" id="channelList">
                <!-- Populated by JS -->
            </div>
        </div>

        <!-- Step 3: Folders -->
        <div id="section3" class="card" style="display:none;">
            <div class="card-header">
                <div class="icon orange">&#128194;</div>
                <div>
                    <h2>Select Input Folders</h2>
                    <p>Choose folders to process</p>
                </div>
            </div>
            <div class="folder-list" id="folderList">
                <!-- Populated by JS -->
            </div>
            <div style="margin-top: 16px;">
                <button class="btn btn-secondary" onclick="openCropTool()" id="cropBtn" style="display:none;">
                    &#9986; Set Crop for Videos
                </button>
            </div>
        </div>

        <!-- Step 4: Options -->
        <div id="section4" class="card" style="display:none;">
            <div class="card-header">
                <div class="icon green">&#9881;</div>
                <div>
                    <h2>Processing Options</h2>
                    <p>Configure pipeline settings</p>
                </div>
            </div>
            <div class="options-list">
                <div class="option-item">
                    <span class="label">Parallel Processing</span>
                    <div class="toggle active" id="optParallel" onclick="toggleOption(this)"></div>
                </div>
                <div class="option-item">
                    <span class="label">Background Music</span>
                    <div class="toggle active" id="optMusic" onclick="toggleOption(this)"></div>
                </div>
                <div class="option-item">
                    <span class="label">Add Logo</span>
                    <div class="toggle" id="optLogo" onclick="toggleOption(this)"></div>
                </div>
            </div>
        </div>

        <!-- Summary -->
        <div id="summarySection" class="card" style="display:none;">
            <div class="card-header">
                <div class="icon blue">&#128203;</div>
                <div>
                    <h2>Summary</h2>
                    <p>Review before starting</p>
                </div>
            </div>
            <div class="summary">
                <div class="summary-row">
                    <span class="label">Category</span>
                    <span class="value" id="sumCategory">-</span>
                </div>
                <div class="summary-row">
                    <span class="label">Channels</span>
                    <span class="value" id="sumChannels">0</span>
                </div>
                <div class="summary-row">
                    <span class="label">Folders</span>
                    <span class="value" id="sumFolders">0</span>
                </div>
            </div>
        </div>

        <!-- Navigation -->
        <div class="nav-buttons">
            <button class="btn btn-secondary" onclick="goBack()">Back</button>
            <button class="btn btn-primary" id="nextBtn" onclick="goNext()">Next</button>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        // Data
        let profiles = {{ profiles | tojson }};
        let categories = {{ categories | tojson }};
        let categoriesData = {{ categories_data | tojson }};

        // State
        let currentStep = 1;
        let selectedCategory = '';
        let selectedChannels = [];
        let selectedFolders = [];
        let options = { parallel: true, music: true, logo: false };

        // Category selection
        function selectCategory(cat) {
            selectedCategory = cat;
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
            document.querySelector(`[data-cat="${cat}"]`).classList.add('selected');

            // Filter channels by category
            renderChannels();
            loadFolders();
        }

        // Render channels for selected category
        function renderChannels() {
            const list = document.getElementById('channelList');
            list.innerHTML = '';

            for (let name in profiles) {
                let p = profiles[name];
                if (!selectedCategory || p.category === selectedCategory) {
                    let div = document.createElement('div');
                    div.className = 'channel-item';
                    div.setAttribute('data-channel', name);
                    div.onclick = function() { toggleChannel(name, this); };
                    div.innerHTML = `
                        <div class="checkbox"></div>
                        <div class="info">
                            <div class="name">${name}</div>
                            <div class="category">${p.category || 'Default'}</div>
                        </div>
                    `;
                    list.appendChild(div);
                }
            }
        }

        // Toggle channel selection
        function toggleChannel(name, el) {
            if (selectedChannels.includes(name)) {
                selectedChannels = selectedChannels.filter(c => c !== name);
                el.classList.remove('selected');
            } else {
                selectedChannels.push(name);
                el.classList.add('selected');
            }
            updateSummary();
        }

        // Load folders for category
        function loadFolders() {
            if (!selectedCategory || !categoriesData[selectedCategory]) return;

            let inputPath = categoriesData[selectedCategory].input_path;
            if (!inputPath) return;

            fetch('/api/folders/' + selectedCategory)
                .then(r => r.json())
                .then(data => {
                    renderFolders(data.folders || []);
                });
        }

        // Render folders
        function renderFolders(folders) {
            const list = document.getElementById('folderList');
            list.innerHTML = '';

            if (folders.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="icon">&#128194;</div><p>No folders found</p></div>';
                return;
            }

            folders.forEach(f => {
                let div = document.createElement('div');
                div.className = 'folder-item';
                div.setAttribute('data-folder', f.path);
                div.onclick = function() { toggleFolder(f.path, this); };
                div.innerHTML = `
                    <div class="checkbox"></div>
                    <div class="folder-icon">&#128194;</div>
                    <div class="info">
                        <div class="name">${f.name}</div>
                        <div class="count">${f.video_count} videos</div>
                    </div>
                `;
                list.appendChild(div);
            });
        }

        // Toggle folder selection
        function toggleFolder(path, el) {
            if (selectedFolders.includes(path)) {
                selectedFolders = selectedFolders.filter(f => f !== path);
                el.classList.remove('selected');
            } else {
                selectedFolders.push(path);
                el.classList.add('selected');
            }
            updateSummary();

            // Show/hide crop button
            document.getElementById('cropBtn').style.display = selectedFolders.length > 0 ? 'block' : 'none';
        }

        // Open crop tool
        function openCropTool() {
            if (selectedFolders.length === 0) {
                showToast('Please select a folder first', 'error');
                return;
            }
            // Open crop page with first selected folder
            window.location.href = '/crop?folder=' + encodeURIComponent(selectedFolders[0]);
        }

        // Toggle option
        function toggleOption(el) {
            el.classList.toggle('active');
            let id = el.id;
            if (id === 'optParallel') options.parallel = el.classList.contains('active');
            if (id === 'optMusic') options.music = el.classList.contains('active');
            if (id === 'optLogo') options.logo = el.classList.contains('active');
        }

        // Update summary
        function updateSummary() {
            document.getElementById('sumCategory').textContent = selectedCategory || '-';
            document.getElementById('sumChannels').textContent = selectedChannels.length;
            document.getElementById('sumFolders').textContent = selectedFolders.length;
        }

        // Navigation
        function goNext() {
            if (currentStep === 1) {
                if (!selectedCategory) {
                    showToast('Please select a category', 'error');
                    return;
                }
                currentStep = 2;
                showStep(2);
            } else if (currentStep === 2) {
                if (selectedChannels.length === 0) {
                    showToast('Please select at least one channel', 'error');
                    return;
                }
                currentStep = 3;
                showStep(3);
            } else if (currentStep === 3) {
                if (selectedFolders.length === 0) {
                    showToast('Please select at least one folder', 'error');
                    return;
                }
                currentStep = 4;
                showStep(4);
            } else if (currentStep === 4) {
                runPipeline();
            }
        }

        function goBack() {
            if (currentStep === 1) {
                location.href = '/';
            } else {
                currentStep--;
                showStep(currentStep);
            }
        }

        function showStep(step) {
            // Update step indicators
            for (let i = 1; i <= 4; i++) {
                let el = document.getElementById('step' + i);
                el.classList.remove('active', 'done');
                if (i < step) el.classList.add('done');
                if (i === step) el.classList.add('active');
            }

            // Show/hide sections
            document.getElementById('section1').style.display = step === 1 ? 'block' : 'none';
            document.getElementById('section2').style.display = step === 2 ? 'block' : 'none';
            document.getElementById('section3').style.display = step === 3 ? 'block' : 'none';
            document.getElementById('section4').style.display = step === 4 ? 'block' : 'none';
            document.getElementById('summarySection').style.display = step === 4 ? 'block' : 'none';

            // Update button
            document.getElementById('nextBtn').textContent = step === 4 ? 'Start Pipeline' : 'Next';

            updateSummary();
        }

        // Run pipeline
        function runPipeline() {
            document.getElementById('nextBtn').disabled = true;
            document.getElementById('nextBtn').textContent = 'Starting...';

            fetch('/api/pipeline/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    category: selectedCategory,
                    channels: selectedChannels,
                    folders: selectedFolders,
                    options: options
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'started' || data.status === 'queued') {
                    showToast('Pipeline started!', 'success');
                    setTimeout(() => location.href = '/status', 1000);
                } else {
                    showToast(data.message || 'Failed to start', 'error');
                    document.getElementById('nextBtn').disabled = false;
                    document.getElementById('nextBtn').textContent = 'Start Pipeline';
                }
            })
            .catch(err => {
                showToast('Connection error', 'error');
                document.getElementById('nextBtn').disabled = false;
                document.getElementById('nextBtn').textContent = 'Start Pipeline';
            });
        }

        // Toast notification
        function showToast(message, type) {
            let toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast show ' + type;
            setTimeout(() => toast.className = 'toast', 3000);
        }

        // Initial render
        renderChannels();
    </script>
</body>
</html>
"""

CROP_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Crop Tool - Remote</title>
    <style>
    {{ css }}

    /* Crop Tool Specific Styles */
    .crop-container {
        position: relative;
        width: 100%;
        max-width: 100%;
        margin: 16px 0;
        background: var(--bg-tertiary);
        border-radius: 12px;
        overflow: hidden;
        touch-action: none;
    }

    .crop-canvas-wrapper {
        position: relative;
        width: 100%;
        overflow: hidden;
    }

    #cropCanvas {
        display: block;
        width: 100%;
        height: auto;
        touch-action: none;
    }

    .crop-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
    }

    .crop-box {
        position: absolute;
        border: 3px solid var(--accent-green);
        background: rgba(35, 134, 54, 0.1);
        box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5);
        pointer-events: auto;
        cursor: move;
    }

    .crop-handle {
        position: absolute;
        width: 24px;
        height: 24px;
        background: var(--accent-green);
        border-radius: 50%;
        transform: translate(-50%, -50%);
    }

    .crop-handle.tl { top: 0; left: 0; cursor: nw-resize; }
    .crop-handle.tr { top: 0; right: 0; transform: translate(50%, -50%); cursor: ne-resize; }
    .crop-handle.bl { bottom: 0; left: 0; transform: translate(-50%, 50%); cursor: sw-resize; }
    .crop-handle.br { bottom: 0; right: 0; transform: translate(50%, 50%); cursor: se-resize; }

    .crop-info {
        display: flex;
        justify-content: space-between;
        padding: 12px 16px;
        background: var(--bg-secondary);
        border-top: 1px solid var(--border-color);
        font-size: 0.875rem;
    }

    .crop-info .label {
        color: var(--text-secondary);
    }

    .crop-info .value {
        font-weight: 600;
        color: var(--success);
    }

    .video-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-height: 200px;
        overflow-y: auto;
    }

    .video-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        background: var(--bg-tertiary);
        border: 2px solid var(--border-color);
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .video-item:active {
        transform: scale(0.98);
    }

    .video-item.selected {
        border-color: var(--accent-blue);
        background: rgba(31, 111, 235, 0.1);
    }

    .video-item.cropped {
        border-color: var(--success);
    }

    .video-item .status-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--border-color);
        flex-shrink: 0;
    }

    .video-item.cropped .status-dot {
        background: var(--success);
    }

    .video-item .name {
        flex: 1;
        font-size: 0.875rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .preset-buttons {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 12px 0;
    }

    .preset-btn {
        padding: 8px 16px;
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        color: var(--text-primary);
        font-size: 0.75rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .preset-btn:active {
        transform: scale(0.95);
    }

    .preset-btn.active {
        background: var(--accent-green);
        border-color: var(--accent-green);
    }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Crop Tool</h1>
            <p>Set crop area for videos</p>
        </div>

        <!-- Video Selection -->
        <div class="card">
            <div class="card-header">
                <div class="icon blue">&#127909;</div>
                <div>
                    <h2>Select Video</h2>
                    <p>Choose video to crop</p>
                </div>
            </div>
            <div class="video-list" id="videoList">
                <div class="loading"><div class="spinner"></div></div>
            </div>
        </div>

        <!-- Crop Area -->
        <div class="card">
            <div class="card-header">
                <div class="icon green">&#9986;</div>
                <div>
                    <h2>Crop Area</h2>
                    <p>Drag corners to adjust</p>
                </div>
            </div>

            <!-- Preset Ratios -->
            <div class="preset-buttons">
                <button class="preset-btn active" onclick="setPreset('9:16')">9:16 (Shorts)</button>
                <button class="preset-btn" onclick="setPreset('1:1')">1:1 (Square)</button>
                <button class="preset-btn" onclick="setPreset('4:5')">4:5 (IG)</button>
                <button class="preset-btn" onclick="setPreset('free')">Free</button>
            </div>

            <div class="crop-container" id="cropContainer">
                <div class="crop-canvas-wrapper">
                    <canvas id="cropCanvas"></canvas>
                    <div class="crop-overlay" id="cropOverlay">
                        <div class="crop-box" id="cropBox">
                            <div class="crop-handle tl" data-handle="tl"></div>
                            <div class="crop-handle tr" data-handle="tr"></div>
                            <div class="crop-handle bl" data-handle="bl"></div>
                            <div class="crop-handle br" data-handle="br"></div>
                        </div>
                    </div>
                </div>
                <div class="crop-info">
                    <span><span class="label">Size: </span><span class="value" id="cropSize">0 x 0</span></span>
                    <span><span class="label">Ratio: </span><span class="value" id="cropRatio">9:16</span></span>
                </div>
            </div>
        </div>

        <!-- Navigation -->
        <div class="nav-buttons">
            <button class="btn btn-secondary" onclick="goBack()">Cancel</button>
            <button class="btn btn-primary" onclick="applyCrop()">Apply Crop</button>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        // State
        let videos = [];
        let currentVideo = null;
        let cropData = {};
        let aspectRatio = 9/16;  // Default 9:16 for shorts
        let freeMode = false;

        // Canvas and crop box elements
        const canvas = document.getElementById('cropCanvas');
        const ctx = canvas.getContext('2d');
        const cropBox = document.getElementById('cropBox');
        const cropOverlay = document.getElementById('cropOverlay');

        // Crop box state
        let cropRect = { x: 0, y: 0, width: 0, height: 0 };
        let isDragging = false;
        let dragHandle = null;
        let dragStart = { x: 0, y: 0 };
        let boxStart = { x: 0, y: 0, width: 0, height: 0 };

        // Image dimensions
        let imgWidth = 0;
        let imgHeight = 0;
        let displayWidth = 0;
        let displayHeight = 0;

        // Get folder path from URL
        const urlParams = new URLSearchParams(window.location.search);
        const folderPath = urlParams.get('folder') || '';

        // Load videos
        function loadVideos() {
            if (!folderPath) {
                document.getElementById('videoList').innerHTML = '<div class="empty-state"><p>No folder selected</p></div>';
                return;
            }

            fetch('/api/videos?folder=' + encodeURIComponent(folderPath))
                .then(r => r.json())
                .then(data => {
                    videos = data.videos || [];
                    renderVideoList();
                    if (videos.length > 0) {
                        selectVideo(videos[0]);
                    }
                })
                .catch(err => {
                    document.getElementById('videoList').innerHTML = '<div class="empty-state"><p>Error loading videos</p></div>';
                });
        }

        // Render video list
        function renderVideoList() {
            const list = document.getElementById('videoList');
            if (videos.length === 0) {
                list.innerHTML = '<div class="empty-state"><p>No videos found</p></div>';
                return;
            }

            list.innerHTML = videos.map((v, i) => `
                <div class="video-item ${cropData[v.path] ? 'cropped' : ''}"
                     data-index="${i}" onclick="selectVideo(videos[${i}])">
                    <div class="status-dot"></div>
                    <div class="name">${v.name}</div>
                </div>
            `).join('');
        }

        // Select video
        function selectVideo(video) {
            currentVideo = video;

            // Update UI
            document.querySelectorAll('.video-item').forEach((el, i) => {
                el.classList.toggle('selected', videos[i] === video);
            });

            // Load thumbnail
            loadThumbnail(video.path);
        }

        // Load thumbnail
        function loadThumbnail(videoPath) {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = function() {
                imgWidth = img.width;
                imgHeight = img.height;

                // Set canvas size
                const container = document.getElementById('cropContainer');
                displayWidth = container.clientWidth;
                displayHeight = (imgHeight / imgWidth) * displayWidth;

                canvas.width = displayWidth;
                canvas.height = displayHeight;

                ctx.drawImage(img, 0, 0, displayWidth, displayHeight);

                // Initialize crop box
                initCropBox();
            };
            img.onerror = function() {
                // Draw placeholder
                displayWidth = 320;
                displayHeight = 180;
                canvas.width = displayWidth;
                canvas.height = displayHeight;
                ctx.fillStyle = '#21262d';
                ctx.fillRect(0, 0, displayWidth, displayHeight);
                ctx.fillStyle = '#8b949e';
                ctx.font = '14px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('Preview not available', displayWidth/2, displayHeight/2);
                initCropBox();
            };
            img.src = '/api/thumbnail?video=' + encodeURIComponent(videoPath);
        }

        // Initialize crop box
        function initCropBox() {
            // Check if we have saved crop for this video
            if (currentVideo && cropData[currentVideo.path]) {
                cropRect = { ...cropData[currentVideo.path] };
            } else {
                // Calculate centered crop with aspect ratio
                if (freeMode) {
                    cropRect = {
                        x: displayWidth * 0.1,
                        y: displayHeight * 0.1,
                        width: displayWidth * 0.8,
                        height: displayHeight * 0.8
                    };
                } else {
                    // Fit aspect ratio in center
                    let cropHeight = displayHeight * 0.9;
                    let cropWidth = cropHeight * aspectRatio;

                    if (cropWidth > displayWidth * 0.9) {
                        cropWidth = displayWidth * 0.9;
                        cropHeight = cropWidth / aspectRatio;
                    }

                    cropRect = {
                        x: (displayWidth - cropWidth) / 2,
                        y: (displayHeight - cropHeight) / 2,
                        width: cropWidth,
                        height: cropHeight
                    };
                }
            }

            updateCropBox();
        }

        // Update crop box display
        function updateCropBox() {
            cropBox.style.left = cropRect.x + 'px';
            cropBox.style.top = cropRect.y + 'px';
            cropBox.style.width = cropRect.width + 'px';
            cropBox.style.height = cropRect.height + 'px';

            // Update info
            const realWidth = Math.round((cropRect.width / displayWidth) * imgWidth);
            const realHeight = Math.round((cropRect.height / displayHeight) * imgHeight);
            document.getElementById('cropSize').textContent = realWidth + ' x ' + realHeight;

            // Calculate ratio
            const gcd = (a, b) => b ? gcd(b, a % b) : a;
            const divisor = gcd(realWidth, realHeight);
            document.getElementById('cropRatio').textContent = (realWidth/divisor) + ':' + (realHeight/divisor);
        }

        // Set preset ratio
        function setPreset(ratio) {
            document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            if (ratio === 'free') {
                freeMode = true;
            } else {
                freeMode = false;
                const [w, h] = ratio.split(':').map(Number);
                aspectRatio = w / h;
            }

            initCropBox();
        }

        // Touch/Mouse event handlers
        cropBox.addEventListener('touchstart', handleDragStart, { passive: false });
        cropBox.addEventListener('mousedown', handleDragStart);
        document.addEventListener('touchmove', handleDragMove, { passive: false });
        document.addEventListener('mousemove', handleDragMove);
        document.addEventListener('touchend', handleDragEnd);
        document.addEventListener('mouseup', handleDragEnd);

        function handleDragStart(e) {
            e.preventDefault();
            isDragging = true;

            const touch = e.touches ? e.touches[0] : e;
            const rect = cropOverlay.getBoundingClientRect();

            dragStart = {
                x: touch.clientX - rect.left,
                y: touch.clientY - rect.top
            };

            boxStart = { ...cropRect };

            // Check if dragging a handle
            if (e.target.classList.contains('crop-handle')) {
                dragHandle = e.target.dataset.handle;
            } else {
                dragHandle = null;
            }
        }

        function handleDragMove(e) {
            if (!isDragging) return;
            e.preventDefault();

            const touch = e.touches ? e.touches[0] : e;
            const rect = cropOverlay.getBoundingClientRect();

            const currentX = touch.clientX - rect.left;
            const currentY = touch.clientY - rect.top;

            const dx = currentX - dragStart.x;
            const dy = currentY - dragStart.y;

            if (dragHandle) {
                // Resize from handle
                let newX = boxStart.x;
                let newY = boxStart.y;
                let newW = boxStart.width;
                let newH = boxStart.height;

                if (dragHandle.includes('l')) {
                    newX = Math.max(0, boxStart.x + dx);
                    newW = boxStart.width - (newX - boxStart.x);
                }
                if (dragHandle.includes('r')) {
                    newW = Math.min(displayWidth - boxStart.x, boxStart.width + dx);
                }
                if (dragHandle.includes('t')) {
                    newY = Math.max(0, boxStart.y + dy);
                    newH = boxStart.height - (newY - boxStart.y);
                }
                if (dragHandle.includes('b')) {
                    newH = Math.min(displayHeight - boxStart.y, boxStart.height + dy);
                }

                // Apply aspect ratio constraint
                if (!freeMode) {
                    if (dragHandle === 'tl' || dragHandle === 'bl') {
                        newW = newH * aspectRatio;
                        newX = boxStart.x + boxStart.width - newW;
                    } else {
                        newW = newH * aspectRatio;
                    }
                }

                // Ensure minimum size
                if (newW > 50 && newH > 50) {
                    cropRect = { x: newX, y: newY, width: newW, height: newH };
                }
            } else {
                // Move entire box
                let newX = boxStart.x + dx;
                let newY = boxStart.y + dy;

                // Constrain to canvas
                newX = Math.max(0, Math.min(displayWidth - cropRect.width, newX));
                newY = Math.max(0, Math.min(displayHeight - cropRect.height, newY));

                cropRect.x = newX;
                cropRect.y = newY;
            }

            updateCropBox();
        }

        function handleDragEnd(e) {
            isDragging = false;
            dragHandle = null;
        }

        // Apply crop to current video
        function applyCrop() {
            if (!currentVideo) {
                showToast('Please select a video', 'error');
                return;
            }

            // Save crop data (convert to real coordinates)
            const realCrop = {
                x: Math.round((cropRect.x / displayWidth) * imgWidth),
                y: Math.round((cropRect.y / displayHeight) * imgHeight),
                width: Math.round((cropRect.width / displayWidth) * imgWidth),
                height: Math.round((cropRect.height / displayHeight) * imgHeight)
            };

            // Store locally
            cropData[currentVideo.path] = { ...cropRect };

            // Send to server
            fetch('/api/crop/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video: currentVideo.path,
                    crop: realCrop
                })
            })
            .then(r => r.json())
            .then(data => {
                showToast('Crop saved!', 'success');
                renderVideoList();

                // Move to next video
                const currentIndex = videos.indexOf(currentVideo);
                if (currentIndex < videos.length - 1) {
                    selectVideo(videos[currentIndex + 1]);
                }
            })
            .catch(err => {
                showToast('Error saving crop', 'error');
            });
        }

        // Go back
        function goBack() {
            // Store all crop data in session/localStorage
            sessionStorage.setItem('cropData', JSON.stringify(cropData));
            history.back();
        }

        // Toast
        function showToast(message, type) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast show ' + type;
            setTimeout(() => toast.className = 'toast', 3000);
        }

        // Load existing crop data from session
        try {
            const saved = sessionStorage.getItem('cropData');
            if (saved) cropData = JSON.parse(saved);
        } catch(e) {}

        // Initialize
        loadVideos();
    </script>
</body>
</html>
"""

STATUS_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Pipeline Status - Remote</title>
    <style>{{ css }}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Pipeline Status</h1>
            <p id="statusText">Checking status...</p>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="icon green" id="statusIcon">&#9654;</div>
                <div>
                    <h2 id="currentTask">Loading...</h2>
                    <p id="currentStep">-</p>
                </div>
            </div>

            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                </div>
                <div class="progress-text">
                    <span id="progressPercent">0%</span>
                    <span id="progressEta">-</span>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="icon blue">&#128203;</div>
                <div>
                    <h2>Activity Log</h2>
                    <p>Recent activity</p>
                </div>
            </div>
            <div class="log-container" id="logContainer">
                <div class="log-entry">Waiting for status...</div>
            </div>
        </div>

        <div class="nav-buttons">
            <button class="btn btn-secondary" onclick="location.href='/'">Home</button>
            <button class="btn btn-danger" id="stopBtn" onclick="stopPipeline()">Stop Pipeline</button>
        </div>
    </div>

    <script>
        function updateStatus() {
            fetch('/api/pipeline/status')
                .then(r => r.json())
                .then(data => {
                    if (data.running) {
                        document.getElementById('statusText').textContent = 'Pipeline Running';
                        document.getElementById('currentTask').textContent = data.current_channel || 'Processing...';
                        document.getElementById('currentStep').textContent = data.current_step || '';
                        document.getElementById('progressFill').style.width = (data.progress || 0) + '%';
                        document.getElementById('progressPercent').textContent = (data.progress || 0) + '%';
                        document.getElementById('stopBtn').style.display = 'block';
                    } else {
                        document.getElementById('statusText').textContent = 'No Pipeline Running';
                        document.getElementById('currentTask').textContent = 'Idle';
                        document.getElementById('currentStep').textContent = 'Ready to start';
                        document.getElementById('progressFill').style.width = '0%';
                        document.getElementById('progressPercent').textContent = '0%';
                        document.getElementById('stopBtn').style.display = 'none';
                    }

                    if (data.logs && data.logs.length > 0) {
                        let html = '';
                        data.logs.slice(-10).forEach(log => {
                            html += `<div class="log-entry"><span class="log-time">${log.time}</span> ${log.message}</div>`;
                        });
                        document.getElementById('logContainer').innerHTML = html;
                    }
                })
                .catch(err => {
                    document.getElementById('statusText').textContent = 'Connection lost';
                });
        }

        function stopPipeline() {
            if (confirm('Are you sure you want to stop the pipeline?')) {
                fetch('/api/pipeline/stop', { method: 'POST' })
                    .then(r => r.json())
                    .then(data => {
                        alert(data.message || 'Pipeline stopped');
                        updateStatus();
                    });
            }
        }

        // Update every 2 seconds
        updateStatus();
        setInterval(updateStatus, 2000);
    </script>
</body>
</html>
"""


# ============================================================================
# STEP 2 CROP PAGE - Touch-friendly crop tool for phone
# ============================================================================
STEP2_CROP_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Crop Interview - Nabil Video Studio</title>
    <style>
        {{ css }}

        .crop-container {
            position: relative;
            width: 100%;
            max-width: 100vw;
            margin: 0 auto;
            touch-action: none;
            overflow: hidden;
        }

        .crop-image {
            width: 100%;
            display: block;
        }

        .crop-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
        }

        .crop-rect {
            position: absolute;
            border: 3px solid #4CAF50;
            background: transparent;
            box-shadow: 0 0 0 9999px rgba(0,0,0,0.6);
            pointer-events: auto;
            touch-action: none;
        }

        .crop-handle {
            position: absolute;
            width: 40px;
            height: 40px;
            background: #4CAF50;
            border-radius: 50%;
            transform: translate(-50%, -50%);
            pointer-events: auto;
            touch-action: none;
        }

        .crop-handle.tl { top: 0; left: 0; }
        .crop-handle.tr { top: 0; right: 0; transform: translate(50%, -50%); }
        .crop-handle.bl { bottom: 0; left: 0; transform: translate(-50%, 50%); }
        .crop-handle.br { bottom: 0; right: 0; transform: translate(50%, 50%); }

        .crop-info {
            text-align: center;
            padding: 15px;
            background: rgba(0,0,0,0.8);
            font-size: 14px;
        }

        .crop-buttons {
            display: flex;
            gap: 10px;
            padding: 15px;
            flex-wrap: wrap;
            justify-content: center;
        }

        .crop-buttons button {
            flex: 1;
            min-width: 100px;
            padding: 15px 20px;
            font-size: 16px;
        }

        .aspect-buttons {
            display: flex;
            gap: 8px;
            padding: 10px 15px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .aspect-btn {
            padding: 10px 15px;
            font-size: 12px;
            background: #3a3a6a;
            border: none;
            border-radius: 6px;
            color: white;
        }

        .aspect-btn.active {
            background: #4CAF50;
        }

        .progress-bar {
            height: 4px;
            background: #333;
            width: 100%;
        }

        .progress-fill {
            height: 100%;
            background: #4CAF50;
            transition: width 0.3s;
        }

        .waiting-screen {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 60vh;
            text-align: center;
            padding: 20px;
        }

        .waiting-screen h2 {
            color: #4CAF50;
            margin-bottom: 20px;
        }

        .spinner {
            width: 50px;
            height: 50px;
            border: 4px solid #333;
            border-top: 4px solid #4CAF50;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 20px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .completed-screen {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 60vh;
            text-align: center;
            padding: 20px;
        }

        .completed-screen h2 {
            color: #4CAF50;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <a href="/" class="back-btn">< Back</a>
        <h1>Crop Interview</h1>
    </div>

    <div id="waiting" class="waiting-screen">
        <h2>Waiting for Crop Request...</h2>
        <div class="spinner"></div>
        <p>The PC app will send videos here when Step 2 needs manual cropping.</p>
        <p style="color: #888; margin-top: 20px;">Make sure "Manual Crop" is enabled in the PC app.</p>
    </div>

    <div id="cropUI" style="display: none;">
        <div class="crop-info">
            <span id="videoName">video.mp4</span> -
            <span id="progress">1/5</span>
        </div>

        <div class="progress-bar">
            <div class="progress-fill" id="progressBar" style="width: 0%"></div>
        </div>

        <div class="crop-container" id="cropContainer">
            <img id="frameImage" class="crop-image" src="" alt="Video frame">
            <div class="crop-overlay">
                <div class="crop-rect" id="cropRect">
                    <div class="crop-handle tl" data-handle="tl"></div>
                    <div class="crop-handle tr" data-handle="tr"></div>
                    <div class="crop-handle bl" data-handle="bl"></div>
                    <div class="crop-handle br" data-handle="br"></div>
                </div>
            </div>
        </div>

        <div class="crop-info" id="cropDimensions">
            Crop: 0x0 at (0, 0)
        </div>

        <div class="aspect-buttons">
            <button class="aspect-btn" data-aspect="0.5625">9:16</button>
            <button class="aspect-btn" data-aspect="1.7778">16:9</button>
            <button class="aspect-btn" data-aspect="1">1:1</button>
            <button class="aspect-btn" data-aspect="1.3333">4:3</button>
        </div>

        <div class="crop-buttons">
            <button id="skipBtn" style="background: #f44336;">Skip (AI)</button>
            <button id="saveBtn" style="background: #4CAF50;">Save + Next</button>
        </div>

        <div class="crop-buttons">
            <button id="finishBtn" style="background: #2196F3;">Finish All</button>
        </div>
    </div>

    <div id="completed" class="completed-screen" style="display: none;">
        <h2>All Crops Completed!</h2>
        <p>The pipeline will continue processing on your PC.</p>
        <a href="/" class="btn" style="margin-top: 20px; display: inline-block; padding: 15px 30px; background: #4CAF50; border-radius: 8px; text-decoration: none;">Back to Home</a>
    </div>

    <script>
        // State
        let currentIndex = 0;
        let totalVideos = 0;
        let videoName = '';
        let frameWidth = 1920;
        let frameHeight = 1080;
        let displayScale = 1;

        // Crop rectangle (in original coordinates)
        let cropX = 0, cropY = 0, cropW = 0, cropH = 0;

        // Touch/drag state
        let isDragging = false;
        let dragHandle = null;
        let startX, startY;
        let startCrop = {};

        // DOM elements
        const waitingDiv = document.getElementById('waiting');
        const cropUI = document.getElementById('cropUI');
        const completedDiv = document.getElementById('completed');
        const frameImage = document.getElementById('frameImage');
        const cropRect = document.getElementById('cropRect');
        const cropContainer = document.getElementById('cropContainer');

        // Check for pending crop
        async function checkStatus() {
            try {
                const response = await fetch('/api/step2crop/status');
                const data = await response.json();

                if (data.pending) {
                    currentIndex = data.current;
                    totalVideos = data.total;
                    videoName = data.video_name;
                    frameWidth = data.frame_width || 1920;
                    frameHeight = data.frame_height || 1080;

                    // Load frame and show UI
                    loadFrame(currentIndex);
                    waitingDiv.style.display = 'none';
                    cropUI.style.display = 'block';
                    completedDiv.style.display = 'none';
                } else if (data.completed) {
                    waitingDiv.style.display = 'none';
                    cropUI.style.display = 'none';
                    completedDiv.style.display = 'flex';
                } else {
                    waitingDiv.style.display = 'flex';
                    cropUI.style.display = 'none';
                    completedDiv.style.display = 'none';
                }
            } catch (e) {
                console.error('Status check failed:', e);
            }
        }

        // Load frame image
        function loadFrame(index) {
            console.log('Loading frame:', index);
            const url = '/api/step2crop/frame/' + index + '?t=' + Date.now();
            console.log('Frame URL:', url);
            frameImage.src = url;
            document.getElementById('videoName').textContent = videoName;
            document.getElementById('progress').textContent = (index + 1) + '/' + totalVideos;
            document.getElementById('progressBar').style.width = ((index + 1) / totalVideos * 100) + '%';
        }

        // Handle image load error
        frameImage.onerror = function() {
            console.error('Failed to load frame image');
            alert('Error: Could not load video frame. Check PC console for details.');
        };

        // Initialize crop when image loads
        frameImage.onload = function() {
            const rect = cropContainer.getBoundingClientRect();
            displayScale = frameImage.naturalWidth / frameImage.clientWidth;

            // Default crop: 80% centered
            cropW = Math.round(frameWidth * 0.8);
            cropH = Math.round(frameHeight * 0.8);
            cropX = Math.round((frameWidth - cropW) / 2);
            cropY = Math.round((frameHeight - cropH) / 2);

            updateCropRect();
        };

        // Update crop rectangle display
        function updateCropRect() {
            const scale = frameImage.clientWidth / frameWidth;

            cropRect.style.left = (cropX * scale) + 'px';
            cropRect.style.top = (cropY * scale) + 'px';
            cropRect.style.width = (cropW * scale) + 'px';
            cropRect.style.height = (cropH * scale) + 'px';

            document.getElementById('cropDimensions').textContent =
                'Crop: ' + cropW + 'x' + cropH + ' at (' + cropX + ', ' + cropY + ')';
        }

        // Touch/mouse event handlers
        function getEventPos(e) {
            if (e.touches && e.touches.length > 0) {
                return { x: e.touches[0].clientX, y: e.touches[0].clientY };
            }
            return { x: e.clientX, y: e.clientY };
        }

        function handleStart(e) {
            e.preventDefault();
            const target = e.target;
            const pos = getEventPos(e);

            if (target.classList.contains('crop-handle')) {
                isDragging = true;
                dragHandle = target.dataset.handle;
            } else if (target.id === 'cropRect' || target.closest('#cropRect')) {
                isDragging = true;
                dragHandle = 'move';
            }

            if (isDragging) {
                startX = pos.x;
                startY = pos.y;
                startCrop = { x: cropX, y: cropY, w: cropW, h: cropH };
            }
        }

        function handleMove(e) {
            if (!isDragging) return;
            e.preventDefault();

            const pos = getEventPos(e);
            const scale = frameImage.clientWidth / frameWidth;
            const dx = Math.round((pos.x - startX) / scale);
            const dy = Math.round((pos.y - startY) / scale);

            if (dragHandle === 'move') {
                cropX = Math.max(0, Math.min(startCrop.x + dx, frameWidth - cropW));
                cropY = Math.max(0, Math.min(startCrop.y + dy, frameHeight - cropH));
            } else if (dragHandle === 'tl') {
                const newX = Math.max(0, startCrop.x + dx);
                const newY = Math.max(0, startCrop.y + dy);
                cropW = Math.max(100, startCrop.w - (newX - startCrop.x));
                cropH = Math.max(100, startCrop.h - (newY - startCrop.y));
                cropX = newX;
                cropY = newY;
            } else if (dragHandle === 'tr') {
                const newY = Math.max(0, startCrop.y + dy);
                cropW = Math.max(100, Math.min(startCrop.w + dx, frameWidth - cropX));
                cropH = Math.max(100, startCrop.h - (newY - startCrop.y));
                cropY = newY;
            } else if (dragHandle === 'bl') {
                const newX = Math.max(0, startCrop.x + dx);
                cropW = Math.max(100, startCrop.w - (newX - startCrop.x));
                cropH = Math.max(100, Math.min(startCrop.h + dy, frameHeight - cropY));
                cropX = newX;
            } else if (dragHandle === 'br') {
                cropW = Math.max(100, Math.min(startCrop.w + dx, frameWidth - cropX));
                cropH = Math.max(100, Math.min(startCrop.h + dy, frameHeight - cropY));
            }

            updateCropRect();
        }

        function handleEnd(e) {
            isDragging = false;
            dragHandle = null;
        }

        // Add event listeners
        cropRect.addEventListener('mousedown', handleStart);
        cropRect.addEventListener('touchstart', handleStart);
        document.addEventListener('mousemove', handleMove);
        document.addEventListener('touchmove', handleMove, { passive: false });
        document.addEventListener('mouseup', handleEnd);
        document.addEventListener('touchend', handleEnd);

        // Handle clicks on handles
        document.querySelectorAll('.crop-handle').forEach(handle => {
            handle.addEventListener('mousedown', handleStart);
            handle.addEventListener('touchstart', handleStart);
        });

        // Aspect ratio buttons
        document.querySelectorAll('.aspect-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const aspect = parseFloat(this.dataset.aspect);
                const centerX = cropX + cropW / 2;
                const centerY = cropY + cropH / 2;

                // Adjust to match aspect ratio
                let newW = cropW;
                let newH = Math.round(cropW / aspect);

                if (newH > frameHeight) {
                    newH = frameHeight * 0.8;
                    newW = Math.round(newH * aspect);
                }

                cropW = newW;
                cropH = newH;
                cropX = Math.max(0, Math.min(Math.round(centerX - cropW / 2), frameWidth - cropW));
                cropY = Math.max(0, Math.min(Math.round(centerY - cropH / 2), frameHeight - cropH));

                updateCropRect();

                // Highlight active
                document.querySelectorAll('.aspect-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
            });
        });

        // Save button
        document.getElementById('saveBtn').addEventListener('click', async function() {
            this.disabled = true;
            this.textContent = 'Saving...';

            try {
                const response = await fetch('/api/step2crop/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        video_name: videoName,
                        x: cropX,
                        y: cropY,
                        w: cropW,
                        h: cropH
                    })
                });

                const data = await response.json();

                if (data.status === 'completed') {
                    cropUI.style.display = 'none';
                    completedDiv.style.display = 'flex';
                } else {
                    // Load next
                    checkStatus();
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }

            this.disabled = false;
            this.textContent = 'Save + Next';
        });

        // Skip button
        document.getElementById('skipBtn').addEventListener('click', async function() {
            this.disabled = true;

            try {
                const response = await fetch('/api/step2crop/skip', { method: 'POST' });
                const data = await response.json();

                if (data.status === 'completed') {
                    cropUI.style.display = 'none';
                    completedDiv.style.display = 'flex';
                } else {
                    checkStatus();
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }

            this.disabled = false;
        });

        // Finish button
        document.getElementById('finishBtn').addEventListener('click', async function() {
            if (!confirm('Finish now? Remaining videos will use AI crop.')) return;

            try {
                await fetch('/api/step2crop/finish', { method: 'POST' });
                cropUI.style.display = 'none';
                completedDiv.style.display = 'flex';
            } catch (e) {
                alert('Error: ' + e.message);
            }
        });

        // Initial check and polling
        checkStatus();
        setInterval(checkStatus, 3000);
    </script>
</body>
</html>
"""


class RemoteControlServer:
    """Remote Control Server with separate Local/Internet modes"""

    def __init__(self, config_manager=None, port=5000, main_window=None):
        self.config_manager = config_manager
        self.port = port
        self.main_window = main_window
        self.local_ip = get_local_ip()

        # Server states
        self.local_server_running = False
        self.internet_server_running = False
        self.local_url = None
        self.internet_url = None

        # Flask app
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'nabil-video-studio-secret'

        # Thread references
        self.flask_thread = None
        self.ngrok_process = None

        # Pipeline state
        self.pending_pipeline = None
        self.pipeline_logs = []
        self.crop_data = {}

        # Step 2 crop state (for remote cropping during pipeline)
        self.step2_crop_pending = False
        self.step2_crop_videos = []  # List of {name, frame_path, index, total}
        self.step2_crop_current = 0
        self.step2_crop_results = {}  # {video_name: (x, y, w, h)}
        self.step2_crop_completed = False
        self.step2_crop_frame_dir = None

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup all Flask routes"""

        @self.app.route('/')
        def home():
            profiles = {}
            categories = []
            if self.config_manager:
                profiles = self.config_manager.config.get('profiles', {})
                categories = self.config_manager.config.get('categories', [])
            return render_template_string(HOME_PAGE,
                css=BASE_CSS,
                profile_count=len(profiles),
                category_count=len(categories))

        @self.app.route('/run')
        def run_page():
            profiles = {}
            categories = []
            categories_data = {}
            if self.config_manager:
                profiles = self.config_manager.config.get('profiles', {})
                categories = self.config_manager.config.get('categories', [])
                categories_data = self.config_manager.config.get('categories_data', {})
            return render_template_string(RUN_PAGE,
                css=BASE_CSS,
                profiles=profiles,
                categories=categories,
                categories_data=categories_data)

        @self.app.route('/status')
        def status_page():
            return render_template_string(STATUS_PAGE, css=BASE_CSS)

        @self.app.route('/crop')
        def crop_page():
            return render_template_string(CROP_PAGE, css=BASE_CSS)

        @self.app.route('/step2crop')
        def step2crop_page():
            """Step 2 crop page - for cropping interviews during pipeline"""
            return render_template_string(STEP2_CROP_PAGE, css=BASE_CSS)

        @self.app.route('/api/step2crop/status')
        def api_step2crop_status():
            """Check if Step 2 crop is pending"""
            if not self.step2_crop_pending or not self.step2_crop_videos:
                return jsonify({
                    'pending': False,
                    'message': 'No crop request pending'
                })

            current_idx = self.step2_crop_current
            if current_idx >= len(self.step2_crop_videos):
                return jsonify({
                    'pending': False,
                    'completed': True,
                    'message': 'All crops completed'
                })

            current_video = self.step2_crop_videos[current_idx]
            return jsonify({
                'pending': True,
                'current': current_idx,
                'total': len(self.step2_crop_videos),
                'video_name': current_video['name'],
                'frame_width': current_video.get('width', 1920),
                'frame_height': current_video.get('height', 1080)
            })

        @self.app.route('/api/step2crop/frame/<int:index>')
        def api_step2crop_frame(index):
            """Get frame image for cropping"""
            print(f"[FRAME] Request for frame {index}")
            print(f"[FRAME] Videos available: {len(self.step2_crop_videos) if self.step2_crop_videos else 0}")

            if not self.step2_crop_videos or index >= len(self.step2_crop_videos):
                print(f"[FRAME] Invalid index {index}")
                return jsonify({'error': 'Invalid index'}), 404

            video = self.step2_crop_videos[index]
            frame_path = video.get('frame_path')
            print(f"[FRAME] Frame path: {frame_path}")

            if frame_path and os.path.exists(frame_path):
                print(f"[FRAME] Sending file: {frame_path}")
                return send_file(frame_path, mimetype='image/jpeg')

            print(f"[FRAME] Frame not found at: {frame_path}")
            return jsonify({'error': 'Frame not found', 'path': frame_path}), 404

        @self.app.route('/api/step2crop/submit', methods=['POST'])
        def api_step2crop_submit():
            """Submit crop coordinates from phone"""
            data = request.get_json()
            video_name = data.get('video_name')
            x = int(data.get('x', 0))
            y = int(data.get('y', 0))
            w = int(data.get('w', 100))
            h = int(data.get('h', 100))

            if video_name:
                self.step2_crop_results[video_name] = (x, y, w, h)
                print(f"[STEP2 CROP] Received crop for {video_name}: {x},{y},{w},{h}")

            # Move to next video
            self.step2_crop_current += 1

            # Check if all done
            if self.step2_crop_current >= len(self.step2_crop_videos):
                self.step2_crop_completed = True
                self.step2_crop_pending = False
                return jsonify({
                    'status': 'completed',
                    'message': 'All crops submitted'
                })

            return jsonify({
                'status': 'next',
                'current': self.step2_crop_current,
                'total': len(self.step2_crop_videos)
            })

        @self.app.route('/api/step2crop/skip', methods=['POST'])
        def api_step2crop_skip():
            """Skip current video (use AI crop)"""
            self.step2_crop_current += 1

            if self.step2_crop_current >= len(self.step2_crop_videos):
                self.step2_crop_completed = True
                self.step2_crop_pending = False
                return jsonify({'status': 'completed'})

            return jsonify({
                'status': 'next',
                'current': self.step2_crop_current,
                'total': len(self.step2_crop_videos)
            })

        @self.app.route('/api/step2crop/finish', methods=['POST'])
        def api_step2crop_finish():
            """Finish cropping (use AI for remaining)"""
            self.step2_crop_completed = True
            self.step2_crop_pending = False
            return jsonify({
                'status': 'finished',
                'crops_submitted': len(self.step2_crop_results)
            })

        @self.app.route('/api/test/crop', methods=['POST'])
        def api_test_crop():
            """TEST ENDPOINT: Simulate crop needed - triggers phone alert"""
            import tempfile
            import os

            # Create test frame directory
            self.step2_crop_frame_dir = tempfile.mkdtemp(prefix='crop_test_')
            print(f"[TEST CROP] Created frame dir: {self.step2_crop_frame_dir}")

            # Create a simple test image (green rectangle)
            try:
                import cv2
                import numpy as np

                # Frame 1 - Green theme
                test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                test_frame[:] = (30, 50, 30)  # Dark green background
                cv2.rectangle(test_frame, (400, 100), (880, 620), (0, 255, 0), 3)
                cv2.putText(test_frame, 'TEST VIDEO 1', (450, 400), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
                cv2.putText(test_frame, 'Drag to crop the person', (350, 500), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)

                frame_path = os.path.join(self.step2_crop_frame_dir, 'frame_0.jpg')
                cv2.imwrite(frame_path, test_frame)
                print(f"[TEST CROP] Created frame 1: {frame_path}, exists: {os.path.exists(frame_path)}")

                # Frame 2 - Blue theme
                test_frame2 = np.zeros((720, 1280, 3), dtype=np.uint8)
                test_frame2[:] = (50, 30, 30)  # Dark blue background
                cv2.rectangle(test_frame2, (300, 150), (980, 570), (255, 0, 0), 3)
                cv2.putText(test_frame2, 'TEST VIDEO 2', (420, 400), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)

                frame_path2 = os.path.join(self.step2_crop_frame_dir, 'frame_1.jpg')
                cv2.imwrite(frame_path2, test_frame2)
                print(f"[TEST CROP] Created frame 2: {frame_path2}, exists: {os.path.exists(frame_path2)}")

                self.step2_crop_videos = [
                    {'name': 'test_video_1.mp4', 'frame_path': frame_path, 'index': 0, 'total': 2, 'width': 1280, 'height': 720},
                    {'name': 'test_video_2.mp4', 'frame_path': frame_path2, 'index': 1, 'total': 2, 'width': 1280, 'height': 720}
                ]
                print(f"[TEST CROP] Videos set: {len(self.step2_crop_videos)}")

            except Exception as e:
                print(f"[TEST CROP] Error creating frames: {e}")
                # Fallback - create simple placeholder
                self.step2_crop_videos = [
                    {'name': 'test_video_1.mp4', 'frame_path': '', 'index': 0, 'total': 2, 'width': 1280, 'height': 720},
                    {'name': 'test_video_2.mp4', 'frame_path': '', 'index': 1, 'total': 2, 'width': 1280, 'height': 720}
                ]

            # Set crop pending
            self.step2_crop_pending = True
            self.step2_crop_current = 0
            self.step2_crop_results = {}
            self.step2_crop_completed = False

            print(f"[TEST CROP] Crop pending set to True, current=0")

            return jsonify({
                'status': 'test_crop_triggered',
                'message': 'Check your phone - crop alert should appear!',
                'videos': 2,
                'frame_dir': self.step2_crop_frame_dir
            })

        @self.app.route('/api/test/crop/cancel', methods=['POST'])
        def api_test_crop_cancel():
            """Cancel test crop"""
            self.step2_crop_pending = False
            self.step2_crop_completed = True
            return jsonify({'status': 'cancelled'})

        @self.app.route('/api/status')
        def api_status():
            return jsonify({
                'status': 'online',
                'local_url': self.local_url,
                'internet_url': self.internet_url
            })

        @self.app.route('/api/profiles')
        def api_profiles():
            profiles = {}
            if self.config_manager:
                profiles = self.config_manager.config.get('profiles', {})
            return jsonify({'profiles': profiles})

        @self.app.route('/api/categories')
        def api_categories():
            categories = []
            categories_data = {}
            if self.config_manager:
                categories = self.config_manager.config.get('categories', [])
                categories_data = self.config_manager.config.get('categories_data', {})
            return jsonify({
                'categories': categories,
                'categories_data': categories_data
            })

        @self.app.route('/api/folders/<category>')
        def api_folders(category):
            """Get input folders for a category"""
            folders = []
            if self.config_manager:
                categories_data = self.config_manager.config.get('categories_data', {})
                if category in categories_data:
                    input_path = categories_data[category].get('input_path', '')
                    if input_path and Path(input_path).exists():
                        # Scan for subfolders
                        for item in sorted(Path(input_path).iterdir()):
                            if item.is_dir():
                                # Count video files
                                video_count = len([f for f in item.iterdir()
                                    if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm']])
                                folders.append({
                                    'name': item.name,
                                    'path': str(item),
                                    'video_count': video_count
                                })
            return jsonify({'folders': folders})

        @self.app.route('/api/videos')
        def api_videos():
            """Get videos in a folder"""
            folder = request.args.get('folder', '')
            videos = []
            if folder and Path(folder).exists():
                for f in sorted(Path(folder).iterdir()):
                    if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                        videos.append({
                            'name': f.name,
                            'path': str(f)
                        })
            return jsonify({'videos': videos})

        @self.app.route('/api/thumbnail')
        def api_thumbnail():
            """Get video thumbnail"""
            from flask import send_file, Response
            import io

            video_path = request.args.get('video', '')
            if not video_path or not Path(video_path).exists():
                # Return a placeholder image
                return Response(status=404)

            try:
                import cv2
                cap = cv2.VideoCapture(video_path)
                # Seek to 1 second or 10% into video
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS) or 30
                seek_frame = min(int(fps), int(total_frames * 0.1))
                cap.set(cv2.CAP_PROP_POS_FRAMES, seek_frame)

                ret, frame = cap.read()
                cap.release()

                if ret:
                    # Resize for faster transfer
                    height, width = frame.shape[:2]
                    max_width = 640
                    if width > max_width:
                        scale = max_width / width
                        frame = cv2.resize(frame, None, fx=scale, fy=scale)

                    # Encode to JPEG
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    return Response(buffer.tobytes(), mimetype='image/jpeg')
            except Exception as e:
                print(f"Thumbnail error: {e}")

            return Response(status=404)

        @self.app.route('/api/crop/save', methods=['POST'])
        def api_crop_save():
            """Save crop data for a video"""
            data = request.get_json()
            video_path = data.get('video', '')
            crop = data.get('crop', {})

            if not video_path or not crop:
                return jsonify({'status': 'error', 'message': 'Missing video or crop data'})

            # Store crop data
            if not hasattr(self, 'crop_data'):
                self.crop_data = {}
            self.crop_data[video_path] = crop

            return jsonify({'status': 'saved', 'message': 'Crop saved successfully'})

        @self.app.route('/api/pipeline/run', methods=['POST'])
        def api_pipeline_run():
            """Start the pipeline"""
            data = request.get_json()

            self.pending_pipeline = {
                'category': data.get('category', ''),
                'channels': data.get('channels', []),
                'folders': data.get('folders', []),
                'options': data.get('options', {})
            }

            # Log
            self.pipeline_logs.append({
                'time': self._get_time(),
                'message': f"Pipeline request: {len(data.get('channels', []))} channels, {len(data.get('folders', []))} folders"
            })

            # Trigger pipeline in main window
            if self.main_window and hasattr(self.main_window, 'run_remote_pipeline'):
                try:
                    # Call run_remote_pipeline directly - it uses Qt signals internally for thread safety
                    self.main_window.run_remote_pipeline(self.pending_pipeline)
                    return jsonify({'status': 'started', 'message': 'Pipeline started'})
                except Exception as e:
                    import traceback
                    print(f"[REMOTE] Error starting pipeline: {e}")
                    print(traceback.format_exc())
                    return jsonify({'status': 'error', 'message': str(e)})
            else:
                print("[REMOTE] No main window connected!")
                return jsonify({'status': 'queued', 'message': 'Pipeline queued (no main window connected)'})

        @self.app.route('/api/pipeline/status')
        def api_pipeline_status():
            """Get current pipeline status"""
            # TODO: Get actual status from main window
            running = False
            if self.main_window and hasattr(self.main_window, 'pipeline_thread'):
                running = self.main_window.pipeline_thread is not None

            return jsonify({
                'running': running,
                'current_channel': '',
                'current_step': '',
                'progress': 0,
                'logs': self.pipeline_logs[-20:]
            })

        @self.app.route('/api/pipeline/stop', methods=['POST'])
        def api_pipeline_stop():
            """Stop the pipeline"""
            if self.main_window and hasattr(self.main_window, 'stop_pipeline'):
                self.main_window.stop_pipeline()
                return jsonify({'status': 'stopped', 'message': 'Pipeline stop requested'})
            return jsonify({'status': 'error', 'message': 'Cannot stop pipeline'})

    def _get_time(self):
        """Get current time string"""
        from datetime import datetime
        return datetime.now().strftime('%H:%M:%S')

    # ========================================================================
    # STEP 2 CROP HELPER METHODS
    # ========================================================================

    def request_step2_crop(self, video_files, temp_dir=None):
        """
        Request Step 2 crop from phone.
        Called from crop_tool.py when manual crop is enabled and remote server is running.

        Args:
            video_files: List of Path objects for videos to crop
            temp_dir: Directory to store frame images

        Returns:
            True if request was set up successfully
        """
        import tempfile
        import cv2

        # Reset state
        self.step2_crop_pending = True
        self.step2_crop_videos = []
        self.step2_crop_current = 0
        self.step2_crop_results = {}
        self.step2_crop_completed = False

        # Create temp dir for frames
        if temp_dir:
            self.step2_crop_frame_dir = Path(temp_dir)
        else:
            self.step2_crop_frame_dir = Path(tempfile.mkdtemp(prefix='nvs_crop_'))

        self.step2_crop_frame_dir.mkdir(parents=True, exist_ok=True)

        # Extract frames from each video
        for i, video_path in enumerate(video_files):
            try:
                cap = cv2.VideoCapture(str(video_path))
                if not cap.isOpened():
                    print(f"[STEP2 CROP] Cannot open: {video_path.name}")
                    continue

                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                # Get frame from 1/3 into video
                cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 3)
                ret, frame = cap.read()
                cap.release()

                if not ret:
                    print(f"[STEP2 CROP] Cannot read frame: {video_path.name}")
                    continue

                # Save frame as JPEG
                frame_path = self.step2_crop_frame_dir / f"frame_{i}.jpg"
                cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

                self.step2_crop_videos.append({
                    'name': video_path.name,
                    'path': str(video_path),
                    'frame_path': str(frame_path),
                    'width': width,
                    'height': height,
                    'index': i
                })

                print(f"[STEP2 CROP] Prepared: {video_path.name} ({width}x{height})")

            except Exception as e:
                print(f"[STEP2 CROP] Error preparing {video_path.name}: {e}")

        print(f"[STEP2 CROP] Ready for {len(self.step2_crop_videos)} videos")
        return len(self.step2_crop_videos) > 0

    def wait_for_step2_crops(self, timeout=600):
        """
        Wait for all Step 2 crops to be completed from phone.
        Blocks until done or timeout.

        Args:
            timeout: Maximum seconds to wait (default 10 minutes)

        Returns:
            Dict of {video_name: (x, y, w, h)} crops
        """
        import time
        start_time = time.time()

        print(f"[STEP2 CROP] Waiting for crops from phone (timeout: {timeout}s)...")

        while not self.step2_crop_completed:
            if time.time() - start_time > timeout:
                print("[STEP2 CROP] Timeout waiting for crops")
                self.step2_crop_pending = False
                break

            time.sleep(1)

            # Show progress
            if self.step2_crop_current > 0:
                print(f"[STEP2 CROP] Progress: {self.step2_crop_current}/{len(self.step2_crop_videos)}")

        # Cleanup frame files
        if self.step2_crop_frame_dir and self.step2_crop_frame_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.step2_crop_frame_dir)
            except:
                pass

        self.step2_crop_pending = False
        return self.step2_crop_results

    def is_step2_crop_ready(self):
        """Check if Step 2 crop is available (server running)"""
        return self.local_server_running or self.internet_server_running

    def start_local(self):
        """Start local server only"""
        if self.local_server_running:
            return {'status': 'already_running', 'url': self.local_url}

        try:
            # Start Flask in thread
            self.flask_thread = threading.Thread(target=self._run_flask, daemon=True)
            self.flask_thread.start()

            self.local_url = f"http://{self.local_ip}:{self.port}"
            self.local_server_running = True

            return {'status': 'started', 'url': self.local_url}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def stop_local(self):
        """Stop local server"""
        # Flask doesn't have a clean shutdown in thread mode
        # We'll just mark it as stopped
        self.local_server_running = False
        self.local_url = None
        return {'status': 'stopped'}

    def start_internet(self, ngrok_api_key=None):
        """Start internet server with ngrok"""
        if self.internet_server_running:
            return {'status': 'already_running', 'url': self.internet_url}

        if not ngrok_api_key:
            # Try to get from config
            if self.config_manager:
                ngrok_api_key = self.config_manager.config.get('ngrok_api_key', '')

        if not ngrok_api_key:
            return {'status': 'error', 'message': 'Ngrok API key required'}

        try:
            # Make sure local server is running first
            if not self.local_server_running:
                self.start_local()

            # Configure ngrok
            subprocess.run(['ngrok', 'config', 'add-authtoken', ngrok_api_key],
                          capture_output=True, timeout=10)

            # Start ngrok tunnel
            self.ngrok_process = subprocess.Popen(
                ['ngrok', 'http', str(self.port), '--log=stdout'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait a moment for ngrok to start
            import time
            time.sleep(2)

            # Get public URL from ngrok API
            import urllib.request
            try:
                with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=5) as response:
                    data = json.loads(response.read().decode())
                    if data.get('tunnels'):
                        self.internet_url = data['tunnels'][0].get('public_url', '')
                        self.internet_server_running = True
                        return {'status': 'started', 'url': self.internet_url}
            except:
                pass

            return {'status': 'error', 'message': 'Could not get ngrok URL'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def stop_internet(self):
        """Stop internet server"""
        if self.ngrok_process:
            self.ngrok_process.terminate()
            self.ngrok_process = None

        self.internet_server_running = False
        self.internet_url = None
        return {'status': 'stopped'}

    def _run_flask(self):
        """Run Flask server"""
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        self.app.run(host='0.0.0.0', port=self.port, threaded=True, use_reloader=False)

    # Legacy methods for compatibility
    def start(self, use_ngrok=False):
        """Legacy start method"""
        result = self.start_local()
        if use_ngrok:
            self.start_internet()
        return result

    def stop(self):
        """Legacy stop method"""
        self.stop_internet()
        self.stop_local()


# For testing
if __name__ == '__main__':
    print("Starting Remote Control Server...")
    server = RemoteControlServer()
    result = server.start_local()
    print(f"Local server: {result}")
    print(f"Access at: http://{get_local_ip()}:5000")

    # Keep running
    import time
    while True:
        time.sleep(1)
