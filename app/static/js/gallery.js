let currentEventId = null;
let currentFolderId = null;
let currentEventName = null;
let nextPageToken = null;
let isLoading = false;

// State Management
let selectedFileIdsByEvent = {};
let currentImages = []; 
let currentLightboxIndex = 0;
let autoSaveTimeout = null; 
let allFetchedImagesMap = new Map();

// AbortController to kill requests when tabs are switched quickly
let fetchAbortController = null;

const observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && nextPageToken && !isLoading) {
        fetchImages(currentFolderId, nextPageToken);
    }
}, { rootMargin: '200px' });

document.addEventListener('DOMContentLoaded', async () => {
    await initializeAllSelections();
    
    const firstTab = document.querySelector('.event-tab');
    if (firstTab) firstTab.click();
    
    document.addEventListener('keydown', (e) => {
        if (!document.getElementById('lightbox').classList.contains('hidden')) {
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowRight') nextImage();
            if (e.key === 'ArrowLeft') prevImage();
        }
    });
});

async function initializeAllSelections() {
    try {
        const res = await fetch(`/api/selections/all/${window.specialId}`);
        if (res.ok) {
            const data = await res.json();
            document.querySelectorAll('.event-tab').forEach(tab => {
                const evtId = tab.dataset.eventId;
                selectedFileIdsByEvent[evtId] = new Set(data.selections[evtId] || []);
            });
            updateAllCounters();
        }
    } catch (err) {
        console.error("Failed to init selections", err);
    }
}

async function loadEvent(eventId, folderId, tabElement, eventName) {
    if (currentEventId === eventId) return;

    if (fetchAbortController) {
        fetchAbortController.abort();
    }
    
    document.querySelectorAll('.event-tab').forEach(el => {
        el.classList.remove('border-black', 'dark:border-white', 'text-black', 'dark:text-white');
        el.classList.add('border-transparent', 'text-neutral-500');
    });
    tabElement.classList.add('border-black', 'dark:border-white', 'text-black', 'dark:text-white');
    tabElement.classList.remove('border-transparent', 'text-neutral-500');

    document.getElementById('gallery-grid').innerHTML = '';
    currentEventId = eventId;
    currentFolderId = folderId;
    currentEventName = eventName;
    nextPageToken = null;
    currentImages = [];
    isLoading = false;

    if(!selectedFileIdsByEvent[currentEventId]) {
        selectedFileIdsByEvent[currentEventId] = new Set();
    }

    fetchImages(folderId);
}

async function fetchImages(folderId, pageToken = '') {
    if (isLoading) return;
    isLoading = true;
    document.getElementById('loading-sentinel').classList.remove('hidden');

    fetchAbortController = new AbortController();
    const signal = fetchAbortController.signal;

    const url = `/api/images/${folderId}${pageToken ? `?pageToken=${pageToken}` : ''}`;
    
    try {
        const response = await fetch(url, { signal });
        const data = await response.json();
        data.images.forEach(img => allFetchedImagesMap.set(img.id, img));                
        nextPageToken = data.next_page_token;
        renderGrid(data.images);
        
        if (nextPageToken) {
            observer.observe(document.getElementById('loading-sentinel'));
        } else {
            observer.disconnect();
            document.getElementById('loading-sentinel').classList.add('hidden');
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Fetch aborted for previous tab');
        } else {
            console.error("Error fetching images:", error);
        }
    } finally {
        isLoading = false;
    }
}

function renderGrid(images) {
    const grid = document.getElementById('gallery-grid');
    const currentSelections = selectedFileIdsByEvent[currentEventId] || new Set();

    images.forEach((img) => {
        const globalIndex = currentImages.length;
        currentImages.push(img);
        const isSelected = currentSelections.has(img.id);
        
        const card = document.createElement('div');
        card.className = "relative group aspect-[4/5] bg-neutral-200 dark:bg-neutral-800 overflow-hidden file-card-" + img.id;
        card.innerHTML = `
            <img src="${img.thumbnail}" alt="${img.name}" loading="lazy" 
                 onerror="this.onerror=null; this.src='${img.full}';" 
                 class="w-full h-full object-cover cursor-pointer transition-transform duration-700 group-hover:scale-105" 
                 onclick="openLightbox(${globalIndex})">
            <div class="absolute top-3 right-3 z-10">
                <button data-file-id="${img.id}" onclick="toggleGridSelection('${img.id}', '${currentEventId}')" class="selection-btn w-8 h-8 flex items-center justify-center border-2 transition-all ${isSelected ? 'bg-black border-black text-white dark:bg-white dark:border-white dark:text-black' : 'border-white/70 bg-black/20 text-transparent hover:border-white'}">
                    <i class="fa-solid fa-check text-sm"></i>
                </button>
            </div>
        `;
        grid.appendChild(card);
    });
}

function toggleGridSelection(fileId, evtId) {
    const evIdToUse = evtId || currentEventId;
    const targetSet = selectedFileIdsByEvent[evIdToUse];

    if (targetSet.has(fileId)) {
        targetSet.delete(fileId);
    } else {
        targetSet.add(fileId);
    }
    
    const btnElement = document.querySelector(`.file-card-${fileId} .selection-btn`);
    if(btnElement) {
        if (targetSet.has(fileId)) {
            btnElement.className = "selection-btn w-8 h-8 flex items-center justify-center border-2 bg-black border-black text-white dark:bg-white dark:border-white dark:text-black transition-all";
        } else {
            btnElement.className = "selection-btn w-8 h-8 flex items-center justify-center border-2 border-white/70 bg-black/20 text-transparent hover:border-white transition-all";
        }
    }
    
    updateAllCounters();
    triggerAutoSave(evIdToUse);
}

function updateAllCounters() {
    let grandTotal = 0;
    
    for (const [evtId, selectionSet] of Object.entries(selectedFileIdsByEvent)) {
        const count = selectionSet.size;
        grandTotal += count;
        
        const tabBadge = document.querySelector(`.tab-count[data-count-for="${evtId}"]`);
        if (tabBadge) {
            if (count > 0) {
                tabBadge.innerText = count;
                tabBadge.classList.remove('hidden');
            } else {
                tabBadge.classList.add('hidden');
            }
        }
    }

    const navTotalEl = document.getElementById('nav-total-count');
    if (navTotalEl) {
        navTotalEl.innerText = grandTotal;
        if(grandTotal > 0) {
            navTotalEl.classList.add('bg-green-500', 'text-white');
            navTotalEl.classList.remove('bg-neutral-800', 'dark:bg-neutral-200');
        } else {
            navTotalEl.classList.remove('bg-green-500', 'text-white');
            navTotalEl.classList.add('bg-neutral-800', 'dark:bg-neutral-200');
        }
    }
    
    const reviewCountEl = document.getElementById('review-count-display');
    if(reviewCountEl) reviewCountEl.innerText = grandTotal;

    const lbFolderCountEl = document.getElementById('lightbox-folder-count');
    const lbGrandTotalEl = document.getElementById('lightbox-grand-total');
    if (lbFolderCountEl && currentEventId && selectedFileIdsByEvent[currentEventId]) {
        lbFolderCountEl.innerText = selectedFileIdsByEvent[currentEventId].size;
    }
    if (lbGrandTotalEl) {
        lbGrandTotalEl.innerText = grandTotal;
    }
}

function triggerAutoSave(evtId) {
    const statusEl = document.getElementById('save-status');
    if (statusEl) {
        statusEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        statusEl.classList.remove('opacity-0');
    }

    if (autoSaveTimeout) clearTimeout(autoSaveTimeout);

    autoSaveTimeout = setTimeout(async () => {
        try {
            const response = await fetch('/api/selections/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    special_id: window.specialId,
                    event_id: evtId,
                    selected_ids: Array.from(selectedFileIdsByEvent[evtId])
                })
            });
            
            if (response.ok && statusEl) {
                statusEl.innerHTML = '<i class="fa-solid fa-check"></i> Saved';
                setTimeout(() => { statusEl.classList.add('opacity-0'); }, 2000);
            }
        } catch (error) {
            if (statusEl) statusEl.innerText = "Error Saving";
        }
    }, 500); 
}

// --- Lightbox Functions ---
function openLightbox(index) {
    currentLightboxIndex = index;
    const imgData = currentImages[index];
    const imgEl = document.getElementById('lightbox-img');
    
    imgEl.src = imgData.thumbnail; 
    const fullImage = new Image();
    fullImage.src = imgData.full;
    fullImage.onload = () => { if(currentLightboxIndex === index) imgEl.src = imgData.full; };

    document.getElementById('lightbox-counter').innerText = `${index + 1} / ${currentImages.length}`;
    document.getElementById('lightbox-filename').innerText = imgData.name;
    document.getElementById('lightbox-folder-name').innerText = currentEventName;
    
    updateLightboxSelectBtn(imgData.id);
    updateAllCounters();

    document.getElementById('lightbox').classList.remove('hidden');
    document.getElementById('lightbox').classList.add('flex');
    document.body.style.overflow = 'hidden'; 
}

function toggleLightboxSelection() {
    const imgId = currentImages[currentLightboxIndex].id;
    toggleGridSelection(imgId, currentEventId); 
    updateLightboxSelectBtn(imgId); 
}

function updateLightboxSelectBtn(fileId) {
    const btn = document.getElementById('lightbox-select-btn');
    const text = document.getElementById('lightbox-select-text');
    const targetSet = selectedFileIdsByEvent[currentEventId];
    
    if (targetSet && targetSet.has(fileId)) {
        btn.classList.add('bg-black', 'text-white', 'dark:bg-white', 'dark:text-black', 'border-black', 'dark:border-white');
        btn.classList.remove('text-neutral-500', 'border-neutral-500');
        text.innerText = "Selected";
    } else {
        btn.classList.remove('bg-black', 'text-white', 'dark:bg-white', 'dark:text-black', 'border-black', 'dark:border-white');
        btn.classList.add('text-neutral-500', 'border-neutral-500');
        text.innerText = "Select";
    }
}

function closeLightbox() {
    document.getElementById('lightbox').classList.add('hidden');
    document.getElementById('lightbox').classList.remove('flex');
    document.body.style.overflow = '';
    document.getElementById('lightbox-img').classList.remove('zoom-active');
}

function nextImage() {
    if (currentLightboxIndex < currentImages.length - 1) {
        document.getElementById('lightbox-img').classList.remove('zoom-active');
        openLightbox(currentLightboxIndex + 1);
    }
}

function prevImage() {
    if (currentLightboxIndex > 0) {
        document.getElementById('lightbox-img').classList.remove('zoom-active');
        openLightbox(currentLightboxIndex - 1);
    }
}

function toggleZoom() { document.getElementById('lightbox-img').classList.toggle('zoom-active'); }
function toggleTheme() {
    document.documentElement.classList.toggle('dark');
    localStorage.theme = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

// --- FULL PAGE REVIEW LOGIC ---
async function openReviewPage() {
    let totalSelected = 0;
    for (const s of Object.values(selectedFileIdsByEvent)) totalSelected += s.size;
    
    if (totalSelected === 0) {
        alert("Please select at least one image before reviewing.");
        return;
    }

    document.getElementById('gallery-view').classList.add('hidden');
    document.getElementById('event-tabs-container').classList.add('hidden');
    document.getElementById('review-view').classList.remove('hidden');
    document.getElementById('nav-review-btn').classList.add('hidden');
    
    const reviewContent = document.getElementById('review-content');
    reviewContent.innerHTML = `
        <div class="w-full text-center py-20" id="review-loading">
            <i class="fa-solid fa-circle-notch fa-spin text-3xl text-neutral-400"></i>
            <p class="text-xs font-mono tracking-widest uppercase text-neutral-500 mt-4">Compiling your final selections...</p>
        </div>`;

    let missingImages = false;
    for (const selectionSet of Object.values(selectedFileIdsByEvent)) {
        for (const fileId of selectionSet) {
            if (!allFetchedImagesMap.has(fileId)) {
                missingImages = true;
                break;
            }
        }
    }

    let eventsData = [];

    try {
        if (!missingImages) {
            for (const [evtId, selectionSet] of Object.entries(selectedFileIdsByEvent)) {
                if (selectionSet.size === 0) continue;
                
                const tabBtn = document.querySelector(`.event-tab[data-event-id="${evtId}"]`);
                const evtName = tabBtn ? tabBtn.childNodes[0].nodeValue.trim() : "Event";
                
                const images = Array.from(selectionSet).map(id => allFetchedImagesMap.get(id));
                eventsData.push({ event_id: evtId, event_name: evtName, images: images });
            }
        } else {
            const response = await fetch(`/api/selections/details/${window.specialId}`);
            const data = await response.json();
            eventsData = data.events;
        }
        
        reviewContent.innerHTML = ''; 
        
        for (const event of eventsData) {
            if (!event.images || event.images.length === 0) continue;
            
            // Sort Alphabetically
            event.images.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));
            
            const section = document.createElement('div');
            section.className = "mb-12";
            
            let imagesHTML = event.images.map(img => `
                <div class="relative aspect-[4/5] bg-neutral-200 dark:bg-neutral-800 overflow-hidden group review-card-${img.id}">
                    <img src="${img.thumbnail}" loading="lazy" class="w-full h-full object-cover">
                    <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <button onclick="removeFromReview('${img.id}', '${event.event_id}')" class="bg-red-600 text-white text-[10px] font-mono tracking-widest uppercase px-6 py-3 hover:bg-red-500 transition">Remove</button>
                    </div>
                </div>
            `).join('');

            section.innerHTML = `
                <h3 class="text-xs font-mono uppercase tracking-widest text-neutral-500 mb-4 border-b border-neutral-200 dark:border-neutral-800 pb-2">${event.event_name} (${event.images.length})</h3>
                <div class="masonry-grid">${imagesHTML}</div>
            `;
            reviewContent.appendChild(section);
        }
    } catch (e) {
        console.error(e);
        reviewContent.innerHTML = `<p class="text-red-500 text-center font-mono uppercase text-xs tracking-widest">Failed to load selections. Please try again.</p>`;
    }
}

function closeReviewPage() {
    document.getElementById('review-view').classList.add('hidden');
    document.getElementById('gallery-view').classList.remove('hidden');
    document.getElementById('event-tabs-container').classList.remove('hidden');
    document.getElementById('nav-review-btn').classList.remove('hidden');
}

function removeFromReview(fileId, evtId) {
    toggleGridSelection(fileId, evtId);
    
    const card = document.querySelector(`.review-card-${fileId}`);
    if (card) card.remove();
    
    let total = 0;
    for (const s of Object.values(selectedFileIdsByEvent)) total += s.size;
    if (total === 0) {
        closeReviewPage();
    }
}

async function confirmAndSubmit() {
    if(!confirm("Are you ready to finalize and send these selections to the studio?")) return;
    
    const btn = document.getElementById('final-submit-btn');
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> SUBMITTING...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/selections/complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ special_id: window.specialId })
        });
        
        if (response.ok) {
            btn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> SUBMITTED SUCCESSFULLY';
            btn.classList.remove('bg-green-600', 'hover:bg-green-500');
            btn.classList.add('bg-black', 'dark:bg-white', 'text-white', 'dark:text-black');
            alert("Thank you! Your final selections have been received.");
            setTimeout(() => { window.location.href = "/"; }, 2000);
        } else {
            throw new Error("Submission failed");
        }
    } catch (error) {
        btn.innerText = "ERROR - TRY AGAIN";
        btn.disabled = false;
    }
}