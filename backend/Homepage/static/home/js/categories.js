
document.addEventListener("DOMContentLoaded", () => {
    console.log("Tipsy Cart Categories page loaded!");

    const currentPath = window.location.pathname;

    document.querySelectorAll("nav a").forEach((link) => {
        if (link.pathname === currentPath) {
            link.setAttribute("aria-current", "page");
        }
    });
});
