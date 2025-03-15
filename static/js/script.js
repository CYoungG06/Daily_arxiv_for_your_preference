// Wait for the document to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Enable tooltips everywhere
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Add smooth scrolling to all links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });
    
    // Add animation to cards when they come into view
    const animateOnScroll = function() {
        const cards = document.querySelectorAll('.card');
        
        cards.forEach(card => {
            const cardPosition = card.getBoundingClientRect();
            
            // Check if card is in viewport
            if(cardPosition.top < window.innerHeight && cardPosition.bottom > 0) {
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }
        });
    };
    
    // Set initial state for cards
    document.querySelectorAll('.card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    });
    
    // Run animation on page load and scroll
    animateOnScroll();
    window.addEventListener('scroll', animateOnScroll);
    
    // Form validation
    const searchForm = document.getElementById('searchForm');
    if (searchForm) {
        searchForm.addEventListener('submit', function(event) {
            let isValid = true;
            const topicGroups = document.querySelectorAll('.topic-group');
            
            topicGroups.forEach(group => {
                const topicName = group.querySelector('.topic-name');
                const topicFilters = group.querySelector('.topic-filters');
                
                if (!topicName.value.trim()) {
                    topicName.classList.add('is-invalid');
                    isValid = false;
                } else {
                    topicName.classList.remove('is-invalid');
                }
                
                if (!topicFilters.value.trim()) {
                    topicFilters.classList.add('is-invalid');
                    isValid = false;
                } else {
                    topicFilters.classList.remove('is-invalid');
                }
            });
            
            if (!isValid) {
                event.preventDefault();
                alert('Please fill in all required fields.');
            }
        });
    }
});