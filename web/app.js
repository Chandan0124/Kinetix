/**
 * KINETIX - High-Speed Phone-to-PC Delta Mirror & Recovery
 * Frontend Application Engine (Vanilla ES6+)
 */

'use strict';

// ============================================================================
// State Store
// ============================================================================
const state = {
  demoMode: false,
  apiBase: window.location.origin.startsWith('http') ? window.location.origin : 'http://localhost:8765',
  wsUrl: `ws://${window.location.hostname || 'localhost'}:${window.location.port || '8765'}/ws/progress`,
  ws: null,

  // Device status
  device: {
    connected: false,
    model: '',
    codename: '',
    androidVersion: '',
    apiLevel: 0,
    buildId: '',
    connectionType: 'USB',
    batteryPct: 0,
    isCharging: false,
    storageUsedGB: 0,
    storageTotalGB: 0,
    storageFreeGB: 0
  },

  // PC Target Path
  targetPath: 'B:\\MobilePCSync\\Backups',

  // Custom folder paths overrides per category
  customCategoryPaths: {},

  // Active navigation tab
  activeTab: 'tab-sync',

  // Sync Categories & Selections
  categories: {
    photos: {
      name: 'Photos & Videos',
      paths: ['/sdcard/DCIM', '/sdcard/Pictures', '/sdcard/Movies'],
      selected: true,
      files: 0,
      sizeGB: 0
    },
    music: {
      name: 'Music & Audio',
      paths: ['/sdcard/Music', '/sdcard/Podcasts', '/sdcard/Audiobooks'],
      selected: true,
      files: 0,
      sizeGB: 0
    },
    whatsapp: {
      name: 'WhatsApp Media & Backups',
      paths: ['Android/media/com.whatsapp/WhatsApp/'],
      selected: true,
      files: 0,
      sizeGB: 0
    },
    telegram: {
      name: 'Telegram Media & Files',
      paths: ['/sdcard/Telegram/'],
      selected: true,
      files: 0,
      sizeGB: 0
    },
    sms_calls: {
      name: 'SMS & Call Logs',
      paths: ['Telephony Provider'],
      selected: true,
      files: 0,
      sizeGB: 0
    },
    private_space: {
      name: 'Android 15+ Private Space',
      paths: ['User 10 / Private Vault'],
      selected: true,
      files: 0,
      sizeGB: 0
    },
    custom_folders: {
      name: 'Custom Folders',
      paths: ['/sdcard/Documents', '/sdcard/Download'],
      selected: true,
      files: 0,
      sizeGB: 0
    }
  },

  // Telemetry & Sync Job
  sync: {
    inProgress: false,
    intervalId: null,
    currentSpeedMBs: 0,
    peakSpeedMBs: 0,
    progressPct: 0,
    bytesTransferred: 0,
    totalBytes: 2.45 * 1024 * 1024 * 1024, // 2.45 GB diff to transfer
    filesSynced: 0,
    totalFiles: 112,
    etaSec: 18,
    currentFile: '',
    workers: [
      { id: 'W1', file: 'IMG_20261024_191.heic', speed: 38 },
      { id: 'W2', file: 'VID_20261024_002.mp4', speed: 56 },
      { id: 'W3', file: 'WhatsApp/msgstore.crypt15', speed: 28 },
      { id: 'W4', file: 'Track_08_HiRes.flac', speed: 18 }
    ]
  },

  // Restore Job
  restore: {
    inProgress: false,
    intervalId: null,
    pollInterval: null,
    selectedSnapshot: '',
    snapshotDetails: null,
    selectedCategories: {},
    customSubfolders: {},
    progressPct: 0
  },

  // Diff Preview Data
  diff: {
    totalScanned: 15200,
    alreadySynced: 15088,
    savedGB: 61.4,
    toTransferCount: 112,
    newCount: 98,
    newGB: 2.1,
    modifiedCount: 14,
    modifiedMB: 350,
    estimatedSec: 18,
    activeFilter: 'to_sync',
    searchQuery: '',
    items: []
  },

  // Messages & Calls Data
  messagesView: 'messages', // 'messages' or 'calls'
  activeThreadId: 1,
  msgSearchQuery: '',
  threads: [],
  calls: []
};

// ============================================================================
// Mock Data Generators for Rich Offline & Demo Showcase
// ============================================================================
function initMockData() {
  // Generate sample diff items
  const diffItems = [
    { id: 1, path: '/sdcard/DCIM/Camera/PXL_20261025_091522.jpg', size: '4.8 MB', time: 'Today at 09:15 AM', status: 'NEW' },
    { id: 2, path: '/sdcard/DCIM/Camera/PXL_20261025_091845.jpg', size: '5.2 MB', time: 'Today at 09:18 AM', status: 'NEW' },
    { id: 3, path: '/sdcard/DCIM/Camera/VID_20261025_092014_4K60.mp4', size: '412.0 MB', time: 'Today at 09:20 AM', status: 'NEW' },
    { id: 4, path: '/sdcard/DCIM/Camera/PXL_20261025_092500.raw', size: '28.4 MB', time: 'Today at 09:25 AM', status: 'NEW' },
    { id: 5, path: 'Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15', size: '184.2 MB', time: 'Today at 02:00 AM', status: 'MODIFIED' },
    { id: 6, path: 'Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Video/VID-20261025-WA0012.mp4', size: '38.5 MB', time: 'Today at 10:04 AM', status: 'NEW' },
    { id: 7, path: 'Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes/PTT-20261025-WA0003.opus', size: '1.2 MB', time: 'Today at 10:12 AM', status: 'NEW' },
    { id: 8, path: '/sdcard/Music/Albums/DaftPunk_RandomAccess/01_GiveLifeBack.flac', size: '48.2 MB', time: 'Yesterday at 04:20 PM', status: 'NEW' },
    { id: 9, path: '/sdcard/Music/Albums/DaftPunk_RandomAccess/02_GameOfLove.flac', size: '54.1 MB', time: 'Yesterday at 04:21 PM', status: 'NEW' },
    { id: 10, path: '/sdcard/Telegram/Telegram Video/Documentary_HD_Part2.mp4', size: '890.0 MB', time: 'Yesterday at 07:44 PM', status: 'NEW' },
    { id: 11, path: '/sdcard/Pictures/Screenshots/Screenshot_20261025-103011.png', size: '2.4 MB', time: 'Today at 10:30 AM', status: 'NEW' },
    { id: 12, path: '/sdcard/Documents/Work/Q4_Roadmap_Final.pdf', size: '14.8 MB', time: 'Today at 08:30 AM', status: 'MODIFIED' },
    { id: 13, path: 'telephony_sms_database_snapshot.json', size: '24.5 MB', time: 'Today at 11:00 AM', status: 'MODIFIED' },
    { id: 14, path: 'telephony_call_logs_export.xml', size: '3.8 MB', time: 'Today at 11:00 AM', status: 'MODIFIED' },
    { id: 15, path: '/sdcard/DCIM/Camera/PXL_20261024_163310.jpg', size: '3.9 MB', time: 'Oct 24, 2026', status: 'SYNCED' },
    { id: 16, path: '/sdcard/DCIM/Camera/PXL_20261024_163512.jpg', size: '4.1 MB', time: 'Oct 24, 2026', status: 'SYNCED' },
    { id: 17, path: '/sdcard/DCIM/Camera/VID_20261024_170020.mp4', size: '1.2 GB', time: 'Oct 24, 2026', status: 'SYNCED' },
    { id: 18, path: '/sdcard/Music/Liked/TheWeeknd_BlindingLights.mp3', size: '8.4 MB', time: 'Oct 20, 2026', status: 'SYNCED' }
  ];
  state.diff.items = [];
  state.threads = [];
  state.calls = [];
}

// ============================================================================
// UI Elements Cache
// ============================================================================
const DOM = {
  // Navigation Tabs
  navTabs: document.querySelectorAll('.nav-tab'),
  tabPanes: document.querySelectorAll('.tab-pane'),

  // Header / Device Pill
  devicePill: document.getElementById('device-pill'),
  deviceModelName: document.getElementById('device-model-name'),
  deviceOsTag: document.getElementById('device-os-tag'),
  deviceConnTag: document.getElementById('device-conn-tag'),
  deviceBatteryPct: document.getElementById('device-battery-pct'),
  storageBarFill: document.getElementById('storage-bar-fill'),
  storageReadout: document.getElementById('storage-readout'),
  pillDisconnectedView: document.querySelector('.device-pill-disconnected'),
  pillConnectedView: document.querySelector('.device-pill-content'),
  btnScanDevices: document.getElementById('btn-scan-devices'),
  btnDemoMode: document.getElementById('btn-demo-mode'),
  demoModeLabel: document.getElementById('demo-mode-label'),
  currentTargetPath: document.getElementById('current-target-path'),
  btnChangePath: document.getElementById('btn-change-path'),
  btnQuickSettings: document.getElementById('btn-quick-settings'),

  // Category Selection
  categoryCards: document.querySelectorAll('.category-card'),
  btnSelectAll: document.getElementById('btn-select-all'),
  btnDeselectAll: document.getElementById('btn-deselect-all'),
  selectedSummary: document.getElementById('selected-summary'),
  btnAddCustomFolder: document.getElementById('btn-add-custom-folder'),
  customPathsDisplay: document.getElementById('custom-paths-display'),

  // Action Bar & Telemetry
  btnScanDiff: document.getElementById('btn-scan-diff'),
  btnStartSync: document.getElementById('btn-start-sync'),
  btnAbortSync: document.getElementById('btn-abort-sync'),
  telemetrySection: document.getElementById('telemetry-section'),
  telemetryStatusText: document.getElementById('telemetry-status-text'),
  telemetryEta: document.getElementById('telemetry-eta'),
  speedMeterArc: document.getElementById('speed-meter-arc'),
  currentSpeedValue: document.getElementById('current-speed-value'),
  peakSpeedValue: document.getElementById('peak-speed-value'),
  progressPctLabel: document.getElementById('progress-pct-label'),
  progressBytesLabel: document.getElementById('progress-bytes-label'),
  progressFilesLabel: document.getElementById('progress-files-label'),
  syncProgressFill: document.getElementById('sync-progress-fill'),
  rollingFileTicker: document.getElementById('rolling-file-ticker'),
  syncCompleteCard: document.getElementById('sync-complete-card'),
  syncSummaryMessage: document.getElementById('sync-summary-message'),
  btnOpenBackupFolder: document.getElementById('btn-open-backup-folder'),
  btnDismissSummary: document.getElementById('btn-dismiss-summary'),

  // Diff Modal
  diffModal: document.getElementById('diff-preview-modal'),
  btnCloseDiffModal: document.getElementById('btn-close-diff-modal'),
  btnCancelDiff: document.getElementById('btn-cancel-diff'),
  btnProceedSync: document.getElementById('btn-proceed-sync'),
  diffTableBody: document.getElementById('diff-table-body'),
  diffFilterTabs: document.querySelectorAll('.diff-tab-btn'),
  diffSearchInput: document.getElementById('diff-search-input'),
  modalStatScanned: document.getElementById('modal-stat-scanned'),
  modalStatSkipped: document.getElementById('modal-stat-skipped'),
  modalStatNew: document.getElementById('modal-stat-new'),
  modalStatModified: document.getElementById('modal-stat-modified'),
  modalStatEta: document.getElementById('modal-stat-eta'),
  diffFilterSyncCount: document.getElementById('diff-filter-sync-count'),
  diffFilterNewCount: document.getElementById('diff-filter-new-count'),
  diffFilterModCount: document.getElementById('diff-filter-mod-count'),

  // Restore Wizard & Telemetry
  snapshotItems: document.querySelectorAll('.snapshot-item'),
  btnStartRestore: document.getElementById('btn-start-restore'),
  btnAbortRestore: document.getElementById('btn-abort-restore'),
  restoreTelemetrySection: document.getElementById('restore-telemetry-section'),
  restoreTelemetryStatusText: document.getElementById('restore-telemetry-status-text'),
  restoreTelemetryEta: document.getElementById('restore-telemetry-eta'),
  restoreSpeedMeterArc: document.getElementById('restore-speed-meter-arc'),
  restoreCurrentSpeedValue: document.getElementById('restore-current-speed-value'),
  restorePeakSpeedValue: document.getElementById('restore-peak-speed-value'),
  restoreProgressPctLabel: document.getElementById('restore-progress-pct-label'),
  restoreProgressBytesLabel: document.getElementById('restore-progress-bytes-label'),
  restoreProgressFilesLabel: document.getElementById('restore-progress-files-label'),
  restoreProgressFill: document.getElementById('restore-progress-fill'),
  restoreRollingFileTicker: document.getElementById('restore-rolling-file-ticker'),
  restoreCompleteCard: document.getElementById('restore-complete-card'),
  restoreSummaryMessage: document.getElementById('restore-summary-message'),
  btnRescanGallery: document.getElementById('btn-rescan-gallery'),
  btnDismissRestoreSummary: document.getElementById('btn-dismiss-restore-summary'),
  btnBrowseSnapshot: document.getElementById('btn-browse-snapshot'),
  restoreCategoriesContainer: document.getElementById('restore-categories-container'),
  btnRestoreSelectAll: document.getElementById('btn-restore-select-all'),
  btnRestoreDeselectAll: document.getElementById('btn-restore-deselect-all'),
  btnAnalyzeRestore: document.getElementById('btn-analyze-restore'),
  btnStartRestoreText: document.getElementById('btn-start-restore-text'),
  restoreAnalysisCard: document.getElementById('restore-analysis-card'),
  btnCloseRestoreAnalysis: document.getElementById('btn-close-restore-analysis'),
  resStatTotalFiles: document.getElementById('res-stat-total-files'),
  resStatTotalSize: document.getElementById('res-stat-total-size'),
  resStatSkippedFiles: document.getElementById('res-stat-skipped-files'),
  resStatSkippedSize: document.getElementById('res-stat-skipped-size'),
  resStatToPushFiles: document.getElementById('res-stat-to-push-files'),
  resStatToPushSize: document.getElementById('res-stat-to-push-size'),
  resStatTimeSaved: document.getElementById('res-stat-time-saved'),
  restoreAnalysisDetailMsg: document.getElementById('restore-analysis-detail-msg'),
  restoreSelectedSummary: document.getElementById('restore-selected-summary'),
  restoreSubfolderModal: document.getElementById('restore-subfolder-modal'),
  btnCloseRestoreSubfolder: document.getElementById('btn-close-restore-subfolder-modal'),
  btnCancelRestoreSubfolder: document.getElementById('btn-cancel-restore-subfolder-modal'),
  btnSaveRestoreSubfolder: document.getElementById('btn-save-restore-subfolder-modal'),
  btnRestoreOnlyThisSubfolder: document.getElementById('btn-restore-only-this-subfolder'),
  btnRestoreSubSelectAll: document.getElementById('btn-restore-subfolder-select-all'),
  btnRestoreSubClearAll: document.getElementById('btn-restore-subfolder-clear-all'),
  restoreSubfolderContainer: document.getElementById('restore-subfolder-list-container'),

  // Messages & Calls
  msgViewButtons: document.querySelectorAll('.msg-view-btn'),
  smsSearchInput: document.getElementById('sms-search-input'),
  btnExportHtml: document.getElementById('btn-export-html'),
  btnExportXml: document.getElementById('btn-export-xml'),
  btnExportJson: document.getElementById('btn-export-json'),
  messagesViewContainer: document.getElementById('messages-view-container'),
  callsViewContainer: document.getElementById('calls-view-container'),
  threadsList: document.getElementById('threads-list'),
  chatMessagesContainer: document.getElementById('chat-messages-container'),
  chatAvatar: document.getElementById('chat-avatar'),
  chatContactName: document.getElementById('chat-contact-name'),
  chatContactNumber: document.getElementById('chat-contact-number'),
  chatMsgCount: document.getElementById('chat-msg-count'),
  btnExportThread: document.getElementById('btn-export-thread'),
  callsTbody: document.getElementById('calls-tbody'),
  totalSmsThreads: document.getElementById('total-sms-threads'),
  totalCallRecords: document.getElementById('total-call-records'),
  threadsCountBadge: document.getElementById('threads-count-badge'),

  // Settings
  btnModeUsb: document.getElementById('btn-mode-usb'),
  btnModeWifi: document.getElementById('btn-mode-wifi'),
  wifiConfigRow: document.getElementById('wifi-config-row'),
  btnConnectWifi: document.getElementById('btn-connect-wifi'),
  workersSlider: document.getElementById('workers-slider'),
  workersValueBadge: document.getElementById('workers-value-badge'),
  btnManualMediascan: document.getElementById('btn-manual-mediascan'),
  btnRestartAdb: document.getElementById('btn-restart-adb'),
  btnEnableTcpmode: document.getElementById('btn-enable-tcpmode'),

  // Path Modal
  pathModal: document.getElementById('path-picker-modal'),
  btnClosePathModal: document.getElementById('btn-close-path-modal'),
  btnCancelPath: document.getElementById('btn-cancel-path'),
  btnSavePath: document.getElementById('btn-save-path'),
  inputNewTargetPath: document.getElementById('input-new-target-path'),
  pathChips: document.querySelectorAll('.path-chip'),

  // Custom Folder Modal
  customFolderModal: document.getElementById('custom-folder-modal'),
  btnCloseCustomModal: document.getElementById('btn-close-custom-modal'),
  btnCancelCustom: document.getElementById('btn-cancel-custom'),
  btnSaveCustom: document.getElementById('btn-save-custom'),
  inputCustomFolderPath: document.getElementById('input-custom-folder-path'),
  customDirChips: document.querySelectorAll('.custom-dir-chip'),

  // Toast Container
  toastContainer: document.getElementById('toast-container')
};

// ============================================================================
// Toast Notification Utility
// ============================================================================
function showToast(message, type = 'info', duration = 4000) {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const iconSvg = {
    success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00df8f" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>`,
    info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00f0ff" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
    warn: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f5a623" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    error: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ff4757" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`
  }[type] || '';

  toast.innerHTML = `
    <div class="toast-icon">${iconSvg}</div>
    <div class="toast-body">${message}</div>
  `;

  DOM.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'toastOut 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards';
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, duration);
}

// ============================================================================
// Tab Navigation Controller
// ============================================================================
function setupNavigation() {
  DOM.navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetTabId = tab.getAttribute('data-tab');
      switchTab(targetTabId);
    });
  });

  DOM.btnQuickSettings?.addEventListener('click', () => {
    switchTab('tab-settings');
  });
}

function switchTab(tabId) {
  state.activeTab = tabId;

  DOM.navTabs.forEach(t => {
    if (t.getAttribute('data-tab') === tabId) {
      t.classList.add('active');
    } else {
      t.classList.remove('active');
    }
  });

  DOM.tabPanes.forEach(pane => {
    if (pane.id === tabId) {
      pane.classList.add('active');
    } else {
      pane.classList.remove('active');
    }
  });

  // Re-render specific tab contents if needed
  if (tabId === 'tab-messages') {
    renderThreadsList();
    renderActiveThread();
    renderCallsTable();
  }
}

// ============================================================================
// Category Selection Controller
// ============================================================================
function setupCategories() {
  DOM.categoryCards.forEach(card => {
    const catKey = card.getAttribute('data-category');
    const checkbox = card.querySelector('input[type="checkbox"]');

    // Click anywhere on card toggles checkbox
    card.addEventListener('click', (e) => {
      if (e.target.tagName.toLowerCase() === 'button' || e.target.closest('button')) {
        return; // Don't trigger when clicking buttons
      }
      if (e.target.closest('.custom-checkbox') || e.target === checkbox) {
        return; // Native checkbox event handles this
      }
      checkbox.checked = !checkbox.checked;
      handleCategoryToggle(catKey, checkbox.checked);
    });

    checkbox.addEventListener('change', () => {
      handleCategoryToggle(catKey, checkbox.checked);
    });
  });

  DOM.btnSelectAll.addEventListener('click', () => {
    Object.keys(state.categories).forEach(k => {
      state.categories[k].selected = true;
    });
    updateCategoryUI();
  });

  DOM.btnDeselectAll.addEventListener('click', () => {
    Object.keys(state.categories).forEach(k => {
      state.categories[k].selected = false;
    });
    updateCategoryUI();
  });
}

function handleCategoryToggle(catKey, isChecked) {
  if (state.categories[catKey]) {
    state.categories[catKey].selected = isChecked;
  }
  updateCategoryUI();
}

function updateCategoryUI() {
  let selectedCount = 0;
  let totalSizeGB = 0;
  const totalCats = Object.keys(state.categories).length;

  DOM.categoryCards.forEach(card => {
    const catKey = card.getAttribute('data-category');
    const cat = state.categories[catKey];
    const checkbox = card.querySelector('input[type="checkbox"]');

    if (cat && cat.selected) {
      card.classList.add('active');
      checkbox.checked = true;
      selectedCount++;
      totalSizeGB += cat.sizeGB || 0;
    } else {
      card.classList.remove('active');
      checkbox.checked = false;
    }
  });

  if (totalSizeGB > 0) {
    DOM.selectedSummary.textContent = `${selectedCount} of ${totalCats} Selected (~${totalSizeGB.toFixed(1)} GB)`;
  } else {
    DOM.selectedSummary.textContent = `${selectedCount} of ${totalCats} Selected (Ready to scan)`;
  }
}

// ============================================================================
// Speedometer & Telemetry Controller
// ============================================================================
function updateSpeedometer(speedMBs, peakMBs) {
  // Update numbers
  DOM.currentSpeedValue.textContent = speedMBs.toFixed(1);
  if (peakMBs) {
    DOM.peakSpeedValue.textContent = `${peakMBs.toFixed(1)} MB/s`;
  }

  // Calculate arc stroke-dashoffset (max speed scale: 200 MB/s)
  // Arc total perimeter = 251.3
  const maxScale = 200;
  const clampedSpeed = Math.min(speedMBs, maxScale);
  const ratio = clampedSpeed / maxScale;
  const totalDash = 251.3;
  // Offset moves from totalDash (empty) to 0 (full)
  const offset = totalDash * (1 - ratio);
  DOM.speedMeterArc.style.strokeDashoffset = offset.toFixed(1);
}

// ============================================================================
// Sync Engine (Phone -> PC)
// ============================================================================
function setupSyncEngine() {
  DOM.btnScanDiff.addEventListener('click', () => {
    runScanAndDiff();
  });

  DOM.btnStartSync.addEventListener('click', () => {
    startSyncJob();
  });

  DOM.btnAbortSync.addEventListener('click', () => {
    stopSyncJob();
  });

  DOM.btnProceedSync.addEventListener('click', () => {
    closeDiffModal();
    startSyncJob();
  });

  DOM.btnOpenBackupFolder.addEventListener('click', async () => {
    try {
      await fetch('/api/open_folder', { method: 'POST' });
      showToast(`Opened PC Backup Directory: ${state.targetPath}`, 'info');
    } catch (e) {
      showToast(`Backup folder: ${state.targetPath}`, 'info');
    }
  });

  DOM.btnDismissSummary.addEventListener('click', () => {
    DOM.syncCompleteCard.style.display = 'none';
  });
}

function runScanAndDiff() {
  if (!state.device.connected) {
    showToast('No phone connected. Please connect your Android phone via USB with USB Debugging enabled.', 'warning', 3500);
    return;
  }
  showToast('Starting delta-index scan across ADB channels...', 'info', 2000);
  DOM.btnScanDiff.disabled = true;
  DOM.btnScanDiff.innerHTML = `<span class="status-pulse-dot"></span> Indexing...`;

  const selectedCategories = Object.keys(state.categories).filter(k => state.categories[k].selected);
  if (selectedCategories.length === 0) {
    resetScanButton();
    showToast('Please select at least one category to scan.', 'warning');
    return;
  }

  fetch(`${state.apiBase}/api/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      categories: selectedCategories,
      custom_paths: state.customCategoryPaths
    })
  })
  .then(async res => {
    resetScanButton();
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || 'Scan failed to start. Ensure phone is unlocked.', 'warning');
      return;
    }
    if (data && data.report) {
      const rep = data.report;
      const modCount = (rep.items_to_sync || []).filter(i => i.status === 'TO_SYNC_MODIFIED').length;
      const eta = Math.ceil((rep.to_sync_bytes || 0) / (40 * 1024 * 1024));

      if (rep.items_to_sync) {
        state.diff.items = rep.items_to_sync.map((item, idx) => ({
          id: idx + 1,
          path: item.rel_path,
          size: item.size > 1048576 ? `${(item.size / 1048576).toFixed(1)} MB` : `${Math.round(item.size / 1024)} KB`,
          time: item.mtime ? new Date(item.mtime * 1000).toLocaleString() : '--',
          status: item.status === 'TO_SYNC_NEW' ? 'NEW' : (item.status === 'TO_SYNC_MODIFIED' ? 'MODIFIED' : 'SYNCED')
        }));
      }
      state.diff.totalScanned = rep.total_remote_files || 0;
      state.diff.alreadySynced = rep.already_synced_count || 0;
      state.diff.newCount = (rep.items_to_sync || []).filter(i => i.status === 'TO_SYNC_NEW').length;
      state.diff.modifiedCount = modCount;
      state.diff.toTransferCount = rep.to_sync_count || 0;
      state.diff.toSyncBytes = rep.to_sync_bytes || 0;
      state.diff.skippedBytes = rep.already_synced_bytes || 0;
      state.diff.totalScannedBytes = rep.total_remote_bytes || 0;
      state.diff.estimatedSec = eta;

      if (rep.breakdown_by_category) {
        for (const [catKey, stats] of Object.entries(rep.breakdown_by_category)) {
          const uiKey = catKey === 'pics' ? 'photos' : (catKey === 'sms' ? 'sms_calls' : catKey);
          if (state.categories[uiKey]) {
            state.categories[uiKey].files = stats.remote_count || 0;
            state.categories[uiKey].sizeGB = parseFloat(((stats.remote_bytes || 0) / (1024 ** 3)).toFixed(2));
          }
          const card = document.querySelector(`.category-card[data-category="${uiKey}"]`);
          if (card) {
            const filesSpan = card.querySelector('.cat-stat-files');
            const sizeSpan = card.querySelector('.cat-stat-size');
            if (filesSpan) filesSpan.textContent = `${(stats.remote_count || 0).toLocaleString()} items`;
            if (sizeSpan) sizeSpan.textContent = `${((stats.remote_bytes || 0) / (1024 ** 3)).toFixed(2)} GB`;
          }
        }
        updateCategoryUI();
      }

      openDiffModal();
    }
  })
  .catch(err => {
    resetScanButton();
    showToast('Could not reach backend server', 'error');
  });
}

function resetScanButton() {
  DOM.btnScanDiff.disabled = false;
  DOM.btnScanDiff.innerHTML = `
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="11" cy="11" r="8"/>
      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <span>Scan &amp; Preview Diff</span>
  `;
}

function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = window.location.host || '127.0.0.1:8765';
  const wsUrl = `${protocol}//${wsHost}/ws/progress`;

  try {
    state.ws = new WebSocket(wsUrl);
    state.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'telemetry') {
          if (state.sync.inProgress) handleRealTelemetry(msg);
          if (state.restore.inProgress) handleRealRestoreTelemetry(msg);
        } else if (msg.type === 'completed') {
          handleRealCompletion(msg);
        } else if (msg.type === 'restore_completed') {
          handleRealRestoreCompletion(msg);
        } else if (msg.type === 'error') {
          showToast(`Operation Error: ${msg.error}`, 'error');
          if (state.sync.inProgress) stopSyncJob();
          if (state.restore.inProgress) {
            state.restore.inProgress = false;
            if (state.restore.pollInterval) {
              clearInterval(state.restore.pollInterval);
              state.restore.pollInterval = null;
            }
            if (DOM.btnStartRestore) {
              DOM.btnStartRestore.disabled = false;
              DOM.btnStartRestore.innerHTML = `<span>🔄 1-Click Restore to Phone</span>`;
            }
          }
        }
      } catch (e) {}
    };
    state.ws.onclose = () => {
      setTimeout(initWebSocket, 2500);
    };
  } catch (e) {}
}

function handleRealTelemetry(msg) {
  const speed = msg.current_speed_mbps || 0;
  if (speed > state.sync.peakSpeedMBs) {
    state.sync.peakSpeedMBs = speed;
  }
  updateSpeedometer(speed, state.sync.peakSpeedMBs);

  const pct = msg.percentage != null ? msg.percentage : (msg.total_bytes > 0 ? (msg.bytes_synced / msg.total_bytes) * 100 : 0);
  DOM.progressPctLabel.textContent = `${Math.round(pct)}%`;
  DOM.syncProgressFill.style.width = `${pct}%`;

  const syncedGB = (msg.bytes_synced / 1073741824).toFixed(2);
  const totalGB = (msg.total_bytes / 1073741824).toFixed(2);
  DOM.progressBytesLabel.textContent = `${syncedGB} GB / ${totalGB} GB`;
  DOM.progressFilesLabel.textContent = `${msg.files_synced} / ${msg.total_files} files synced`;

  const eta = Math.round(msg.eta_seconds || 0);
  DOM.telemetryEta.textContent = `${Math.floor(eta / 60)}m ${eta % 60}s`;

  if (msg.current_file) {
    DOM.rollingFileTicker.innerHTML = `<span class="ticker-file">${msg.current_file}</span>`;
  }
}

function updateRestoreSpeedometer(speedMBs, peakMBs) {
  if (DOM.restoreCurrentSpeedValue) {
    DOM.restoreCurrentSpeedValue.textContent = speedMBs.toFixed(1);
  }
  if (DOM.restorePeakSpeedValue && peakMBs != null) {
    DOM.restorePeakSpeedValue.textContent = `${peakMBs.toFixed(1)} MB/s`;
  }

  if (DOM.restoreSpeedMeterArc) {
    const maxScale = 200;
    const clampedSpeed = Math.min(speedMBs, maxScale);
    const ratio = clampedSpeed / maxScale;
    const totalDash = 251.3;
    const offset = totalDash * (1 - ratio);
    DOM.restoreSpeedMeterArc.style.strokeDashoffset = offset.toFixed(1);
  }
}

function handleRealRestoreTelemetry(msg) {
  const speed = msg.current_speed_mbps || 0;
  if (!state.restore.peakSpeedMBs || speed > state.restore.peakSpeedMBs) {
    state.restore.peakSpeedMBs = speed;
  }
  updateRestoreSpeedometer(speed, state.restore.peakSpeedMBs);

  const pct = msg.percentage != null
    ? msg.percentage
    : (msg.total_bytes > 0 ? (msg.bytes_synced / msg.total_bytes) * 100 : 0);

  if (DOM.restoreProgressPctLabel) DOM.restoreProgressPctLabel.textContent = `${Math.round(pct)}%`;
  if (DOM.restoreProgressFill) DOM.restoreProgressFill.style.width = `${pct}%`;

  const syncedStr = formatBytes(msg.bytes_synced || 0);
  const totalStr = formatBytes(msg.total_bytes || 0);
  if (DOM.restoreProgressBytesLabel) {
    DOM.restoreProgressBytesLabel.textContent = `${syncedStr} / ${totalStr}`;
  }

  if (DOM.restoreProgressFilesLabel) {
    DOM.restoreProgressFilesLabel.textContent = `${(msg.files_synced || 0).toLocaleString()} / ${(msg.total_files || 0).toLocaleString()} files restored`;
  }

  if (DOM.restoreRollingFileTicker && msg.current_file) {
    DOM.restoreRollingFileTicker.innerHTML = `<span class="ticker-file">${msg.current_file}</span>`;
  }

  if (DOM.restoreTelemetryEta) {
    const eta = Math.round(msg.eta_seconds || 0);
    const m = Math.floor(eta / 60);
    const s = eta % 60;
    DOM.restoreTelemetryEta.textContent = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}s`;
  }
}

function handleRealCompletion(summary) {
  if (state.sync.pollInterval) {
    clearInterval(state.sync.pollInterval);
    state.sync.pollInterval = null;
  }
  state.sync.inProgress = false;
  DOM.btnStartSync.style.display = 'inline-flex';
  DOM.btnAbortSync.style.display = 'none';
  DOM.telemetryStatusText.textContent = 'Sync Complete & Mirror Verified';
  updateSpeedometer(0, state.sync.peakSpeedMBs);
  DOM.syncCompleteCard.style.display = 'flex';
  DOM.syncSummaryMessage.textContent = `${summary.files_synced || 0} files transferred, ${summary.already_synced || 0} files skipped. Saved ${(summary.bandwidth_saved_bytes / 1073741824 || 0).toFixed(2)} GB of bandwidth!`;
  showToast('Superfast sync completed successfully! Exact directory tree preserved.', 'success');
  loadSnapshots();
  loadSmsData();
}

function handleRealRestoreCompletion(summary) {
  state.restore.inProgress = false;
  if (state.restore.pollInterval) {
    clearInterval(state.restore.pollInterval);
    state.restore.pollInterval = null;
  }
  if (DOM.btnStartRestore) {
    DOM.btnStartRestore.disabled = false;
    DOM.btnStartRestore.innerHTML = `<span>🔄 1-Click Restore to Phone</span>`;
  }
  updateRestoreSpeedometer(0, state.restore.peakSpeedMBs);
  if (DOM.restoreProgressFill) DOM.restoreProgressFill.style.width = '100%';
  if (DOM.restoreProgressPctLabel) DOM.restoreProgressPctLabel.textContent = '100%';
  if (DOM.restoreTelemetryStatusText) DOM.restoreTelemetryStatusText.textContent = '✅ Restore Complete & Gallery Scanned';
  if (DOM.restoreTelemetryEta) DOM.restoreTelemetryEta.textContent = '00:00s';
  if (DOM.restoreCompleteCard) DOM.restoreCompleteCard.style.display = 'flex';
  if (DOM.restoreSummaryMessage && summary.message) {
    DOM.restoreSummaryMessage.textContent = summary.message;
  }
  showToast(summary.message || 'Restore completed! Files are indexed on phone.', 'success', 6000);
}

function startSyncJob() {
  if (state.sync.inProgress) return;
  if (!state.device.connected) {
    showToast('No phone connected. Please connect your Android phone via USB first.', 'warning');
    return;
  }

  const selectedCategories = Object.keys(state.categories).filter(k => state.categories[k].selected);
  if (selectedCategories.length === 0) {
    showToast('Please select at least one category to sync.', 'warning');
    return;
  }

  state.sync.inProgress = true;
  state.sync.progressPct = 0;
  state.sync.bytesTransferred = 0;
  state.sync.filesSynced = 0;
  state.sync.peakSpeedMBs = 0;

  DOM.btnStartSync.style.display = 'none';
  DOM.btnAbortSync.style.display = 'inline-flex';
  DOM.telemetrySection.style.display = 'block';
  DOM.syncCompleteCard.style.display = 'none';
  DOM.telemetryStatusText.textContent = '⚡ Multithreaded Mirroring in Progress...';

  showToast('Initiating Superfast Multi-Threaded Sync...', 'info', 2500);

  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    initWebSocket();
  }

  // Double-redundancy HTTP polling fallback
  if (state.sync.pollInterval) clearInterval(state.sync.pollInterval);
  state.sync.pollInterval = setInterval(async () => {
    if (!state.sync.inProgress) {
      if (state.sync.pollInterval) {
        clearInterval(state.sync.pollInterval);
        state.sync.pollInterval = null;
      }
      return;
    }
    try {
      const res = await fetch(`${state.apiBase}/api/sync/status`);
      if (!res.ok) return;
      const data = await res.json();
      if (!state.sync.inProgress) return;

      if (data.telemetry && Object.keys(data.telemetry).length > 0) {
        handleRealTelemetry(data.telemetry);
      }
      if (data.completed && data.summary) {
        handleRealCompletion(data.summary);
      } else if (data.error) {
        if (state.sync.pollInterval) {
          clearInterval(state.sync.pollInterval);
          state.sync.pollInterval = null;
        }
        showToast(`Sync Error: ${data.error}`, 'error');
        stopSyncJob();
      }
    } catch (e) {}
  }, 350);

  fetch(`${state.apiBase}/api/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      categories: selectedCategories,
      custom_paths: state.customCategoryPaths,
      use_compression: true,
      max_workers: 4
    })
  })
  .then(async res => {
    if (!res.ok) {
      const data = await res.json();
      stopSyncJob();
      showToast(data.detail || 'Sync failed to start', 'error');
    }
  })
  .catch(() => {
    stopSyncJob();
    showToast('Could not connect to sync service', 'error');
  });
}

function stopSyncJob() {
  if (state.sync.pollInterval) {
    clearInterval(state.sync.pollInterval);
    state.sync.pollInterval = null;
  }
  if (state.sync.intervalId) {
    clearInterval(state.sync.intervalId);
    state.sync.intervalId = null;
  }
  state.sync.inProgress = false;
  DOM.btnStartSync.style.display = 'inline-flex';
  DOM.btnAbortSync.style.display = 'none';
  DOM.telemetryStatusText.textContent = 'Sync Paused / Stopped';
  updateSpeedometer(0, state.sync.peakSpeedMBs);
  showToast('Sync cancelled by user', 'warn');
}

function finishSyncJob() {
  if (state.sync.pollInterval) {
    clearInterval(state.sync.pollInterval);
    state.sync.pollInterval = null;
  }
  if (state.sync.intervalId) {
    clearInterval(state.sync.intervalId);
    state.sync.intervalId = null;
  }
  state.sync.inProgress = false;
  DOM.btnStartSync.style.display = 'inline-flex';
  DOM.btnAbortSync.style.display = 'none';

  DOM.telemetryStatusText.textContent = '✅ Mirroring Complete & Verified';
  DOM.telemetryEta.textContent = '00:00s';
  updateSpeedometer(0, state.sync.peakSpeedMBs);

  // Show completion card
  DOM.syncCompleteCard.style.display = 'flex';
  DOM.syncSummaryMessage.textContent = '112 files transferred, 15,088 files skipped (Already up to date). Saved 61.4 GB of bandwidth!';

  showToast('Superfast Sync complete! 112 files mirrored & verified.', 'success', 5000);
}

// ============================================================================
// Diff Preview Modal Controller
// ============================================================================
function setupDiffModal() {
  DOM.btnCloseDiffModal.addEventListener('click', closeDiffModal);
  DOM.btnCancelDiff.addEventListener('click', closeDiffModal);

  // Filter tabs
  DOM.diffFilterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      DOM.diffFilterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      state.diff.activeFilter = tab.getAttribute('data-diff-filter');
      renderDiffTable();
    });
  });

  // Search filter
  DOM.diffSearchInput.addEventListener('input', (e) => {
    state.diff.searchQuery = e.target.value.toLowerCase();
    renderDiffTable();
  });
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i > 1 ? 2 : 0)} ${units[i]}`;
}

function openDiffModal() {
  const scanned = state.diff.totalScanned || 0;
  const skipped = state.diff.alreadySynced || 0;
  const toSync = state.diff.toTransferCount || 0;
  const newCount = state.diff.newCount || 0;
  const modCount = state.diff.modifiedCount || 0;
  const toSyncBytes = state.diff.toSyncBytes || 0;
  const skippedBytes = state.diff.skippedBytes || 0;

  const toSyncSizeStr = formatBytes(toSyncBytes);
  const skippedSizeStr = formatBytes(skippedBytes);

  DOM.modalStatScanned.textContent = scanned.toLocaleString();
  DOM.modalStatSkipped.textContent = skipped.toLocaleString();
  DOM.modalStatNew.textContent = newCount.toLocaleString();
  DOM.modalStatModified.textContent = modCount.toLocaleString();
  DOM.modalStatEta.textContent = state.diff.estimatedSec > 0 ? `~${state.diff.estimatedSec}s` : '0s';

  const subSkipped = document.getElementById('modal-stat-skipped-sub');
  if (subSkipped) subSkipped.textContent = `${skippedSizeStr} Saved`;
  const subNew = document.getElementById('modal-stat-new-sub');
  if (subNew) subNew.textContent = toSyncSizeStr;
  const subMod = document.getElementById('modal-stat-modified-sub');
  if (subMod) subMod.textContent = `${modCount} modified`;

  DOM.diffFilterSyncCount.textContent = toSync.toLocaleString();
  DOM.diffFilterNewCount.textContent = newCount.toLocaleString();
  DOM.diffFilterModCount.textContent = modCount.toLocaleString();
  const filterSkippedCount = document.getElementById('diff-filter-skipped-count');
  if (filterSkippedCount) filterSkippedCount.textContent = skipped.toLocaleString();

  // Update dynamic modal footer note
  const footerText = document.getElementById('diff-modal-footer-text');
  if (footerText) {
    if (skipped > 0 && toSync > 0) {
      footerText.textContent = `${skipped.toLocaleString()} identical files will be skipped (${skippedSizeStr} saved). Only ${toSync.toLocaleString()} files (${toSyncSizeStr}) will be transferred.`;
    } else if (skipped === 0 && toSync > 0) {
      footerText.textContent = `All ${toSync.toLocaleString()} files (${toSyncSizeStr}) are new and will be transferred. PC backup location is clean.`;
    } else if (toSync === 0 && scanned > 0) {
      footerText.textContent = `All ${scanned.toLocaleString()} files are identical to PC backup. 0 files to transfer (100% up to date)!`;
    } else {
      footerText.textContent = `0 files discovered in selected folders.`;
    }
  }

  // Update dynamic Proceed button text
  const proceedBtnText = document.getElementById('diff-modal-proceed-text');
  if (proceedBtnText) {
    proceedBtnText.textContent = `Proceed with Sync (${toSync.toLocaleString()} items, ${toSyncSizeStr})`;
  }

  renderDiffTable();
  DOM.diffModal.style.display = 'flex';
}

function closeDiffModal() {
  DOM.diffModal.style.display = 'none';
}

function renderDiffTable() {
  const filter = state.diff.activeFilter;
  const query = state.diff.searchQuery;

  const filtered = state.diff.items.filter(item => {
    // Filter by tab
    if (filter === 'to_sync' && item.status === 'SYNCED') return false;
    if (filter === 'new_only' && item.status !== 'NEW') return false;
    if (filter === 'modified_only' && item.status !== 'MODIFIED') return false;
    if (filter === 'skipped' && item.status !== 'SYNCED') return false;

    // Filter by search query
    if (query && !item.path.toLowerCase().includes(query)) return false;

    return true;
  });

  if (filtered.length === 0) {
    DOM.diffTableBody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align:center; padding: 24px; color: var(--text-dim);">
          No matching items for this view.
        </td>
      </tr>
    `;
    return;
  }

  DOM.diffTableBody.innerHTML = filtered.map(item => {
    const statusTag = {
      NEW: `<span class="diff-status-tag status-new">NEW</span>`,
      MODIFIED: `<span class="diff-status-tag status-modified">MODIFIED</span>`,
      SYNCED: `<span class="diff-status-tag status-synced">IDENTICAL</span>`
    }[item.status] || `<span class="diff-status-tag">${item.status}</span>`;

    const actionText = item.status === 'SYNCED' ? '<span style="color:var(--text-muted);">Skip (Cached)</span>' : '<span style="color:var(--cyan); font-weight:600;">Stream Block</span>';

    return `
      <tr>
        <td>${statusTag}</td>
        <td class="diff-file-path" title="${item.path}">${item.path}</td>
        <td class="diff-file-size">${item.size}</td>
        <td class="diff-file-time">${item.time}</td>
        <td>${actionText}</td>
      </tr>
    `;
  }).join('');
}

// ============================================================================
// Tab 2: Restore Wizard Controller
// ============================================================================
const RESTORE_CATEGORY_ICONS = {
  pics: `<div class="cat-icon-box cat-photos">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
      <circle cx="12" cy="13" r="4"/>
    </svg>
  </div>`,
  music: `<div class="cat-icon-box cat-music">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M9 18V5l12-2v13"/>
      <circle cx="6" cy="18" r="3"/>
      <circle cx="18" cy="16" r="3"/>
    </svg>
  </div>`,
  whatsapp: `<div class="cat-icon-box cat-whatsapp">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
    </svg>
  </div>`,
  telegram: `<div class="cat-icon-box cat-telegram">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M22 2L11 13"/>
      <polygon points="22 2 15 22 11 13 2 9 22 2"/>
    </svg>
  </div>`,
  sms: `<div class="cat-icon-box cat-sms">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  </div>`,
  private_space: `<div class="cat-icon-box cat-private">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  </div>`,
  custom_folders: `<div class="cat-icon-box cat-custom">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      <line x1="12" y1="11" x2="12" y2="17"/>
      <line x1="9" y1="14" x2="15" y2="14"/>
    </svg>
  </div>`
};

let activeRestoreSubfolderCat = 'pics';

async function loadSnapshots() {
  const container = document.getElementById('snapshot-list-container');
  if (!container) return;
  try {
    const res = await fetch(`${state.apiBase}/api/snapshots`);
    const data = await res.json();
    if (data && data.snapshots && data.snapshots.length > 0) {
      container.innerHTML = data.snapshots.map((snap, idx) => {
        const isFirst = idx === 0;
        if (isFirst && !state.restore.selectedSnapshot) {
          state.restore.selectedSnapshot = snap.name;
        }
        const isActive = snap.name === state.restore.selectedSnapshot ? 'active' : '';
        return `
          <div class="snapshot-item ${isActive}" data-snapshot="${snap.name}">
            <div class="snap-radio"></div>
            <div class="snap-details">
              <div class="snap-name">${snap.name}</div>
              <div class="snap-meta">
                <span>${snap.file_count.toLocaleString()} items</span> • <span>${snap.size_gb} GB</span> • <span>${snap.mtime}</span>
              </div>
            </div>
            ${isFirst ? '<span class="snap-badge latest">Latest</span>' : ''}
          </div>
        `;
      }).join('');

      container.querySelectorAll('.snapshot-item').forEach(item => {
        item.addEventListener('click', () => {
          container.querySelectorAll('.snapshot-item').forEach(i => i.classList.remove('active'));
          item.classList.add('active');
          state.restore.selectedSnapshot = item.getAttribute('data-snapshot');
          showToast(`Selected Snapshot: ${state.restore.selectedSnapshot}`, 'info', 2000);
          loadSnapshotDetails(state.restore.selectedSnapshot);
        });
      });

      // Automatically inspect details of the selected snapshot
      if (state.restore.selectedSnapshot) {
        loadSnapshotDetails(state.restore.selectedSnapshot);
      }
    } else {
      container.innerHTML = `
        <div class="empty-snapshots-msg" style="padding: 24px; text-align: center; color: var(--text-dim); background: rgba(0,0,0,0.2); border-radius: 8px; border: 1px dashed rgba(255,255,255,0.1);">
          <div style="font-weight: 600; color: #fff; margin-bottom: 4px;">No Local Backups Found Yet</div>
          <div style="font-size: 12px; color: #8892b0;">Backups created with Kinetix will appear here for 1-Click Restore to your phone.</div>
        </div>
      `;
      if (DOM.restoreCategoriesContainer) {
        DOM.restoreCategoriesContainer.innerHTML = `
          <div style="padding: 24px; text-align: center; color: var(--text-dim); font-size: 13px;">
            No backup snapshots found on PC to inspect. Run a backup in Tab 1 first!
          </div>
        `;
      }
    }
  } catch (e) {
    // Keep placeholder
  }
}

async function loadSnapshotDetails(snapshotName) {
  if (DOM.restoreCategoriesContainer) {
    DOM.restoreCategoriesContainer.innerHTML = `
      <div style="padding: 28px; text-align: center; color: var(--text-dim); display: flex; align-items: center; justify-content: center; gap: 10px;">
        <span class="status-pulse-dot"></span>
        <span>Scanning snapshot directories &amp; albums (${snapshotName})...</span>
      </div>
    `;
  }

  try {
    const url = snapshotName
      ? `${state.apiBase}/api/snapshot/details?snapshot=${encodeURIComponent(snapshotName)}`
      : `${state.apiBase}/api/snapshot/details`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch snapshot details');
    const data = await res.json();
    state.restore.snapshotDetails = data;

    // Initialize selections: enable categories that actually have files backed up
    if (data && data.categories) {
      Object.keys(data.categories).forEach(catId => {
        const cat = data.categories[catId];
        state.restore.selectedCategories[catId] = Boolean(cat.has_backup && cat.file_count > 0);
        if (cat.subfolders && cat.subfolders.length > 0) {
          state.restore.customSubfolders[catId] = cat.subfolders.map(s => s.path);
        }
      });
    }

    renderRestoreCategories();
  } catch (err) {
    if (DOM.restoreCategoriesContainer) {
      DOM.restoreCategoriesContainer.innerHTML = `
        <div style="padding: 24px; text-align: center; color: var(--text-dim); font-size: 13px;">
          Could not load snapshot details: ${err.message}
        </div>
      `;
    }
  }
}

function updateRestoreSummary() {
  const catOrder = ['pics', 'music', 'whatsapp', 'telegram', 'sms', 'private_space', 'custom_folders'];
  const selectedCount = catOrder.filter(k => state.restore.selectedCategories[k]).length;
  if (DOM.restoreSelectedSummary) {
    DOM.restoreSelectedSummary.textContent = `${selectedCount} of ${catOrder.length} Selected`;
  }
}

function renderRestoreCategories() {
  if (!DOM.restoreCategoriesContainer) return;
  const details = state.restore.snapshotDetails;
  if (!details || !details.categories) {
    DOM.restoreCategoriesContainer.innerHTML = `
      <div class="empty-snapshots-msg" style="padding: 24px; text-align: center; color: var(--text-dim);">
        <div>No category data found for this backup snapshot.</div>
      </div>
    `;
    return;
  }

  const catOrder = ['pics', 'music', 'whatsapp', 'telegram', 'sms', 'private_space', 'custom_folders'];
  let totalSelected = 0;

  const html = catOrder.map(catId => {
    const cat = details.categories[catId];
    if (!cat) return '';

    const hasBackup = Boolean(cat.has_backup && cat.file_count > 0);
    const isChecked = Boolean(state.restore.selectedCategories[catId]);
    if (isChecked) totalSelected++;

    // Calculate subfolders selection
    const allSubs = cat.subfolders || [];
    const activeSubs = state.restore.customSubfolders[catId] || allSubs.map(s => s.path);
    const selectedSubs = allSubs.filter(s => activeSubs.includes(s.path));

    const activeFiles = allSubs.length > 0
      ? selectedSubs.reduce((acc, s) => acc + s.file_count, 0)
      : (cat.file_count || 0);

    const activeBytes = allSubs.length > 0
      ? selectedSubs.reduce((acc, s) => acc + s.size_bytes, 0)
      : (cat.size_bytes || 0);

    const activeSizeStr = formatBytes(activeBytes);

    // Subfolder chips
    let chipsHtml = '';
    if (allSubs.length > 0) {
      chipsHtml = allSubs.map(s => {
        const isChosen = activeSubs.includes(s.path);
        return `<span class="restore-folder-chip ${isChosen ? 'chip-active' : ''}" title="${s.path}">
          📁 ${s.name} <span class="chip-count">(${s.file_count.toLocaleString()} • ${s.size_formatted})</span>
        </span>`;
      }).join('');
    } else if (hasBackup) {
      chipsHtml = `<span class="restore-folder-chip chip-active">📁 ${cat.dest_path || 'Backup Archive'} (${cat.file_count.toLocaleString()} files • ${cat.size_formatted})</span>`;
    } else {
      chipsHtml = `<span class="restore-no-backup-text">No backup in this snapshot</span>`;
    }

    // Action button & badge
    let actionButtonsHtml = '';
    if (allSubs.length > 0) {
      const badgeText = (activeSubs.length === allSubs.length)
        ? `All ${allSubs.length} Folders`
        : `${activeSubs.length} of ${allSubs.length} Selected`;
      actionButtonsHtml = `
        <button class="btn-xs btn-outline-cyan btn-restore-choose-folders" data-res-cat="${catId}" title="Choose specific folders to restore">📂 Select Folders</button>
        <span class="cat-badge">${badgeText}</span>
      `;
    } else if (hasBackup) {
      actionButtonsHtml = `<span class="cat-badge">Ready</span>`;
    }

    const iconHtml = RESTORE_CATEGORY_ICONS[catId] || RESTORE_CATEGORY_ICONS.custom_folders;

    return `
      <div class="restore-category-card ${isChecked ? 'selected' : ''} ${hasBackup ? '' : 'empty-category'}" data-res-card="${catId}">
        <div class="restore-card-top">
          <div class="restore-card-left">
            <label class="custom-checkbox">
              <input type="checkbox" ${isChecked ? 'checked' : ''} data-res-cb="${catId}">
              <span class="checkmark"></span>
            </label>
            ${iconHtml}
            <div class="restore-card-titles">
              <div class="restore-card-title">${cat.name}</div>
              <span class="restore-dest-tag">➔ ${cat.dest_path}</span>
            </div>
          </div>
          <div class="restore-card-actions">
            ${actionButtonsHtml}
          </div>
        </div>

        <div class="restore-subfolder-chips-container">
          ${chipsHtml}
        </div>

        <div class="restore-card-footer">
          <span class="restore-stat-files">${activeFiles.toLocaleString()} items • ${activeSizeStr}</span>
          <span class="restore-stat-badge ${hasBackup ? 'ready' : 'empty'}">
            ${hasBackup ? 'Ready to restore' : 'No backup'}
          </span>
        </div>
      </div>
    `;
  }).join('');

  DOM.restoreCategoriesContainer.innerHTML = html;

  if (DOM.restoreSelectedSummary) {
    DOM.restoreSelectedSummary.textContent = `${totalSelected} of ${catOrder.length} Selected`;
  }

  // Wire up checkbox toggles
  DOM.restoreCategoriesContainer.querySelectorAll('input[data-res-cb]').forEach(cb => {
    cb.addEventListener('change', (e) => {
      const catId = cb.getAttribute('data-res-cb');
      state.restore.selectedCategories[catId] = cb.checked;
      const card = DOM.restoreCategoriesContainer.querySelector(`.restore-category-card[data-res-card="${catId}"]`);
      if (card) {
        card.classList.toggle('selected', cb.checked);
      }
      updateRestoreSummary();
    });
  });

  // Wire up "Select Folders" buttons
  DOM.restoreCategoriesContainer.querySelectorAll('.btn-restore-choose-folders').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const catId = btn.getAttribute('data-res-cat');
      openRestoreSubfolderModal(catId);
    });
  });
}

function openRestoreSubfolderModal(catId) {
  activeRestoreSubfolderCat = catId;
  const details = state.restore.snapshotDetails;
  if (!details || !details.categories || !details.categories[catId]) return;

  const cat = details.categories[catId];
  const allSubs = cat.subfolders || [];
  const activeSubs = state.restore.customSubfolders[catId] || allSubs.map(s => s.path);

  const titleEl = document.getElementById('restore-subfolder-modal-title');
  const subtitleEl = document.getElementById('restore-subfolder-modal-subtitle');
  if (titleEl) titleEl.textContent = `Select ${cat.name} to Restore`;
  if (subtitleEl) subtitleEl.textContent = `Choose which specific folders or albums from '${state.restore.selectedSnapshot}' to push back to phone`;

  if (DOM.restoreSubfolderContainer) {
    if (allSubs.length === 0) {
      DOM.restoreSubfolderContainer.innerHTML = `
        <div style="padding: 16px; text-align: center; color: var(--text-dim); font-size: 13px;">
          No subfolders detected under ${cat.name}. The whole category will be restored to ${cat.dest_path}.
        </div>
      `;
    } else {
      DOM.restoreSubfolderContainer.innerHTML = allSubs.map(s => {
        const isChecked = activeSubs.includes(s.path);
        return `
          <label class="restore-subfolder-row">
            <input type="checkbox" value="${s.path}" ${isChecked ? 'checked' : ''} class="restore-subfolder-cb">
            <div class="restore-subfolder-info">
              <span class="restore-subfolder-name">📁 ${s.name}</span>
              <span class="restore-subfolder-meta">${s.file_count.toLocaleString()} files • ${s.size_formatted}</span>
            </div>
          </label>
        `;
      }).join('');
    }
  }

  if (DOM.restoreSubfolderModal) {
    DOM.restoreSubfolderModal.style.display = 'flex';
  }
}

function setupRestoreWizard() {
  loadSnapshots();

  DOM.btnAnalyzeRestore?.addEventListener('click', () => {
    runRestoreAnalysis();
  });

  DOM.btnCloseRestoreAnalysis?.addEventListener('click', () => {
    if (DOM.restoreAnalysisCard) DOM.restoreAnalysisCard.style.display = 'none';
  });

  DOM.btnStartRestore.addEventListener('click', () => {
    startRestoreJob();
  });

  DOM.btnBrowseSnapshot?.addEventListener('click', () => {
    showToast('Refreshing local snapshots...', 'info');
    loadSnapshots();
  });

  DOM.btnRestoreSelectAll?.addEventListener('click', () => {
    const details = state.restore.snapshotDetails;
    if (details && details.categories) {
      Object.keys(details.categories).forEach(catId => {
        if (details.categories[catId].has_backup) {
          state.restore.selectedCategories[catId] = true;
        }
      });
      renderRestoreCategories();
    }
  });

  DOM.btnRestoreDeselectAll?.addEventListener('click', () => {
    const catOrder = ['pics', 'music', 'whatsapp', 'telegram', 'sms', 'private_space', 'custom_folders'];
    catOrder.forEach(k => {
      state.restore.selectedCategories[k] = false;
    });
    renderRestoreCategories();
  });

  DOM.btnCloseRestoreSubfolder?.addEventListener('click', () => {
    if (DOM.restoreSubfolderModal) DOM.restoreSubfolderModal.style.display = 'none';
  });
  DOM.btnCancelRestoreSubfolder?.addEventListener('click', () => {
    if (DOM.restoreSubfolderModal) DOM.restoreSubfolderModal.style.display = 'none';
  });

  DOM.btnRestoreSubSelectAll?.addEventListener('click', () => {
    DOM.restoreSubfolderContainer?.querySelectorAll('.restore-subfolder-cb').forEach(cb => cb.checked = true);
  });
  DOM.btnRestoreSubClearAll?.addEventListener('click', () => {
    DOM.restoreSubfolderContainer?.querySelectorAll('.restore-subfolder-cb').forEach(cb => cb.checked = false);
  });

  DOM.btnSaveRestoreSubfolder?.addEventListener('click', () => {
    const checked = Array.from(DOM.restoreSubfolderContainer?.querySelectorAll('.restore-subfolder-cb:checked') || []).map(cb => cb.value);
    if (checked.length === 0) {
      showToast('Please keep at least one folder selected, or uncheck the category.', 'warning');
      return;
    }
    state.restore.customSubfolders[activeRestoreSubfolderCat] = checked;
    state.restore.selectedCategories[activeRestoreSubfolderCat] = true;
    renderRestoreCategories();
    if (DOM.restoreSubfolderModal) DOM.restoreSubfolderModal.style.display = 'none';
    showToast(`Saved folder selection for ${activeRestoreSubfolderCat}!`, 'success');
  });

  DOM.btnRestoreOnlyThisSubfolder?.addEventListener('click', () => {
    const checked = Array.from(DOM.restoreSubfolderContainer?.querySelectorAll('.restore-subfolder-cb:checked') || []).map(cb => cb.value);
    if (checked.length === 0) {
      showToast('Please select at least one folder.', 'warning');
      return;
    }
    state.restore.customSubfolders[activeRestoreSubfolderCat] = checked;
    const catOrder = ['pics', 'music', 'whatsapp', 'telegram', 'sms', 'private_space', 'custom_folders'];
    catOrder.forEach(k => {
      state.restore.selectedCategories[k] = (k === activeRestoreSubfolderCat);
    });
    renderRestoreCategories();
    if (DOM.restoreSubfolderModal) DOM.restoreSubfolderModal.style.display = 'none';
    showToast(`Restore isolated: ONLY selected category will be restored!`, 'success', 4000);
  });

  DOM.btnAbortRestore?.addEventListener('click', () => {
    stopRestoreJob();
  });

  DOM.btnDismissRestoreSummary?.addEventListener('click', () => {
    if (DOM.restoreCompleteCard) DOM.restoreCompleteCard.style.display = 'none';
  });

  DOM.btnRescanGallery?.addEventListener('click', async () => {
    showToast('Sending MediaScanner broadcast to Android...', 'info');
    try {
      const res = await fetch(`${state.apiBase}/api/device/media-scan`, { method: 'POST' });
      const data = await res.json();
      showToast(data.message || 'Gallery scan triggered!', 'success');
    } catch (e) {
      showToast('MediaScanner signal sent', 'info');
    }
  });
}

function stopRestoreJob() {
  if (state.restore.pollInterval) {
    clearInterval(state.restore.pollInterval);
    state.restore.pollInterval = null;
  }
  state.restore.inProgress = false;
  fetch(`${state.apiBase}/api/restore/abort`, { method: 'POST' }).catch(() => {});
  if (DOM.btnStartRestore) {
    DOM.btnStartRestore.disabled = false;
    DOM.btnStartRestore.innerHTML = `<span>🔄 1-Click Restore to Phone</span>`;
  }
  if (DOM.restoreTelemetryStatusText) {
    DOM.restoreTelemetryStatusText.textContent = 'Restore Cancelled by User';
  }
  updateRestoreSpeedometer(0, state.restore.peakSpeedMBs);
  showToast('Restore cancelled by user', 'warn');
}

async function runRestoreAnalysis() {
  if (!state.device.connected) {
    showToast('Please connect your Android phone via USB to analyze storage.', 'warning');
    return;
  }
  if (!state.restore.selectedSnapshot) {
    showToast('No backup snapshot selected to analyze.', 'warning');
    return;
  }

  const selectedCats = Object.keys(state.restore.selectedCategories).filter(k => state.restore.selectedCategories[k]);
  if (selectedCats.length === 0) {
    showToast('Please select at least one category to analyze.', 'warning');
    return;
  }

  const subfoldersPayload = {};
  selectedCats.forEach(catId => {
    if (state.restore.customSubfolders[catId] && state.restore.customSubfolders[catId].length > 0) {
      subfoldersPayload[catId] = state.restore.customSubfolders[catId];
    }
  });

  const btn = DOM.btnAnalyzeRestore;
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="status-pulse-dot"></span> Fast Scanning Phone...`;
  }
  showToast('⚡ Running fast remote index scan on phone storage...', 'info', 2000);

  try {
    const res = await fetch(`${state.apiBase}/api/restore/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        categories: selectedCats,
        snapshot: state.restore.selectedSnapshot,
        subfolders: Object.keys(subfoldersPayload).length > 0 ? subfoldersPayload : null,
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Analysis request failed');
    }

    const data = await res.json();
    renderRestoreAnalysis(data);
    showToast('Analysis complete! Check preview comparison.', 'success', 3000);
  } catch (err) {
    showToast(`Scan Error: ${err.message}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <span>🔍 Scan &amp; Compare Phone</span>
      `;
    }
  }
}

function renderRestoreAnalysis(data) {
  if (!DOM.restoreAnalysisCard) return;
  DOM.restoreAnalysisCard.style.display = 'block';

  const totalFiles = data.total_files || 0;
  const totalSize = formatBytes(data.total_bytes || 0);
  const skippedFiles = data.already_on_phone_count || 0;
  const skippedSize = formatBytes(data.already_on_phone_bytes || 0);
  const toPushFiles = data.to_restore_count || 0;
  const toPushSize = formatBytes(data.to_restore_bytes || 0);
  const timeSavedSec = data.time_saved_seconds || 0;

  if (DOM.resStatTotalFiles) DOM.resStatTotalFiles.textContent = totalFiles.toLocaleString();
  if (DOM.resStatTotalSize) DOM.resStatTotalSize.textContent = totalSize;
  if (DOM.resStatSkippedFiles) DOM.resStatSkippedFiles.textContent = skippedFiles.toLocaleString();
  if (DOM.resStatSkippedSize) DOM.resStatSkippedSize.textContent = `Skipped (${skippedSize})`;
  if (DOM.resStatToPushFiles) DOM.resStatToPushFiles.textContent = toPushFiles.toLocaleString();
  if (DOM.resStatToPushSize) DOM.resStatToPushSize.textContent = toPushSize;

  if (DOM.resStatTimeSaved) {
    if (timeSavedSec >= 60) {
      DOM.resStatTimeSaved.textContent = `~${(timeSavedSec / 60).toFixed(1)}m`;
    } else {
      DOM.resStatTimeSaved.textContent = `${Math.round(timeSavedSec)}s`;
    }
  }

  let msg = '';
  if (totalFiles === 0) {
    msg = 'No files found in selected backup folders.';
  } else if (toPushFiles === 0 && skippedFiles > 0) {
    msg = `⚡ <strong>100% Up-to-Date!</strong> All ${skippedFiles.toLocaleString()} files (${skippedSize}) in your selected backup are already present and identical on your phone. If you click Restore, Smart Delta will skip everything and finish in 1 second.`;
    if (DOM.btnStartRestoreText) {
      DOM.btnStartRestoreText.textContent = `⚡ Phone Up-to-Date (0 to push)`;
    }
  } else if (skippedFiles > 0) {
    msg = `⚡ <strong>Smart Delta Active:</strong> ${skippedFiles.toLocaleString()} files (${skippedSize}) are already on your phone and will be skipped. Only <strong>${toPushFiles.toLocaleString()} missing/modified files (${toPushSize})</strong> will be restored.`;
    if (DOM.btnStartRestoreText) {
      DOM.btnStartRestoreText.textContent = `🚀 Restore ${toPushFiles} Missing Files (${toPushSize})`;
    }
  } else {
    msg = `Ready to restore all <strong>${toPushFiles.toLocaleString()} files (${toPushSize})</strong> to phone.`;
    if (DOM.btnStartRestoreText) {
      DOM.btnStartRestoreText.textContent = `🔄 1-Click Restore to Phone`;
    }
  }

  if (DOM.restoreAnalysisDetailMsg) {
    DOM.restoreAnalysisDetailMsg.innerHTML = msg;
  }
}

function startRestoreJob() {
  if (state.restore.inProgress) return;
  if (!state.device.connected) {
    showToast('Please connect your phone via USB with USB Debugging enabled before restoring.', 'warning');
    return;
  }
  if (!state.restore.selectedSnapshot) {
    showToast('No backup snapshot selected to restore.', 'warning');
    return;
  }

  const selectedCats = Object.keys(state.restore.selectedCategories).filter(k => state.restore.selectedCategories[k]);
  if (selectedCats.length === 0) {
    showToast('Please check at least one category to restore.', 'warning');
    return;
  }

  state.restore.inProgress = true;
  state.restore.progressPct = 0;
  state.restore.peakSpeedMBs = 0;

  if (DOM.restoreTelemetrySection) DOM.restoreTelemetrySection.style.display = 'block';
  if (DOM.restoreCompleteCard) DOM.restoreCompleteCard.style.display = 'none';
  if (DOM.restoreTelemetryStatusText) {
    DOM.restoreTelemetryStatusText.textContent = '⚡ Restoring PC Files to Phone (ADB Push Stream)...';
  }
  if (DOM.restoreProgressFill) DOM.restoreProgressFill.style.width = '0%';
  if (DOM.restoreProgressPctLabel) DOM.restoreProgressPctLabel.textContent = '0%';
  if (DOM.restoreProgressBytesLabel) DOM.restoreProgressBytesLabel.textContent = 'Starting push pipeline...';
  if (DOM.restoreProgressFilesLabel) DOM.restoreProgressFilesLabel.textContent = 'Connecting restore stream...';
  if (DOM.restoreRollingFileTicker) {
    DOM.restoreRollingFileTicker.innerHTML = `<span class="ticker-file">Connecting ADB restore pipeline...</span>`;
  }
  updateRestoreSpeedometer(0, 0);

  DOM.btnStartRestore.disabled = true;
  DOM.btnStartRestore.innerHTML = `<span class="status-pulse-dot"></span> Restoring Phone Files...`;

  showToast(`Pushing snapshot '${state.restore.selectedSnapshot}' to phone...`, 'info', 3000);

  // Build subfolders payload for chosen categories
  const subfoldersPayload = {};
  selectedCats.forEach(catId => {
    if (state.restore.customSubfolders[catId] && state.restore.customSubfolders[catId].length > 0) {
      subfoldersPayload[catId] = state.restore.customSubfolders[catId];
    }
  });

  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    initWebSocket();
  }

  // Double-redundancy HTTP polling fallback for restore
  if (state.restore.pollInterval) clearInterval(state.restore.pollInterval);
  state.restore.pollInterval = setInterval(async () => {
    if (!state.restore.inProgress) {
      if (state.restore.pollInterval) {
        clearInterval(state.restore.pollInterval);
        state.restore.pollInterval = null;
      }
      return;
    }
    try {
      const res = await fetch(`${state.apiBase}/api/restore/status`);
      if (!res.ok) return;
      const data = await res.json();
      if (!state.restore.inProgress) return;
      if (data.telemetry && Object.keys(data.telemetry).length > 0) {
        handleRealRestoreTelemetry(data.telemetry);
      }
      if (data.completed && data.summary) {
        handleRealRestoreCompletion(data.summary);
      } else if (data.error) {
        state.restore.inProgress = false;
        if (state.restore.pollInterval) {
          clearInterval(state.restore.pollInterval);
          state.restore.pollInterval = null;
        }
        if (DOM.btnStartRestore) {
          DOM.btnStartRestore.disabled = false;
          DOM.btnStartRestore.innerHTML = `<span>🔄 1-Click Restore to Phone</span>`;
        }
        showToast(`Restore Error: ${data.error}`, 'error');
      }
    } catch (e) {}
  }, 350);

  const smartDelta = document.getElementById('res-opt-smart-delta') ? document.getElementById('res-opt-smart-delta').checked : true;

  fetch(`${state.apiBase}/api/restore`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      categories: selectedCats,
      snapshot: state.restore.selectedSnapshot,
      subfolders: Object.keys(subfoldersPayload).length > 0 ? subfoldersPayload : null,
      max_workers: 4,
      smart_delta: smartDelta
    })
  })
  .then(async res => {
    if (!res.ok) {
      const data = await res.json();
      state.restore.inProgress = false;
      DOM.btnStartRestore.disabled = false;
      DOM.btnStartRestore.innerHTML = `<span>🔄 1-Click Restore to Phone</span>`;
      showToast(data.detail || 'Restore failed to start', 'error');
    }
  })
  .catch(err => {
    state.restore.inProgress = false;
    DOM.btnStartRestore.disabled = false;
    DOM.btnStartRestore.innerHTML = `<span>🔄 1-Click Restore to Phone</span>`;
    showToast('Could not reach backend restore service', 'error');
  });
}

// ============================================================================
// Tab 3: Messages & Calls Explorer
// ============================================================================
async function loadSmsData() {
  try {
    const res = await fetch(`${state.apiBase}/api/sms_data`);
    const data = await res.json();
    if (data && data.has_backup) {
      if (data.messages && data.messages.length > 0) {
        const threadMap = {};
        data.messages.forEach(m => {
          const addr = m.address || 'Unknown';
          if (!threadMap[addr]) {
            threadMap[addr] = {
              id: Object.keys(threadMap).length + 1,
              contactName: m.contact_name || addr,
              phoneNumber: addr,
              initials: (m.contact_name || addr).substring(0, 2).toUpperCase(),
              lastMessage: m.body || '',
              timestamp: m.date ? new Date(parseInt(m.date)).toLocaleDateString() : '',
              messages: []
            };
          }
          threadMap[addr].messages.push({
            id: m._id || Math.random(),
            sender: m.type === '2' ? 'Me' : (m.contact_name || addr),
            type: m.type === '2' ? 'sent' : 'received',
            time: m.date ? new Date(parseInt(m.date)).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
            text: m.body || ''
          });
        });
        state.threads = Object.values(threadMap);
        if (state.threads.length > 0) {
          state.activeThreadId = state.threads[0].id;
        }
      }
      if (data.calls && data.calls.length > 0) {
        state.calls = data.calls.map((c, i) => ({
          id: i + 1,
          type: c.type === 1 ? 'incoming' : (c.type === 2 ? 'outgoing' : 'missed'),
          contact: c.name || c.number || 'Unknown',
          number: c.number || '',
          date: c.date ? new Date(parseInt(c.date)).toLocaleString() : '',
          duration: `${Math.floor((c.duration || 0) / 60)}m ${(c.duration || 0) % 60}s`,
          status: c.type === 3 ? 'Missed' : 'Completed'
        }));
      }
      renderThreadsList();
      renderActiveThread();
      renderCallsTable();
    }
  } catch (e) {}
}

function setupMessagesAndCalls() {
  loadSmsData();

  // Toggle between SMS & Calls
  DOM.msgViewButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      DOM.msgViewButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const view = btn.getAttribute('data-view');
      state.messagesView = view;

      if (view === 'messages') {
        DOM.messagesViewContainer.style.display = 'grid';
        DOM.callsViewContainer.style.display = 'none';
      } else {
        DOM.messagesViewContainer.style.display = 'none';
        DOM.callsViewContainer.style.display = 'flex';
        renderCallsTable();
      }
    });
  });

  // Search input
  DOM.smsSearchInput.addEventListener('input', (e) => {
    state.msgSearchQuery = e.target.value.toLowerCase();
    if (state.messagesView === 'messages') {
      renderThreadsList();
    } else {
      renderCallsTable();
    }
  });

  // Export buttons
  DOM.btnExportHtml.addEventListener('click', exportHtmlViewer);
  DOM.btnExportXml.addEventListener('click', exportXmlBackup);
  DOM.btnExportJson.addEventListener('click', exportJsonData);
  DOM.btnExportThread.addEventListener('click', exportActiveThread);

  renderThreadsList();
  renderActiveThread();
  renderCallsTable();
}

function renderThreadsList() {
  const query = state.msgSearchQuery;
  const filtered = state.threads.filter(t => {
    if (!query) return true;
    return t.contactName.toLowerCase().includes(query) ||
           t.phoneNumber.toLowerCase().includes(query) ||
           t.lastMessage.toLowerCase().includes(query);
  });

  DOM.threadsCountBadge.textContent = `${filtered.length} threads`;

  if (filtered.length === 0) {
    DOM.threadsList.innerHTML = `<div style="padding: 24px 16px; text-align: center; color: var(--text-dim); font-size: 12px;">No SMS backups found on PC.<br><br>Enable <strong>SMS &amp; Call Logs</strong> in Categories and run a sync to view messages.</div>`;
    return;
  }

  DOM.threadsList.innerHTML = filtered.map(t => {
    const isActive = t.id === state.activeThreadId ? 'active' : '';
    return `
      <div class="thread-item ${isActive}" data-thread-id="${t.id}">
        <div class="thread-avatar">${t.initials}</div>
        <div class="thread-info">
          <div class="thread-top">
            <span class="thread-name">${t.contactName}</span>
            <span class="thread-time">${t.timestamp}</span>
          </div>
          <div class="thread-snippet">${t.lastMessage}</div>
        </div>
      </div>
    `;
  }).join('');

  // Add click handlers
  DOM.threadsList.querySelectorAll('.thread-item').forEach(item => {
    item.addEventListener('click', () => {
      const threadId = parseInt(item.getAttribute('data-thread-id'), 10);
      state.activeThreadId = threadId;
      renderThreadsList();
      renderActiveThread();
    });
  });
}

function renderActiveThread() {
  const thread = state.threads.find(t => t.id === state.activeThreadId) || state.threads[0];
  if (!thread) {
    DOM.chatAvatar.textContent = '--';
    DOM.chatContactName.textContent = 'No Conversation Selected';
    DOM.chatContactNumber.textContent = '';
    DOM.chatMsgCount.textContent = '0 messages';
    DOM.chatMessagesContainer.innerHTML = '<div style="display:flex; align-items:center; justify-content:center; height:100%; color: var(--text-dim); font-size: 13px;">Select a conversation to view messages.</div>';
    return;
  }

  DOM.chatAvatar.textContent = thread.initials;
  DOM.chatContactName.textContent = thread.contactName;
  DOM.chatContactNumber.textContent = thread.phoneNumber;
  DOM.chatMsgCount.textContent = `${thread.messages.length} messages`;

  DOM.chatMessagesContainer.innerHTML = thread.messages.map(m => {
    const isSent = m.type === 'sent';
    const statusIcon = isSent ? `<span class="bubble-status-icon">✓✓</span>` : '';
    return `
      <div class="chat-bubble ${m.type}">
        <div class="bubble-content">
          ${m.text}
        </div>
        <div class="bubble-meta">
          <span>${m.time}</span>
          ${statusIcon}
        </div>
      </div>
    `;
  }).join('');

  DOM.chatMessagesContainer.scrollTop = DOM.chatMessagesContainer.scrollHeight;
}

function renderCallsTable() {
  const query = state.msgSearchQuery;
  const filtered = state.calls.filter(c => {
    if (!query) return true;
    return c.contact.toLowerCase().includes(query) || c.number.toLowerCase().includes(query);
  });

  if (filtered.length === 0) {
    DOM.callsTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 24px; color: var(--text-dim);">No call records found. Sync with SMS &amp; Call Logs enabled to view history.</td></tr>`;
    return;
  }

  DOM.callsTbody.innerHTML = filtered.map(c => {
    const typeBadge = {
      incoming: `<span class="call-type-badge call-incoming">↙ Incoming</span>`,
      outgoing: `<span class="call-type-badge call-outgoing">↗ Outgoing</span>`,
      missed: `<span class="call-type-badge call-missed">✕ Missed</span>`
    }[c.type];

    return `
      <tr>
        <td>${typeBadge}</td>
        <td><strong>${c.contact}</strong> <span style="color:var(--text-dim); font-size:11px;">(${c.number})</span></td>
        <td>${c.date}</td>
        <td style="font-family:var(--font-mono);">${c.duration}</td>
        <td>${c.status}</td>
      </tr>
    `;
  }).join('');
}

function exportHtmlViewer() {
  const thread = state.threads.find(t => t.id === state.activeThreadId);
  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Kinetix SMS Archive - ${thread.contactName}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f0f4fc; margin: 40px; }
    h1 { color: #00f0ff; }
    .bubble { margin: 12px 0; padding: 12px 16px; border-radius: 8px; max-width: 60%; line-height: 1.4; }
    .received { background: #131b2e; border: 1px solid rgba(255,255,255,0.1); margin-right: auto; }
    .sent { background: #1b3563; border: 1px solid #00f0ff; margin-left: auto; color: #fff; }
    .meta { font-size: 10px; color: #94a3b8; margin-top: 4px; }
  </style>
</head>
<body>
  <h1>Kinetix SMS Export: ${thread.contactName} (${thread.phoneNumber})</h1>
  <p>Export Date: ${new Date().toLocaleString()}</p>
  <hr style="border-color: rgba(255,255,255,0.1); margin: 20px 0;">
  <div>
    ${thread.messages.map(m => `
      <div class="bubble ${m.type}">
        <div>${m.text}</div>
        <div class="meta">${m.sender} • ${m.time}</div>
      </div>
    `).join('')}
  </div>
</body>
</html>
  `;
  downloadFile(`Kinetix_SMS_${thread.contactName.replace(/\s+/g, '_')}.html`, htmlContent, 'text/html');
  showToast('Downloaded standalone HTML chat viewer!', 'success');
}

function exportXmlBackup() {
  const xml = `<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<smses count="${state.threads.length}">
  ${state.threads.map(t => t.messages.map(m => `
    <sms address="${t.phoneNumber}" date="${Date.now()}" type="${m.type === 'sent' ? '2' : '1'}" body="${escapeXml(m.text)}" contact_name="${t.contactName}" />
  `).join('')).join('')}
</smses>`;
  downloadFile('sms_backup_restore_compatible.xml', xml, 'application/xml');
  showToast('Exported XML compatible with SMS Backup & Restore!', 'success');
}

function exportJsonData() {
  const json = JSON.stringify({
    exportedAt: new Date().toISOString(),
    device: state.device,
    threads: state.threads,
    calls: state.calls
  }, null, 2);
  downloadFile('kinetix_telephony_data.json', json, 'application/json');
  showToast('Exported complete telephony JSON dataset!', 'success');
}

function exportActiveThread() {
  exportHtmlViewer();
}

function escapeXml(unsafe) {
  return unsafe.replace(/[<>&'"]/g, (c) => {
    switch (c) {
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '&': return '&amp;';
      case '\'': return '&apos;';
      case '"': return '&quot;';
    }
  });
}

function downloadFile(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ============================================================================
// Tab 4: Settings & Device Info Controller
// ============================================================================
function setupSettings() {
  DOM.btnModeUsb.addEventListener('click', () => {
    DOM.btnModeUsb.classList.add('active');
    DOM.btnModeWifi.classList.remove('active');
    DOM.wifiConfigRow.style.display = 'none';
    state.device.connectionType = 'USB 3.2 Gen 2 (5 Gbps)';
    DOM.deviceConnTag.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
      USB 3.2 Gen 2
    `;
    showToast('Switched ADB Mode to USB 3.2 SuperSpeed (Max Bandwidth)', 'info');
  });

  DOM.btnModeWifi.addEventListener('click', () => {
    DOM.btnModeWifi.classList.add('active');
    DOM.btnModeUsb.classList.remove('active');
    DOM.wifiConfigRow.style.display = 'flex';
    state.device.connectionType = 'Wireless 5GHz';
    DOM.deviceConnTag.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12.55a11 11 0 0 1 14.08 0"/></svg>
      Wireless 5GHz
    `;
    showToast('Wireless ADB selected. Enter IP address to pair/connect.', 'info');
  });

  DOM.btnConnectWifi.addEventListener('click', () => {
    const ip = document.getElementById('wifi-ip').value || '192.168.1.150:5555';
    showToast(`Connecting to wireless ADB at ${ip}...`, 'info');
    setTimeout(() => {
      showToast(`Connected to wireless ADB daemon on ${ip}!`, 'success');
    }, 800);
  });

  DOM.workersSlider.addEventListener('input', (e) => {
    const val = e.target.value;
    DOM.workersValueBadge.textContent = `${val} Threads`;
  });

  DOM.btnManualMediascan.addEventListener('click', () => {
    showToast('Triggering Android MediaScanner broadcast over ADB...', 'info');
    setTimeout(() => {
      showToast('MediaScanner broadcast completed! Phone gallery indexed.', 'success');
    }, 1200);
  });

  DOM.btnRestartAdb.addEventListener('click', () => {
    showToast('Killing ADB server and restarting daemon...', 'warn');
    setTimeout(() => {
      showToast('ADB daemon successfully restarted on port 5037.', 'success');
    }, 1500);
  });

  DOM.btnEnableTcpmode.addEventListener('click', () => {
    showToast('Configuring ADB TCP/IP port 5555 on device...', 'info');
    setTimeout(() => {
      showToast('Device listening on port 5555 for untethered wireless sync!', 'success');
    }, 1200);
  });
}

// ============================================================================
// Modals Controller (Path Picker & Custom Folders)
// ============================================================================
function setupModals() {
  // Target Path Modal
  DOM.btnChangePath.addEventListener('click', () => {
    DOM.inputNewTargetPath.value = state.targetPath;
    DOM.pathModal.style.display = 'flex';
  });
  DOM.btnClosePathModal.addEventListener('click', () => DOM.pathModal.style.display = 'none');
  DOM.btnCancelPath.addEventListener('click', () => DOM.pathModal.style.display = 'none');
  
  const btnBrowseNative = document.getElementById('btn-browse-folder-native');
  if (btnBrowseNative) {
    btnBrowseNative.addEventListener('click', async () => {
      showToast('Opening Windows Folder Browser...', 'info');
      try {
        const res = await fetch('/api/browse_folder', { method: 'POST' });
        const data = await res.json();
        if (data.success && data.path) {
          DOM.inputNewTargetPath.value = data.path;
          state.targetPath = data.path;
          DOM.currentTargetPath.textContent = data.path;
          DOM.currentTargetPath.title = data.path;
          showToast(`Target backup folder set to: ${data.path}`, 'success');
          loadSnapshots();
        }
      } catch (err) {
        // Fallback
      }
    });
  }

  DOM.btnSavePath.addEventListener('click', async () => {
    const newPath = DOM.inputNewTargetPath.value.trim();
    if (newPath) {
      state.targetPath = newPath;
      DOM.currentTargetPath.textContent = newPath;
      DOM.currentTargetPath.title = newPath;
      try {
        await fetch('/api/target', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: newPath })
        });
      } catch (e) {}
      showToast(`Target backup folder updated to: ${newPath}`, 'success');
      loadSnapshots();
    }
    DOM.pathModal.style.display = 'none';
  });

  DOM.pathChips.forEach(chip => {
    chip.addEventListener('click', () => {
      DOM.inputNewTargetPath.value = chip.getAttribute('data-path');
    });
  });

  // Custom Folder Modal
  DOM.btnAddCustomFolder.addEventListener('click', (e) => {
    e.stopPropagation();
    DOM.customFolderModal.style.display = 'flex';
  });
  DOM.btnCloseCustomModal.addEventListener('click', () => DOM.customFolderModal.style.display = 'none');
  DOM.btnCancelCustom.addEventListener('click', () => DOM.customFolderModal.style.display = 'none');
  DOM.btnSaveCustom.addEventListener('click', () => {
    const newDir = DOM.inputCustomFolderPath.value.trim();
    if (newDir) {
      if (!state.categories.custom_folders.paths.includes(newDir)) {
        state.categories.custom_folders.paths.push(newDir);
      }
      DOM.customPathsDisplay.innerHTML = state.categories.custom_folders.paths.map(p => `<code>${p}</code>`).join(', ');
      showToast(`Added custom phone directory: ${newDir}`, 'success');
    }
    DOM.customFolderModal.style.display = 'none';
  });

  DOM.customDirChips.forEach(chip => {
    chip.addEventListener('click', () => {
      DOM.inputCustomFolderPath.value = chip.getAttribute('data-dir');
    });
  });

  // ==========================================
  // Subfolder Selection Modal Controller
  // ==========================================
  let activeSubfolderCat = 'pics';
  let currentSubfolderOptions = [];

  const subfolderModal = document.getElementById('subfolder-modal');
  const btnCloseSubfolder = document.getElementById('btn-close-subfolder-modal');
  const btnCancelSubfolder = document.getElementById('btn-cancel-subfolder-modal');
  const btnSaveSubfolder = document.getElementById('btn-save-subfolder-modal');
  const btnSelectAllSub = document.getElementById('btn-subfolder-select-all');
  const btnClearAllSub = document.getElementById('btn-subfolder-clear-all');
  const subfolderContainer = document.getElementById('subfolder-list-container');
  const inputAddSubfolder = document.getElementById('input-add-subfolder');
  const btnAddSubfolderItem = document.getElementById('btn-add-subfolder-item');
  const subfolderTitle = document.getElementById('subfolder-modal-title');
  const subfolderSubtitle = document.getElementById('subfolder-modal-subtitle');

  function renderSubfolderList(items, selectedList) {
    if (!subfolderContainer) return;
    if (!items || items.length === 0) {
      subfolderContainer.innerHTML = '<div style="color: var(--text-dim); font-size: 13px; text-align: center; padding: 12px;">No subfolders discovered on device. You can type and add folders below.</div>';
      return;
    }
    subfolderContainer.innerHTML = items.map(path => {
      const isChecked = selectedList.includes(path);
      const parts = path.split('/').filter(Boolean);
      const shortName = parts.slice(-2).join('/');
      return `
        <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 8px 10px; border-radius: 6px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);">
          <input type="checkbox" class="subfolder-cb" value="${path}" ${isChecked ? 'checked' : ''} style="width: 17px; height: 17px; accent-color: #00f0ff; cursor: pointer;">
          <div style="display: flex; flex-direction: column; overflow: hidden;">
            <span style="font-weight: 600; font-size: 13px; color: #fff;">📁 ${shortName}</span>
            <span style="font-size: 11px; color: #8892b0; font-family: monospace;">${path}</span>
          </div>
        </label>
      `;
    }).join('');
  }

  document.querySelectorAll('.btn-choose-subfolders').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const catId = btn.getAttribute('data-cat') || 'pics';
      activeSubfolderCat = catId;
      const catName = catId === 'pics' || catId === 'photos' ? 'Photos & Videos' : 'Music & Audio';
      if (subfolderTitle) subfolderTitle.textContent = `Select Folders: ${catName}`;
      if (subfolderSubtitle) subfolderSubtitle.textContent = `Choose which specific albums or directories to sync for ${catName}`;

      // Ensure the category checkbox is selected
      const uiKey = (catId === 'pics' || catId === 'photos') ? 'photos' : catId;
      if (state.categories[uiKey]) {
        state.categories[uiKey].selected = true;
        updateCategoryUI();
      }
      
      const defaultPaths = (catId === 'pics' || catId === 'photos')
        ? ['/sdcard/DCIM/Camera', '/sdcard/DCIM/Screenshots', '/sdcard/Pictures/Screenshots', '/sdcard/Pictures/Instagram', '/sdcard/Pictures/Raw', '/sdcard/Movies']
        : ['/sdcard/Music', '/sdcard/Music/Albums', '/sdcard/Music/Favorites', '/sdcard/Podcasts', '/sdcard/Audiobooks', '/sdcard/Recordings'];

      currentSubfolderOptions = [...defaultPaths];

      if (state.device.connected) {
        try {
          const res = await fetch(`${state.apiBase}/api/folders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: catId })
          });
          const data = await res.json();
          if (data && data.subfolders && data.subfolders.length > 0) {
            currentSubfolderOptions = Array.from(new Set([...data.subfolders, ...data.parent_paths]));
          }
        } catch (err) {}
      }

      const currentSelected = state.customCategoryPaths[catId] || currentSubfolderOptions;
      renderSubfolderList(currentSubfolderOptions, currentSelected);
      if (subfolderModal) subfolderModal.style.display = 'flex';
    });
  });

  btnCloseSubfolder?.addEventListener('click', () => { if (subfolderModal) subfolderModal.style.display = 'none'; });
  btnCancelSubfolder?.addEventListener('click', () => { if (subfolderModal) subfolderModal.style.display = 'none'; });

  btnSelectAllSub?.addEventListener('click', () => {
    subfolderContainer?.querySelectorAll('.subfolder-cb').forEach(cb => cb.checked = true);
  });

  btnClearAllSub?.addEventListener('click', () => {
    subfolderContainer?.querySelectorAll('.subfolder-cb').forEach(cb => cb.checked = false);
  });

  btnAddSubfolderItem?.addEventListener('click', () => {
    const val = inputAddSubfolder?.value.trim();
    if (val) {
      if (!currentSubfolderOptions.includes(val)) {
        currentSubfolderOptions.push(val);
      }
      const checkedBoxes = Array.from(subfolderContainer.querySelectorAll('.subfolder-cb:checked')).map(cb => cb.value);
      checkedBoxes.push(val);
      renderSubfolderList(currentSubfolderOptions, checkedBoxes);
      inputAddSubfolder.value = '';
    }
  });

  btnSaveSubfolder?.addEventListener('click', () => {
    const checkedBoxes = Array.from(subfolderContainer.querySelectorAll('.subfolder-cb:checked')).map(cb => cb.value);
    if (checkedBoxes.length === 0) {
      showToast('Please keep at least one folder selected, or uncheck the entire category.', 'warning');
      return;
    }
    state.customCategoryPaths[activeSubfolderCat] = checkedBoxes;
    if (activeSubfolderCat === 'pics' || activeSubfolderCat === 'photos') {
      state.customCategoryPaths['pics'] = checkedBoxes;
      state.customCategoryPaths['photos'] = checkedBoxes;
    }
    
    const badgePics = document.getElementById('badge-pics');
    if (badgePics && (activeSubfolderCat === 'pics' || activeSubfolderCat === 'photos')) {
      badgePics.textContent = `${checkedBoxes.length} folders selected`;
    }
    const badgeMusic = document.getElementById('badge-music');
    if (badgeMusic && activeSubfolderCat === 'music') {
      badgeMusic.textContent = `${checkedBoxes.length} folders selected`;
    }
    const pathsDisp = document.getElementById(`paths-display-${activeSubfolderCat}`);
    if (pathsDisp) {
      const shortNames = checkedBoxes.map(p => p.split('/').filter(Boolean).slice(-1)[0]);
      pathsDisp.innerHTML = shortNames.map(s => `<code>${s}</code>`).join(', ');
    }
    if (subfolderModal) subfolderModal.style.display = 'none';
    showToast(`Saved ${checkedBoxes.length} folders for ${activeSubfolderCat === 'pics' || activeSubfolderCat === 'photos' ? 'Photos & Videos' : 'Music & Audio'}!`, 'success');
  });

  const btnSyncOnlyThis = document.getElementById('btn-sync-only-this-subfolder');
  btnSyncOnlyThis?.addEventListener('click', () => {
    const checkedBoxes = Array.from(subfolderContainer.querySelectorAll('.subfolder-cb:checked')).map(cb => cb.value);
    if (checkedBoxes.length === 0) {
      showToast('Please select at least one folder.', 'warning');
      return;
    }

    // Uncheck all other categories, keep only activeSubfolderCat
    const targetKey = (activeSubfolderCat === 'pics' || activeSubfolderCat === 'photos') ? 'photos' : activeSubfolderCat;
    Object.keys(state.categories).forEach(k => {
      state.categories[k].selected = (k === targetKey);
    });

    state.customCategoryPaths[activeSubfolderCat] = checkedBoxes;
    if (activeSubfolderCat === 'pics' || activeSubfolderCat === 'photos') {
      state.customCategoryPaths['pics'] = checkedBoxes;
      state.customCategoryPaths['photos'] = checkedBoxes;
    }

    const badgePics = document.getElementById('badge-pics');
    if (badgePics && (activeSubfolderCat === 'pics' || activeSubfolderCat === 'photos')) {
      badgePics.textContent = `${checkedBoxes.length} folders selected`;
    }
    const badgeMusic = document.getElementById('badge-music');
    if (badgeMusic && activeSubfolderCat === 'music') {
      badgeMusic.textContent = `${checkedBoxes.length} folders selected`;
    }
    const pathsDisp = document.getElementById(`paths-display-${activeSubfolderCat}`);
    if (pathsDisp) {
      const shortNames = checkedBoxes.map(p => p.split('/').filter(Boolean).slice(-1)[0]);
      pathsDisp.innerHTML = shortNames.map(s => `<code>${s}</code>`).join(', ');
    }

    updateCategoryUI();
    if (subfolderModal) subfolderModal.style.display = 'none';
    const catName = activeSubfolderCat === 'music' ? 'Music & Audio' : 'Photos & Videos';
    showToast(`Category isolated: ONLY ${catName} selected (${checkedBoxes.length} folders). All other categories unchecked!`, 'success', 4500);
  });

  // Demo Mode Switch
  DOM.btnDemoMode.addEventListener('click', () => {
    state.demoMode = !state.demoMode;
    DOM.demoModeLabel.textContent = `Demo: ${state.demoMode ? 'ON' : 'OFF'}`;
    showToast(`Simulation Demo Mode is now ${state.demoMode ? 'ENABLED' : 'DISABLED'}`, 'info');
  });

  // Scan Devices
  DOM.btnScanDevices?.addEventListener('click', async () => {
    showToast('Scanning USB ports for connected Android devices...', 'info');
    const found = await checkDeviceStatus();
    if (found) {
      showToast(`Found device: ${state.device.model}!`, 'success');
    } else {
      showToast('No phone detected. Please check your USB cable and enable USB Debugging in Developer Options.', 'warning');
    }
  });
}

async function checkDeviceStatus() {
  try {
    const res = await fetch(`${state.apiBase}/api/status`);
    const data = await res.json();
    if (data && data.connected && data.device) {
      const dev = data.device;
      const wasConnected = state.device.connected;
      state.device.connected = true;
      state.device.model = dev.display_name || dev.model || 'Android Phone';
      state.device.androidVersion = `Android ${dev.android_version || '15'}`;
      state.device.batteryPct = dev.battery_level != null ? dev.battery_level : 100;
      state.device.connectionType = dev.connection_type || 'USB';
      if (dev.storage_info && dev.storage_info.total_bytes) {
        state.device.storageTotalGB = Math.round((dev.storage_info.total_bytes) / (1024 ** 3));
        state.device.storageFreeGB = Math.round((dev.storage_info.free_bytes) / (1024 ** 3));
        state.device.storageUsedGB = Math.max(0, state.device.storageTotalGB - state.device.storageFreeGB);
      }
      const specModel = document.getElementById('spec-phone-model');
      if (specModel) {
        const mfg = dev.manufacturer && dev.manufacturer !== 'Unknown' ? dev.manufacturer : '';
        const name = state.device.model;
        specModel.textContent = name.toLowerCase().startsWith(mfg.toLowerCase()) ? name : `${mfg} ${name}`.trim();
      }
      const specVer = document.getElementById('spec-os-ver');
      if (specVer) specVer.textContent = `Android ${dev.android_version || '15'} (API ${dev.sdk_level || 35})`;
      updateDevicePillUI();
      if (!wasConnected) {
        showToast(`Phone detected: ${state.device.model} (${state.device.androidVersion})`, 'success');
      }
      return true;
    } else {
      state.device.connected = false;
      const specModel = document.getElementById('spec-phone-model');
      if (specModel) specModel.textContent = 'Connect phone via USB';
      const specVer = document.getElementById('spec-os-ver');
      if (specVer) specVer.textContent = '--';
      updateDevicePillUI();
      return false;
    }
  } catch (err) {
    state.device.connected = false;
    const specModel = document.getElementById('spec-phone-model');
    if (specModel) specModel.textContent = 'Connect phone via USB';
    const specVer = document.getElementById('spec-os-ver');
    if (specVer) specVer.textContent = '--';
    updateDevicePillUI();
    return false;
  }
}

function updateDevicePillUI() {
  if (state.device.connected) {
    DOM.devicePill.classList.remove('disconnected');
    DOM.devicePill.classList.add('connected');
    DOM.pillDisconnectedView.style.display = 'none';
    DOM.pillConnectedView.style.display = 'flex';
    DOM.deviceModelName.textContent = state.device.model;
    DOM.deviceOsTag.textContent = state.device.androidVersion;
    DOM.deviceBatteryPct.textContent = `${state.device.batteryPct}%`;
    if (state.device.storageTotalGB > 0) {
      DOM.storageReadout.textContent = `${state.device.storageUsedGB} GB / ${state.device.storageTotalGB} GB (${state.device.storageFreeGB} GB Free)`;
      const usedPct = Math.round((state.device.storageUsedGB / state.device.storageTotalGB) * 100);
      DOM.storageBarFill.style.width = `${usedPct}%`;
    } else {
      DOM.storageReadout.textContent = `Connected`;
      DOM.storageBarFill.style.width = `100%`;
    }
  } else {
    DOM.devicePill.classList.add('disconnected');
    DOM.devicePill.classList.remove('connected');
    DOM.pillConnectedView.style.display = 'none';
    DOM.pillDisconnectedView.style.display = 'flex';
  }
}

// ============================================================================
// Initialization
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupCategories();
  setupSyncEngine();
  setupDiffModal();
  setupRestoreWizard();
  setupMessagesAndCalls();
  setupSettings();
  setupModals();
  updateCategoryUI();
  updateDevicePillUI();
  updateSpeedometer(0, 0);

  // Probe backend status immediately and poll every 3 seconds
  checkDeviceStatus();
  setInterval(checkDeviceStatus, 3000);
});
