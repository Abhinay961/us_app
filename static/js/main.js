document.addEventListener('DOMContentLoaded', () => {
// Mobile menu toggle
const menuToggle = document.getElementById('mobile-menu-toggle');
const extendedMenu = document.getElementById('mobile-extended-menu');
const closeMenu = document.getElementById('close-menu');

```
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

// 🔥 SPA Navigation (NON-DESTRUCTIVE ADDITION)
initSPANavigation();

// 🔥 Prefetch links for instant feel
initPrefetch();
```

});

function showNotification(title, body) {
if ('Notification' in window && Notification.permission === 'granted') {
new Notification(title, { body, icon: '/static/icon-192.png' });
}
}

// =======================
// 🚀 SPA NAVIGATION SYSTEM
// =======================

const pageCache = {};
let isNavigating = false;

function initSPANavigation() {
document.addEventListener("click", function(e) {
const link = e.target.closest("a");

```
    if (!link) return;

    const url = link.getAttribute("href");

    // Only intercept internal links
    if (url && url.startsWith("/") && !url.startsWith("//") && !link.hasAttribute("target")) {
        e.preventDefault();
        navigateTo(url);
    }
});

window.addEventListener("popstate", () => {
    navigateTo(window.location.pathname, false);
});
```

}

function navigateTo(url, push = true) {
if (isNavigating) return;

```
const container = document.getElementById("app-content");
if (!container) {
    window.location.href = url;
    return;
}

isNavigating = true;

// ⚡ Instant load from cache
if (pageCache[url]) {
    container.innerHTML = pageCache[url];
    if (push) window.history.pushState({}, "", url);
    isNavigating = false;
    return;
}

container.style.opacity = "0.6";

fetch(url)
    .then(res => res.text())
    .then(html => {
        const doc = new DOMParser().parseFromString(html, "text/html");
        const newContent = doc.querySelector("#app-content");

        if (!newContent) {
            window.location.href = url;
            return;
        }

        pageCache[url] = newContent.innerHTML;
        container.innerHTML = newContent.innerHTML;

        container.style.opacity = "1";

        if (push) window.history.pushState({}, "", url);

        isNavigating = false;
    })
    .catch(() => {
        window.location.href = url;
    });
```

}

// =======================
// ⚡ PREFETCH SYSTEM
// =======================

function initPrefetch() {
document.addEventListener("mouseover", function(e) {
const link = e.target.closest("a");
if (!link) return;

```
    const url = link.href;

    if (url && !pageCache[url] && url.startsWith(window.location.origin)) {
        fetch(url)
            .then(res => res.text())
            .then(html => {
                const doc = new DOMParser().parseFromString(html, "text/html");
                const content = doc.querySelector("#app-content");
                if (content) {
                    pageCache[url] = content.innerHTML;
                }
            })
            .catch(() => {});
    }
});
```

}
