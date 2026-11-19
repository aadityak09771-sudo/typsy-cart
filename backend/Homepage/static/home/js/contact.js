
const contactForm = document.getElementById("contact-form");
const formStatus = document.getElementById("form-status");

contactForm.addEventListener("submit", function (event) {
    event.preventDefault();

    if (!contactForm.reportValidity()) return;

    const data = new FormData(contactForm);

    const subject = `Tipsy Cart enquiry: ${data.get("subject")}`;
    const body = [
        `Name: ${data.get("name")}`,
        `Email: ${data.get("email")}`,
        `Topic: ${data.get("subject")}`,
        "",
        "Message:",
        data.get("message")
    ].join("\n");

    const mailto = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

    formStatus.textContent =
        "Your email app will open if configured. The message has not been sent by this website.";

    window.location.href = mailto;
});
