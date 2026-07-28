document.addEventListener('DOMContentLoaded', () => {
    
    // ==========================================
    // 1. INVERT THEME LOGIC (Dark/Light)
    // ==========================================
    const themeToggleBtn = document.getElementById('theme-toggle');
    const mobileThemeToggleBtn = document.getElementById('mobile-theme-toggle');
    
    function applyTheme(isDark) {
        if (isDark) {
            document.documentElement.classList.add('dark');
            localStorage.setItem('color-theme', 'dark');
        } else {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('color-theme', 'light');
        }
    }

    // Initialize based on local storage or system preference
    if (localStorage.getItem('color-theme') === 'dark' || (!('color-theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        applyTheme(true);
    } else {
        applyTheme(false);
    }

    // Toggle events
    const toggleHandler = () => {
        const isCurrentlyDark = document.documentElement.classList.contains('dark');
        applyTheme(!isCurrentlyDark);
    };

    if(themeToggleBtn) themeToggleBtn.addEventListener('click', toggleHandler);
    if(mobileThemeToggleBtn) mobileThemeToggleBtn.addEventListener('click', toggleHandler);


    // ==========================================
    // 2. MOBILE MENU & HAMBURGER ANIMATION
    // ==========================================
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');
    const line1 = document.getElementById('line-1');
    const line2 = document.getElementById('line-2');
    const mobileLinks = document.querySelectorAll('.mobile-link');
    
    let isMenuOpen = false;

    function toggleMenu() {
        isMenuOpen = !isMenuOpen;
        
        if (isMenuOpen) {
            // Open Menu
            mobileMenu.classList.remove('opacity-0', 'pointer-events-none');
            // Animate Hamburger into an X
            line1.style.transform = 'translateY(3.5px) rotate(45deg)';
            line2.style.transform = 'translateY(-3.5px) rotate(-45deg)';
            // Prevent scrolling on body
            document.body.style.overflow = 'hidden';
        } else {
            // Close Menu
            mobileMenu.classList.add('opacity-0', 'pointer-events-none');
            // Revert Hamburger
            line1.style.transform = 'translateY(0) rotate(0)';
            line2.style.transform = 'translateY(0) rotate(0)';
            // Allow scrolling
            document.body.style.overflow = 'auto';
        }
    }

    if(mobileMenuBtn) mobileMenuBtn.addEventListener('click', toggleMenu);

    // Close menu when a link is clicked
    mobileLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (isMenuOpen) toggleMenu();
        });
    });


    // ==========================================
    // 3. NAVBAR SCROLL EFFECT
    // ==========================================
    const navbar = document.getElementById('navbar');
    
    window.addEventListener('scroll', () => {
        if (!navbar) return;
        if (window.scrollY > 50) {
            navbar.classList.add('py-0');
            navbar.classList.remove('py-2');
        } else {
            navbar.classList.add('py-2');
            navbar.classList.remove('py-0');
        }
    });

    // ==========================================
    // 4. PARALLAX HERO EFFECT
    // ==========================================
    const heroImg = document.getElementById('hero-img');
    
    window.addEventListener('scroll', () => {
        if (!heroImg) return;
        // Calculate scroll percentage
        const scrollPosition = window.scrollY;
        // Only animate if hero is visible
        if (scrollPosition < window.innerHeight) {
            // Move the image down slightly as user scrolls down
            heroImg.style.transform = `translateY(${scrollPosition * 0.4}px) scale(1.05)`;
        }
    });
    
    // Initial scale-in effect on load
    if(heroImg) {
        setTimeout(() => {
            heroImg.style.transform = 'scale(1) translateY(0)';
        }, 100);
    }

    // ==========================================
    // 5. FORM INTERCEPT (MOVED INSIDE DOMContentLoaded)
    // ==========================================
    const accessForm = document.getElementById('accessForm');

    if (accessForm) {
        accessForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Stop the default ?id= submission
            
            const specialId = document.getElementById('special_id').value.trim();
            if (specialId) {
                // Redirect to the clean URL path
                window.location.href = `/gallery/${specialId}`;
            }
        });
    }
// ==========================================
    // 5. PORTFOLIO FILTERING ENGINE
    // ==========================================
    const filterBtns = document.querySelectorAll('.filter-btn');
    const portfolioItems = document.querySelectorAll('.portfolio-item');

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // 1. Update UI styles for the clicked button
            filterBtns.forEach(b => {
                b.classList.remove('font-bold', 'text-mono-black', 'dark:text-mono-white', 'border-b', 'border-current');
                b.classList.add('font-medium', 'text-mono-500');
            });
            
            btn.classList.add('font-bold', 'text-mono-black', 'dark:text-mono-white', 'border-b', 'border-current');
            btn.classList.remove('font-medium', 'text-mono-500');

            const filterValue = btn.getAttribute('data-filter').trim().toLowerCase();

            // 2. Smooth Filtering Logic
            portfolioItems.forEach(item => {
                const rawCategory = item.getAttribute('data-category') || '';
                const category = rawCategory.trim().toLowerCase();
                
                // Check if the item belongs to the clicked category
                const isMatch = filterValue === 'all' || category === filterValue;

                if (isMatch) {
                    // Show item
                    item.style.display = 'block';
                    item.style.transition = 'all 0.5s ease-out';
                    
                    // Tiny delay ensures display:block registers before fading in
                    setTimeout(() => {
                        item.style.opacity = '1';
                        item.style.transform = 'scale(1)';
                    }, 50);
                } else {
                    // Hide item
                    item.style.transition = 'all 0.4s ease-in';
                    item.style.opacity = '0';
                    item.style.transform = 'scale(0.95)';
                    
                    // Wait for the fade-out animation to finish before removing from layout
                    setTimeout(() => {
                        // Only set display to none if it's still meant to be hidden
                        if (item.style.opacity === '0') {
                            item.style.display = 'none';
                        }
                    }, 400); 
                }
            });
        });
    });
    // ==========================================
    // 7. CINEMATIC LIGHTBOX LOGIC
    // ==========================================
    const lightboxModal = document.getElementById('lightbox-modal');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxTitle = document.getElementById('lightbox-title');
    const lightboxCategory = document.getElementById('lightbox-category');
    
    let visibleItems = [];
    let currentImageIndex = 0;

    window.openLightbox = function(element) {
        // Build an array of only the currently visible images based on the active filter
        visibleItems = Array.from(document.querySelectorAll('.portfolio-item')).filter(
            item => item.style.display !== 'none'
        );
        
        currentImageIndex = visibleItems.indexOf(element);
        updateLightboxContent(element);

        // Open Modal
        lightboxModal.classList.remove('opacity-0', 'pointer-events-none');
        document.body.style.overflow = 'hidden'; // Prevent scrolling
        
        // Image scale-in effect
        setTimeout(() => {
            lightboxImg.classList.remove('scale-95');
            lightboxImg.classList.add('scale-100');
        }, 50);
    };

    window.closeLightbox = function() {
        lightboxModal.classList.add('opacity-0', 'pointer-events-none');
        lightboxImg.classList.remove('scale-100');
        lightboxImg.classList.add('scale-95');
        document.body.style.overflow = 'auto'; // Restore scrolling
    };

    window.changeLightboxImage = function(direction) {
        if (visibleItems.length === 0) return;
        
        currentImageIndex += direction;
        
        if (currentImageIndex >= visibleItems.length) {
            currentImageIndex = 0;
        } else if (currentImageIndex < 0) {
            currentImageIndex = visibleItems.length - 1;
        }
        
        const nextElement = visibleItems[currentImageIndex];
        
        lightboxImg.style.opacity = 0;
        setTimeout(() => {
            updateLightboxContent(nextElement);
            lightboxImg.style.opacity = 1;
        }, 200);
    };

    function updateLightboxContent(element) {
        const img = element.querySelector('img');
        const titleText = element.querySelector('p').innerText;
        const categoryText = element.querySelector('span').innerText;
        
        lightboxImg.src = img.src;
        lightboxTitle.innerText = titleText;
        lightboxCategory.innerText = categoryText;
    }

    // Keyboard support for Lightbox
    document.addEventListener('keydown', (e) => {
        if (lightboxModal && !lightboxModal.classList.contains('opacity-0')) {
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowRight') changeLightboxImage(1);
            if (e.key === 'ArrowLeft') changeLightboxImage(-1);
        }
    });
});
// ==========================================
    // 8. FORMSPREE AJAX SUBMISSION LOGIC
    // ==========================================
    const contactForm = document.getElementById('contactForm');
    const formStatus = document.getElementById('form-status');
    const emailInput = document.getElementById('email');
    const replyToHidden = document.getElementById('replyto_hidden');

    if (contactForm) {
        
        // Sync the hidden reply-to field with the visual email field
        emailInput.addEventListener('input', () => {
            replyToHidden.value = emailInput.value;
        });

        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Visual feedback
            formStatus.innerText = 'Transmitting...';
            formStatus.classList.add('animate-pulse');

            // Formspree natively accepts FormData objects beautifully
            const formData = new FormData(contactForm);

            fetch(contactForm.action, {
                method: 'POST',
                headers: {
                    'Accept': 'application/json'
                },
                body: formData
            })
            .then(response => {
                if (response.ok) {
                    // Success State
                    formStatus.innerText = 'Transmission Successful.';
                    formStatus.classList.remove('animate-pulse');
                    formStatus.classList.add('font-bold', 'text-mono-black', 'dark:text-mono-white');
                    
                    contactForm.reset();
                    
                    setTimeout(() => {
                        formStatus.innerText = 'Awaiting Input';
                        formStatus.classList.remove('font-bold', 'text-mono-black', 'dark:text-mono-white');
                    }, 5000);
                } else {
                    // Error Handling
                    response.json().then(data => {
                        if (Object.hasOwn(data, 'errors')) {
                            formStatus.innerText = data["errors"].map(error => error["message"]).join(", ");
                        } else {
                            formStatus.innerText = 'Signal Corrupted. Retry.';
                        }
                        formStatus.classList.remove('animate-pulse');
                    });
                }
            })
            .catch(error => {
                formStatus.innerText = 'Connection Lost. Try Again.';
                formStatus.classList.remove('animate-pulse');
            });
        });
    }