document.addEventListener('DOMContentLoaded', () => {
    // Mobile menu toggle
    const menuToggle = document.getElementById('mobile-menu-toggle');
    const extendedMenu = document.getElementById('mobile-extended-menu');
    const closeMenu = document.getElementById('close-menu');

    if (menuToggle && extendedMenu) {
        menuToggle.addEventListener('click', (e) => {
            e.preventDefault();
            extendedMenu.classList.add('show');
        });

        closeMenu.addEventListener('click', () => {
            extendedMenu.classList.remove('show');
        });

        extendedMenu.addEventListener('click', (e) => {
            if (e.target === extendedMenu) {
                extendedMenu.classList.remove('show');
            }
        });
    }

    // Request Notification Permission
    if ('Notification' in window) {
        if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
            Notification.requestPermission();
        }
    }
});

function showNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body, icon: '/static/icon-192.png' });
    }
}
