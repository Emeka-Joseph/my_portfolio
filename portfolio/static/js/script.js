    // Typing Animation
    const typingTexts = [
        'Crafting Elegant Solutions',
        'Python Expert',
        'React Developer',
        'API Architect',
        'Full-Stack Builder'
    ];
    let textIndex = 0;
    let charIndex = 0;
    let isDeleting = false;

    function typeText() {
        const element = document.getElementById('typing-text');
        const currentText = typingTexts[textIndex];
        
        if (isDeleting) {
            element.textContent = currentText.substring(0, charIndex - 1);
            charIndex--;
            
            if (charIndex === 0) {
                isDeleting = false;
                textIndex = (textIndex + 1) % typingTexts.length;
            }
        } else {
            element.textContent = currentText.substring(0, charIndex + 1);
            charIndex++;
            
            if (charIndex === currentText.length) {
                isDeleting = true;
                setTimeout(typeText, 2000);
                return;
            }
        }
        
        setTimeout(typeText, isDeleting ? 50 : 100);
    }

    typeText();


/*  */
    // Counter Animation
    const counters = document.querySelectorAll('.counter');
    let hasAnimated = false;

    function animateCounters() {
        if (hasAnimated) return;
        
        counters.forEach(counter => {
            const target = parseInt(counter.dataset.target);
            const increment = target / 50;
            let current = 0;

            const updateCount = () => {
                current += increment;
                if (current < target) {
                    counter.textContent = Math.floor(current);
                    requestAnimationFrame(updateCount);
                } else {
                    counter.textContent = target;
                }
            };

            updateCount();
        });

        hasAnimated = true;
    }

    // Trigger counter animation when about section is visible
    const aboutSection = document.getElementById('about');
    const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            animateCounters();
            observer.unobserve(aboutSection);
        }
    }, { threshold: 0.5 });

    observer.observe(aboutSection);
    
    
    
    

    // Project Filter
    const filterBtns = document.querySelectorAll('.filter-btn');
    const projectCards = document.querySelectorAll('.project-card');

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const filter = btn.dataset.filter;

            filterBtns.forEach(b => {
                b.classList.remove('bg-blue-500', 'text-white');
                b.classList.add('bg-slate-800', 'text-slate-300');
            });

            btn.classList.remove('bg-slate-800', 'text-slate-300');
            btn.classList.add('bg-blue-500', 'text-white');

            projectCards.forEach(card => {
                const tags = card.dataset.tags.split(' ');
                
                if (filter === 'all' || tags.includes(filter)) {
                    card.style.opacity = '1';
                    card.style.pointerEvents = 'auto';
                } else {
                    card.style.opacity = '0.3';
                    card.style.pointerEvents = 'none';
                }
            });
        });
    });

    // Form Submission
    const contactForm = document.getElementById('contact-form');

    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const name = document.getElementById('name').value;
        const email = document.getElementById('email').value;
        const subject = document.getElementById('subject').value;
        const message = document.getElementById('message').value;

        let isValid = true;

        if (!name.trim()) {
            document.querySelector('input[name="name"]').nextElementSibling.classList.remove('hidden');
            isValid = false;
        } else {
            document.querySelector('input[name="name"]').nextElementSibling.classList.add('hidden');
        }

        if (!validateEmail(email)) {
            document.querySelector('input[name="email"]').nextElementSibling.classList.remove('hidden');
            isValid = false;
        } else {
            document.querySelector('input[name="email"]').nextElementSibling.classList.add('hidden');
        }

        if (!subject.trim()) {
            document.querySelector('input[name="subject"]').nextElementSibling.classList.remove('hidden');
            isValid = false;
        } else {
            document.querySelector('input[name="subject"]').nextElementSibling.classList.add('hidden');
        }

        if (!message.trim()) {
            document.querySelector('textarea[name="message"]').nextElementSibling.classList.remove('hidden');
            isValid = false;
        } else {
            document.querySelector('textarea[name="message"]').nextElementSibling.classList.add('hidden');
        }

        if (!isValid) return;

        const submitText = document.getElementById('submit-text');
        const submitSpinner = document.getElementById('submit-spinner');
        submitText.classList.add('hidden');
        submitSpinner.classList.remove('hidden');

        try {
            const response = await fetch('/api/contact', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name, email, subject, message })
            });

            const data = await response.json();

            submitText.classList.remove('hidden');
            submitSpinner.classList.add('hidden');

            if (data.success) {
                const successMsg = document.getElementById('success-message');
                successMsg.classList.remove('hidden');
                contactForm.reset();

                setTimeout(() => {
                    successMsg.classList.add('hidden');
                }, 5000);
            }
        } catch (error) {
            console.error('Error:', error);
            submitText.classList.remove('hidden');
            submitSpinner.classList.add('hidden');
            alert('An error occurred. Please try again.');
        }
    });

   // Download Resume
    // Goes through /resume/download so the server records the hit before
    // streaming the PDF — the counter can't be missed by a failed fetch().
    function downloadResume() {
    const element = document.createElement('a');
    element.href = '/resume/download';
    element.setAttribute('download', 'Emeka_Joseph_Ijegalu_IT_CV.pdf');
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
}